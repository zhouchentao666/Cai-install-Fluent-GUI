# -*- coding: utf-8 -*-
"""
CW 提取核心模块 (供 Web-GUI 后端调用)
整合了本地生成 CW 文件和网络换取授权码的功能。
"""

import os
import sys
import json
import time
import struct
import base64
from datetime import datetime, timedelta, timezone
from ctypes import WinDLL, c_void_p, c_bool, c_int, c_uint32, c_uint64, POINTER, create_string_buffer, byref
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------- 加密库导入 ---------------
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    HAVE_PYCRYPTODOME = True
except ImportError:
    HAVE_PYCRYPTODOME = False


class MySteamAPI:
    """Steam API 封装，用于直接与本地 Steam 客户端通信获取票证"""
    def __init__(self, logger=None):
        self.steam = None
        self._logger = logger or (lambda s: print(s))
        self._load_dll()

    def _get_resource_path(self, relative_path=""):
        """获取资源路径，兼容 PyInstaller / Nuitka 打包"""
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def _get_project_root(self) -> str:
        """获取项目根目录（兼容直接运行和 PyInstaller 打包）"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后，exe 所在目录
            return os.path.dirname(sys.executable)
        # 开发模式，以本文件所在目录的父目录为根（backend 的父目录）
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _load_dll(self):
        dll_name = 'steam_api64.dll' if sys.maxsize > 2**32 else 'steam_api.dll'
        
        # 获取项目根目录
        project_root = self._get_project_root()
        
        # 依次在 backend目录、当前目录、assets目录中寻找
        # 支持开发模式和打包后的路径结构
        search_paths = [
            self._get_resource_path(os.path.join("backend", dll_name)),  # 打包后: _MEIPASS/backend/
            self._get_resource_path(dll_name),  # 打包后: _MEIPASS/
            os.path.join(os.path.dirname(os.path.abspath(__file__)), dll_name),  # 开发模式: backend/
            os.path.join(project_root, dll_name),  # 项目根目录
            os.path.join(project_root, "backend", dll_name),  # 项目根目录/backend/
            self._get_resource_path(os.path.join("assets", dll_name))  # assets目录
        ]
        
        dll_path = None
        for path in search_paths:
            if os.path.isfile(path):
                dll_path = path
                self._logger(f"找到 DLL: {dll_path}")
                break
                
        if not dll_path:
            raise FileNotFoundError(f'缺少核心组件 {dll_name}！请确保该文件存在于程序目录下。搜索路径: {search_paths}')
            
        try:
            self.steam = WinDLL(dll_path)
        except Exception as e:
            raise RuntimeError(f'加载 {dll_name} 失败: {e}')

    def initialize(self, app_id):
        os.environ['SteamAppId'] = str(app_id)
        os.environ['SteamGameId'] = str(app_id)
        for cand in ['SteamAPI_InitSafe', 'SteamAPI_Init']:
            try:
                func = getattr(self.steam, cand)
                func.restype = c_bool
                if func():
                    return
            except AttributeError:
                continue
        raise RuntimeError('Steam API 初始化失败！请确保：\n1. 已登录 Steam 客户端\n2. 你的账号拥有该游戏\n3. 游戏已下载安装 (至少存在清单)')

    def _get_user(self):
        names = ['SteamAPI_SteamUser_v023', 'SteamAPI_SteamUser_v022',
                 'SteamAPI_SteamUser_v021', 'SteamAPI_SteamUser_v020',
                 'SteamAPI_SteamUser', 'SteamUser']
        for n in names:
            try:
                f = getattr(self.steam, n)
                f.restype = c_void_p
                user = f()
                if user: return user
            except AttributeError:
                continue
        raise RuntimeError('无法获取 SteamUser 接口')

    def get_ticket(self):
        user = self._get_user()
        req_candidates = [
            'SteamAPI_ISteamUser_RequestEncryptedAppTicket',
            'SteamAPI_RequestEncryptedAppTicket',
            'RequestEncryptedAppTicket',
        ]
        get_candidates = [
            'SteamAPI_ISteamUser_GetEncryptedAppTicket',
            'SteamAPI_GetEncryptedAppTicket',
            'GetEncryptedAppTicket',
        ]
        
        req = None
        for rn in req_candidates:
            try:
                req = getattr(self.steam, rn)
                req.argtypes = [c_void_p, c_void_p, c_int]
                req.restype = c_bool
                if req(user, None, 0): break
            except AttributeError:
                continue
        if req is None:
            raise RuntimeError('找不到 RequestEncryptedAppTicket 函数')

        run = getattr(self.steam, 'SteamAPI_RunCallbacks', lambda: None)
        buf = create_string_buffer(8192)
        sz = c_uint32()
        
        # 轮询等待回调
        for _ in range(60):
            run()
            for gn in get_candidates:
                try:
                    get = getattr(self.steam, gn)
                    get.argtypes = [c_void_p, c_void_p, c_int, POINTER(c_uint32)]
                    get.restype = c_bool
                    if get(user, buf, 8192, byref(sz)) and sz.value:
                        return {
                            "steam_id": self._get_steam_id(user),
                            "ticket_data": buf.raw[:sz.value],
                            "ticket_size": sz.value
                        }
                except AttributeError:
                    continue
            time.sleep(0.2)
        raise TimeoutError('向 Steam 请求加密票证超时。')

    def get_app_ticket(self):
        user = self._get_user()
        candidates = [
            'SteamAPI_ISteamUser_GetAuthSessionTicket',
            'SteamAPI_GetAuthSessionTicket',
            'GetAuthSessionTicket',
        ]
        for gn in candidates:
            try:
                get = getattr(self.steam, gn)
                get.argtypes = [c_void_p, c_void_p, c_int, POINTER(c_uint32)]
                get.restype = c_uint32
                buf = create_string_buffer(8192)
                sz = c_uint32()
                handle = get(user, buf, 8192, byref(sz))
                if handle and sz.value:
                    return {
                        "ticket_handle": handle,
                        "ticket_data": buf.raw[:sz.value],
                        "ticket_size": sz.value
                    }
            except AttributeError:
                continue
        raise RuntimeError('无法获取 App Ticket 接口')

    def _get_steam_id(self, user):
        for fn in ['SteamAPI_ISteamUser_GetSteamID', 'GetSteamID']:
            try:
                f = getattr(self.steam, fn)
                f.argtypes = [c_void_p]
                f.restype = c_uint64
                return f(user)
            except AttributeError:
                continue
        return 0

    def shutdown(self):
        try:
            f = getattr(self.steam, 'SteamAPI_Shutdown')
            f()
        except Exception:
            pass

    # --- DLC 相关查询 ---
    def _get_apps(self):
        names = ["SteamAPI_SteamApps_v008", "SteamAPI_SteamApps"]
        for n in names:
            try:
                f = getattr(self.steam, n)
                f.restype = c_void_p
                apps = f()
                if apps: return apps
            except AttributeError:
                continue
        raise RuntimeError("无法获取 SteamApps 接口")

    def owns_dlc(self, dlc_appid: int) -> bool:
        try:
            apps = self._get_apps()
            f = getattr(self.steam, "SteamAPI_ISteamApps_BIsDlcInstalled")
            f.argtypes = [c_void_p, c_uint32]
            f.restype = c_bool
            return f(apps, dlc_appid)
        except: return False

    def get_dlc_count(self) -> int:
        try:
            apps = self._get_apps()
            f = getattr(self.steam, "SteamAPI_ISteamApps_GetDLCCount")
            f.argtypes = [c_void_p]
            f.restype = c_int
            return f(apps)
        except: return 0

    def get_dlc_data(self, index: int):
        try:
            apps = self._get_apps()
            f = getattr(self.steam, "SteamAPI_ISteamApps_BGetDLCDataByIndex")
            f.argtypes = [c_void_p, c_int, POINTER(c_uint32), POINTER(c_bool), c_void_p, c_int]
            f.restype = c_bool
            app_id = c_uint32()
            available = c_bool()
            name_buf = create_string_buffer(256)
            if f(apps, index, byref(app_id), byref(available), name_buf, 256):
                return {
                    "appid": app_id.value,
                    "available": bool(available.value),
                    "name": name_buf.value.decode("utf-8", errors="ignore")
                }
            return None
        except: return None

    def is_subscribed_app(self, appid: int) -> bool:
        try:
            apps = self._get_apps()
            f = getattr(self.steam, "SteamAPI_ISteamApps_BIsSubscribedApp")
            f.argtypes = [c_void_p, c_uint32]
            f.restype = c_bool
            return f(apps, appid)
        except: return False


class CWFileCrypto:
    """负责将票证打包成标准的 .cw 文件"""
    _FIXED_KEY_SOURCE = b"af0a3329787c9e6a6f3a1b69f841fd09a67cdfcade8b182d67a4442357815f60"

    @staticmethod
    def get_aes_key():
        import hashlib
        return hashlib.sha256(CWFileCrypto._FIXED_KEY_SOURCE).digest()

    @staticmethod
    def encrypt_cw_file(appid, steam_id, timeout_start, timeout_end,
                        encrypted_ticket_base64, ticket_raw: bytes,
                        dlc_text: str, output_path):
        encrypted_ticket = base64.b64decode(encrypted_ticket_base64)
        extensions = {"dlcs": dlc_text.strip()}

        cw_data = {
            "format_version": "3.0",
            "metadata": {
                "appid": appid,
                "steam_id": steam_id,
                "created_timestamp": timeout_start,
                "expires_timestamp": timeout_end
            },
            "auth_data": {
                "app_ticket": ticket_raw.hex(),
                "encrypted_ticket": encrypted_ticket.hex(),
                "ticket_sizes": {
                    "app_ticket": len(ticket_raw),
                    "encrypted_ticket": len(encrypted_ticket)
                }
            },
            "lua_script": {
                "enabled": False,
                "content": ""
            },
            "extensions": extensions
        }

        json_bytes = json.dumps(cw_data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

        header = b"CWSQ"
        header += struct.pack('<Qi', timeout_start, len(json_bytes))
        raw = header + json_bytes

        iv = os.urandom(16)
        aes_key = CWFileCrypto.get_aes_key()
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        padded = pad(raw, AES.block_size)
        encrypted = cipher.encrypt(padded)

        with open(output_path, "wb") as f:
            f.write(iv + encrypted)
        return True


class LocalExtractor:
    """提供给 main.py 调用的提取器包装类"""
    
    def __init__(self, app_id: int, logger_callback):
        self.app_id = int(app_id)
        self.logger = logger_callback

    def _get_dlcs(self, ticket_gen):
        owned_dlcs = []
        try:
            dlc_count = ticket_gen.get_dlc_count()
        except Exception:
            dlc_count = 0
            
        self.logger(f"检测到游戏共有 {dlc_count} 个 DLC")
        bundle_keywords = ["ticket", "pass", "bundle", "edition", "pack"]

        for i in range(dlc_count):
            info = ticket_gen.get_dlc_data(i)
            if not info: continue
            
            aid = info["appid"]
            name = info["name"] or ""
            name_l = name.lower()
            
            try: subscribed = ticket_gen.is_subscribed_app(aid)
            except Exception: subscribed = False
                
            try: installed = ticket_gen.owns_dlc(aid)
            except Exception: installed = False
                
            is_bundle = any(kw in name_l for kw in bundle_keywords)

            if subscribed or (is_bundle and installed):
                owned_dlcs.append(f"{aid}={name}")
                
        return owned_dlcs

    def extract_to_authcode(self):
        """模式: 提交票证获取网络授权码"""
        ticket_gen = MySteamAPI(self.logger)
        try:
            self.logger("正在初始化 Steam API 并请求票证...")
            ticket_gen.initialize(self.app_id)
            
            result = ticket_gen.get_ticket()
            steam_id = result['steam_id']
            ticket_hex = result['ticket_data'].hex().upper()
            
            self.logger("票证提取成功，正在提交到服务器 (drm.steam.run) ...")
            
            resp = requests.post(
                "https://drm.steam.run/api/submit_encrypted_ticket.php",
                data={"appid": self.app_id, "steamid": steam_id, "ticket_data": ticket_hex, "usage_limit": -1},
                timeout=15,
                verify=False
            )
            resp.raise_for_status()
            js = resp.json()
            
            if not js.get("success"):
                raise RuntimeError(js.get("message", "API 返回失败状态"))
                
            auth_code = js["data"]["auth_code"]
            now_bj = datetime.now(timezone(timedelta(hours=8)))
            expire_bj = now_bj + timedelta(minutes=30)
            
            self.logger(f"授权有效期至：{expire_bj.strftime('%Y-%m-%d %H:%M')} (北京时间)")
            return {"success": True, "auth_code": auth_code}
            
        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            ticket_gen.shutdown()

    def extract_to_cw_file(self, output_dir=None):
        """模式: 在本地离线生成 CW 文件"""
        if not HAVE_PYCRYPTODOME:
            return {"success": False, "message": "缺失 pycryptodome 库，请使用 pip install pycryptodome 安装"}
            
        ticket_gen = MySteamAPI(self.logger)
        try:
            self.logger("正在初始化 Steam API 并请求加密票证...")
            ticket_gen.initialize(self.app_id)
            
            enc_res = ticket_gen.get_ticket()
            app_ticket_res = ticket_gen.get_app_ticket()
            
            steam_id = enc_res['steam_id']
            encrypted_ticket_bytes = enc_res['ticket_data']
            app_ticket_data = app_ticket_res['ticket_data']
            
            # 修剪 App Ticket 头部
            header_sig = b'\x04\x00\x00\x00'
            idx = app_ticket_data.find(header_sig)
            ticket_raw = app_ticket_data[max(0, idx - 4):] if idx != -1 else app_ticket_data

            # 获取 DLC 列表
            self.logger("正在扫描已拥有的 DLC...")
            owned_dlcs = self._get_dlcs(ticket_gen)
            dlc_text = "[app::dlcs]\n" + ("\n".join(owned_dlcs) + "\n" if owned_dlcs else "")

            # 时间计算 (30分钟有效期)
            now_bj = datetime.now(timezone(timedelta(hours=8)))
            expire_bj = now_bj + timedelta(minutes=30)
            start_ts = int(now_bj.timestamp())
            expire_ts = int(expire_bj.timestamp())

            # 确定输出路径
            if not output_dir:
                output_dir = os.path.join(self._get_project_root(), str(self.app_id))
            os.makedirs(output_dir, exist_ok=True)
            out_path = os.path.join(output_dir, f"{self.app_id}.cw")

            self.logger("正在加密并生成 CW 文件...")
            b64_encrypted = base64.b64encode(encrypted_ticket_bytes).decode()
            
            CWFileCrypto.encrypt_cw_file(
                appid=self.app_id,
                steam_id=steam_id,
                timeout_start=start_ts,
                timeout_end=expire_ts,
                encrypted_ticket_base64=b64_encrypted,
                ticket_raw=ticket_raw,
                dlc_text=dlc_text,
                output_path=out_path,
            )
            
            return {"success": True, "file_path": out_path, "dlc_count": len(owned_dlcs)}
            
        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            ticket_gen.shutdown()