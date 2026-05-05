#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D加密后端模块
从 3.2.py 提取核心功能，供前端调用
"""

import base64
import datetime
import hashlib
import os
import shutil
import stat
import struct
import subprocess
import sys
import time
import winreg
import ctypes
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass

# 固定的AES密钥
_FIXED_KEY_SOURCE = b"af0a3329787c9e6a6f3a1b69f841fd09a67cdfcade8b182d67a4442357815f60"
AES_KEY = hashlib.sha256(_FIXED_KEY_SOURCE).digest()
AES_IV_LENGTH = 16


@dataclass
class DecryptResult:
    """CW解密结果"""
    appid: int
    steam_id: int
    timeout_start: float
    timeout_end: float
    ticket: bytes
    encrypted_ticket: bytes
    lua_content: str
    has_lua: bool
    raw_dlcs: str = ""


class DrmBackend:
    """D加密后端核心类"""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.steam_path = self._get_steam_path()
        self._SPECIAL_APP_LIST = {
            "2054970": [2593180, 2593190, 2593200, 2593210, 2593220,
                       2593230, 2593240, 2593250, 2593260]
        }
    
    def _log(self, msg: str):
        """记录日志"""
        if self.logger:
            self.logger.info(msg)
        else:
            print(f"[DRM] {msg}")
    
    @staticmethod
    def _get_steam_path() -> Optional[Path]:
        """获取Steam安装路径"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            return Path(path)
        except Exception:
            return None
    
    @staticmethod
    def _get_desktop() -> Path:
        """获取桌面路径"""
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
        return Path(buf.value)
    
    @staticmethod
    def _get_resource_path(relative_path: str) -> Path:
        """获取资源路径（兼容打包环境）"""
        if hasattr(sys, "_MEIPASS"):
            base_path = Path(sys._MEIPASS)
            # 打包后的路径映射：免steam补丁 -> GBE_Patch
            if relative_path == "免steam补丁":
                return base_path / "GBE_Patch"
            return base_path / relative_path
        else:
            base_path = Path(__file__).parent / "DRM"
        return base_path / relative_path
    
    @staticmethod
    def ts_to_str(ts: float) -> str:
        """时间戳转字符串"""
        return datetime.datetime.fromtimestamp(
            ts, tz=datetime.timezone.utc
        ).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    
    def decrypt_cw_file(self, path: str | Path) -> DecryptResult:
        """解密CW文件"""
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        
        data = Path(path).read_bytes()
        iv = data[:AES_IV_LENGTH]
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(data[AES_IV_LENGTH:]), AES.block_size)
        
        pos = 0
        if decrypted[pos:pos + 4] != b"CWPS":
            raise ValueError("无效文件头 (不是 CWPS 格式)")
        pos += 4
        
        try:
            timeout_start, timeout_end, appid, ticket_len, encrypted_len, steam_id, lua_len = \
                struct.unpack("<QQiiiQi", decrypted[pos:pos + 40])
            pos += 40
        except struct.error:
            timeout_start, timeout_end, appid, ticket_len, encrypted_len, steam_id = \
                struct.unpack("<QQiiiQ", decrypted[pos:pos + 36])
            pos += 36
            lua_len = 0
        
        ticket = decrypted[pos:pos + ticket_len]
        pos += ticket_len
        encrypted_ticket = decrypted[pos:pos + encrypted_len]
        
        # 提取DLC信息
        raw_dlcs = ""
        start = decrypted.find(b"[app::dlcs]")
        if start != -1:
            end = decrypted.find(b"\n[", start + 11)
            if end == -1:
                end = len(decrypted)
            raw_dlcs = decrypted[start:end].decode('utf-8', errors='ignore').strip()
        
        return DecryptResult(
            appid=appid,
            steam_id=steam_id,
            timeout_start=timeout_start,
            timeout_end=timeout_end,
            ticket=ticket,
            encrypted_ticket=encrypted_ticket,
            lua_content="",
            has_lua=False,
            raw_dlcs=raw_dlcs
        )
    
    def make_ini_from_cw_result(self, res: DecryptResult) -> str:
        """从CW结果生成INI配置"""
        lines = [
            "[user::general]",
            f"account_name=User{res.steam_id % 10000}",
            f"account_steamid={res.steam_id}",
            "[user::sockets]",
            "connect=0",
            "[app::dlcs]",
            "unlock_all=0",
        ]
        
        # 解析DLC
        if res.raw_dlcs:
            for line in res.raw_dlcs.split('\n')[1:]:  # 跳过[app::dlcs]行
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    lines.append(line)
        
        return '\n'.join(lines)
    
    def extract_dlc_entries(self, res: DecryptResult) -> List[str]:
        """提取DLC条目"""
        entries = []
        if res.raw_dlcs:
            for line in res.raw_dlcs.split('\n')[1:]:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    entries.append(line)
        return entries
    
    # ==================== GBE模式 ====================
    
    async def authorize_gbe_mode(self, cw_result: DecryptResult, game_exe_path: str,
                                  dlc_ids: list = None, used_lua_dlc: bool = False) -> Tuple[bool, str]:
        """GBE模式授权"""
        try:
            self._log("开始GBE模式授权...")
            
            appid_str = str(cw_result.appid)
            steamid_str = str(cw_result.steam_id)
            steamid3 = str(int(steamid_str) - 76561197960265728)
            
            # 1. 查找依赖补丁包
            src_res = self._get_resource_path("免steam补丁")
            if not src_res.is_dir():
                return False, f"未找到 '免steam补丁' 文件夹\n预计路径: {src_res}"
            
            # 2. 检查userdata
            official_dir = self.steam_path / "userdata" / steamid3 / appid_str
            if not official_dir.exists():
                return False, f"未找到原存档路径：{official_dir}\n\n请确认该游戏在此设备上至少成功运行过一次！"
            
            digit_files = [f for f in official_dir.rglob("*") if f.is_file() and f.stem.isdigit()]
            if not digit_files:
                return False, "在 userdata 最底层未找到纯数字授权文件！\n\n请确认该游戏产生过正常存档数据！"
            
            # 3. 在桌面构建临时补丁环境
            desktop = self._get_desktop()
            patch_name = f"【{appid_str}临时授权文件】"
            patch_dir = desktop / patch_name
            
            # 清理旧的
            if patch_dir.exists():
                shutil.rmtree(patch_dir, ignore_errors=True)
            patch_dir.mkdir(exist_ok=True)
            
            # 拷贝补丁基础文件
            for item in src_res.iterdir():
                if item.name.lower() in ["steam_stubbed.dll", "controller.zip"]:
                    continue
                if item.is_file():
                    shutil.copy2(item, patch_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, patch_dir / item.name, dirs_exist_ok=True)
            
            # 4. 生成配置
            settings_dir = patch_dir / "steam_settings"
            settings_dir.mkdir(exist_ok=True)
            
            # 解压BIAO.zip
            self._extract_biao_zip(settings_dir)
            
            # 写 steam_appid.txt
            (settings_dir / "steam_appid.txt").write_text(appid_str, encoding="utf-8")
            
            # 写 configs.user.ini
            ini_content = self.make_ini_from_cw_result(cw_result)
            (settings_dir / "configs.user.ini").write_text(ini_content, encoding="utf-8")
            
            # 写 ColdClientLoader.ini
            (patch_dir / "ColdClientLoader.ini").write_text(
                f"[SteamClient]\nExe = {game_exe_path}\nAppId = {appid_str}\n"
                f"SteamClientDll = steamclient.dll\nSteamClient64Dll = steamclient64.dll\n\n"
                f"[Injection]\nexample:\nDllsToInjectFolder=extra_dlls\n",
                encoding="utf-8"
            )
            
            # 写 configs.app.ini
            app_ini = settings_dir / "configs.app.ini"
            dlc_entries = self.extract_dlc_entries(cw_result)
            with app_ini.open('w', encoding='utf-8') as f:
                f.write("[app::dlcs]\nunlock_all=0\n")
                if dlc_entries:
                    for entry in dlc_entries:
                        f.write(f"{entry}\n")
            
            # 复制 steam_stubbed.dll
            steam_stubbed_src = src_res / "steam_stubbed.dll"
            if steam_stubbed_src.exists():
                load_dlls_dir = settings_dir / "load_dlls"
                load_dlls_dir.mkdir(exist_ok=True)
                shutil.copy2(steam_stubbed_src, load_dlls_dir / "steam_stubbed.dll")
            
            # 拷贝userdata
            user_data_dir = patch_dir / "userdata" / steamid3 / appid_str
            user_data_dir.mkdir(parents=True, exist_ok=True)
            for f in digit_files:
                shutil.copy2(f, user_data_dir / f.name)
            
            self._log(f"GBE授权文件已生成: {patch_dir}")
            return True, f"免Steam补丁已生成在桌面：\n{patch_dir}\n\n打开文件夹后双击 steamclient_loader_x64.exe 即可启动游戏。"
            
        except Exception as e:
            import traceback
            return False, f"GBE授权失败: {e}\n{traceback.format_exc()}"
    
    def _extract_biao_zip(self, steam_settings_dir: Path):
        """解压BIAO.zip到steam_settings目录"""
        import zipfile
        
        biao_zip = self._get_resource_path("BIAO.zip")
        if not biao_zip.exists():
            biao_zip = self._get_resource_path("免steam补丁") / "BIAO.zip"
        
        if biao_zip.exists():
            try:
                with zipfile.ZipFile(biao_zip, 'r') as zip_ref:
                    zip_ref.extractall(steam_settings_dir)
                self._log("已解压 BIAO.zip")
            except Exception as e:
                self._log(f"解压 BIAO.zip 失败: {e}")
    
    # ==================== GreenLuma模式 ====================
    
    async def authorize_gl_mode(self, cw_result: DecryptResult) -> Tuple[bool, str]:
        """GreenLuma模式授权"""
        try:
            self._log("开始GreenLuma模式授权...")
            
            if not self.steam_path:
                return False, "未能在注册表找到Steam安装路径"
            
            # 1. 强杀Steam进程
            self._kill_steam_processes()
            
            # 2. 部署授权文件
            if not self._deploy_cw_tickets(cw_result):
                self._restore_gl_files()
                return False, "部署授权文件失败"
            
            # 3. 注入GL
            if not self._inject_gl():
                self._restore_gl_files()
                return False, "注入GreenLuma失败"
            
            # 4. 启动DLLInjector
            dll_injector = self.steam_path / "DLLInjector.exe"
            try:
                subprocess.Popen([str(dll_injector)], cwd=self.steam_path)
                self._log("已启动 DLLInjector")
            except Exception as e:
                self._restore_gl_files()
                return False, f"启动DLLInjector失败: {e}"
            
            return True, "GreenLuma授权成功！Steam正在启动..."
            
        except Exception as e:
            import traceback
            self._restore_gl_files()
            return False, f"GreenLuma授权失败: {e}\n{traceback.format_exc()}"
    
    def _deploy_cw_tickets(self, res: DecryptResult) -> bool:
        """部署CW授权文件"""
        try:
            own_dir = self.steam_path / "AppOwnershipTickets"
            enc_dir = self.steam_path / "EncryptedAppTickets"
            own_dir.mkdir(exist_ok=True)
            enc_dir.mkdir(exist_ok=True)
            
            (own_dir / f"Ticket.{res.appid}").write_bytes(res.ticket)
            (enc_dir / f"EncryptedTicket.{res.appid}").write_bytes(res.encrypted_ticket)
            self._log(f"已生成 Ticket.{res.appid} & EncryptedTicket.{res.appid}")
            
            # 处理特殊AppID的DLC
            if str(res.appid) in self._SPECIAL_APP_LIST:
                for dlc_id in self._SPECIAL_APP_LIST[str(res.appid)]:
                    (own_dir / f"Ticket.{dlc_id}").write_bytes(res.ticket)
                    (enc_dir / f"EncryptedTicket.{dlc_id}").write_bytes(res.encrypted_ticket)
                    self._log(f"已生成特殊DLC Ticket: {dlc_id}")
            
            # 生成AppList
            app_list_dir = self.steam_path / "AppList"
            app_list_dir.mkdir(exist_ok=True)
            (app_list_dir / str(res.appid)).write_text("1", encoding="utf-8")
            
            return True
        except Exception as e:
            self._log(f"部署授权文件失败: {e}")
            return False
    
    def _inject_gl(self) -> bool:
        """注入GreenLuma文件"""
        try:
            src_gl = self._get_resource_path("GreenLuma")
            if not src_gl.is_dir():
                self._log(f"未找到GreenLuma目录: {src_gl}")
                return False
            
            # 备份原文件
            self._backup_file(self.steam_path / "hid.dll")
            self._backup_file(self.steam_path / "bin" / "x64launcher.exe")
            
            # 复制GL文件
            file_list = [
                "GreenLuma2026_Files", "DLLInjector.exe", "DLLInjector.ini",
                "GreenLuma_2026_x64.dll", "GreenLuma_2026_x86.dll", "GreenLumaSettings_2026.exe",
                "x64launcher.exe",
            ]
            
            for item in file_list:
                src = src_gl / item
                dst = self.steam_path / item
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src, dst)
                elif src.is_file():
                    shutil.copy2(src, dst)
                else:
                    self._log(f"警告: GL文件不存在 {src}")
            
            # 创建hid.dll
            hid_src = self.steam_path / "GreenLuma_2026_x64.dll"
            hid_dst = self.steam_path / "hid.dll"
            if hid_src.exists():
                shutil.copy2(hid_src, hid_dst)
            
            # 替换x64launcher.exe
            launcher_src = self.steam_path / "x64launcher.exe"
            launcher_dst = self.steam_path / "bin" / "x64launcher.exe"
            if launcher_src.exists() and launcher_dst.exists():
                self._backup_file(launcher_dst)
                shutil.copy2(launcher_src, launcher_dst)
            
            self._log("GreenLuma注入完成")
            return True
            
        except Exception as e:
            self._log(f"注入GreenLuma失败: {e}")
            return False
    
    def _backup_file(self, file_path: Path):
        """备份文件"""
        if file_path.exists():
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            if not backup_path.exists():
                shutil.copy2(file_path, backup_path)
                self._log(f"已备份: {file_path.name}")
    
    def _restore_gl_files(self):
        """恢复GL文件"""
        try:
            files_to_restore = [
                (self.steam_path / "hid.dll", self.steam_path / "hid.dll.bak"),
                (self.steam_path / "bin" / "x64launcher.exe", self.steam_path / "bin" / "x64launcher.exe.bak"),
            ]
            
            for original, backup in files_to_restore:
                if backup.exists():
                    if original.exists():
                        original.unlink()
                    shutil.move(backup, original)
                    self._log(f"已恢复: {original.name}")
            
            # 删除GL文件
            gl_items = ["GreenLuma2026_Files", "DLLInjector.exe", "DLLInjector.ini",
                       "GreenLuma_2026_x64.dll", "GreenLuma_2026_x86.dll",
                       "GreenLumaSettings_2026.exe", "x64launcher.exe", "hid.dll"]
            for item in gl_items:
                path = self.steam_path / item
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                elif path.is_file():
                    path.unlink(missing_ok=True)
            
            self._log("GreenLuma环境已清理")
        except Exception as e:
            self._log(f"恢复文件失败: {e}")
    
    def _kill_steam_processes(self):
        """结束Steam进程"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() in ['steam.exe', 'steamwebhelper.exe']:
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate()
                        p.wait(timeout=5)
                    except Exception:
                        pass
            self._log("已结束Steam进程")
        except Exception as e:
            self._log(f"结束Steam进程失败: {e}")
    
    async def restore_gl_environment(self) -> Tuple[bool, str]:
        """恢复GreenLuma环境"""
        try:
            self._kill_steam_processes()
            self._restore_gl_files()
            return True, "GreenLuma环境已彻底清理并还原！"
        except Exception as e:
            return False, f"恢复失败: {e}"
    
    # ==================== 授权码下载CW文件 ====================
    
    async def download_cw_by_auth_code(self, code: str, logger=None) -> Tuple[bool, str, Optional[Path]]:
        """
        通过授权码下载CW文件
        
        Args:
            code: 授权码
            logger: 可选的日志回调函数
            
        Returns:
            (成功标志, 消息, 临时文件路径)
        """
        import tempfile
        import httpx
        
        def _log(msg: str):
            if logger:
                logger(msg)
            self._log(msg)
        
        if not code:
            return False, "授权码为空", None
        
        _log(f"正在使用授权码 '{code}' 下载 CW ...")
        
        try:
            # 1. 获取API域名
            _log("正在获取远程 API 域名 ...")
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://api.ksmlc.cn/SteamUnlockFileManager/version.json")
                response.raise_for_status()
                domain = response.json()["cw_web"]
                _log(f"API 域名: {domain}")
                
                # 2. 下载授权文件
                _log("开始下载授权文件 ...")
                rsp = await client.get(f"https://{domain}/api/auth/{code}/download", timeout=15)
                rsp.raise_for_status()
                
                if not rsp.content:
                    return False, "授权码无效或已过期", None
                
                # 3. 解密并保存
                from Crypto.Cipher import AES
                from Crypto.Util.Padding import unpad
                
                data = rsp.content
                iv, cipher = data[:16], data[16:]
                plain = unpad(AES.new(AES_KEY, AES.MODE_CBC, iv).decrypt(cipher), 16)
                
                if plain[:4] != b"CWSQ":
                    return False, "不是合法 CW 文件", None
                
                tmp = Path(tempfile.gettempdir()) / f"{code}.cw"
                tmp.write_bytes(data)
                _log(f"下载成功，已保存至: {tmp}")
                return True, "下载成功", tmp
                
        except Exception as e:
            err_msg = f"授权码下载失败: {e}"
            _log(err_msg)
            return False, err_msg, None
    
    # ==================== e0错误修复 ====================
    
    def fix_e0_error(self, appid: str, steamid: str) -> Tuple[bool, str]:
        """
        修复e0错误（写入注册表）
        
        Args:
            appid: 游戏AppID
            steamid: SteamID64
            
        Returns:
            (成功标志, 消息)
        """
        if not appid or not steamid:
            return False, "AppID 或 SteamID 为空"
        
        try:
            steamid_int = int(steamid)
            if steamid_int <= 0:
                return False, "SteamID 格式非法"
        except ValueError:
            return False, "SteamID 格式非法"
        
        try:
            key_path = rf"Software\Valve\Steam\Apps\{appid}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "steamID", 0, winreg.REG_QWORD, steamid_int)
            
            msg = f"已写入注册表: HKCU\\{key_path} -> steamID = {steamid_int}"
            self._log(msg)
            return True, "尝试修复成功，不包100%！"
        except Exception as e:
            err_msg = f"修复失败: {e}"
            self._log(err_msg)
            return False, err_msg
