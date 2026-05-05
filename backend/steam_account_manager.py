"""
Steam 账号管理模块
负责 Steam 账号的读取、切换、删除等操作
"""
import os
import sys
import subprocess
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Callable

# 添加项目根目录到路径
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import vdf
except ImportError:
    vdf = None
    print("警告: 未安装 vdf 模块，Steam 账号功能将不可用")


class SteamAccountManager:
    """Steam 账号管理器"""

    def __init__(self, steam_path: Optional[Path] = None, log_callback: Optional[Callable] = None):
        self._steam_path = steam_path
        self._log_callback = log_callback
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("SteamAccountManager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def _log(self, level: str, message: str):
        if self._log_callback:
            self._log_callback(level, message)
        else:
            getattr(self._logger, level.lower(), self._logger.info)(message)

    def _stack_error(self, e: Exception) -> str:
        import traceback
        return f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    @property
    def steam_path(self) -> Optional[Path]:
        if self._steam_path is None:
            self._steam_path = self._detect_steam_path()
        return self._steam_path

    @steam_path.setter
    def steam_path(self, path: Optional[Path]):
        self._steam_path = path

    def _detect_steam_path(self) -> Optional[Path]:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            return Path(steam_path)
        except Exception:
            common_paths = [
                Path(r"C:\Program Files (x86)\Steam"),
                Path(r"C:\Program Files\Steam"),
            ]
            for path in common_paths:
                if path.exists() and (path / "steam.exe").exists():
                    return path
            return None

    def get_steam_accounts(self) -> List[Dict]:
        if not self.steam_path:
            self._log("error", "未找到 Steam 路径")
            return []
        if vdf is None:
            self._log("error", "未安装 vdf 模块")
            return []

        loginusers_path = self.steam_path / 'config' / 'loginusers.vdf'
        if not loginusers_path.exists():
            return []

        try:
            with open(loginusers_path, 'r', encoding='utf-8') as f:
                data = vdf.load(f)

            accounts = []
            users = data.get('users', {})
            for steamid, user_info in users.items():
                account = user_info.get('AccountName', '')
                if account:
                    accounts.append({
                        'steamid': steamid,
                        'account': account,
                        'persona_name': user_info.get('PersonaName', ''),
                        'most_recent': user_info.get('MostRecent', '0') == '1',
                        'remember_password': user_info.get('RememberPassword', '0') == '1'
                    })
            accounts.sort(key=lambda x: x['most_recent'], reverse=True)
            return accounts
        except Exception as e:
            self._log("error", f"读取失败: {e}")
            return []

    def switch_steam_account(self, account_name: str, offline: bool = False) -> bool:
        """
        切换到指定 Steam 账号，并尽量跳过账号选择界面。
        """
        if not self.steam_path:
            self._log("error", "未找到 Steam 路径")
            return False

        steam_exe = self.steam_path / "steam.exe"
        if not steam_exe.exists():
            self._log("error", "未找到 steam.exe")
            return False

        loginusers_path = self.steam_path / "config" / "loginusers.vdf"
        if not loginusers_path.exists():
            return False

        try:
            # 读取账号
            with open(loginusers_path, 'r', encoding='utf-8') as f:
                data = vdf.load(f)

            users = data.get("users", {})
            target = None
            target_info = None
            for sid, info in users.items():
                if info.get("AccountName") == account_name:
                    target = sid
                    target_info = info
                    break

            if not target:
                self._log("error", f"未找到账号 {account_name}")
                return False

            remember_password = str((target_info or {}).get("RememberPassword", "0")) == "1"

            # 先彻底关闭 Steam，避免仍在旧会话里时切换失败。
            subprocess.run("taskkill /f /im steam.exe", capture_output=True, shell=True)
            subprocess.run("taskkill /f /im steamwebhelper.exe", capture_output=True, shell=True)
            time.sleep(1.5)

            # 将目标账号标记为最近登录账号，并同步自动登录相关状态。
            for sid, info in users.items():
                if sid == target:
                    info["MostRecent"] = "1"
                    info["AllowAutoLogin"] = "1" if remember_password else info.get("AllowAutoLogin", "0")
                    info["WantsOfflineMode"] = "1" if offline else "0"
                    if remember_password:
                        info["RememberPassword"] = "1"
                else:
                    info["MostRecent"] = "0"
                    if "WantsOfflineMode" in info:
                        info["WantsOfflineMode"] = "0"
                    if remember_password and "AllowAutoLogin" in info:
                        info["AllowAutoLogin"] = "0"

            with open(loginusers_path, 'w', encoding='utf-8') as f:
                vdf.dump(data, f)

            # 同步注册表中的自动登录账号，让 Steam 登录器直接落到目标账号。
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", 0, winreg.KEY_WRITE)
                winreg.SetValueEx(key, "AutoLoginUser", 0, winreg.REG_SZ, account_name)
                winreg.SetValueEx(key, "RememberPassword", 0, winreg.REG_DWORD, 1 if remember_password else 0)
                winreg.SetValueEx(key, "WantsOfflineMode", 0, winreg.REG_DWORD, 1 if offline else 0)
                winreg.CloseKey(key)
            except Exception as reg_error:
                self._log("warning", f"写入自动登录注册表失败: {reg_error}")

            # 按账号名直接启动 Steam，强制落到目标账号。
            cmd = [str(steam_exe), "-login", account_name]

            if offline:
                cmd.append("-offline")

            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True
            )

            if remember_password:
                self._log("info", f"已切换账号并尝试自动登录：{account_name}")
            else:
                self._log("info", f"已切换到账号登录页：{account_name}，需手动输入密码")
            return True

        except Exception as e:
            self._log("error", f"切换失败：{self._stack_error(e)}")
            return False

    def delete_steam_account(self, account: str) -> bool:
        if not self.steam_path or vdf is None:
            return False

        path = self.steam_path / "config" / "loginusers.vdf"
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = vdf.load(f)
            users = data.get("users", {})
            del_id = None
            for sid, info in users.items():
                if info.get("AccountName") == account:
                    del_id = sid
                    break
            if del_id:
                del users[del_id]
                with open(path, 'w', encoding='utf-8') as f:
                    vdf.dump(data, f)
                return True
        except:
            pass
        return False

    def restart_steam(self) -> bool:
        try:
            subprocess.run("taskkill /f /im steam.exe", capture_output=True, shell=True)
            subprocess.run("taskkill /f /im steamwebhelper.exe", capture_output=True, shell=True)
            time.sleep(2)
            subprocess.Popen([str(self.steam_path / "steam.exe")],
                             creationflags=subprocess.DETACHED_PROCESS, close_fds=True)
            return True
        except:
            return False


# 快捷接口
def get_steam_accounts(steam_path=None):
    return SteamAccountManager(Path(steam_path) if steam_path else None).get_steam_accounts()

def switch_steam_account(account_name, offline=False, steam_path=None):
    return SteamAccountManager(Path(steam_path) if steam_path else None).switch_steam_account(account_name, offline)

def delete_steam_account(account, steam_path=None):
    return SteamAccountManager(Path(steam_path) if steam_path else None).delete_steam_account(account)


if __name__ == "__main__":
    m = SteamAccountManager()
    print("Steam 路径:", m.steam_path)
    for a in m.get_steam_accounts():
        print(a['account'])
