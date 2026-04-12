import sys
import os
import traceback
import time
import logging
import subprocess
import asyncio
import re
import aiofiles
import random
import string
import colorlog
import httpx
import winreg
import ujson as json
import vdf
import zipfile
import shutil
import struct
import zlib
import io  # For workshop manifest processing
from pathlib import Path
from typing import Tuple, Any, List, Dict, Literal
from urllib.parse import quote

CURRENT_VERSION = "2.7"  # 当前版本号
GITHUB_REPO = "zhouchentao666/Fluent-Install"
# --- LOGGING SETUP ---
LOG_FORMAT = '%(log_color)s%(message)s'
LOG_COLORS = {
    'INFO': 'cyan',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'purple',
}

CAIGAMES_HEADERS = {
    "X-Client-Auth": "CaiGames-pvzcxw",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

# --- MODIFIED: Added Custom_Repos setting ---
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "ManifestAPIKey": "",
    "Custom_Steam_Path": "",
    "debug_mode": False,
    "logging_files": True,
    "background_image_path": "",
    "background_blur": 0,
    "background_saturation": 100,
    "background_brightness": 80, 
    "show_console_on_startup": False,
    "force_unlocker_type": "auto",
    "language": "system",
    "theme_mode": "auto",
    "theme_color": "#0078d4",
    "window_effect": "mica",
    "default_page": "home",
    "Custom_Repos": {
        "github": [],
        "zip": []
    },
    "DLCTimeout": 60,           # DLC 入库/联网超时时间（秒）
    "ST_Fixed_Version": True,   # SteamTools固定版本模式（默认启用）
    "ST_Fixed_Manifest_Mode": "ask",  # 固定版本manifest修复模式: always/never/ask
    "patch_manifest_default": False,    # 默认是否修补manifest
    "QA1": "温馨提示: Github_Personal_Token(个人访问令牌)可在Github设置的最底下开发者选项中找到, 详情请看教程。",
    "QA2": "Force_Unlocker: 强制指定解锁工具, 填入 'steamtools' 或 'greenluma'。留空则自动检测。",
    "QA3": "Custom_Repos: 自定义清单库配置。github数组用于添加GitHub仓库，zip数组用于添加ZIP清单库。",
    "QA4": "GitHub仓库格式: {\"name\": \"显示名称\", \"repo\": \"用户名/仓库名\"}",
    "QA5": "ZIP清单库格式: {\"name\": \"显示名称\", \"url\": \"下载URL，用{app_id}作为占位符\"}"
}

# --- 模块级游戏名称缓存（跨实例共享，避免重复请求）---
_global_name_cache: Dict[str, str] = {}
_name_cache_path = Path(__file__).parent.parent / 'config' / 'name_cache.json'

def _load_global_name_cache():
    global _global_name_cache
    try:
        if _name_cache_path.exists():
            with open(_name_cache_path, 'r', encoding='utf-8') as f:
                _global_name_cache = json.loads(f.read())
    except Exception:
        _global_name_cache = {}

def _save_global_name_cache():
    try:
        with open(_name_cache_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(_global_name_cache, ensure_ascii=False))
    except Exception:
        pass

_load_global_name_cache()

class STConverter:
    def __init__(self):
        self.logger = logging.getLogger('STConverter')

    def convert_file(self, st_path: str) -> str:
        try:
            content, _ = self.parse_st_file(st_path)
            return content
        except Exception as e:
            self.logger.error(f'ST文件转换失败: {st_path} - {e}')
            raise

    def parse_st_file(self, st_file_path: str) -> Tuple[str, dict]:
        with open(st_file_path, 'rb') as stfile:
            content = stfile.read()
        if len(content) < 12: raise ValueError("文件头过短")
        header = content[:12]
        xorkey, size, xorkeyverify = struct.unpack('III', header)
        xorkey ^= 0xFFFEA4C8
        xorkey &= 0xFF
        encrypted_data = content[12:12+size]
        if len(encrypted_data) < size: raise ValueError("加密数据小于预期大小")
        data = bytearray(encrypted_data)
        for i in range(len(data)):
            data[i] ^= xorkey
        decompressed_data = zlib.decompress(data)
        lua_content = decompressed_data[512:].decode('utf-8')
        metadata = {'original_xorkey': xorkey, 'size': size, 'xorkeyverify': xorkeyverify}
        return lua_content, metadata

# 语言代码到 Steam API 语言参数的映射
LANG_TO_STEAM = {
    "zh_CN": "schinese",
    "zh_TW": "tchinese",
    "en_US": "english",
    "fr_FR": "french",
    "ru_RU": "russian",
    "de_DE": "german",
    "ja_JP": "japanese",
}

def get_steam_lang(lang_code: str) -> str:
    return LANG_TO_STEAM.get(lang_code, "english")

class CaiBackend:
    def __init__(self):
        self.project_root = Path.cwd()
        self.client: httpx.AsyncClient | None = None
        self.config = {}
        self.steam_path = None
        self.unlocker_type = None
        self.lock = asyncio.Lock()
        self.temp_path = self.project_root / 'temp'
        self.manifest_record_path = self.project_root / 'manifest_records.json'
        self.log = self._init_log()
        self.name_cache: Dict[str, str] = _global_name_cache  # 引用全局缓存

    async def __aenter__(self):
        self.client = httpx.AsyncClient(verify=False, trust_env=True)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def _init_log(self, level=logging.INFO) -> logging.Logger:
        logger = logging.getLogger(' Cai install')
        logger.setLevel(level)
        if not logger.handlers:
            stream_handler = colorlog.StreamHandler()
            stream_handler.setLevel(level)
            fmt = colorlog.ColoredFormatter(LOG_FORMAT, log_colors=LOG_COLORS)
            stream_handler.setFormatter(fmt)
            logger.addHandler(stream_handler)
        return logger

    def _configure_logger(self):
        if not self.config:
            self.log.warning("无法应用日志配置，因为配置尚未加载。")
            return
        is_debug = self.config.get("debug_mode", False)
        level = logging.DEBUG if is_debug else logging.INFO
        self.log.setLevel(level)
        for handler in self.log.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(level)
        self.log.debug(f"日志等级已设置为: {'DEBUG' if is_debug else 'INFO'}")
        self.log.handlers = [h for h in self.log.handlers if not isinstance(h, logging.FileHandler)]
        if self.config.get("logging_files", True):
            logs_dir = self.project_root / 'logs'
            logs_dir.mkdir(exist_ok=True)
            log_file_path = logs_dir / f'cai-install-gui-{time.strftime("%Y-%m-%d")}.log'
            file_handler = logging.FileHandler(log_file_path, 'a', encoding='utf-8')
            file_handler.setLevel(level)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(file_formatter)
            self.log.addHandler(file_handler)
            self.log.info(f"已启用文件日志，将保存到: {log_file_path}")
        else:
            self.log.info("文件日志已禁用。")

    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较版本号，返回 -1, 0, 1"""
        try:
            import re
            
            def parse_version(v):
                # 分离主版本号和后缀
                match = re.match(r'(\d+(?:\.\d+)*)(.*)', v)
                if not match:
                    return (0, 0, 0), ''
                
                version_nums = match.group(1)
                suffix = match.group(2)
                
                # 解析版本号
                parts = version_nums.split('.')
                # 填充到3位
                while len(parts) < 3:
                    parts.append('0')
                
                # 转换为整数元组
                version_tuple = tuple(int(p) for p in parts[:3])
                
                return version_tuple, suffix
            
            v1_tuple, v1_suffix = parse_version(v1)
            v2_tuple, v2_suffix = parse_version(v2)
            
            # 首先比较主版本号
            if v1_tuple < v2_tuple:
                return -1
            elif v1_tuple > v2_tuple:
                return 1
            
            # 版本号相同，比较后缀
            # 空后缀被认为是正式版本，高于带后缀的版本
            if not v1_suffix and v2_suffix:
                return 1
            elif v1_suffix and not v2_suffix:
                return -1
            elif v1_suffix < v2_suffix:
                return -1
            elif v1_suffix > v2_suffix:
                return 1
            
            return 0
            
        except Exception as e:
            self.log.warning(f"版本比较失败: {e}")
            return 0
    
    async def check_for_updates(self) -> Tuple[bool, Dict]:
        """
        检查是否有新版本可用，支持镜像加速
        返回: (是否有更新, 版本信息字典)
        """
        try:
            self.log.info("正在检查更新...")
            
            # 获取 GitHub token（如果有的话）
            github_token = self.config.get("Github_Personal_Token", "").strip()
            headers = {'Authorization': f'Bearer {github_token}'} if github_token else {}
            
            # 添加 User-Agent 以避免 API 限制
            headers['User-Agent'] = 'Cai-Install-Updater'
            
            # 镜像 URL 列表（国内用户优先使用镜像）
            api_urls = [
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",  # 原始 API
            ]
            
            # 如果检测到中国大陆，优先使用镜像
            if await self.checkcn():
                # 国内镜像（优先级更高）
                mirror_urls = [
                    f"https://gh-proxy.org/https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    f"https://cdn.gh-proxy.org/https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    f"https://edgeone.gh-proxy.org/https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    f"https://ghp.ci/https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                ]
                api_urls = mirror_urls + api_urls
            
            response = None
            last_error = None
            
            # 尝试所有可用的 URL
            for api_url in api_urls:
                try:
                    self.log.info(f"尝试从 {api_url.split('/')[2]} 检查更新...")
                    response = await self.client.get(api_url, headers=headers, timeout=8, follow_redirects=True)
                    
                    # 如果成功，跳出循环
                    if response.status_code == 200:
                        self.log.info(f"成功从 {api_url.split('/')[2]} 获取更新信息")
                        break
                    
                    # 如果失败，记录错误并继续尝试下一个
                    last_error = f"HTTP {response.status_code}"
                    
                except Exception as e:
                    last_error = str(e)
                    continue
            
            # 如果所有尝试都失败
            if not response or response.status_code != 200:
                self.log.warning(f"所有更新源均失败，最后错误: {last_error}")
                # 尝试网页重定向兜底
                return await self._fallback_to_web_update_check()
            
            if response.status_code == 404:
                # 没有发布版本
                self.log.info("未找到发布版本")
                return False, {}
            
            response.raise_for_status()
            release_data = response.json()
            
            # 提取版本信息
            latest_version = release_data.get('tag_name', '').strip()
            if latest_version.startswith('v'):
                latest_version = latest_version[1:]  # 去掉 'v' 前缀
            
            release_name = release_data.get('name', '')
            release_body = release_data.get('body', '')
            release_url = release_data.get('html_url', '')
            published_at = release_data.get('published_at', '')
            
            # 获取下载链接
            download_urls = []
            assets = release_data.get('assets', [])
            for asset in assets:
                download_urls.append({
                    'name': asset.get('name', ''),
                    'url': asset.get('browser_download_url', ''),
                    'size': asset.get('size', 0)
                })
            
            # 如果没有 assets，使用 zipball_url
            if not download_urls and release_data.get('zipball_url'):
                download_urls.append({
                    'name': 'Source code (zip)',
                    'url': release_data.get('zipball_url', ''),
                    'size': 0
                })
            
            # 比较版本
            if self._compare_versions(CURRENT_VERSION, latest_version) < 0:
                self.log.info(f"发现新版本: {latest_version} (当前版本: {CURRENT_VERSION})")
                return True, {
                    'current_version': CURRENT_VERSION,
                    'latest_version': latest_version,
                    'release_name': release_name,
                    'release_body': release_body,
                    'release_url': release_url,
                    'published_at': published_at,
                    'download_urls': download_urls
                }
            else:
                self.log.info(f"当前已是最新版本 ({CURRENT_VERSION})")
                return False, {}
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.log.warning("GitHub API 受限，启用网页重定向兜底...")
                try:
                    html_url = f"https://github.com/{GITHUB_REPO}/releases/latest"
                    resp = await self.client.get(html_url, follow_redirects=False, timeout=10)
                    if resp.status_code in (301, 302):
                        loc = resp.headers.get('Location', '')
                        if loc:
                            latest_version = loc.split('/')[-1].lstrip('v')
                            if self._compare_versions(CURRENT_VERSION, latest_version) < 0:
                                self.log.info(f"发现新版本（兜底）: {latest_version}")
                                return True, {
                                    'current_version': CURRENT_VERSION,
                                    'latest_version': latest_version,
                                    'release_name': '', 'release_body': '',
                                    'release_url': html_url,
                                    'published_at': '', 'download_urls': []
                                }
                except Exception:
                    pass
            else:
                self.log.warning(f"检查更新时 HTTP 错误: {e}")
            return False, {}
        except httpx.TimeoutException:
            self.log.warning("检查更新超时，跳过")
            return False, {}
        except Exception as e:
            self.log.warning(f"检查更新失败: {e}")
            return False, {}

    async def _fallback_to_web_update_check(self) -> Tuple[bool, Dict]:
        """
        网页重定向兜底方案：通过访问GitHub releases页面获取最新版本
        """
        try:
            self.log.warning("GitHub API 受限，启用网页重定向兜底...")
            
            # 网页 URL 列表（支持镜像）
            web_urls = [
                f"https://github.com/{GITHUB_REPO}/releases/latest",
            ]
            
            # 如果检测到中国大陆，优先使用镜像
            if await self.checkcn():
                mirror_urls = [
                    f"https://gh-proxy.org/https://github.com/{GITHUB_REPO}/releases/latest",
                    f"https://cdn.gh-proxy.org/https://github.com/{GITHUB_REPO}/releases/latest",
                    f"https://edgeone.gh-proxy.org/https://github.com/{GITHUB_REPO}/releases/latest",
                ]
                web_urls = mirror_urls + web_urls
            
            last_error = None
            
            # 尝试所有可用的网页URL
            for web_url in web_urls:
                try:
                    self.log.info(f"尝试从 {web_url.split('/')[2]} 网页检查更新...")
                    resp = await self.client.get(web_url, follow_redirects=False, timeout=8)
                    
                    if resp.status_code in (301, 302):
                        loc = resp.headers.get('Location', '')
                        if loc:
                            latest_version = loc.split('/')[-1].lstrip('v')
                            if self._compare_versions(CURRENT_VERSION, latest_version) < 0:
                                self.log.info(f"发现新版本（网页兜底）: {latest_version}")
                                return True, {
                                    'current_version': CURRENT_VERSION,
                                    'latest_version': latest_version,
                                    'release_name': '', 'release_body': '',
                                    'release_url': web_url,
                                    'published_at': '', 'download_urls': []
                                }
                            else:
                                self.log.info(f"当前已是最新版本 ({CURRENT_VERSION})")
                                return False, {}
                    
                    last_error = f"HTTP {resp.status_code}"
                    
                except Exception as e:
                    last_error = str(e)
                    continue
            
            self.log.warning(f"网页重定向兜底也失败，最后错误: {last_error}")
            return False, {}
            
        except Exception as e:
            self.log.warning(f"网页重定向兜底失败: {e}")
            return False, {}

    async def initialize(self) -> Literal["steamtools", "greenluma", "conflict", "none", None]:
        if not self.config: self.config = await self.load_config()
        if self.config is None: return None
        self._configure_logger()
        
        self.steam_path = self.get_steam_path()
        if not self.steam_path or not self.steam_path.exists():
            self.log.error('无法确定有效的Steam路径。请在设置中手动指定。')
            return None
        self.log.info(f"Steam路径: {self.steam_path}")

        force_unlocker = self.config.get("force_unlocker_type", "auto")

        if force_unlocker in ["steamtools", "greenluma"]:
            self.unlocker_type = force_unlocker
            self.log.warning(f"已根据配置强制使用解锁工具: {force_unlocker.capitalize()}")
        else:
            is_steamtools = (self.steam_path / 'config' / 'stplug-in').is_dir()
            is_greenluma = any((self.steam_path / dll).exists() for dll in ['GreenLuma_2026_x86.dll', 'GreenLuma_2026_x64.dll'])
            if is_steamtools and is_greenluma:
                self.log.error("环境冲突：同时检测到SteamTools和GreenLuma！请在设置中强制指定一个。")
                self.unlocker_type = "conflict"
            elif is_steamtools:
                self.log.info("自动检测到解锁工具: SteamTools")
                self.unlocker_type = "steamtools"
            elif is_greenluma:
                self.log.info("自动检测到解锁工具: GreenLuma")
                self.unlocker_type = "greenluma"
            else:
                self.log.warning("未能自动检测到解锁工具。将默认使用标准模式（可能需要手动配置）。")
                self.unlocker_type = "none"

        try:
            (self.steam_path / 'config' / 'stplug-in').mkdir(parents=True, exist_ok=True)
            (self.steam_path / 'AppList').mkdir(parents=True, exist_ok=True)
            (self.steam_path / 'depotcache').mkdir(parents=True, exist_ok=True)
            # Create config/depotcache for workshop manifests
            (self.steam_path / 'config' / 'depotcache').mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log.error(f"创建Steam子目录时失败: {e}")

        # 每次初始化时检查并恢复被 Steam 更新清除的入库文件
        self.restore_managed_files_from_backup()

        return self.unlocker_type

    def stack_error(self, exception: Exception) -> str:
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    async def gen_config_file(self):
        config_path = self.project_root / 'config' / 'config.json'
        try:
        # 确保目录存在
            config_path.parent.mkdir(exist_ok=True, parents=True)
        
            with open(config_path, mode="w", encoding="utf-8") as f:
                f.write(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
            self.log.info('未识别到config.json，可能为首次启动，已自动生成，若进行配置重启生效')
        except Exception as e:
            self.log.error(f'生成配置文件失败: {self.stack_error(e)}')
    
    async def load_config(self) -> Dict | None:
        config_path = self.project_root / 'config' / 'config.json'
        if not config_path.exists():
            await self.gen_config_file()
            return DEFAULT_CONFIG

        try:
            async with aiofiles.open(config_path, mode="r", encoding="utf-8") as f:
                # --- MODIFIED: Load config and merge with defaults to handle new keys ---
                user_config = json.loads(await f.read())
                config = DEFAULT_CONFIG.copy()
                config.update(user_config)
                
                # --- NEW: Ensure Custom_Repos structure exists ---
                if 'Custom_Repos' not in config:
                    config['Custom_Repos'] = {"github": [], "zip": []}
                elif not isinstance(config['Custom_Repos'], dict):
                    config['Custom_Repos'] = {"github": [], "zip": []}
                else:
                    if 'github' not in config['Custom_Repos']:
                        config['Custom_Repos']['github'] = []
                    if 'zip' not in config['Custom_Repos']:
                        config['Custom_Repos']['zip'] = []
                
                return config
        except Exception as e:
            self.log.error(f"加载配置文件失败: {self.stack_error(e)}。正在重置配置文件...")
            if config_path.exists(): os.remove(config_path)
            await self.gen_config_file()
            self.log.error("配置文件已损坏并被重置。请重启程序。")
            return None

    def get_steam_path(self) -> Path | None:
        try:
            custom_steam_path = self.config.get("Custom_Steam_Path", "").strip()
            if custom_steam_path:
                self.log.info(f"正使用配置文件中的自定义Steam路径: {custom_steam_path}")
                return Path(custom_steam_path)
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
            steam_path, _ = winreg.QueryValueEx(key, 'SteamPath')
            winreg.CloseKey(key)
            return Path(steam_path)
        except Exception:
            self.log.error(f'获取Steam路径失败。请检查Steam是否正确安装，或在config.json中设置Custom_Steam_Path。')
            return None
            
    # --- NEW: File Manager Methods ---

    async def _fetch_game_name_for_manager(self, appid: str, lang: str = "schinese") -> str:
        """为文件管理器异步获取游戏名称，并使用缓存。默认使用steamCMD API，失败则使用Steam官方API。"""
        if not appid or not appid.isdigit():
            return "无效AppID"
        
        cache_key = f"{appid}_{lang}"
        if cache_key in self.name_cache:
            return self.name_cache[cache_key]

        # 优先使用 steamCMD API
        try:
            r = await self.client.get(
                f"https://api.9178666.xyz/cmd/{appid}",
                headers={
                    "X-Client-Auth": "CaiGames-pvzcxw",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                },
                timeout=15
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and "data" in data:
                    game_name = data["data"].get("name", "")
                    if game_name:
                        self.name_cache[cache_key] = game_name
                        _save_global_name_cache()
                        return game_name
        except Exception as e:
            self.log.debug(f"steamCMD API 获取 AppID {appid} 名称失败，尝试官方API: {e}")

        # 备用：Steam官方API
        try:
            api_urls = [
                f"https://store.steampowered.com/api/appdetails?appids={appid}&l={lang}",
                f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english",
                f"https://store.steampowered.com/api/appdetails?appids={appid}"
            ]
            for api_url in api_urls:
                response = await self.client.get(api_url, headers={'User-Agent': 'Cai-Install-Manager/1.0'}, timeout=15)
                if response.status_code != 200:
                    continue
                data = response.json()
                app_data = data.get(str(appid), {})
                if app_data.get("success") and "data" in app_data:
                    game_name = app_data["data"].get("name", "")
                    if game_name:
                        self.name_cache[cache_key] = game_name
                        _save_global_name_cache()
                        return game_name
        except Exception as e:
            self.log.warning(f"从Steam官方API获取 AppID {appid} 的名称也失败了: {e}")

        return f"AppID {appid}"

    # --- 联机游戏启动配置管理 ---

    async def get_launcher_profiles(self) -> List[Dict]:
        """获取所有联机启动配置"""
        profile_path = self.project_root / 'launcher_profiles.json'
        if not profile_path.exists():
            return []
        try:
            async with aiofiles.open(profile_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            self.log.error(f"读取启动配置文件失败: {e}")
            return []

    async def save_launcher_profile(self, profile_data: Dict) -> Dict:
        """保存或更新单个启动配置"""
        profile_path = self.project_root / 'launcher_profiles.json'
        profiles = await self.get_launcher_profiles()

        is_update = False
        for i, p in enumerate(profiles):
            if p.get('id') == profile_data.get('id'):
                profiles[i] = profile_data
                is_update = True
                break

        if not is_update:
            profiles.append(profile_data)

        try:
            async with aiofiles.open(profile_path, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(profiles, indent=2, ensure_ascii=False))
            return {"success": True, "message": "配置已保存", "profiles": profiles}
        except Exception as e:
            self.log.error(f"保存启动配置文件失败: {e}")
            return {"success": False, "message": str(e)}

    async def delete_launcher_profile(self, profile_id: str) -> Dict:
        """删除启动配置"""
        profile_path = self.project_root / 'launcher_profiles.json'
        profiles = await self.get_launcher_profiles()
        new_profiles = [p for p in profiles if p.get('id') != profile_id]

        try:
            async with aiofiles.open(profile_path, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(new_profiles, indent=2, ensure_ascii=False))
            return {"success": True, "message": "配置已删除", "profiles": new_profiles}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --- END 联机游戏启动配置管理 ---

    async def get_managed_files(self, lang: str = "schinese") -> Dict:
        """扫描所有相关目录，返回文件信息。缓存中有名称则直接填充，否则留空（AppID占位）。"""
        if not self.steam_path or not self.steam_path.exists():
            return {"error": "Steam路径未配置或无效。"}

        file_data = {"st": [], "gl": [], "assistant": []}

        # 1. 扫描文件
        st_path = self.steam_path / 'config' / 'stplug-in'
        gl_path = self.steam_path / 'AppList'

        if st_path.exists():
            file_data['st'], _ = self._scan_st_files(st_path)
        if gl_path.exists():
            file_data['gl'], _ = self._scan_generic_files(gl_path, ".txt")

        # 2. 用缓存填充已知名称，未知的留空（前端显示 AppID 占位）
        for category in file_data:
            for item in file_data[category]:
                cache_key = f"{item['appid']}_{lang}"
                if cache_key in self.name_cache:
                    item['game_name'] = self.name_cache[cache_key]

        return file_data

    async def fetch_missing_game_names(self, file_data: Dict, lang: str = "schinese") -> Dict:
        """对 file_data 中名称缺失的条目批量请求 Steam API，返回 {appid: name} 映射。"""
        missing = set()
        for category in file_data:
            for item in file_data[category]:
                cache_key = f"{item['appid']}_{lang}"
                if cache_key not in self.name_cache and item['appid'].isdigit():
                    missing.add(item['appid'])

        if not missing:
            return {}

        tasks = [self._fetch_game_name_for_manager(appid, lang) for appid in missing]
        results = await asyncio.gather(*tasks)
        name_map = {}
        for appid, name in zip(missing, results):
            name_map[appid] = name
        _save_global_name_cache()
        return name_map

    async def fetch_game_info_batch(self, file_data: Dict, lang: str = "schinese") -> Dict:
        """批量获取游戏名称。
        
        Args:
            file_data: get_managed_files 返回的文件数据
            lang: 语言代码
        
        Returns:
            {'names': {appid: name}}
        """
        # 获取缺失的游戏名称
        name_map = await self.fetch_missing_game_names(file_data, lang)
        return {'names': name_map}

    def _scan_st_files(self, directory: Path) -> Tuple[List[Dict], set]:
        """扫描SteamTools目录，返回文件数据和AppID集合。"""
        data, appids = [], set()
        file_data_map = {}
        try:
            for filename in os.listdir(directory):
                if filename.endswith(".lua") and filename != "steamtools.lua":
                    file_path = directory / filename
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    match = re.search(r'addappid\s*\(\s*(\d+)', content)
                    appid = match.group(1) if match else "N/A"
                    
                    # 检查是否是固定版本模式
                    is_fixed = bool(re.search(r'^\s*setManifestid\(', content, re.MULTILINE))
                    mode = "fixed" if is_fixed else "auto"
                    
                    if appid.isdigit():
                        appids.add(appid)
                        file_data_map[appid] = {
                            "filename": filename, 
                            "appid": appid, 
                            "game_name": "", 
                            "status": "ok",
                            "mode": mode
                        }
            
            st_lua_path = directory / "steamtools.lua"
            if st_lua_path.exists():
                data.append({"filename": "steamtools.lua", "appid": "N/A", "game_name": "SteamTools核心文件", "status": "core_file", "mode": "auto"})
                content = st_lua_path.read_text(encoding='utf-8', errors='ignore')
                # --- CRITICAL FIX: Use a more general regex to find all appids ---
                unlocked_appids = set(re.findall(r'addappid\s*\(\s*(\d+)', content))
                for appid in unlocked_appids:
                    if appid not in file_data_map:
                        appids.add(appid)
                        file_data_map[appid] = {
                            "filename": f"缺少 {appid}.lua", 
                            "appid": appid, 
                            "game_name": "", 
                            "status": "unlocked_only",
                            "mode": "auto"
                        }
        except Exception as e:
            self.log.error(f"扫描SteamTools目录失败: {e}")
        
        data.extend(sorted(file_data_map.values(), key=lambda item: int(item.get('appid', 0)), reverse=True))
        return data, appids

    def _scan_generic_files(self, directory: Path, extension: str) -> Tuple[List[Dict], set]:
        """扫描通用目录（如GreenLuma），返回文件数据和AppID集合。"""
        data, appids = [], set()
        try:
            files = [f for f in os.listdir(directory) if f.endswith(extension)]
            for filename in files:
                file_path = directory / filename

                # 对于GreenLuma，读取TXT文件内容获取AppID
                if extension == ".txt":
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().strip()
                            # 尝试将文件内容解析为AppID
                            if content.isdigit():
                                appid = content
                            else:
                                # 如果内容不是纯数字，使用文件名作为备用
                                appid = Path(filename).stem
                    except Exception as e:
                        self.log.warning(f"读取GreenLuma文件 {filename} 失败: {e}")
                        appid = Path(filename).stem
                else:
                    # 对于其他文件类型，使用文件名
                    appid = Path(filename).stem

                if appid.isdigit():
                    appids.add(appid)
                    data.append({"filename": filename, "appid": appid, "game_name": "", "status": "ok"})
        except Exception as e:
            self.log.error(f"扫描目录 {directory} 失败: {e}")

        # 按AppID数字大小排序
        data.sort(key=lambda x: int(x.get('appid', 0)) if x.get('appid', '0').isdigit() else 0, reverse=True)
        return data, appids
    
    def _load_manifest_records(self) -> Dict[str, List[str]]:
        """加载 manifest 跟踪记录。格式: {appid: [filename, ...]}"""
        try:
            if not self.manifest_record_path.exists():
                return {}
            with open(self.manifest_record_path, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
            if isinstance(data, dict):
                return {str(k): [str(x) for x in v if isinstance(x, str)] for k, v in data.items() if isinstance(v, list)}
        except Exception as e:
            self.log.warning(f"读取 manifest_records.json 失败，将使用空记录: {e}")
        return {}

    def _save_manifest_records(self, records: Dict[str, List[str]]):
        """保存 manifest 跟踪记录。"""
        try:
            with open(self.manifest_record_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(records, ensure_ascii=False, indent=2))
        except Exception as e:
            self.log.warning(f"保存 manifest_records.json 失败: {e}")

    def _record_manifests_for_app(self, app_id: str, manifest_files: List[str]):
        """记录某 AppID 下载过的 manifest 文件名。"""
        app_id = str(app_id)
        if not app_id or not manifest_files:
            return
        records = self._load_manifest_records()
        existing = set(records.get(app_id, []))
        existing.update(manifest_files)
        records[app_id] = sorted(existing)
        self._save_manifest_records(records)

    def _delete_recorded_manifests_for_app(self, app_id: str) -> int:
        """按记录删除某 AppID 对应的 manifest 文件，并移除记录。"""
        app_id = str(app_id)
        if not app_id:
            return 0
        records = self._load_manifest_records()
        filenames = records.get(app_id, [])
        if not filenames:
            return 0
        removed = 0
        target_dirs = [self.steam_path / 'depotcache', self.steam_path / 'config' / 'depotcache']
        for filename in filenames:
            for target_dir in target_dirs:
                try:
                    path = target_dir / filename
                    if path.exists() and path.is_file():
                        os.remove(path)
                        removed += 1
                except Exception as e:
                    self.log.warning(f"删除记录的清单文件失败 {filename}: {e}")
        records.pop(app_id, None)
        self._save_manifest_records(records)
        return removed

    def _remove_backup_files_for_item(self, file_type: str, filename: str | None, appid: str | None) -> int:
        """删除 backup 目录中与条目对应的备份文件，避免刷新时自动恢复。"""
        removed = 0
        backup_root = self.project_root / 'backup'
        backup_dir = backup_root / ('stplug-in' if file_type == 'st' else 'AppList')
        if not backup_dir.exists():
            return 0
        candidates = set()
        if filename:
            candidates.add(filename)
        if appid and str(appid).isdigit():
            candidates.add(f"{appid}.lua" if file_type == 'st' else f"{appid}.txt")
        for candidate in candidates:
            try:
                path = backup_dir / candidate
                if path.exists() and path.is_file():
                    os.remove(path)
                    removed += 1
            except Exception as e:
                self.log.warning(f"删除备份文件失败 {candidate}: {e}")
        return removed

    def delete_managed_files(self, file_type: str, items: List[Dict]) -> Dict:
        """根据类型和项目列表删除文件, 并清理关联的manifest。"""
        if not self.steam_path or not self.steam_path.exists():
            return {"success": False, "message": "Steam路径无效。"}
        
        base_path = None
        if file_type == 'st':
            base_path = self.steam_path / 'config' / 'stplug-in'
        elif file_type == 'gl':
            base_path = self.steam_path / 'AppList'
        
        if not base_path:
            return {"success": False, "message": f"未知的类型: {file_type}。"}

        deleted_count, failed, manifests_deleted_count = 0, [], 0
        backup_deleted_count = 0
        processed_appids = set()
        
        for item in items:
            try:
                # 步骤1: 如果是ST类型，清理 steamtools.lua 中的解锁条目
                if file_type == 'st' and item.get('status') != 'core_file' and item.get('appid', 'N/A').isdigit():
                    self._modify_st_lua_for_delete(item['appid'])

                # 步骤2: 清理物理文件和关联的 manifest
                filename = item.get('filename')
                appid = item.get('appid')
                if filename and "缺少" not in filename:
                    file_path = base_path / filename
                    if file_path.exists() and file_path.is_file():
                        if file_type == 'st' and filename.endswith('.lua'):
                            try:
                                content = file_path.read_text(encoding='utf-8', errors='ignore')
                                gids = re.findall(r'setManifestid\s*\(\s*\d+\s*,\s*"(\d+)"\s*\)', content)
                                depotcache_paths = [
                                    self.steam_path / 'depotcache',
                                    self.steam_path / 'config' / 'depotcache'
                                ]
                                for gid in gids:
                                    for cache_path in depotcache_paths:
                                        if cache_path.exists():
                                            for mf in cache_path.glob(f'*_{gid}.manifest'):
                                                if mf.exists():
                                                    os.remove(mf)
                                                    manifests_deleted_count += 1
                            except Exception as e:
                                self.log.error(f"清理 {filename} 的清单时失败: {e}")
                        
                        os.remove(file_path)
                        deleted_count += 1

                # 步骤3: 清理 backup 目录，防止刷新时自动恢复
                backup_deleted_count += self._remove_backup_files_for_item(file_type, filename, appid)

                # 步骤4: 按记录清理该 AppID 下载的 manifest 文件
                if appid and str(appid).isdigit() and appid not in processed_appids:
                    manifests_deleted_count += self._delete_recorded_manifests_for_app(str(appid))
                    processed_appids.add(appid)
            except Exception as e:
                failed.append(f"{item.get('filename', item.get('appid'))}: {e}")

        message = f"成功处理 {len(items) - len(failed)}/{len(items)} 个条目。"
        if deleted_count > 0:
            message += f" 删除了 {deleted_count} 个文件。"
        if manifests_deleted_count > 0:
            message += f" 清理了 {manifests_deleted_count} 个关联清单文件。"
        if backup_deleted_count > 0:
            message += f" 清理了 {backup_deleted_count} 个备份文件。"
        if failed:
            message += f" 失败条目: {', '.join(failed)}"
        
        return {"success": not failed, "message": message}

    async def toggle_st_version(self, filename: str) -> Dict:
        """切换ST文件版本模式（自动更新/固定版本）"""
        if not self.steam_path:
            return {"success": False, "message": "Steam路径未设置"}
        
        file_path = self.steam_path / 'config' / 'stplug-in' / filename
        if not file_path.exists():
            return {"success": False, "message": "文件不存在"}

        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()

            # 检查当前是否是固定版本模式
            is_currently_fixed = bool(re.search(r'^\s*setManifestid\(', content, re.MULTILINE))
            
            if is_currently_fixed:
                # 切换到自动更新模式（注释掉setManifestid）
                new_content = re.sub(r'(^\s*)setManifestid\(', r'\1--setManifestid(', content, flags=re.MULTILINE)
                action_msg = "已切换为自动更新"
            else:
                # 切换到固定版本模式
                if re.search(r'^\s*--\s*setManifestid\(', content, re.MULTILINE):
                    # 恢复被注释的setManifestid
                    new_content = re.sub(r'(^\s*)--\s*setManifestid\(', r'\1setManifestid(', content, flags=re.MULTILINE)
                    action_msg = "已恢复为固定版本 (取消注释)"
                else:
                    # 查找depot ID并添加对应的manifest ID
                    depot_ids = re.findall(r'addappid\(\s*(\d+)\s*,', content)
                    if not depot_ids:
                        return {"success": False, "message": "未在文件中找到有效的 Depot ID"}

                    manifest_lines = []
                    found_count = 0
                    search_paths = [
                        self.steam_path / 'config' / 'depotcache',
                        self.steam_path / 'depotcache'
                    ]

                    for depot_id in depot_ids:
                        found_manifest_id = None
                        for search_dir in search_paths:
                            if not search_dir.exists():
                                continue
                            candidates = list(search_dir.glob(f"{depot_id}_*.manifest"))
                            if candidates:
                                # 提取manifest ID
                                match = re.match(rf"{depot_id}_(\d+)\.manifest", candidates[0].name)
                                if match:
                                    found_manifest_id = match.group(1)
                                    break
                        
                        if found_manifest_id:
                            manifest_lines.append(f'setManifestid({depot_id}, "{found_manifest_id}")')
                            found_count += 1

                    if found_count == 0:
                        return {"success": False, "message": "未在本地找到对应 Manifest 文件，无法固定版本"}

                    # 在文件末尾添加固定版本的manifest配置
                    new_content = content.rstrip() + "\n\n-- Fixed Manifests (Generated)\n" + "\n".join(manifest_lines) + "\n"
                    action_msg = f"已切换为固定版本 (匹配到 {found_count} 个文件)"

            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(new_content)
            
            self.log.info(f"ST文件 {filename} 版本切换成功: {action_msg}")
            return {"success": True, "message": action_msg}

        except Exception as e:
            self.log.error(f"切换ST文件版本失败: {e}")
            return {"success": False, "message": str(e)}

    def _modify_st_lua_for_delete(self, appid: str):
        """从steamtools.lua中移除一个解锁条目。"""
        st_lua_path = self.steam_path / 'config' / 'stplug-in' / "steamtools.lua"
        if not st_lua_path.exists(): return

        try:
            content = st_lua_path.read_text(encoding='utf-8', errors='ignore')
            # 匹配 addappid(XXX, 1) 或 addappid(XXX) 两种形式
            pattern = re.compile(r'^\s*addappid\s*\(\s*' + re.escape(appid) + r'[^)]*\)\s*$', re.MULTILINE)
            new_content, count = pattern.subn('', content)
            
            if count > 0:
                # 清理空行
                new_content_cleaned = "\n".join(line for line in new_content.splitlines() if line.strip())
                st_lua_path.write_text(new_content_cleaned + "\n" if new_content_cleaned else "", encoding='utf-8')
                self.log.info(f"已从 steamtools.lua 移除 AppID {appid} 的解锁条目。")
        except Exception as e:
            self.log.error(f"修改 steamtools.lua 以删除 AppID {appid} 时失败: {e}")
            # 不再抛出异常，避免中断整个删除过程
            
    # --- END OF File Manager Methods ---

    # --- NEW: Custom repository support functions ---
    def get_custom_github_repos(self) -> List[Dict]:
        """获取自定义GitHub仓库列表"""
        custom_repos = self.config.get("Custom_Repos", {}).get("github", [])
        validated_repos = []
        
        for repo in custom_repos:
            if isinstance(repo, dict) and 'name' in repo and 'repo' in repo:
                validated_repos.append(repo)
            else:
                self.log.warning(f"无效的自定义GitHub仓库配置: {repo}")
        
        return validated_repos

    def get_custom_zip_repos(self) -> List[Dict]:
        """获取自定义ZIP仓库列表"""
        custom_repos = self.config.get("Custom_Repos", {}).get("zip", [])
        validated_repos = []
        
        for repo in custom_repos:
            if isinstance(repo, dict) and 'name' in repo and 'url' in repo:
                # 验证URL中是否包含{app_id}占位符
                if '{app_id}' in repo['url']:
                    validated_repos.append(repo)
                else:
                    self.log.warning(f"自定义ZIP仓库URL缺少'{{app_id}}'占位符: {repo}")
            else:
                self.log.warning(f"无效的自定义ZIP仓库配置: {repo}")
        
        return validated_repos

    async def process_custom_zip_manifest(self, app_id: str, repo_config: Dict, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理自定义ZIP清单库"""
        repo_name = repo_config.get('name', '未知仓库')
        url_template = repo_config.get('url', '')
        
        # 替换占位符
        download_url = url_template.replace('{app_id}', app_id)
        
        return await self._process_zip_manifest_generic(app_id, download_url, f"自定义ZIP库 ({repo_name})", self.unlocker_type, False, add_all_dlc, patch_depot_key)

    def get_all_github_repos(self) -> List[str]:
        """获取所有GitHub仓库（内置+自定义）"""
        builtin_repos = ['Auiowu/ManifestAutoUpdate','Satisl/MAU']
        custom_repos = [repo['repo'] for repo in self.get_custom_github_repos()]
        return builtin_repos + custom_repos

    # NEW: HTTP helper function for safe requests with retry mechanism
# NEW: HTTP helper function for safe requests with retry mechanism
    async def http_get_safe(self, url: str, timeout: int = None, max_retries: int = 3, retry_delay: float = 1.0, headers: Dict = None) -> httpx.Response | None:
        """安全的HTTP GET请求，带错误处理和重试机制"""
        if timeout is None:
            timeout = self.config.get("download_timeout", 30)
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Use different timeout strategies for different attempts
                current_timeout = timeout if attempt == 0 else min(timeout * (attempt + 1), 60)
                
                # --- MODIFIED: Added headers support ---
                response = await self.client.get(url, timeout=current_timeout, headers=headers)
                if response.status_code == 200:
                    if attempt > 0:  # Log successful retry
                        self.log.info(f"HTTP请求在第 {attempt + 1} 次尝试后成功: {url}")
                    return response
                else:
                    self.log.warning(f"HTTP请求失败，状态码: {response.status_code} - {url} (尝试 {attempt + 1}/{max_retries})")
                    if response.status_code in [429, 503, 502, 504]:  # Retry on server errors
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                    return None
            except Exception as e:
                last_exception = e
                self.log.warning(f"HTTP请求异常: {e} - {url} (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    
        if last_exception:
            self.log.debug(f"HTTP请求最终失败: {url} - {last_exception}")
        return None

    # NEW: Updated DLC retrieval function with better error handling
    async def get_dlc_ids_safe(self, appid: str) -> List[str]:
        """安全的DLC ID获取函数"""
        self.log.info(f"正在获取 AppID {appid} 的DLC信息...")

        def parse_steamcmd_style_json(json_data: dict) -> List[str]:
            try:
                # 兼容 9178666 的 data 层
                info_root = json_data.get("data", {})
                info = info_root.get(str(appid), info_root) # 如果 data 下直接是 appid，或者 data 就是内容本身
                
                dlc_str = info.get("extended", {}).get("listofdlc", "") or info.get("common", {}).get("listofdlc", "")
                if dlc_str:
                    return sorted(filter(str.isdigit, map(str.strip, dlc_str.split(","))), key=int)
            except Exception:
                pass
            return []

        # 1. 尝试 CaiGames 源 (替代原 ddxnb)
        self.log.debug(f"尝试从 CaiGames源 获取 AppID {appid} 的DLC...")
        data = await self.http_get_safe(
            f"https://api.9178666.xyz/cmd/{appid}", 
            timeout=20, 
            max_retries=2,
            headers=CAIGAMES_HEADERS
        )
        if data:
            try:
                dlc_ids = parse_steamcmd_style_json(data.json())
                if dlc_ids:
                    self.log.info(f"从 CaiGames源 成功获取到 {len(dlc_ids)} 个DLC")
                    return dlc_ids
            except Exception as e:
                self.log.warning(f"解析 CaiGames源 响应失败: {e}")

        # 2. 尝试 SteamCMD API (原源)
        self.log.debug(f"尝试从 SteamCMD API 获取 AppID {appid} 的DLC...")
        data = await self.http_get_safe(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20, max_retries=2)
        if data:
            try:
                dlc_ids = parse_steamcmd_style_json(data.json())
                if dlc_ids:
                    self.log.info(f"从 SteamCMD API 成功获取到 {len(dlc_ids)} 个DLC")
                    return dlc_ids
                self.log.debug(f"SteamCMD API 中 AppID {appid} 没有DLC信息")
            except Exception as e:
                self.log.warning(f"解析 SteamCMD API 响应失败: {e}")
        else:
            self.log.warning(f"无法从 SteamCMD API 获取 AppID {appid} 的数据")
        
        # 3. 降级：使用官方 API (兜底)
        self.log.debug(f"尝试从 Steam 官方 API 获取 AppID {appid} 的DLC...")
        api_variants = [
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese",
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english",
            f"https://store.steampowered.com/api/appdetails?appids={appid}"
        ]
        
        for api_url in api_variants:
            data = await self.http_get_safe(api_url, timeout=25, max_retries=2, retry_delay=2.0)
            if data:
                try:
                    j = data.json()
                    app_data = j.get(str(appid), {})
                    if app_data.get("success") and "data" in app_data:
                        dlc_list = app_data["data"].get("dlc", [])
                        if dlc_list:
                            dlc_ids = [str(d) for d in dlc_list]
                            self.log.info(f"从 Steam 官方 API 成功获取到 {len(dlc_ids)} 个DLC")
                            return dlc_ids
                except Exception as e:
                    self.log.warning(f"解析 Steam 官方 API 响应失败 ({api_url}): {e}")
                    continue
        
        self.log.info(f"未找到 AppID {appid} 的DLC信息（已尝试所有数据源）")
        return []

    # NEW: Updated depot retrieval function with better error handling
    async def _get_cached_app_tokens(self) -> Dict[str, str]:
        cache_file = self.project_root / "app_tokens_cache.json"
        current_time = time.time()
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                    cache_content = json.loads(await f.read())
                if current_time - cache_content.get('timestamp', 0) < 86400:
                    return cache_content.get('data', {})
            except:
                pass
        try:
            response = await self.client.get("https://api.993499094.xyz/appaccesstokens.json", timeout=30)
            if response.status_code == 200:
                data = response.json()
                async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps({"timestamp": current_time, "data": data}, ensure_ascii=False))
                return data
        except Exception:
            pass
        return {}

    async def _get_app_info_via_token(self, appid: str, token: str) -> Dict | None:
        # 延迟导入 steam 模块，避免循环依赖
        try:
            from steam.client import SteamClient
        except ImportError:
            self.log.error("steam 模块未安装，无法获取 App 信息")
            return None

        def _fetch_task():
            try:
                client = SteamClient()
                if client.anonymous_login() != 1:
                    return None
                product_info = client.get_product_info(apps=[{'appid': int(appid), 'access_token': int(token)}])
                if product_info and 'apps' in product_info and int(appid) in product_info['apps']:
                    raw_data = product_info['apps'][int(appid)]
                    return {str(appid): raw_data}
                return None
            except Exception:
                return None
            finally:
                if 'client' in locals() and client:
                    client.disconnect()
        return await asyncio.to_thread(_fetch_task)

    def _parse_token_app_info(self, appid: str, app_info: Dict) -> Dict:
        """解析通过 Token 获取的 app_info，返回 {'depots': [...]} 格式"""
        result = []
        try:
            raw = app_info.get(str(appid), {})
            depots = raw.get("depots", {})
            for depot_id, depot_info in depots.items():
                if not isinstance(depot_info, dict):
                    continue
                manifests = depot_info.get("manifests", {})
                manifest_info = manifests.get("public")
                if not isinstance(manifest_info, dict):
                    continue
                manifest_id = manifest_info.get("gid")
                size = int(manifest_info.get("download", 0))
                dlc_appid = depot_info.get("dlcappid")
                source_label = f"DLC:{dlc_appid}" if dlc_appid else "主游戏"
                if manifest_id:
                    result.append((depot_id, manifest_id, size, source_label))
        except Exception:
            pass
        return {"depots": result}

    async def get_depots_safe(self, appid: str) -> List[Tuple[str, str, int, str]]:
        """安全的Depot获取函数，返回 (depot_id, manifest_id, size, source) 元组列表"""
        self.log.info(f"正在获取 AppID {appid} 的Depot信息...")

        # 0. 优先使用 Token 探测隐藏 Depot
        try:
            tokens = await self._get_cached_app_tokens()
            token = tokens.get(str(appid))
            if token:
                self.log.debug(f"找到 AppID {appid} 的 access token，尝试 Token 方式获取 Depot...")
                app_info = await self._get_app_info_via_token(appid, token)
                if app_info:
                    parsed = self._parse_token_app_info(appid, app_info)
                    if parsed["depots"]:
                        self.log.info(f"通过 Token 成功获取到 {len(parsed['depots'])} 个Depot（含隐藏）")
                        return parsed["depots"]
        except Exception:
            pass
        
        # 通用解析函数 (适用于 ddxnb 和 steamcmd)
        def parse_steamcmd_style_depots(json_data: dict) -> List[Tuple[str, str, int, str]]:
            out = []
            try:
                info = json_data.get("data", {}).get(str(appid), {})
                depots = info.get("depots", {})
                if depots:
                    for depot_id, depot_info in depots.items():
                        if not isinstance(depot_info, dict): continue
                        manifest_info = depot_info.get("manifests", {}).get("public")
                        if not isinstance(manifest_info, dict): continue
                        
                        manifest_id = manifest_info.get("gid")
                        size = int(manifest_info.get("download", 0))
                        dlc_appid = depot_info.get("dlcappid")
                        source_label = f"DLC:{dlc_appid}" if dlc_appid else "主游戏"
                        
                        if manifest_id:
                            out.append((depot_id, manifest_id, size, source_label))
            except Exception:
                pass
            return out

        self.log.debug(f"尝试从 CaiGames源 获取 AppID {appid} 的Depot...")
        data = await self.http_get_safe(
            f"https://api.9178666.xyz/cmd/{appid}", 
            timeout=20, 
            max_retries=2,
            headers=CAIGAMES_HEADERS
        )
        if data:
            try:
                out = parse_steamcmd_style_depots(data.json())
                if out:
                    self.log.info(f"从 CaiGames源 成功获取到 {len(out)} 个Depot")
                    return out
            except Exception as e:
                self.log.warning(f"解析 CaiGames源 Depot 信息失败: {e}")

        # 2. 尝试 SteamCMD API (原源)
        self.log.debug(f"尝试从 SteamCMD API 获取 AppID {appid} 的Depot...")
        data = await self.http_get_safe(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20, max_retries=2)
        if data:
            try:
                out = parse_steamcmd_style_depots(data.json())
                if out:
                    self.log.info(f"从 SteamCMD API 成功获取到 {len(out)} 个Depot")
                    return out
            except Exception as e:
                self.log.warning(f"解析 SteamCMD API Depot 信息失败: {e}")
        else:
            self.log.warning(f"无法从 SteamCMD API 获取 AppID {appid} 的Depot数据")
        
        # 3. 降级：使用官方 API (兜底)
        self.log.debug(f"尝试从 Steam 官方 API 获取 AppID {appid} 的Depot...")
        api_variants = [
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese",
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english",
            f"https://store.steampowered.com/api/appdetails?appids={appid}"
        ]
        
        for api_url in api_variants:
            data = await self.http_get_safe(api_url, timeout=25, max_retries=2, retry_delay=2.0)
            if data:
                try:
                    j = data.json()
                    app_data = j.get(str(appid), {})
                    if app_data.get("success") and "data" in app_data:
                        depots = app_data["data"].get("depots", {})
                        out = []
                        for depot_id, depot_info in depots.items():
                            if not isinstance(depot_info, dict): continue
                            manifest_info = depot_info.get("manifests", {}).get("public")
                            if not isinstance(manifest_info, dict): continue
                            
                            manifest_id = manifest_info.get("gid")
                            size = int(manifest_info.get("download", 0))
                            dlc_appid = depot_info.get("dlcappid")
                            source_label = f"DLC:{dlc_appid}" if dlc_appid else "主游戏"
                            
                            if manifest_id:
                                out.append((depot_id, manifest_id, size, source_label))
                        if out:
                            self.log.info(f"从 Steam 官方 API 成功获取到 {len(out)} 个Depot")
                            return out
                except Exception as e:
                    self.log.warning(f"解析 Steam 官方 API Depot 信息失败 ({api_url}): {e}")
                    continue
        
        self.log.info(f"未找到 AppID {appid} 的Depot信息（已尝试所有数据源）")
        return []

    # Workshop-related methods
    def extract_workshop_id(self, input_text: str) -> str | None:
        """Extract workshop ID from URL or direct ID input"""
        input_text = input_text.strip()
        if not input_text:
            return None
        
        # Try to match URL pattern
        url_match = re.search(r"https?://steamcommunity\.com/sharedfiles/filedetails/\?id=(\d+)", input_text)
        if url_match:
            return url_match.group(1)
        
        # If it's just digits, treat as direct ID
        if input_text.isdigit():
            return input_text
        
        return None


    async def _get_session_token(self) -> str | None:
        """获取manifest.steam.run会话令牌"""
        
        backup_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        try:
            self.log.info("正在获取会话令牌...")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://manifest.steam.run/",
                "Origin": "https://manifest.steam.run",
                "Accept": "application/json, text/plain, */*",
            }
            
            session_resp = await self.client.post(
                "https://manifest.steam.run/api/session", 
                headers=headers,
                timeout=30
            )
            
            if session_resp.status_code == 200:
                data = session_resp.json()
                if "token" in data:
                    token = data["token"]
                    self.log.info(f"成功获取会话令牌: ...{token[-6:]}")
                    return token
            
            self.log.warning("会话令牌获取失败，使用备用令牌")
            
        except Exception as e:
            self.log.warning(f"获取会话令牌时出错: {e}，使用备用令牌")
        
        return backup_token


    async def get_workshop_depot_info(self, workshop_id: str) -> Tuple[str, str, str] | None:
        """Get depot and manifest info for workshop item with title"""
        try:
            self.log.info(f"正在查询创意工坊物品 {workshop_id} 的信息...")
            api_url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
            data = {
                'itemcount': 1,
                'publishedfileids[0]': workshop_id
            }
            
            max_retries, retry_delay = 3, 2
            for attempt in range(max_retries):
                try:
                    response = await self.client.post(api_url, data=data, timeout=30)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    if 'response' not in result or 'publishedfiledetails' not in result['response'] or not result['response']['publishedfiledetails']:
                        self.log.error("API响应格式不正确或未找到物品详情")
                        return None
                    
                    details = result['response']['publishedfiledetails'][0]
                    
                    if int(details.get('result', 0)) != 1:
                        self.log.error(f"未找到创意工坊物品 {workshop_id}")
                        return None
                    
                    consumer_app_id = details.get('consumer_app_id')
                    hcontent_file = details.get('hcontent_file')
                    title = details.get('title', '未知标题')
                    
                    if not consumer_app_id or not hcontent_file:
                        self.log.error(f"创意工坊物品 '{title}' 缺少必要的信息 (App ID 或 Manifest ID)。")
                        return None
                    
                    self.log.info(f"成功获取创意工坊物品信息:")
                    self.log.info(f"  标题: {title}")
                    self.log.info(f"  所属游戏 AppID: {consumer_app_id}")
                    self.log.info(f"  清单 ManifestID: {hcontent_file}")
                    return str(consumer_app_id), str(hcontent_file), title
                    
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        self.log.warning(f"API请求失败，正在重试 ({attempt+1}/{max_retries})...")
                        await asyncio.sleep(retry_delay)
                    else:
                        self.log.error(f"API请求失败: {e}")
                        return None
                except Exception as e:
                    self.log.error(f"获取创意工坊物品信息出错: {self.stack_error(e)}")
                    return None
                    
        except Exception as e:
            self.log.error(f"获取创意工坊物品信息时发生错误: {self.stack_error(e)}")
            return None


    async def download_workshop_manifest(self, depot_id: str, manifest_id: str) -> bytes | None:
        """Download workshop manifest using new method from CLI version"""
        output_filename = f"{depot_id}_{manifest_id}.manifest"
        self.log.info(f"准备下载清单: {output_filename}")
        
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Step 1: 获取 session token
                session_token = await self._get_session_token()
                if not session_token:
                    self.log.error("无法获取会话令牌")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)
                        continue
                    return None
                
                # Step 2: 请求下载代码
                self.log.info(f"正在请求清单下载链接... [Depot: {depot_id}, Manifest: {manifest_id}]")
                
                request_payload = {
                    "depot_id": str(depot_id),
                    "manifest_id": str(manifest_id),
                    "token": session_token
                }
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://manifest.steam.run/",
                    "Origin": "https://manifest.steam.run",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json"
                }
                
                # 等待避免频率限制
                await asyncio.sleep(2)
                
                code_response = await self.client.post(
                    "https://manifest.steam.run/api/request-code",
                    json=request_payload,
                    headers=headers,
                    timeout=60
                )
                
                if code_response.status_code == 429:
                    self.log.warning(f"请求频率过高，等待后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(30)
                        continue
                    return None
                
                if code_response.status_code != 200:
                    self.log.error(f"请求失败，状态码: {code_response.status_code}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(10)
                        continue
                    return None
                
                try:
                    code_data = code_response.json()
                except:
                    self.log.error("服务器返回无效的JSON响应")
                    if attempt < max_retries - 1:
                        continue
                    return None
                
                download_url = code_data.get("download_url")
                if not download_url:
                    error_msg = code_data.get('error', code_data.get('message', '未知错误'))
                    self.log.error(f"请求下载链接失败: {error_msg}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(15)
                        continue
                    return None
                
                self.log.info(f"获取到下载链接")
                
                # Step 3: 下载清单文件
                self.log.info("正在下载清单文件...")
                manifest_response = await self.client.get(download_url, timeout=max(180, self.config.get("download_timeout", 30) * 6))
                
                if manifest_response.status_code != 200:
                    self.log.error(f"下载失败，状态码: {manifest_response.status_code}")
                    if attempt < max_retries - 1:
                        continue
                    return None
                
                manifest_content = manifest_response.content
                
                # Step 4: 处理文件内容（检查是否为ZIP）
                final_content = None
                
                # 检查是否为ZIP文件
                if manifest_content.startswith(b'PK\x03\x04'):
                    self.log.info("检测到ZIP文件，正在自动解压...")
                    try:
                        with io.BytesIO(manifest_content) as mem_zip:
                            with zipfile.ZipFile(mem_zip, 'r') as z:
                                file_list = z.namelist()
                                if len(file_list) == 1:
                                    target_file = file_list[0]
                                    self.log.info(f"从ZIP中提取文件: {target_file}")
                                    final_content = z.read(target_file)
                                else:
                                    self.log.warning(f"ZIP包中文件数量不为1: {len(file_list)}")
                                    final_content = manifest_content
                    except Exception as e:
                        self.log.warning(f"处理ZIP文件时出错: {e}")
                        final_content = manifest_content
                else:
                    self.log.info("文件不是ZIP，将直接保存。")
                    final_content = manifest_content
                
                if not final_content:
                    self.log.error("最终文件内容为空")
                    if attempt < max_retries - 1:
                        continue
                    return None
                
                self.log.info(f"成功下载创意工坊清单，大小: {len(final_content)} 字节")
                return final_content
                
            except Exception as e:
                self.log.error(f"下载过程中出错: {e}")
                if attempt < max_retries - 1:
                    self.log.info(f"等待后重试... (尝试 {attempt + 2}/{max_retries})")
                    await asyncio.sleep(15)
                    continue
        
        self.log.error(f"下载清单 {output_filename} 失败：所有重试都失败了")
        return None

    async def process_workshop_item(self, workshop_input: str, copy_to_config: bool = True, copy_to_depot: bool = True) -> bool:
        """Process workshop item and copy manifest to specified directories"""
        workshop_id = self.extract_workshop_id(workshop_input)
        if not workshop_id:
            self.log.error(f"无法从输入中提取有效的创意工坊ID: {workshop_input}")
            return False
            
        # Get depot and manifest info
        details = await self.get_workshop_depot_info(workshop_id)
        if not details:
            return False # 错误已在 get_workshop_depot_info 中记录
        
        consumer_app_id, hcontent_file, title = details
        
        # Download manifest using new method
        manifest_content = await self.download_workshop_manifest(consumer_app_id, hcontent_file)
        if not manifest_content:
            return False
        
        # Generate filename
        output_filename = f"{consumer_app_id}_{hcontent_file}.manifest"
        
        try:
            # Copy to specified directories
            success_count = 0
            
            if copy_to_config:
                config_depot_path = self.steam_path / 'config' / 'depotcache'
                config_depot_path.mkdir(parents=True, exist_ok=True)
                config_file_path = config_depot_path / output_filename
                async with aiofiles.open(config_file_path, 'wb') as f:
                    await f.write(manifest_content)
                self.log.info(f"清单文件已保存到: {config_file_path}")
                success_count += 1
            
            if copy_to_depot:
                depot_cache_path = self.steam_path / 'depotcache'
                depot_cache_path.mkdir(parents=True, exist_ok=True)
                depot_file_path = depot_cache_path / output_filename
                async with aiofiles.open(depot_file_path, 'wb') as f:
                    await f.write(manifest_content)
                self.log.info(f"清单文件已保存到: {depot_file_path}")
                success_count += 1
            
            if success_count > 0:
                self.log.info(f"创意工坊清单 {output_filename} 处理完成。标题: {title}")
                return True
            else:
                self.log.error("未指定任何目标目录。")
                return False
                
        except Exception as e:
            self.log.error(f"保存创意工坊清单文件时出错: {self.stack_error(e)}")
            return False

    async def _get_buqiuren_manifest_code(self, manifest_id: str) -> str | None:
        """通过 manifest.steam.run API 获取清单请求码"""
        headers = {
            "Host": "manifest.steam.run",
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
        }
        try:
            url = f"https://manifest.steam.run/api/manifest/{manifest_id}"
            res = await self.client.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                content = res.json().get("content")
                if content:
                    return str(content).strip()
            self.log.warning(f"获取清单Code失败，状态码: {res.status_code}")
        except Exception as e:
            self.log.warning(f"获取清单Code时出错: {e}")
        return None

    async def _download_manifest_buqiuren(self, depot_id: str, manifest_id: str, depot_name: str) -> bool:
        """使用不求人接口下载清单（manifest.steam.run 新版流程）"""
        output_filename = f"{depot_id}_{manifest_id}.manifest"
        cdn_host = "steamcontent.tnkjmec.com"
        max_retries = 3

        for attempt in range(max_retries):
            try:
                self.log.info(f"正在获取清单Code... [Depot: {depot_id}, Manifest: {manifest_id}]")
                code = await self._get_buqiuren_manifest_code(manifest_id)
                if not code:
                    self.log.error(f"无法获取清单Code")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)
                        continue
                    return False

                download_url = f"https://{cdn_host}/depot/{depot_id}/manifest/{manifest_id}/5/{code}"
                self.log.info(f"正在从CDN下载清单文件...")

                manifest_response = await self.client.get(
                    download_url,
                    timeout=max(180, self.config.get("download_timeout", 30) * 6)
                )

                if manifest_response.status_code == 429:
                    self.log.warning("请求频率过高，等待后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(30)
                        continue
                    return False

                if manifest_response.status_code != 200:
                    self.log.error(f"下载失败，状态码: {manifest_response.status_code}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(10)
                        continue
                    return False

                manifest_content = manifest_response.content

                # 处理文件内容（检查是否为ZIP）
                final_content = None
                if manifest_content.startswith(b'PK\x03\x04'):
                    self.log.info("检测到ZIP文件，正在自动解压...")
                    try:
                        with zipfile.ZipFile(io.BytesIO(manifest_content), 'r') as z:
                            z.testzip()
                            file_list = z.namelist()
                            if file_list:
                                final_content = z.read(file_list[0])
                                self.log.info(f"从ZIP中提取文件: {file_list[0]}")
                            else:
                                self.log.warning("ZIP包为空")
                    except Exception as e:
                        self.log.warning(f"处理ZIP文件时出错: {e}")
                        final_content = manifest_content
                else:
                    final_content = manifest_content

                if not final_content:
                    self.log.error("最终文件内容为空")
                    if attempt < max_retries - 1:
                        continue
                    return False

                # 保存文件到depotcache目录
                if self.unlocker_type == "steamtools":
                    st_depot_path = self.steam_path / 'config' / 'depotcache'
                    gl_depot_path = self.steam_path / 'depotcache'
                    st_depot_path.mkdir(parents=True, exist_ok=True)
                    gl_depot_path.mkdir(parents=True, exist_ok=True)
                    (st_depot_path / output_filename).write_bytes(final_content)
                    (gl_depot_path / output_filename).write_bytes(final_content)
                    self.log.info(f"清单已保存到: {st_depot_path / output_filename}")
                else:
                    depot_path = self.steam_path / 'depotcache'
                    depot_path.mkdir(parents=True, exist_ok=True)
                    (depot_path / output_filename).write_bytes(final_content)
                    self.log.info(f"清单已保存到: {depot_path / output_filename}")

                self.log.info(f"成功下载清单: {depot_name} ({output_filename})")
                return True

            except Exception as e:
                self.log.error(f"下载过程中出错: {e}")
                if attempt < max_retries - 1:
                    self.log.info(f"等待后重试... (尝试 {attempt + 2}/{max_retries})")
                    await asyncio.sleep(15)
                    continue

        self.log.error(f"下载清单 {output_filename} 失败：所有重试都失败了")
        return False

    async def _get_cached_sudama_data(self) -> Dict:
        """
        核心函数：获取 Sudama 密钥数据
        逻辑：检查本地 sudama_cache.json -> 检查时间戳是否超过24小时 -> 下载或读取缓存
        """
        cache_file = self.project_root / "sudama_cache.json"
        current_time = time.time()
        one_day_seconds = 86400

        # 1. 尝试读取缓存
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                    cache_content = json.loads(await f.read())
                
                last_update = cache_content.get('timestamp', 0)
                # 检查是否过期
                if current_time - last_update < one_day_seconds:
                    self.log.info(f"使用本地缓存的密钥库 (上次更新: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_update))})")
                    return cache_content.get('data', {})
                else:
                    self.log.info("本地密钥缓存已超过24小时，准备从服务器同步最新数据...")
            except Exception as e:
                self.log.warning(f"读取本地缓存失败，将重新下载: {e}")

        # 2. 下载新数据
        url = "https://api.993499094.xyz/depotkeys.json"
        
        # 实现重试机制
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                self.log.info(f"正在从 Sudama API ({url}) 下载全量密钥库... (尝试 {attempt + 1}/{max_retries})")
                # 减少超时时间，避免长时间等待
                response = await self.client.get(url, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                
                if not isinstance(data, dict):
                    self.log.error("API 返回的数据格式不正确 (应为 JSON 对象)")
                    return {}

                # 3. 写入缓存
                cache_data = {
                    "timestamp": current_time,
                    "data": data
                }
                async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(cache_data, ensure_ascii=False))
                
                self.log.info(f"密钥库下载完成并缓存，共 {len(data)} 条数据。")
                return data
                
            except Exception as e:
                self.log.warning(f"第 {attempt + 1} 次下载 Sudama 数据失败: {str(e)[:200]}...")
                
                if attempt < max_retries - 1:
                    self.log.info(f"等待 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    self.log.error(f"下载 Sudama 数据失败，所有重试都失败了")
                    
                # 下载失败时的兜底：如果有过期的缓存，尽量使用过期的
                if cache_file.exists():
                    try:
                        self.log.warning("网络获取失败，尝试使用旧的本地缓存...")
                        async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                            cached_data = json.loads(await f.read())
                            if cached_data.get('data'):
                                self.log.info(f"使用旧的本地缓存成功，数据更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cached_data.get('timestamp', 0)))}")
                                return cached_data.get('data', {})
                    except Exception as cache_error:
                        self.log.warning(f"使用旧的本地缓存也失败了: {cache_error}")
                        
                return {}


# --- SUDAMA REPO START ---
    async def _get_sudama_data(self) -> Dict[str, str]:
        """从 sudama API 获取所有密钥数据 (兼容性包装)"""
        return await self._get_cached_sudama_data()

    async def process_sudama_manifest(self, app_id: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理 Sudama 库清单"""
        try:
            self.log.info(f'正从 Sudama 库处理 AppID {app_id} 的清单...')
            
            # 1. 获取 Depot 和 Manifest 信息 (使用现有的 api 接口)
            depot_manifest_map = await self._get_depots_and_manifests(app_id)
            if not depot_manifest_map:
                self.log.warning(f"未能从 API 获取到 AppID {app_id} 的 depot 信息，跳过该AppID的处理")
                return True  # 返回True表示跳过了处理，而不是失败
            
            self.log.info(f"获取到 {len(depot_manifest_map)} 个 depot 及其 manifest")

            # 2. 获取 Sudama 的所有密钥数据 (改为调用缓存函数)
            sudama_keys = await self._get_cached_sudama_data()
            if not sudama_keys:
                self.log.warning("无法获取 Sudama 密钥库数据，跳过该AppID的处理")
                return True  # 返回True表示跳过了处理，而不是失败

            # 3. 匹配 Depot 与 Key
            valid_depots = {}
            for depot_id in depot_manifest_map.keys():
                if depot_id in sudama_keys:
                    key = sudama_keys[depot_id]
                    if key and str(key).strip():
                        valid_depots[depot_id] = str(key).strip()
                        self.log.info(f"在 Sudama 库中找到 depot {depot_id} 的密钥")
                else:
                    self.log.warning(f"Sudama 库中未找到 depot {depot_id} 的密钥")

            if not valid_depots:
                self.log.warning(f"AppID {app_id} 没有在 Sudama 库中找到任何有效的 depot 密钥")
                return False

            # 4. 根据解锁工具类型处理 (复用 ManifestHub V2 的逻辑)
            if unlocker_type == "steamtools":
                # 将 sudama_keys 作为 depotkeys_data 传入，以便复用修补逻辑
                return await self._process_steamautocracks_v2_for_steamtools(
                    app_id, valid_depots, depot_manifest_map, use_st_auto_update, add_all_dlc, patch_depot_key, sudama_keys
                )
            else:
                return await self._process_steamautocracks_v2_for_greenluma(app_id, valid_depots)

        except Exception as e:
            self.log.error(f'处理 Sudama 库清单时出错: {self.stack_error(e)}')
            return False
            
            
    async def _process_cysaw_manifest(self, app_id: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool) -> bool:
        """处理 Cysaw 清单下载（cysaw.pw POST 接口）"""
        self.log.info(f"正从 Cysaw 下载 AppID {app_id} 的清单...")
        zip_path = self.temp_path / f"cysaw_{app_id}.zip"
        extract_path = self.temp_path / f"cysaw_{app_id}"
        try:
            resp = await self.client.post(
                "https://cysaw.pw/proxy",
                json={"appId": int(app_id)},
                headers={
                    "Origin": "https://cysaw.pw",
                    "Referer": "https://cysaw.pw/",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
                timeout=max(180, self.config.get("download_timeout", 30) * 6),
                follow_redirects=True,
            )
            if resp.status_code == 404:
                self.log.warning(f"Cysaw 中未找到 AppID {app_id}")
                return False
            if resp.status_code != 200:
                self.log.error(f"Cysaw 下载失败，状态码: {resp.status_code}")
                return False

            self.temp_path.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(zip_path, 'wb') as f:
                await f.write(resp.content)
            self.log.info("正在解压...")
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(extract_path)

            st_files = list(extract_path.rglob('*.st'))
            if st_files:
                st_converter = STConverter()
                for st_file in st_files:
                    try:
                        lua_content = st_converter.convert_file(str(st_file))
                        st_file.with_suffix('.lua').write_text(lua_content, encoding='utf-8')
                    except Exception as e:
                        self.log.error(f"转换 {st_file.name} 失败: {e}")

            manifest_files = list(extract_path.rglob('*.manifest'))
            lua_files = list(extract_path.rglob('*.lua'))

            if unlocker_type == "steamtools":
                stplug_path = self.steam_path / 'config' / 'stplug-in'
                stplug_path.mkdir(parents=True, exist_ok=True)
                all_depots = {}
                for lua_f in lua_files:
                    all_depots.update(self.parse_lua_file_for_depots(str(lua_f)))
                lua_filepath = stplug_path / f"{app_id}.lua"
                async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                    await lua_file.write(f'addappid({app_id})\n')
                    for depot_id, info in all_depots.items():
                        await lua_file.write(f'addappid({depot_id}, 1, "{info["DecryptionKey"]}")\n')
                    for manifest_f in manifest_files:
                        match = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                        if match:
                            line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                            await lua_file.write('--' + line if use_st_auto_update else line)
                for manifest_f in manifest_files:
                    for dest in [self.steam_path / 'config' / 'depotcache', self.steam_path / 'depotcache']:
                        dest.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(manifest_f, dest / manifest_f.name)
                self.log.info(f"已为 SteamTools 生成解锁文件: {app_id}.lua")
                if add_all_dlc:
                    await self._add_free_dlcs_to_lua(app_id, lua_filepath)
                if patch_depot_key:
                    await self.patch_lua_with_depotkey(app_id, lua_filepath)
            else:
                steam_depot_path = self.steam_path / 'depotcache'
                steam_depot_path.mkdir(parents=True, exist_ok=True)
                for f in manifest_files:
                    shutil.copy2(f, steam_depot_path / f.name)
                all_depots = {}
                for lua in lua_files:
                    all_depots.update(self.parse_lua_file_for_depots(str(lua)))
                if all_depots:
                    await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})

            self.log.info(f"成功处理 Cysaw 清单: AppID {app_id}")
            return True
        except Exception as e:
            self.log.error(f"处理 Cysaw 清单时出错: {self.stack_error(e)}")
            return False
        finally:
            if zip_path.exists():
                zip_path.unlink(missing_ok=True)
            if extract_path.exists():
                shutil.rmtree(extract_path, ignore_errors=True)

    async def _process_gmrc_manifest(self, app_id: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool) -> bool:
        """处理 gmrc 清单下载（gmrc.wudrm.com，按 manifest ID 逐个下载）"""
        self.log.info(f"正从 GMRC 处理 AppID {app_id} 的清单...")
        try:
            # 1. 获取 depot/manifest 映射
            depot_manifest_map = await self._get_depots_and_manifests(app_id)
            if not depot_manifest_map:
                self.log.warning(f"GMRC: 未能获取 AppID {app_id} 的 depot 信息")
                return False

            self.log.info(f"GMRC: 获取到 {len(depot_manifest_map)} 个 depot")

            # 2. 逐个下载 manifest 文件
            success_count = 0
            depotcache_paths = [
                self.steam_path / 'config' / 'depotcache',
                self.steam_path / 'depotcache',
            ]
            for p in depotcache_paths:
                p.mkdir(parents=True, exist_ok=True)

            for depot_id, manifest_id in depot_manifest_map.items():
                url = f"http://gmrc.wudrm.com/manifest/{manifest_id}"
                try:
                    resp = await self.client.get(url, timeout=30, follow_redirects=True)
                    if resp.status_code == 404:
                        self.log.warning(f"GMRC: manifest {manifest_id} 未找到 (404)")
                        continue
                    if resp.status_code != 200:
                        self.log.warning(f"GMRC: manifest {manifest_id} 下载失败，状态码 {resp.status_code}")
                        continue
                    content = resp.content
                    filename = f"{depot_id}_{manifest_id}.manifest"
                    for p in depotcache_paths:
                        (p / filename).write_bytes(content)
                    self.log.info(f"GMRC: 已下载 {filename}")
                    success_count += 1
                except Exception as e:
                    self.log.warning(f"GMRC: 下载 manifest {manifest_id} 失败: {e}")

            if success_count == 0:
                self.log.error(f"GMRC: AppID {app_id} 没有成功下载任何清单")
                return False

            # 3. 生成 lua 文件（SteamTools）
            if unlocker_type == "steamtools":
                stplug_path = self.steam_path / 'config' / 'stplug-in'
                stplug_path.mkdir(parents=True, exist_ok=True)
                lua_filepath = stplug_path / f"{app_id}.lua"
                async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as f:
                    await f.write(f'addappid({app_id})\n')
                    for depot_id, manifest_id in depot_manifest_map.items():
                        line = f'setManifestid({depot_id}, "{manifest_id}")\n'
                        await f.write('--' + line if use_st_auto_update else line)
                self.log.info(f"GMRC: 已生成 {app_id}.lua")
                if add_all_dlc:
                    await self._add_free_dlcs_to_lua(app_id, lua_filepath)
                if patch_depot_key:
                    await self.patch_lua_with_depotkey(app_id, lua_filepath)
            else:
                all_depots = {}
                if all_depots:
                    await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})

            self.log.info(f"GMRC: 成功处理 AppID {app_id}，下载了 {success_count} 个清单")
            return True
        except Exception as e:
            self.log.error(f"处理 GMRC 清单时出错: {self.stack_error(e)}")
            return False

    async def _process_mhub_manifest(self, app_id: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool) -> bool:
        """处理 MHub 清单下载（steamhub.156354.xyz）"""
        try:
            self.log.info(f"正从 MHub 处理 AppID {app_id} 的清单...")

            # 1. 获取 download_token
            info_url = f"https://steamhub.156354.xyz/api/games/{app_id}"
            resp = await self.client.get(info_url, timeout=15)
            if resp.status_code == 404:
                self.log.warning(f"MHub 中未找到 AppID {app_id}")
                return False
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                self.log.error(f"MHub API 返回失败: {data.get('message')}")
                return False
            token = data["data"].get("download_token")
            if not token:
                self.log.error("MHub API 未返回 download_token")
                return False

            # 2. 下载 zip
            download_url = f"https://steamhub.156354.xyz/api/games/{app_id}/download?token={token}"
            self.log.info("正在从 MHub 下载清单包...")
            dl_resp = await self.client.get(download_url, timeout=max(180, self.config.get("download_timeout", 30) * 6), follow_redirects=True)
            if dl_resp.status_code != 200:
                self.log.error(f"MHub 下载失败，状态码: {dl_resp.status_code}")
                return False

            # 3. 解压并处理（复用通用逻辑）
            zip_path = self.temp_path / f"mhub_{app_id}.zip"
            extract_path = self.temp_path / f"mhub_{app_id}"
            self.temp_path.mkdir(parents=True, exist_ok=True)
            try:
                async with aiofiles.open(zip_path, 'wb') as f:
                    await f.write(dl_resp.content)
                self.log.info("正在解压...")
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(extract_path)

                st_files = list(extract_path.rglob('*.st'))
                if st_files:
                    st_converter = STConverter()
                    for st_file in st_files:
                        try:
                            lua_content = st_converter.convert_file(str(st_file))
                            st_file.with_suffix('.lua').write_text(lua_content, encoding='utf-8')
                        except Exception as e:
                            self.log.error(f"转换 {st_file.name} 失败: {e}")

                manifest_files = list(extract_path.rglob('*.manifest'))
                lua_files = list(extract_path.rglob('*.lua'))

                if unlocker_type == "steamtools":
                    stplug_path = self.steam_path / 'config' / 'stplug-in'
                    stplug_path.mkdir(parents=True, exist_ok=True)

                    all_depots = {}
                    for lua_f in lua_files:
                        all_depots.update(self.parse_lua_file_for_depots(str(lua_f)))

                    lua_filename = f"{app_id}.lua"
                    lua_filepath = stplug_path / lua_filename
                    async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                        await lua_file.write(f'addappid({app_id})\n')
                        for depot_id, info in all_depots.items():
                            await lua_file.write(f'addappid({depot_id}, 1, "{info["DecryptionKey"]}")\n')
                        for manifest_f in manifest_files:
                            match = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                            if match:
                                line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                                if use_st_auto_update:
                                    await lua_file.write('--' + line)
                                else:
                                    await lua_file.write(line)
                    self.log.info(f"已为 SteamTools 生成解锁文件: {lua_filename}")

                    # 复制 manifest 文件
                    for manifest_f in manifest_files:
                        for dest in [self.steam_path / 'config' / 'depotcache', self.steam_path / 'depotcache']:
                            dest.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(manifest_f, dest / manifest_f.name)

                    if add_all_dlc:
                        await self._add_free_dlcs_to_lua(app_id, lua_filepath)
                    if patch_depot_key:
                        await self.patch_lua_with_depotkey(app_id, lua_filepath)

                else:
                    # GreenLuma
                    depot_path = self.steam_path / 'depotcache'
                    depot_path.mkdir(parents=True, exist_ok=True)
                    for manifest_f in manifest_files:
                        shutil.copy2(manifest_f, depot_path / manifest_f.name)
                    await self.greenluma_add([d for d in all_depots] if 'all_depots' in dir() else [])

                self.log.info(f"MHub 清单处理完成: AppID {app_id}")
                return True
            finally:
                if zip_path.exists():
                    zip_path.unlink()
                if extract_path.exists():
                    shutil.rmtree(extract_path, ignore_errors=True)

        except httpx.HTTPStatusError as e:
            self.log.error(f"MHub 请求失败: HTTP {e.response.status_code}")
            return False
        except Exception as e:
            self.log.error(f"处理 MHub 清单时出错: {self.stack_error(e)}")
            return False

    async def process_buqiuren_manifest(self, app_id: str) -> bool:
        """处理不求人库清单下载"""
        try:
            self.log.info(f'正从 清单不求人库 处理 AppID {app_id} 的清单...')
            
            # 使用 API获取depot和manifest信息（复用现有逻辑）
            depot_manifest_map = await self._get_depots_and_manifests(app_id)
            if not depot_manifest_map:
                self.log.warning(f"未能从 API 获取到 AppID {app_id} 的 depot 信息，跳过该AppID的处理")
                return True  # 返回True表示跳过了处理，而不是失败
            
            self.log.info(f"从 API 获取到 {len(depot_manifest_map)} 个 depot 及其 manifest")
            
            # 下载所有depot的清单
            success_count = 0
            total_count = len(depot_manifest_map)
            
            for i, (depot_id, manifest_id) in enumerate(depot_manifest_map.items(), 1):
                self.log.info(f"处理进度: {i}/{total_count}")
                depot_name = f"Depot {depot_id}"
                
                # 使用不求人接口下载
                if await self._download_manifest_buqiuren(depot_id, manifest_id, depot_name):
                    success_count += 1
                else:
                    self.log.warning(f"下载 depot {depot_id} 的清单失败")
                
                # 添加延迟避免频率限制
                if i < total_count:
                    delay = random.uniform(10, 20)
                    self.log.info(f"等待 {delay:.1f} 秒后继续...")
                    await asyncio.sleep(delay)
            
            if success_count == 0:
                self.log.error(f"AppID {app_id} 没有成功下载任何清单")
                return False
            
            self.log.info(f"成功处理不求人库清单: 成功 {success_count}/{total_count}")
            return True
            
        except Exception as e:
            self.log.error(f'处理不求人库清单时出错: {self.stack_error(e)}')
            return False

    async def process_github_api_manifest(self, app_id: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理方式N+1：基于GitHub API的清单下载器（从SteamAutoCracks/ManifestHub仓库下载）"""
        try:
            self.log.info(f'正从 GitHub API 处理 AppID {app_id} 的清单...')
            
            # 获取GitHub仓库信息
            repo = "SteamAutoCracks/ManifestHub"
            github_token = self.config.get("Github_Personal_Token", "")
            headers = {'Authorization': f'Bearer {github_token}'} if github_token else {}
            
            # 获取分支信息
            branch_url = f"https://api.github.com/repos/{repo}/branches/{app_id}"
            branch_response = await self.client.get(branch_url, headers=headers, timeout=30)
            
            if branch_response.status_code != 200:
                self.log.warning(f"GitHub API: 未找到 AppID {app_id} 的分支，跳过处理")
                return True  # 返回True表示跳过了处理，而不是失败
            
            branch_data = branch_response.json()
            commit_sha = branch_data['commit']['sha']
            
            # 获取文件树
            tree_url = f"https://api.github.com/repos/{repo}/git/trees/{commit_sha}?recursive=1"
            tree_response = await self.client.get(tree_url, headers=headers, timeout=30)
            
            if tree_response.status_code != 200:
                self.log.error(f"GitHub API: 无法获取文件树，状态码 {tree_response.status_code}")
                return False
            
            tree_data = tree_response.json()
            files = [file for file in tree_data.get('tree', []) if file['type'] == 'blob']
            
            if not files:
                self.log.warning(f"GitHub API: AppID {app_id} 分支中没有找到文件")
                return True
            
            self.log.info(f"GitHub API: 找到 {len(files)} 个文件，开始下载...")
            
            # 创建临时目录
            import tempfile
            import zipfile
            import shutil
            
            temp_dir = Path(tempfile.mkdtemp())
            extract_path = temp_dir / "extract"
            extract_path.mkdir(parents=True, exist_ok=True)
            
            success_count = 0
            
            # 下载所有文件
            for file_info in files:
                file_path = file_info['path']
                file_url = f"https://raw.githubusercontent.com/{repo}/{app_id}/{file_path}"
                
                try:
                    file_response = await self.client.get(file_url, timeout=30)
                    if file_response.status_code == 200:
                        # 创建子目录结构
                        target_path = extract_path / file_path
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # 保存文件
                        target_path.write_bytes(file_response.content)
                        success_count += 1
                        self.log.info(f"GitHub API: 已下载 {file_path}")
                    else:
                        self.log.warning(f"GitHub API: 下载 {file_path} 失败，状态码 {file_response.status_code}")
                except Exception as e:
                    self.log.warning(f"GitHub API: 下载 {file_path} 时出错: {e}")
            
            if success_count == 0:
                self.log.error(f"GitHub API: AppID {app_id} 没有成功下载任何文件")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # 处理下载的文件
            st_files = list(extract_path.rglob('*.st'))
            manifest_files = list(extract_path.rglob('*.manifest'))
            lua_files = list(extract_path.rglob('*.lua'))
            
            # 转换.st文件为.lua文件
            if st_files:
                st_converter = STConverter()
                for st_file in st_files:
                    try:
                        lua_content = st_converter.convert_file(str(st_file))
                        st_file.with_suffix('.lua').write_text(lua_content, encoding='utf-8')
                        self.log.info(f"GitHub API: 已转换 {st_file.name} -> {st_file.with_suffix('.lua').name}")
                    except Exception as e:
                        self.log.error(f"GitHub API: 转换 {st_file.name} 失败: {e}")
            
            # 复制清单文件到Steam目录
            depotcache_paths = [
                self.steam_path / 'config' / 'depotcache',
                self.steam_path / 'depotcache'
            ]
            
            for p in depotcache_paths:
                p.mkdir(parents=True, exist_ok=True)
            
            manifest_count = 0
            for manifest_file in manifest_files:
                try:
                    for p in depotcache_paths:
                        target_path = p / manifest_file.name
                        shutil.copy2(manifest_file, target_path)
                    manifest_count += 1
                except Exception as e:
                    self.log.warning(f"GitHub API: 复制清单文件 {manifest_file.name} 失败: {e}")
            
            # 生成或更新lua文件
            if unlocker_type == "steamtools":
                stplug_path = self.steam_path / 'config' / 'stplug-in'
                stplug_path.mkdir(parents=True, exist_ok=True)
                
                # 解析现有的lua文件或创建新的
                all_depots = {}
                for lua_f in lua_files:
                    all_depots.update(self.parse_lua_file_for_depots(str(lua_f)))
                
                lua_filepath = stplug_path / f"{app_id}.lua"
                async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                    await lua_file.write(f'addappid({app_id})\n')
                    
                    # 添加depot密钥
                    for depot_id, info in all_depots.items():
                        decryption_key = info.get('DecryptionKey', '')
                        await lua_file.write(f'addappid({depot_id}, 1, "{decryption_key}")\n')
                    
                    # 添加manifest映射
                    for manifest_f in manifest_files:
                        import re
                        match = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                        if match:
                            depot_id, manifest_id = match.groups()
                            line = f'setManifestid({depot_id}, "{manifest_id}")\n'
                            await lua_file.write('--' + line if use_st_auto_update else line)
                
                self.log.info(f"GitHub API: 已生成 {app_id}.lua")
                
                # 添加免费DLC
                if add_all_dlc:
                    await self._add_free_dlcs_to_lua(app_id, lua_filepath)
                
                # 修补depot密钥
                if patch_depot_key:
                    await self.patch_lua_with_depotkey(app_id, lua_filepath)
            
            # 清理临时文件
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            self.log.info(f"GitHub API: 成功处理 AppID {app_id}，下载了 {success_count} 个文件，复制了 {manifest_count} 个清单")
            return True
            
        except Exception as e:
            self.log.error(f'处理 GitHub API 清单时出错: {self.stack_error(e)}')
            return False

    async def _download_single_manifest_via_github_api(self, app_id: str, depot_id: str, manifest_id: str, filename: str):
        """通过GitHub API下载单个清单文件（方法3：N+1）"""
        try:
            # 获取GitHub仓库信息
            repo = "SteamAutoCracks/ManifestHub"
            github_token = self.config.get("Github_Personal_Token", "")
            headers = {'Authorization': f'Bearer {github_token}'} if github_token else {}
            
            # 检查分支是否存在
            branch_url = f"https://api.github.com/repos/{repo}/branches/{app_id}"
            branch_response = await self.client.get(branch_url, headers=headers, timeout=30)
            
            if branch_response.status_code != 200:
                self.log.warning(f"[补全清单文件] 方法3：GitHub API未找到AppID {app_id}的分支")
                return None
            
            # 直接尝试下载清单文件
            file_url = f"https://raw.githubusercontent.com/{repo}/{app_id}/{filename}"
            file_response = await self.client.get(file_url, timeout=30)
            
            if file_response.status_code == 200 and file_response.content:
                self.log.info(f"[补全清单文件] 方法3：成功从GitHub API下载 {filename}")
                return file_response.content
            else:
                self.log.warning(f"[补全清单文件] 方法3：GitHub API下载失败 {filename}，状态码 {file_response.status_code}")
                return None
                
        except Exception as e:
            self.log.warning(f"[补全清单文件] 方法3：GitHub API下载异常 {filename}: {e}")
            return None

    # NEW: DepotKey patching methods
    async def download_depotkeys_json(self) -> Dict:
        """
        获取 DepotKeys 数据。
        已修改：不再从 GitHub/ManifestHub 下载，而是直接复用 Sudama API 的缓存逻辑。
        这样 '修补创意工坊密钥' 功能也会使用 Sudama 的数据源。
        """
        self.log.info("正在获取 DepotKeys (来源: Sudama API)...")
        data = await self._get_cached_sudama_data()
        if not data:
            self.log.warning("无法获取 Sudama 密钥库数据，将使用空数据继续处理")
        return data or {}

    async def process_steamautocracks_v2_manifest(self, app_id: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理 SteamAutoCracks/ManifestHub(2) 清单库 - 使用  API 获取 depot 和 manifest 信息"""
        try:
            self.log.info(f'正从 SteamAutoCracks/ManifestHub(2) 处理 AppID {app_id} 的清单...')
            
            # 1. 从  API 获取 depot 和 manifest 信息
            depot_manifest_map = await self._get_depots_and_manifests(app_id)
            if not depot_manifest_map:
                self.log.warning(f"未能从 API 获取到 AppID {app_id} 的 depot 信息，跳过该AppID的处理")
                return True  # 返回True表示跳过了处理，而不是失败
            
            self.log.info(f"从 API 获取到 {len(depot_manifest_map)} 个 depot 及其 manifest")
            
            # 2. 下载 depotkeys.json（复用现有方法）
            if 'IS_CN' not in os.environ:
                self.log.info("检测网络环境以优化下载源选择...")
                await self.checkcn()
            
            depotkeys_data = await self.download_depotkeys_json()
            if not depotkeys_data:
                self.log.warning("无法获取 depotkeys 数据，将跳过密钥修补功能")
                # 继续处理，只是不修补密钥
                patch_depot_key = False
            
            # 3. 匹配 depot 与 depotkey
            valid_depots = {}
            for depot_id in depot_manifest_map.keys():
                if depot_id in depotkeys_data:
                    depotkey = depotkeys_data[depot_id]
                    # 检查 depotkey 是否有效（不为空字符串）
                    if depotkey and str(depotkey).strip():
                        valid_depots[depot_id] = str(depotkey).strip()
                        self.log.info(f"找到 depot {depot_id} 的有效 depotkey: {depotkey}")
                    else:
                        self.log.warning(f"depot {depot_id} 的 depotkey 为空，自动跳过")
                else:
                    self.log.warning(f"未找到 depot {depot_id} 的 depotkey，自动跳过")
            
            if not valid_depots:
                self.log.warning(f"AppID {app_id} 没有找到任何有效的 depot 密钥，此 AppID 可能没有创意工坊密钥或暂未收录，不影响本体使用")
                return True  # 仅密钥源，无密钥视为正常完成
            
            # 4. 根据解锁工具类型处理
            if unlocker_type == "steamtools":
                return await self._process_steamautocracks_v2_for_steamtools(app_id, valid_depots, depot_manifest_map, use_st_auto_update, add_all_dlc, patch_depot_key, depotkeys_data)
            else:
                return await self._process_steamautocracks_v2_for_greenluma(app_id, valid_depots)
                
        except Exception as e:
            self.log.error(f'处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {self.stack_error(e)}')
            return False

    async def _get_depots_and_manifests(self, app_id: str) -> Dict[str, str]:
        """
        统一获取 depot 和 manifest 映射：
        底层直接调用 get_depots_safe，依次极速尝试 Token -> CaiGames -> SteamCMD -> Steam 官方 API。
        """
        depot_manifest_map = {}
        self.log.info(f"正尝试获取 AppID {app_id} 的 Depot 与 Manifest 映射信息...")
        
        try:
            # get_depots_safe 已经实现了最高效的优先级链路
            safe_depots = await self.get_depots_safe(app_id)
            if safe_depots:
                for depot_id, manifest_id, size, source in safe_depots:
                    # 过滤掉无效的数据
                    if depot_id and manifest_id:
                        depot_manifest_map[str(depot_id)] = str(manifest_id)
                
                if depot_manifest_map:
                    self.log.info(f"成功获取 {len(depot_manifest_map)} 个 depot 映射（包含隐藏Depot）。")
                    return depot_manifest_map
                    
            self.log.warning(f"未能解析到 AppID {app_id} 的任何有效 depot 映射。")
        except Exception as e:
            self.log.warning(f"获取 AppID {app_id} depot 映射时发生异常: {e}")
            
        return depot_manifest_map

    async def _process_steamautocracks_v2_for_steamtools(self, app_id: str, valid_depots: Dict[str, str], depot_manifest_map: Dict[str, str], use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool, depotkeys_data: Dict) -> bool:
        """为 SteamTools 处理 SteamAutoCracks/ManifestHub(2) 清单"""
        try:
            stplug_path = self.steam_path / 'config' / 'stplug-in'
            
            lua_filename = f"{app_id}.lua"
            lua_filepath = stplug_path / lua_filename
            
            # 检查是否启用了自动更新模式
            is_auto_update_mode = use_st_auto_update
            
            # 生成 lua 文件内容
            lines = []
            
            # 第一行：主游戏 appid
            lines.append(f'addappid({app_id})')
            
            # 添加所有有效的 depot 及其密钥
            for depot_id, depotkey in valid_depots.items():
                lines.append(f'addappid({depot_id}, 1, "{depotkey}")')
            
            # 添加 setManifestid 行（使用从  API 获取的 manifest 信息）
            manifest_lines = []
            for depot_id in valid_depots.keys():
                if depot_id in depot_manifest_map:
                    manifest_id = depot_manifest_map[depot_id]
                    # 根据是否启用自动更新决定是否注释掉 manifest 行
                    if is_auto_update_mode:
                        # 自动更新模式：注释掉 setManifestid 行
                        manifest_lines.append(f'--setManifestid({depot_id}, "{manifest_id}")')
                        self.log.info(f"添加注释的 manifest 映射（自动更新模式）: depot {depot_id} -> manifest {manifest_id}")
                    else:
                        # 固定版本模式：正常添加 setManifestid 行
                        manifest_lines.append(f'setManifestid({depot_id}, "{manifest_id}")')
                        self.log.info(f"添加 manifest 映射（固定版本）: depot {depot_id} -> manifest {manifest_id}")
            
            # 写入文件
            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write('\n'.join(lines) + '\n')
                if manifest_lines:
                    await lua_file.write('\n-- Manifests\n')
                    await lua_file.write('\n'.join(manifest_lines) + '\n')
            
            self.log.info(f"已为SteamTools生成解锁文件: {lua_filename}")

            # 同步备份，防止 Steam 更新后丢失
            try:
                backup_st = self.project_root / 'backup' / 'stplug-in'
                backup_st.mkdir(parents=True, exist_ok=True)
                shutil.copy2(lua_filepath, backup_st / lua_filename)
            except Exception:
                pass
            
            # 处理 DLC
            if add_all_dlc:
                await self._add_free_dlcs_to_lua(app_id, lua_filepath)
            
            # 处理创意工坊密钥修补（复用已下载的 depotkeys_data）
            if patch_depot_key:
                self.log.info("开始修补创意工坊depotkey...")
                await self._patch_lua_with_existing_depotkeys(app_id, lua_filepath, depotkeys_data)
            
            return True
            
        except Exception as e:
            self.log.error(f'为 SteamTools 处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {e}')
            return False

    async def _process_steamautocracks_v2_for_greenluma(self, app_id: str, valid_depots: Dict[str, str]) -> bool:
        """为 GreenLuma 处理 SteamAutoCracks/ManifestHub(2) 清单"""
        try:
            # GreenLuma needs the depotkeys merged into config.vdf
            depots_config = {'depots': {depot_id: {"DecryptionKey": key} for depot_id, key in valid_depots.items()}}
            
            # Merge depotkeys
            config_vdf_path = self.steam_path / 'config' / 'config.vdf'
            if await self.depotkey_merge(config_vdf_path, depots_config):
                self.log.info("已将密钥合并到 config.vdf")
            
            # Add app IDs to GreenLuma
            gl_ids = list(valid_depots.keys())
            gl_ids.append(app_id)
            await self.greenluma_add(list(set(gl_ids)))
            self.log.info("已添加到 GreenLuma")
            
            return True
            
        except Exception as e:
            self.log.error(f'为 GreenLuma 处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {e}')
            return False
    
    async def _patch_lua_with_existing_depotkeys(self, app_id: str, lua_file_path: Path, depotkeys_data: Dict) -> bool:
            """搬运自 Reborn：增强型修补逻辑，防止废档"""
            try:
                if app_id not in depotkeys_data:
                    return False
                depotkey = str(depotkeys_data[app_id]).strip()
                if not depotkey:  # 防止修补空密钥
                    return False
                if not lua_file_path.exists():
                    return False

                async with self.lock:
                    async with aiofiles.open(lua_file_path, 'r', encoding='utf-8') as f:
                        lines = (await f.read()).strip().split('\n')

                    new_lines, replaced = [], False
                    for line in lines:
                        if line.strip() == f"addappid({app_id})":
                            new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                            replaced = True
                        else:
                            new_lines.append(line.strip())
                    if not replaced:
                        new_lines.append(f'addappid({app_id},1,"{depotkey}")')

                    async with aiofiles.open(lua_file_path, 'w', encoding='utf-8') as f:
                        await f.write('\n'.join(new_lines) + '\n')
                return True
            except Exception:
                return False

    async def patch_lua_with_depotkey(self, app_id: str, lua_file_path: Path) -> bool:
        """Patch LUA file with depotkey from SteamAutoCracks repository"""
        try:
            # Ensure network environment is detected for mirror selection
            if 'IS_CN' not in os.environ:
                self.log.info("检测网络环境以优化下载源选择...")
                await self.checkcn()
            
            # Download depotkeys.json
            depotkeys_data = await self.download_depotkeys_json()
            if not depotkeys_data:
                self.log.error("无法获取 depotkeys 数据，跳过 depotkey 修补。")
                return False
            
            # Check if app_id exists in depotkeys
            if app_id not in depotkeys_data:
                self.log.warning(f"没有此AppID的depotkey: {app_id}，，这是正常情况，可能此APP ID没有创意功放密钥或者暂未收录，不影响本体使用")
                return False
            
            depotkey = depotkeys_data[app_id]
            
            # FIXED: Check if depotkey is valid (not empty, not None, not just whitespace)
            if not depotkey or not str(depotkey).strip():
                self.log.warning(f"AppID {app_id} 的 depotkey 为空或无效，跳过修补: '{depotkey}，这是正常情况，可能此APP ID没有创意功放密钥或者暂未收录，不影响本体使用'")
                return False
            
            # Make sure depotkey is string and strip whitespace
            depotkey = str(depotkey).strip()
            self.log.info(f"找到 AppID {app_id} 的有效 depotkey: {depotkey}")
            
            # Read existing LUA file
            if not lua_file_path.exists():
                self.log.error(f"LUA文件不存在: {lua_file_path}")
                return False
            
            async with aiofiles.open(lua_file_path, 'r', encoding='utf-8') as f:
                lua_content = await f.read()
            
            # Parse lines
            lines = lua_content.strip().split('\n')
            new_lines = []
            app_id_line_removed = False
            
            # Remove existing addappid({app_id}) line and add new one with depotkey
            for line in lines:
                line = line.strip()
                # Check if this is the simple addappid line we need to replace
                if line == f"addappid({app_id})":
                    # Replace with depotkey version
                    new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                    app_id_line_removed = True
                    self.log.info(f"已替换: addappid({app_id}) -> addappid({app_id},1,\"{depotkey}\")")
                else:
                    new_lines.append(line)
            
            # If we didn't find the simple addappid line, add the depotkey version
            if not app_id_line_removed:
                new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                self.log.info(f"已添加新的 depotkey 条目: addappid({app_id},1,\"{depotkey}\")")
            
            # Write back to file
            async with aiofiles.open(lua_file_path, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(new_lines) + '\n')
            
            self.log.info(f"成功修补 LUA 文件的 depotkey: {lua_file_path.name}")
            return True
            
        except Exception as e:
            self.log.error(f"修补 LUA depotkey 时出错: {self.stack_error(e)}")
            return False

    # Original methods continue...
    def restore_managed_files_from_backup(self) -> int:
        """检查备份目录，将 Steam 更新后丢失的入库文件恢复回去。返回恢复的文件数量。"""
        if not self.steam_path:
            return 0
        backup_dir = self.project_root / 'backup'
        st_backup = backup_dir / 'stplug-in'
        gl_backup = backup_dir / 'AppList'
        st_src = self.steam_path / 'config' / 'stplug-in'
        gl_src = self.steam_path / 'AppList'

        restored = 0
        try:
            if st_src.exists() and st_backup.exists():
                for f in st_backup.glob('*.lua'):
                    dest = st_src / f.name
                    if not dest.exists():
                        shutil.copy2(f, dest)
                        restored += 1
                        self.log.info(f"[恢复] {f.name}")
            if gl_src.exists() and gl_backup.exists():
                for f in gl_backup.glob('*.txt'):
                    dest = gl_src / f.name
                    if not dest.exists():
                        shutil.copy2(f, dest)
                        restored += 1
                        self.log.info(f"[恢复] {f.name}")
            if restored:
                self.log.info(f"Steam 更新后共恢复 {restored} 个入库文件")
        except Exception as e:
            self.log.warning(f"恢复入库文件时出错: {e}")
        return restored

    def _update_steamtools_config(self):
        """写入 SteamTools 注册表配置，确保重启后解锁生效"""
        try:
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steamtools", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "ActivateUnlockMode", 0, winreg.REG_SZ, "true")
            winreg.SetValueEx(key, "AlwaysStayUnlocked", 0, winreg.REG_SZ, "true")
            winreg.SetValueEx(key, "notUnlockDepot", 0, winreg.REG_SZ, "false")
            winreg.CloseKey(key)
            self.log.info("已更新 SteamTools 注册表配置")
            return True
        except Exception as e:
            self.log.warning(f"更新 SteamTools 注册表配置失败（非致命）: {e}")
            return False

    def restart_steam(self) -> bool:
        if not self.steam_path:
            self.log.error("无法重启 Steam：未找到 Steam 路径。")
            return False
        steam_exe_path = self.steam_path / 'steam.exe'
        if not steam_exe_path.exists():
            self.log.error(f"无法启动 Steam：在 '{self.steam_path}' 目录下未找到 steam.exe。")
            return False
        try:
            self._update_steamtools_config()
            subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], capture_output=True, text=True, check=False)
            time.sleep(3)
            subprocess.Popen([str(steam_exe_path)], creationflags=subprocess.DETACHED_PROCESS, close_fds=True)
            self.log.info("Steam 已重启。")
            return True
        except Exception as e:
            self.log.error(f"重启 Steam 失败: {self.stack_error(e)}")
            return False

    async def check_github_api_rate_limit(self) -> bool:
        github_token = self.config.get("Github_Personal_Token", "").strip()
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        if github_token: self.log.info("已配置GitHub Token。")
        else: self.log.warning("未找到GitHub Token。您的API请求将受到严格的速率限制。")
        url = 'https://api.github.com/rate_limit'
        try:
            r = await self.client.get(url, headers=headers)
            r.raise_for_status()
            rate_limit = r.json().get('resources', {}).get('core', {})
            remaining = rate_limit.get('remaining', 0)
            reset_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(rate_limit.get('reset', 0)))
            self.log.info(f'GitHub API剩余请求次数: {remaining}')
            if remaining == 0:
                self.log.error("GitHub API请求次数已用尽。")
                self.log.error(f"您的请求次数将于 {reset_time} 重置。")
                self.log.error("要提升请求上限，请在config.json文件中添加您的'Github_Personal_Token'。")
                return False
            return True
        except Exception as e:
            self.log.error(f'检查GitHub API速率限制失败: {self.stack_error(e)}')
            return False

    async def checkcn(self) -> bool:
        try:
            req = await self.client.get('https://mips.kugou.com/check/iscn?&format=json', timeout=5)
            body = req.json()
            is_cn = bool(body['flag'])
            os.environ['IS_CN'] = 'yes' if is_cn else 'no'
            if is_cn: self.log.info(f"检测到区域为中国大陆 ({body['country']})。将使用国内镜像。")
            else: self.log.info(f"检测到区域为非中国大陆 ({body['country']})。将直接使用GitHub。")
            return is_cn
        except Exception:
            os.environ['IS_CN'] = 'yes'
            self.log.warning('无法确定服务器位置，默认您在中国大陆。')
            return True

    def parse_lua_file_for_depots(self, lua_file_path: str) -> Dict:
        addappid_pattern = re.compile(r'addappid\((\d+),\s*1,\s*"([^"]+)"\)')
        depots = {}
        try:
            with open(lua_file_path, 'r', encoding='utf-8') as file:
                lua_content = file.read()
                for match in addappid_pattern.finditer(lua_content):
                    depots[match.group(1)] = {"DecryptionKey": match.group(2)}
        except Exception as e:
            self.log.error(f"解析lua文件 {lua_file_path} 出错: {e}")
        return depots

    async def depotkey_merge(self, config_path: Path, depots_config: dict) -> bool:
        if not config_path.exists():
            self.log.error('未找到Steam默认配置文件，您可能尚未登录。')
            return False
        try:
            async with aiofiles.open(config_path, encoding='utf-8') as f: content = await f.read()
            config_vdf = vdf.loads(content)
            steam = config_vdf.get('InstallConfigStore', {}).get('Software', {}).get('Valve') or \
                    config_vdf.get('InstallConfigStore', {}).get('Software', {}).get('valve')
            if steam is None:
                self.log.error('找不到Steam配置节。')
                return False
            depots = steam.setdefault('depots', {})
            depots.update(depots_config.get('depots', {}))
            async with aiofiles.open(config_path, mode='w', encoding='utf-8') as f:
                await f.write(vdf.dumps(config_vdf, pretty=True))
            self.log.info('成功将密钥合并到config.vdf。')
            return True
        except Exception as e:
            self.log.error(f'合并失败: {self.stack_error(e)}')
            return False

    def _build_mirror_urls(self, repo: str, sha: str, path: str) -> List[str]:
        """构建镜像URL列表（国内环境优先使用代理）"""
        if os.environ.get('IS_CN') == 'yes':
            return [
                f'https://gh-proxy.org/https://github.com/{repo}/{sha}/{path}',
                f'https://cdn.gh-proxy.org/https://github.com/{repo}/{sha}/{path}',
                f'https://edgeone.gh-proxy.org/https://github.com/{repo}/{sha}/{path}',
                f'https://github.chenc.dev/github.com/{repo}/{sha}/{path}',
                f'https://fastgit.cc/https://github.com/{repo}/{sha}/{path}',
                f'https://gh.llkk.cc/https://github.com/{repo}/{sha}/{path}',
                f'https://gh.akass.cn/{repo}/{sha}/{path}',
                f'https://raw.githubusercontent.com/{repo}/{sha}/{path}',
            ]
        return [f'https://raw.githubusercontent.com/{repo}/{sha}/{path}']

    async def _get_from_mirrors(self, sha: str, path: str, repo: str) -> bytes:
        urls = self._build_mirror_urls(repo, sha, path)

        # 如果有上次成功的镜像索引，把它移到最前面优先尝试
        preferred = getattr(self, '_preferred_mirror_index', None)
        if preferred is not None and 0 < preferred < len(urls):
            urls = [urls[preferred]] + urls[:preferred] + urls[preferred + 1:]

        for idx, url in enumerate(urls):
            try:
                r = await self.client.get(url, timeout=30)
                if r.status_code == 200:
                    self.log.info(f'下载成功: {path} (来自 {url.split("/")[2]})')
                    # 记录本次成功的镜像在原始列表中的位置
                    original_urls = self._build_mirror_urls(repo, sha, path)
                    try:
                        self._preferred_mirror_index = original_urls.index(url)
                    except ValueError:
                        pass
                    return r.content
                self.log.error(f'下载失败: {path} (来自 {url.split("/")[2]}) - 状态码: {r.status_code}')
            except httpx.RequestError as e:
                self.log.error(f'下载失败: {path} (来自 {url.split("/")[2]}) - 错误: {e}')
        raise Exception(f'尝试所有镜像后仍无法下载文件: {path}')

    async def greenluma_add(self, depot_id_list: list) -> bool:
        app_list_path = self.steam_path / 'AppList'
        try:
            for file in app_list_path.glob('*.txt'): file.unlink(missing_ok=True)
            depot_dict = { int(i.stem): int(i.read_text(encoding='utf-8').strip()) for i in app_list_path.iterdir() if i.is_file() and i.stem.isdecimal() and i.suffix == '.txt' }
            for depot_id in map(int, depot_id_list):
                if depot_id not in depot_dict.values():
                    index = max(depot_dict.keys(), default=-1) + 1
                    (app_list_path / f'{index}.txt').write_text(str(depot_id), encoding='utf-8')
                    depot_dict[index] = depot_id
            self.log.info(f"成功将 {len(depot_id_list)} 个ID添加到GreenLuma的AppList中。")
            # 同步备份，防止 Steam 更新后丢失
            try:
                backup_gl = self.project_root / 'backup' / 'AppList'
                backup_gl.mkdir(parents=True, exist_ok=True)
                for f in app_list_path.glob('*.txt'):
                    shutil.copy2(f, backup_gl / f.name)
            except Exception:
                pass
            return True
        except Exception as e:
            self.log.error(f'GreenLuma添加 AppID失败: {e}')
            return False
            
    async def _get_steamcmd_api_data(self, appid: str) -> Dict:
        try:
            resp = await self.client.get(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.log.error(f"从 api.steamcmd.net 获取 AppID {appid} 数据失败: {e}")
            return {}

    # UPDATED: Use new safe functions for DLC retrieval
    async def _get_dlc_ids(self, appid: str) -> List[str]:
        """获取DLC ID列表，使用新的安全函数"""
        return await self.get_dlc_ids_safe(appid)

    # UPDATED: Use new safe functions for depot retrieval  
    async def _get_depots(self, appid: str) -> List[Dict]:
        """获取Depot信息列表，转换为旧格式兼容"""
        depot_tuples = await self.get_depots_safe(appid)
        # Convert to old format for compatibility
        return [
            {
                "depot_id": depot_id,
                "size": size,
                "dlc_appid": source.split(':')[1] if source.startswith('DLC:') else None
            }
            for depot_id, manifest_id, size, source in depot_tuples
        ]

    async def _add_free_dlcs_to_lua(self, app_id: str, lua_filepath: Path) -> bool:
            """重写：Reborn 过滤逻辑 + 异步文件锁 + 全局超时控制"""
            timeout = int(self.config.get("DLCTimeout", 60))

            async def _do_fetch_and_write():
                try:
                    all_dlc_ids = await self._get_dlc_ids(app_id)
                    if not all_dlc_ids:
                        return True

                    # 用主游戏 depot 信息过滤掉已有 depot 的 DLC，只处理"落单"的
                    main_depots = await self.get_depots_safe(app_id)
                    dlcs_with_depots = {src.split(":")[1] for _, _, _, src in main_depots if src.startswith("DLC:")}
                    depot_less_dlc_ids = [str(dlc) for dlc in all_dlc_ids if str(dlc) not in dlcs_with_depots]

                    if not depot_less_dlc_ids:
                        return True

                    async with self.lock:
                        if not lua_filepath.exists():
                            return False
                        async with aiofiles.open(lua_filepath, 'r', encoding='utf-8') as f:
                            existing_lines = [line.strip() for line in (await f.read()).splitlines() if line.strip()]

                        existing_appids = {m.group(1) for line in existing_lines if (m := re.search(r'addappid\((\d+)', line))}
                        new_dlcs_to_add = [dlc for dlc in depot_less_dlc_ids if dlc not in existing_appids]
                        if not new_dlcs_to_add:
                            return True

                        final_lines = set(existing_lines)
                        for dlc_id in new_dlcs_to_add:
                            final_lines.add(f"addappid({dlc_id})")

                        def sort_key(line):
                            if m := re.search(r'addappid\((\d+)', line): return (0, int(m.group(1)))
                            if m := re.search(r'setManifestid\((\d+)', line): return (1, int(m.group(1)))
                            return (2, line)

                        sorted_lines = sorted(list(final_lines), key=sort_key)
                        async with aiofiles.open(lua_filepath, 'w', encoding='utf-8') as f:
                            await f.write('\n'.join(sorted_lines) + '\n')
                    return True
                except Exception:
                    return False

            try:
                return await asyncio.wait_for(_do_fetch_and_write(), timeout=timeout)
            except asyncio.TimeoutError:
                self.log.error(f"AppID {app_id} DLC 检索任务超时，已释放")
                return False

    # MODIFIED: Added patch_depot_key parameter
    async def _process_zip_manifest_generic(self, app_id: str, download_url: str, source_name: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool = False) -> bool:
        zip_path = self.temp_path / f'{app_id}.zip'
        extract_path = self.temp_path / app_id
        try:
            self.temp_path.mkdir(exist_ok=True, parents=True)
            self.log.info(f'正从 {source_name} 下载 AppID {app_id} 的清单...')
            
            try:
                response = await self.client.get(download_url, timeout=60)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.log.warning(f'AppID {app_id} 在 {source_name} 中未找到 (404错误)')
                    return False
                elif e.response.status_code == 429:
                    self.log.error(f'请求 {source_name} 过于频繁 (429错误)，请稍后重试')
                    return False
                else:
                    self.log.error(f'从 {source_name} 下载失败: HTTP {e.response.status_code}')
                    return False
            except Exception as e:
                self.log.error(f'从 {source_name} 下载时出错: {self.stack_error(e)}')
                return False
                
            async with aiofiles.open(zip_path, 'wb') as f: await f.write(response.content)
            self.log.info('正在解压...')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(extract_path)
            
            # codeload zip 解压后文件在子目录里（如 ManifestHub-{app_id}/），用 rglob 递归匹配
            st_files = list(extract_path.rglob('*.st'))
            if st_files:
                st_converter = STConverter()
                for st_file in st_files:
                    try:
                        lua_content = st_converter.convert_file(str(st_file))
                        (st_file.with_suffix('.lua')).write_text(lua_content, encoding='utf-8')
                        self.log.info(f'已转换 {st_file.name} -> {st_file.with_suffix(".lua").name}')
                    except Exception as e: self.log.error(f'转换 .st 文件 {st_file.name} 失败: {e}')

            manifest_files = list(extract_path.rglob('*.manifest'))
            lua_files = list(extract_path.rglob('*.lua'))
            
            if unlocker_type == "steamtools":
                self.log.info(f"SteamTools 自动更新模式: {'已启用' if use_st_auto_update else '已禁用'}")
                stplug_path = self.steam_path / 'config' / 'stplug-in'
                
                all_depots = {}
                for lua_f in lua_files:
                    depots = self.parse_lua_file_for_depots(str(lua_f))
                    all_depots.update(depots)

                lua_filename = f"{app_id}.lua"
                lua_filepath = stplug_path / lua_filename
                async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                    await lua_file.write(f'addappid({app_id})\n')
                    for depot_id, info in all_depots.items():
                        await lua_file.write(f'addappid({depot_id}, 1, "{info["DecryptionKey"]}")\n')

                    for manifest_f in manifest_files:
                        match = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                        if match:
                            line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                            if use_st_auto_update: await lua_file.write('--' + line)
                            else: await lua_file.write(line)
                
                # 复制manifest文件到depotcache目录
                steam_depot_path = self.steam_path / 'depotcache'
                for f in manifest_files:
                    shutil.copy2(f, steam_depot_path / f.name)
                    self.log.info(f'已复制清单: {f.name}')
                
                self.log.info(f"已为 SteamTools 生成解锁文件: {lua_filename}")

                if add_all_dlc:
                    await self._add_free_dlcs_to_lua(app_id, lua_filepath)

                # NEW: Apply depotkey patch if requested
                if patch_depot_key:
                    self.log.info("开始修补创意工坊depotkey...")
                    await self.patch_lua_with_depotkey(app_id, lua_filepath)

            else:
                self.log.info(f'检测到 GreenLuma/标准模式，将处理来自 {source_name} 的文件。')
                if not manifest_files:
                    self.log.warning(f"在来自 {source_name} 的压缩包中未找到 .manifest 文件。")
                    return False

                steam_depot_path = self.steam_path / 'depotcache'
                for f in manifest_files:
                    shutil.copy2(f, steam_depot_path / f.name)
                    self.log.info(f'已复制清单: {f.name}')
                
                all_depots = {}
                for lua in lua_files:
                    depots = self.parse_lua_file_for_depots(str(lua))
                    all_depots.update(depots)
                if all_depots:
                    await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})

            self.log.info(f'成功处理来自 {source_name} 的清单。')
            return True
        except Exception as e:
            self.log.error(f'处理来自 {source_name} 的清单时出错: {self.stack_error(e)}')
            return False
        finally:
            if zip_path.exists(): zip_path.unlink(missing_ok=True)
            if extract_path.exists(): shutil.rmtree(extract_path)

    async def process_zip_source(self, app_id: str, tool_type: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool = False) -> bool:
        source_map = {
            "cysaw": "special",
            "walftech": "https://walftech.com/proxy.php?url=https%3A%2F%2Fsteamgames554.s3.us-east-1.amazonaws.com%2F{app_id}.zip",
            "steamautocracks_v2": "special",
            "steamautocracks_v1": "special",
            "sac-other": "special",
            "MHub": "special",
            "buqiuren": "special",
            "sudama": "special"
        }
        source_name_map = {
            "walftech": "Walftech",
            "MHub": "MHub",
            "steamautocracks_v2": "SteamAutoCracks/ManifestHub(2)",
            "steamautocracks_v1": "SteamAutoCracks V1 (ManifestHub)"
        }
        
        # 特殊处理 steamautocracks_v2
        if tool_type == "steamautocracks_v2":
            return await self.process_steamautocracks_v2_manifest(app_id, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        # 特殊处理 steamautocracks_v1（GitHub分支方式）
        if tool_type == "steamautocracks_v1":
            return await self.process_github_manifest(app_id, "SteamAutoCracks/ManifestHub", unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        # 特殊处理 Cysaw：POST 请求
        if tool_type == "cysaw":
            return await self._process_cysaw_manifest(app_id, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        # 特殊处理 sac-other：直连失败时自动走镜像
        if tool_type == "sac-other":
            repo = "SteamAutoCracks/ManifestHub"
            direct_url = f"https://codeload.github.com/{repo}/zip/refs/heads/{app_id}"
            self.log.info(f"正从 SAC分流 下载 AppID {app_id} 的清单...")
            ok = await self._process_zip_manifest_generic(app_id, direct_url, "SAC分流", unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
            if ok:
                return True
            self.log.warning("SAC分流直连失败，尝试镜像...")
            for mirror in [
                f"https://gh-proxy.org/https://codeload.github.com/{repo}/zip/refs/heads/{app_id}",
                f"https://cdn.gh-proxy.org/https://codeload.github.com/{repo}/zip/refs/heads/{app_id}",
                f"https://edgeone.gh-proxy.org/https://codeload.github.com/{repo}/zip/refs/heads/{app_id}",
            ]:
                self.log.info(f"尝试镜像: {mirror.split('/')[2]}")
                ok = await self._process_zip_manifest_generic(app_id, mirror, "SAC分流(镜像)", unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
                if ok:
                    return True
            self.log.error("SAC分流所有镜像均失败")
            return False
        # 特殊处理 MHub：先获取 token，再下载
        if tool_type == "MHub":
            return await self._process_mhub_manifest(app_id, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        # 特殊处理 gmrc：按 manifest ID 逐个下载
        if tool_type == "gmrc":
            return await self._process_gmrc_manifest(app_id, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        if tool_type == "buqiuren":
            return await self.process_buqiuren_manifest(app_id)
            
        if tool_type == "sudama":
            return await self.process_sudama_manifest(app_id, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
            
        # Check for custom zip repos
        custom_zip_repos = self.get_custom_zip_repos()
        for repo_config in custom_zip_repos:
            if tool_type == f"custom_zip_{repo_config['name']}":
                return await self.process_custom_zip_manifest(app_id, repo_config, add_all_dlc, patch_depot_key)
        
        url_template = source_map.get(tool_type)
        source_name = source_name_map.get(tool_type)
        if not url_template or not source_name:
            self.log.error(f"未知的压缩包源: {tool_type}")
            return False
        download_url = url_template.format(app_id=app_id)
        return await self._process_zip_manifest_generic(app_id, download_url, source_name, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)

    async def _fetch_branch_via_web(self, app_id: str, repo: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool) -> bool:
        """API 耗尽时的兜底方案：直接从 codeload.github.com 下载分支 zip"""
        self.log.info(f"[Web兜底] 尝试直接下载 {repo} 分支 {app_id} 的 zip 包...")
        download_url = f"https://codeload.github.com/{repo}/zip/refs/heads/{app_id}"
        result = await self._process_zip_manifest_generic(
            app_id, download_url, f"GitHub/{repo}(web)", unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key
        )
        if result:
            self.log.info(f"[Web兜底] 成功从 codeload.github.com 获取 {app_id} 的清单")
        else:
            self.log.warning(f"[Web兜底] codeload.github.com 也未找到 {app_id}，尝试国内镜像...")
            # 国内镜像 codeload 代理
            mirror_urls = [
                f"https://gh-proxy.org/https://codeload.github.com/{repo}/zip/refs/heads/{app_id}",
                f"https://cdn.gh-proxy.org/https://codeload.github.com/{repo}/zip/refs/heads/{app_id}",
                f"https://edgeone.gh-proxy.org/https://codeload.github.com/{repo}/zip/refs/heads/{app_id}",
            ]
            for url in mirror_urls:
                self.log.info(f"[Web兜底] 尝试镜像: {url.split('/')[2]}")
                result = await self._process_zip_manifest_generic(
                    app_id, url, f"GitHub/{repo}(mirror)", unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key
                )
                if result:
                    self.log.info(f"[Web兜底] 镜像成功: {url.split('/')[2]}")
                    return True
        return result

    async def fetch_branch_info(self, url: str, headers: Dict) -> Dict | None:
        try:
            r = await self.client.get(url, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.log.error("GitHub API请求次数已用尽。")
                self._github_api_exhausted = True  # 标记 API 已耗尽
            elif e.response.status_code != 404: self.log.error(f"从 {url} 获取信息失败: {self.stack_error(e)}")
            return None
        except Exception as e:
            self.log.error(f'从 {url} 获取信息时发生意外错误: {self.stack_error(e)}')
            return None
            
    # MODIFIED: Updated to use all github repos including custom ones
    async def search_all_repos_for_appid(self, app_id: str, repos: List[str] = None) -> List[Dict]:
        """Search for app_id in all GitHub repositories (builtin + custom)"""
        if repos is None:
            repos = self.get_all_github_repos()
        
        github_token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        tasks = [self._search_single_repo(app_id, repo, headers) for repo in repos]
        results = await asyncio.gather(*tasks)
        return [res for res in results if res]

    async def _search_single_repo(self, app_id: str, repo: str, headers: Dict) -> Dict | None:
        self.log.info(f"正在仓库 {repo} 中搜索 AppID: {app_id}")
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await self.fetch_branch_info(url, headers)
        if r_json and 'commit' in r_json:
            tree_url = r_json['commit']['commit']['tree']['url']
            r2_json = await self.fetch_branch_info(tree_url, headers)
            if r2_json and 'tree' in r2_json:
                self.log.info(f"在 {repo} 中找到清单。")
                return {'repo': repo, 'sha': r_json['commit']['sha'], 'tree': r2_json['tree'], 'update_date': r_json["commit"]["commit"]["author"]["date"]}
        return None

    # MODIFIED: Added patch_depot_key parameter
    async def process_github_manifest(self, app_id: str, repo: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool = False) -> bool:
        github_token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        
        # 如果本次会话已知 API 耗尽，直接走 web 兜底
        if getattr(self, '_github_api_exhausted', False):
            self.log.warning(f"GitHub API 已耗尽，直接使用 Web 兜底下载 {repo}/{app_id}")
            return await self._fetch_branch_via_web(app_id, repo, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await self.fetch_branch_info(url, headers)
        if not (r_json and 'commit' in r_json):
            # API 耗尽时 fallback
            if getattr(self, '_github_api_exhausted', False):
                self.log.warning(f"API 耗尽，切换到 Web 兜底下载 {repo}/{app_id}")
                return await self._fetch_branch_via_web(app_id, repo, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
            self.log.error(f'无法获取 {repo} 中 {app_id} 的分支信息。如果该清单在此仓库中不存在，这是正常现象。')
            return False
        
        sha, tree_url = r_json['commit']['sha'], r_json['commit']['commit']['tree']['url']
        r2_json = await self.fetch_branch_info(tree_url, headers)
        if not (r2_json and 'tree' in r2_json):
            self.log.error(f'无法获取 {repo} 中 {app_id} 的文件列表。')
            return False
            
        all_files_in_tree = r2_json.get('tree', [])
        files_to_download = all_files_in_tree[:]
        
        if unlocker_type == "steamtools" and use_st_auto_update:
            files_to_download = [item for item in all_files_in_tree if not item['path'].endswith('.manifest')]
        
        if not files_to_download and all_files_in_tree: self.log.info("没有需要下载的文件（可能是因为自动更新模式跳过了所有文件）。")
        if not all_files_in_tree:
            self.log.warning(f"仓库 {repo} 的分支 {app_id} 为空。")
            return True

        try:
            downloaded_files = {}
            if files_to_download:
                tasks = [self._get_from_mirrors(sha, item['path'], repo) for item in files_to_download]
                downloaded_contents = await asyncio.gather(*tasks)
                downloaded_files = {item['path']: content for item, content in zip(files_to_download, downloaded_contents)}
        except Exception as e:
            self.log.error(f"下载文件失败，正在中止对 {app_id} 的处理: {e}")
            return False
        
        all_manifest_paths_in_tree = [item['path'] for item in all_files_in_tree if item['path'].endswith('.manifest')]
        downloaded_manifest_paths = [p for p in downloaded_files if p.endswith('.manifest')]
        key_vdf_path = next((p for p in downloaded_files if "key.vdf" in p.lower()), None)
        all_depots = {}
        if key_vdf_path:
            try:
                depots_config = vdf.loads(downloaded_files[key_vdf_path].decode('utf-8'))
                all_depots = depots_config.get('depots', {})
            except Exception as e: self.log.error(f"解析 key.vdf 失败: {e}")

        if unlocker_type == "steamtools":
            self.log.info(f"SteamTools 自动更新模式: {'已启用' if use_st_auto_update else '已禁用'}")
            stplug_path = self.steam_path / 'config' / 'stplug-in'
            lua_filename = f"{app_id}.lua"
            lua_filepath = stplug_path / lua_filename
            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write(f'addappid({app_id})\n')
                for depot_id, info in all_depots.items():
                    key = info.get("DecryptionKey", "")
                    await lua_file.write(f'addappid({depot_id}, 1, "{key}")\n')
                for manifest_file_path in all_manifest_paths_in_tree:
                    match = re.search(r'(\d+)_(\w+)\.manifest', Path(manifest_file_path).name)
                    if match:
                        line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                        if use_st_auto_update: await lua_file.write('--' + line)
                        else: await lua_file.write(line)
            self.log.info(f"已为 SteamTools 生成解锁文件: {app_id}.lua")
            
            if add_all_dlc:
                await self._add_free_dlcs_to_lua(app_id, lua_filepath)

            # NEW: Apply depotkey patch if requested
            if patch_depot_key:
                self.log.info("开始修补创意工坊depotkey...")
                await self.patch_lua_with_depotkey(app_id, lua_filepath)

        else:
            self.log.info("检测到 GreenLuma/标准模式，将复制 .manifest 文件到 depotcache。")
            if not downloaded_manifest_paths:
                self.log.error("GreenLuma 模式需要 .manifest 文件，但未能找到或下载。")
                return False
            
            depot_cache_path = self.steam_path / 'depotcache'
            for path in downloaded_manifest_paths:
                filename = Path(path).name
                (depot_cache_path / filename).write_bytes(downloaded_files[path])
                self.log.info(f"已为 GreenLuma 保存清单: {filename}")
            
            if all_depots:
                await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})
                gl_ids = list(all_depots.keys())
                gl_ids.append(app_id)
                await self.greenluma_add(list(set(gl_ids)))
                self.log.info("已合并密钥并添加到GreenLuma。")

        self.log.info(f'清单最后更新时间: {r_json["commit"]["commit"]["author"]["date"]}')
        return True
    
    def extract_app_id(self, user_input: str) -> str | None:
        match = re.search(r"/app/(\d+)", user_input) or re.search(r"steamdb\.info/app/(\d+)", user_input)
        if match: return match.group(1)
        return user_input if user_input.isdigit() else None

    async def find_appid_by_name(self, game_name: str, lang: str = "schinese") -> List[Dict]:

        # 备用：CaiGames API
        try:
            r = await self.client.get(
                "https://api.9178666.xyz/search",
                params={'term': game_name},
                headers={
                    "X-Client-Auth": "CaiGames-pvzcxw",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                },
                timeout=20
            )
            if r.status_code != 403:
                r.raise_for_status()
                resp_json = r.json()
                raw_data = resp_json.get("data", []) if isinstance(resp_json, dict) and (resp_json.get("status") == "ok" or "data" in resp_json) else []
                results = [{'appid': str(i.get('appid')), 'name': i.get('name'), 'header_image': i.get('image')} for i in raw_data if i.get('appid') and i.get('name')]
                if results:
                    self.log.info(f"CaiGames API 成功找到 {len(results)} 个匹配结果")
                    return results
            else:
                self.log.warning("CaiGames API 返回 403，切换到 Steam 搜索")
        except Exception as e:
            self.log.warning(f"CaiGames API 搜索失败，切换到 Steam 搜索: {e}")

        # 备用：Steam 商店搜索
        try:
            import urllib.parse, re
            encoded_game_name = urllib.parse.quote(game_name)
            search_url = f"https://store.steampowered.com/search/?term={encoded_game_name}&supportedlang={lang}&ndl=1"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            r = await self.client.get(search_url, headers=headers, timeout=30)
            if r.status_code != 200:
                self.log.warning(f"Steam 搜索请求失败，状态码: {r.status_code}")
                return []
            game_pattern = re.compile(r'<a href="https://store\.steampowered\.com/app/(\d+)/[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
            games_list = []
            for appid, content in game_pattern.findall(r.text):
                name_match = re.search(r'<span class="title">(.*?)</span>', content)
                if name_match:
                    games_list.append({
                        'appid': appid,
                        'name': name_match.group(1).strip(),
                        'header_image': f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
                    })
                    if len(games_list) >= 20:
                        break
            if games_list:
                self.log.info(f"Steam 搜索成功找到 {len(games_list)} 个匹配结果")
                return games_list
            self.log.warning("未找到相关游戏。")
        except Exception as e:
            self.log.error(f"搜索游戏 '{game_name}' 失败: {self.stack_error(e)}")

        return []

    async def get_game_info_by_appid(self, appid: str) -> Dict:
        """通过AppID获取游戏详细信息，使用steamCMD信息代理"""
        try:
            self.log.info(f"正在获取游戏详细信息: AppID {appid}")
            
            # 使用steamCMD信息代理
            r = await self.client.get(
                f"https://api.9178666.xyz/cmd/{appid}",
                headers={
                    "X-Client-Auth": "CaiGames-pvzcxw",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                },
                timeout=20
            )
            
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and "data" in data:
                    game_data = data["data"]
                    return {
                        "appid": appid,
                        "name": game_data.get("name", ""),
                        "header_image": game_data.get("header_image", f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"),
                        "description": game_data.get("short_description", ""),
                        "price": game_data.get("price_overview", {}).get("final_formatted", ""),
                        "release_date": game_data.get("release_date", {}).get("date", ""),
                        "platforms": game_data.get("platforms", {}),
                        "metacritic": game_data.get("metacritic", {}).get("score", 0)
                    }
            
            self.log.warning(f"无法通过API获取游戏 {appid} 的详细信息")
            return {"appid": appid, "name": "", "header_image": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"}
            
        except Exception as e:
            self.log.error(f"获取游戏 {appid} 信息失败: {e}")
            return {"appid": appid, "name": "", "header_image": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"}

    async def get_game_dlcs(self, appid: str) -> List[Dict]:
        """获取游戏的DLC列表，使用steam DLC列表代理"""
        try:
            self.log.info(f"正在获取游戏 DLC 列表: AppID {appid}")
            
            # 使用steam DLC列表代理
            r = await self.client.get(
                f"https://api.9178666.xyz/dlcs/{appid}",
                headers={
                    "X-Client-Auth": "CaiGames-pvzcxw",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                },
                timeout=20
            )
            
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and "data" in data:
                    dlc_list = data["data"]
                    return [{
                        "appid": str(dlc.get("appid", "")),
                        "name": dlc.get("name", ""),
                        "price": dlc.get("price_overview", {}).get("final_formatted", "免费")
                    } for dlc in dlc_list if dlc.get("appid")]
            
            self.log.warning(f"无法通过API获取游戏 {appid} 的DLC列表")
            return []
            
        except Exception as e:
            self.log.error(f"获取游戏 {appid} DLC列表失败: {e}")
            return []

    async def check_steam_status(self) -> Dict:
        """检查Steam服务器状态"""
        try:
            self.log.info("正在检查Steam服务器状态")
            
            r = await self.client.get(
                "https://api.9178666.xyz",
                headers={
                    "X-Client-Auth": "CaiGames-pvzcxw",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                },
                timeout=10
            )
            
            if r.status_code == 200:
                return {"status": "online", "message": "Steam服务器正常运行"}
            else:
                return {"status": "offline", "message": "Steam服务器暂时不可用"}
                
        except Exception as e:
            self.log.error(f"检查Steam服务器状态失败: {e}")
            return {"status": "error", "message": f"检查失败: {str(e)}"}

    async def cleanup_temp_files(self):
        try:
            if self.temp_path.exists():
                shutil.rmtree(self.temp_path)
                self.log.info('临时文件已清理。')
        except Exception as e:
            self.log.error(f'清理临时文件失败: {self.stack_error(e)}')

    async def migrate(self, st_use: bool):
        directory = self.steam_path / "config" / "stplug-in"
        if st_use and directory.exists():
            self.log.info('检测到SteamTools, 正在检查是否有旧文件需要迁移...')
            for file in directory.glob("Cai_unlock_*.lua"):
                new_filename = directory / file.name.replace("Cai_unlock_", "")
                try:
                    file.rename(new_filename)
                    self.log.info(f'已重命名: {file.name} -> {new_filename.name}')
                except Exception as e:
                    self.log.error(f'重命名失败 {file.name}: {e}')

    # ==================== Steam 加速 ====================

    # 参考 SteamTools Hosts 模式，将 Steam 关键域名指向国内可用 IP
    STEAM_HOSTS_MAP = {
        "store.steampowered.com":    "23.52.12.176",
        "api.steampowered.com":      "23.52.12.176",
        "steamcommunity.com":        "23.52.12.176",
        "www.steamcommunity.com":    "23.52.12.176",
        "cdn.steamcommunity.com":    "23.52.12.176",
        "steamcdn-a.akamaihd.net":   "23.52.12.176",
        "media.steampowered.com":    "23.52.12.176",
        "cs.steampowered.com":       "23.52.12.176",
        "login.steampowered.com":    "23.52.12.176",
        "help.steampowered.com":     "23.52.12.176",
        "partner.steamgames.com":    "23.52.12.176",
        "steambroadcast.akamaized.net": "23.52.12.176",
    }
    HOSTS_MARK_BEGIN = "# >>> Cai-Install Steam Accelerate Begin <<<"
    HOSTS_MARK_END   = "# >>> Cai-Install Steam Accelerate End <<<"
    HOSTS_PATH = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "drivers" / "etc" / "hosts"

    def _get_hosts_content(self) -> str:
        try:
            return self.HOSTS_PATH.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self.HOSTS_PATH.read_text(encoding="gbk")

    def get_accelerate_status(self) -> bool:
        """检查加速是否已启用（hosts 中是否有我们的标记）"""
        try:
            return self.HOSTS_MARK_BEGIN in self._get_hosts_content()
        except Exception:
            return False

    def enable_steam_accelerate(self) -> Dict:
        """向 hosts 写入 Steam 加速条目（需要管理员权限）"""
        try:
            content = self._get_hosts_content()
            # 先清理旧条目
            content = self._remove_accelerate_block(content)
            block_lines = [self.HOSTS_MARK_BEGIN]
            for domain, ip in self.STEAM_HOSTS_MAP.items():
                block_lines.append(f"{ip}  {domain}")
            block_lines.append(self.HOSTS_MARK_END)
            new_content = content.rstrip("\n") + "\n" + "\n".join(block_lines) + "\n"
            self.HOSTS_PATH.write_text(new_content, encoding="utf-8")
            return {"success": True}
        except PermissionError:
            return {"success": False, "error": "permission_denied"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disable_steam_accelerate(self) -> Dict:
        """从 hosts 移除 Steam 加速条目"""
        try:
            content = self._get_hosts_content()
            new_content = self._remove_accelerate_block(content)
            self.HOSTS_PATH.write_text(new_content, encoding="utf-8")
            return {"success": True}
        except PermissionError:
            return {"success": False, "error": "permission_denied"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _remove_accelerate_block(self, content: str) -> str:
        lines = content.splitlines()
        out, skip = [], False
        for line in lines:
            if line.strip() == self.HOSTS_MARK_BEGIN:
                skip = True
                continue
            if line.strip() == self.HOSTS_MARK_END:
                skip = False
                continue
            if not skip:
                out.append(line)
        # 去掉末尾多余空行
        while out and out[-1].strip() == "":
            out.pop()
        return "\n".join(out) + "\n" if out else ""

    def is_admin(self) -> bool:
        """检查当前进程是否有管理员权限"""
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def run_as_admin_to_toggle_accelerate(self, enable: bool) -> Dict:
        """以管理员权限重新运行自身来修改 hosts"""
        try:
            import ctypes
            script = self.project_root / "_hosts_helper.py"
            action = "enable" if enable else "disable"
            helper_code = f"""
import sys, os
from pathlib import Path
sys.path.insert(0, r"{self.project_root}")
from backend import CaiBackend
b = CaiBackend()
result = b.{"enable_steam_accelerate" if enable else "disable_steam_accelerate"}()
print("OK" if result["success"] else result.get("error","fail"))
"""
            script.write_text(helper_code, encoding="utf-8")
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}"', None, 0
            )
            script.unlink(missing_ok=True)
            return {"success": ret > 32}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _update_lua_for_fixed_version(self, app_id: str, depots: List[Dict]):
        """在固定版本模式下，更新 lua 文件添加 setManifestid 行"""
        try:
            if not self.steam_path:
                return
            
            lua_filename = f"{app_id}.lua"
            lua_path = self.steam_path / 'config' / 'stplug-in' / lua_filename
            
            # 如果 lua 文件不存在，跳过
            if not lua_path.exists():
                self.log.info(f"[固定版本] lua 文件不存在，跳过: {lua_filename}")
                return
            
            # 读取现有内容
            async with aiofiles.open(lua_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # 检查是否已经是固定版本模式
            is_currently_fixed = bool(re.search(r'^\s*setManifestid\(', content, re.MULTILINE))
            
            # 生成新的 setManifestid 行
            manifest_lines = []
            for depot in depots:
                depot_id = str(depot.get('depotid', '')).strip()
                manifest_id = str(depot.get('manifestid', '')).strip()
                if depot_id.isdigit() and manifest_id:
                    manifest_lines.append(f'setManifestid({depot_id}, "{manifest_id}")')
            
            if not manifest_lines:
                self.log.warning(f"[固定版本] 没有有效的 manifest 配置可添加")
                return
            
            if is_currently_fixed:
                # 已经是固定版本，替换现有的 setManifestid 行
                # 先移除旧的 setManifestid 行（包括注释掉的）
                content = re.sub(r'^\s*--?\s*setManifestid\([^\n]*\n', '', content, flags=re.MULTILINE)
                self.log.info(f"[固定版本] 更新现有 lua 文件的 setManifestid 配置: {lua_filename}")
            else:
                # 从自动更新模式切换到固定版本
                # 注释掉现有的 setManifestid 行（如果有的话）
                content = re.sub(r'(^\s*)setManifestid\(', r'\1--setManifestid(', content, flags=re.MULTILINE)
                self.log.info(f"[固定版本] 为 lua 文件添加 setManifestid 配置: {lua_filename}")
            
            # 移除文件末尾的空白行和固定版本注释块
            content = content.rstrip()
            content = re.sub(r'\n*-- Fixed Manifests \(Generated\)[^\n]*\n*', '\n', content)
            
            # 添加新的 setManifestid 行
            new_content = content + "\n\n-- Fixed Manifests (Generated)\n" + "\n".join(manifest_lines) + "\n"
            
            # 写回文件
            async with aiofiles.open(lua_path, 'w', encoding='utf-8') as f:
                await f.write(new_content)
            
            self.log.info(f"[固定版本] 已更新 {lua_filename}，添加了 {len(manifest_lines)} 个 manifest 配置")
            
        except Exception as e:
            self.log.error(f"[固定版本] 更新 lua 文件失败: {e}")

    async def complete_manifest_files(self, app_id: str, progress_callback=None, cancel_check=None) -> Dict:
        """主入库成功后的补全清单文件步骤：按 depot API 补全下载 manifest。"""

        def _report(progress: int, text: str = ""):
            if callable(progress_callback):
                try:
                    progress_callback(max(0, min(100, int(progress))), text)
                except Exception:
                    pass

        def _is_cancelled() -> bool:
            if callable(cancel_check):
                try:
                    return bool(cancel_check())
                except Exception:
                    return False
            return False

        try:
            if not self.steam_path:
                return {"success": False, "message": "Steam 路径未初始化", "downloaded": 0, "total": 0}

            if _is_cancelled():
                return {"success": False, "cancelled": True, "message": "任务已取消", "downloaded": 0, "total": 0}

            self.log.info(f"[补全清单文件] 开始补全 AppID {app_id} 的 manifest 文件...")
            _report(5, "补全清单文件：准备阶段（读取 Depot 列表）")

            # ================== 修改部分开始 ==================
            depots = []
            try:
                # 优先使用我们统一的底层方法（带 Token 和 SteamCMD 官方链路解析）获取最全列表
                depot_map = await self._get_depots_and_manifests(app_id)
                if depot_map:
                    depots = [{"depotid": k, "manifestid": v} for k, v in depot_map.items()]
            except Exception as e:
                self.log.warning(f"[补全清单文件] 获取统一下发清单失败，准备降级使用 manifest.steam.run: {e}")

            # 如果统一获取失败，再退回原来的 manifest.steam.run 老 API
            if not depots:
                api_url = f"https://manifest.steam.run/api/depot/{app_id}"
                response = await self.http_get_safe(
                    api_url,
                    timeout=max(20, self.config.get("download_timeout", 30)),
                    max_retries=3
                )
                if not response:
                    msg = "补全清单文件失败：无法获取 depot 列表"
                    self.log.error(f"[补全清单文件] {msg} ({api_url})")
                    return {"success": False, "message": msg, "downloaded": 0, "total": 0}

                try:
                    payload = response.json()
                    depots = payload.get("depots", []) if isinstance(payload, dict) else []
                except Exception as e:
                    msg = f"补全清单文件失败：Depot API JSON 解析失败: {e}"
                    self.log.error(f"[补全清单文件] {msg}")
                    return {"success": False, "message": msg, "downloaded": 0, "total": 0}

            if not depots:
                msg = "补全清单文件失败：Depot 列表为空"
                self.log.warning(f"[补全清单文件] {msg}")
                return {"success": False, "message": msg, "downloaded": 0, "total": 0}
            # ================== 修改部分结束 ==================

            self.log.info(f"[补全清单文件] 获取到 {len(depots)} 个 depots，开始镜像测速与下载")
            _report(15, f"补全清单文件：识别镜像源（共 {len(depots)} 个文件）")

            raw_base = "https://raw.githubusercontent.com/qwe213312/k25FCdfEOoEJ42S6/main"
            mirrors = [
                "https://ghfast.top/",
                "https://ghproxy.net/",
                "https://ghp.ci/",
                "https://gh-proxy.com/",
                ""
            ]

            first = depots[0]
            first_name = f"{first.get('depotid')}_{first.get('manifestid')}.manifest"
            first_url = f"{raw_base}/{first_name}"
            self.log.info(f"[补全清单文件] 测试第一个 manifest 文件的镜像可用性: {first_url}")

            scored = []
            for prefix in mirrors:
                test_url = f"{prefix}{first_url}" if prefix else first_url
                started = time.perf_counter()
                try:
                    r = await self.client.get(test_url, timeout=12)
                    if r.status_code == 200 and r.content:
                        cost = time.perf_counter() - started
                        scored.append((cost, prefix))
                        self.log.info(f"[补全清单文件] 镜像可用: {test_url.split('/')[2] if '://' in test_url else 'direct'} ({cost:.2f}s)")
                except Exception:
                    pass

            if scored:
                scored.sort(key=lambda x: x[0])
                ordered_mirrors = [p for _, p in scored]
                for p in mirrors:
                    if p not in ordered_mirrors:
                        ordered_mirrors.append(p)
            else:
                ordered_mirrors = mirrors
                self.log.warning("[补全清单文件] 镜像测速未命中，按默认顺序尝试")

            depotcache = self.steam_path / 'depotcache'
            depotcache.mkdir(parents=True, exist_ok=True)
            config_depotcache = self.steam_path / 'config' / 'depotcache'
            config_depotcache.mkdir(parents=True, exist_ok=True)

            downloaded = 0
            total = len(depots)
            downloaded_names = []
            failed_names = []
            max_file_retries = 3
            method2_max_retries = 2
            method2_success_count = 0
            manifest_api_key = str(self.config.get("ManifestAPIKey", "") or "").strip()
            if not manifest_api_key:
                legacy_keys = ["ManifestKey", "manifest_api_key", "manifestKey", "manifest_apiKey"]
                for key_name in legacy_keys:
                    legacy_value = str(self.config.get(key_name, "") or "").strip()
                    if legacy_value:
                        manifest_api_key = legacy_value
                        self.log.info(f"[补全清单文件] 检测到兼容配置键: {key_name}")
                        break

            def _rollback_downloaded_files():
                for name in downloaded_names:
                    for folder in (depotcache, config_depotcache):
                        try:
                            target = folder / name
                            if target.exists() and target.is_file():
                                os.remove(target)
                        except Exception as cleanup_error:
                            self.log.warning(f"[补全清单文件] 回滚删除失败 {name}: {cleanup_error}")

            for index, depot in enumerate(depots, start=1):
                if _is_cancelled():
                    _rollback_downloaded_files()
                    msg = f"补全清单文件已取消：已回滚本次下载文件（{downloaded}/{total}）"
                    self.log.warning(f"[补全清单文件] {msg}")
                    return {
                        "success": False,
                        "cancelled": True,
                        "message": msg,
                        "downloaded": downloaded,
                        "total": total
                    }

                depot_id = str(depot.get('depotid', '')).strip()
                manifest_id = str(depot.get('manifestid', '')).strip()

                if not depot_id.isdigit() or not manifest_id:
                    failed_names.append(str(depot))
                    self.log.warning(f"[补全清单文件] 跳过无效 depot 项: {depot}")
                    continue

                filename = f"{depot_id}_{manifest_id}.manifest"
                raw_url = f"{raw_base}/{filename}"
                file_base_progress = 20 + int((index - 1) / max(total, 1) * 70)
                _report(file_base_progress, f"补全清单文件 {index}/{total}：方法1（镜像源）{filename}")

                content = None
                used_url = None
                for attempt in range(1, max_file_retries + 1):
                    if _is_cancelled():
                        break

                    _report(
                        min(92, file_base_progress + 6),
                        f"补全清单文件 {index}/{total}：方法1第 {attempt}/{max_file_retries} 次尝试"
                    )
                    for prefix in ordered_mirrors:
                        url = f"{prefix}{raw_url}" if prefix else raw_url
                        try:
                            r = await self.client.get(url, timeout=max(20, self.config.get("download_timeout", 30)))
                            if r.status_code == 200 and r.content:
                                content = r.content
                                used_url = url
                                break
                        except Exception:
                            continue

                    if content:
                        break

                    self.log.warning(f"[补全清单文件] 文件 {filename} 第 {attempt}/{max_file_retries} 次尝试失败")
                    if attempt < max_file_retries:
                        await asyncio.sleep(1.2 * attempt)

                if _is_cancelled():
                    _rollback_downloaded_files()
                    msg = f"补全清单文件已取消：已回滚本次下载文件（{downloaded}/{total}）"
                    self.log.warning(f"[补全清单文件] {msg}")
                    return {
                        "success": False,
                        "cancelled": True,
                        "message": msg,
                        "downloaded": downloaded,
                        "total": total
                    }

                # 方法1失败后走方法2 API
                # 方法1失败后走方法2 API
                if not content:
                    if not manifest_api_key:
                        self.log.warning(f"[补全清单文件] 方法2不可用（未配置 ManifestAPIKey）: {filename}")
                        # 方法3：直接使用GitHub API下载器（N+1）
                        _report(
                            min(95, file_base_progress + 10),
                            f"补全清单文件 {index}/{total}：方法3（GitHub API）"
                        )
                        self.log.info(f"[补全清单文件] 尝试方法3（GitHub API）下载: {filename}")
                        
                        # 使用GitHub API下载整个AppID的清单
                        method3_success = await self._download_single_manifest_via_github_api(app_id, depot_id, manifest_id, filename)
                        if method3_success:
                            content = method3_success
                            used_url = f"GitHub API (AppID: {app_id})"
                            self.log.info(f"[补全清单文件] 方法3下载成功: {filename}")
                    else:
                        for api_attempt in range(1, method2_max_retries + 1):
                            if _is_cancelled():
                                break

                            method2_url = (
                                "https://api.manifesthub1.filegear-sg.me/manifest"
                                f"?apikey={quote(manifest_api_key, safe='')}&depotid={depot_id}&manifestid={manifest_id}"
                            )
                            _report(
                                min(95, file_base_progress + 10),
                                f"补全清单文件 {index}/{total}：方法2（API）第 {api_attempt}/{method2_max_retries} 次尝试"
                            )
                            try:
                                r2 = await self.client.get(method2_url, timeout=max(20, self.config.get("download_timeout", 30)))
                                if r2.status_code == 200 and r2.content:
                                    content = r2.content
                                    used_url = method2_url
                                    method2_success_count += 1
                                    self.log.info(f"[补全清单文件] 方法2下载成功: {filename}")
                                    break
                            except Exception as method2_error:
                                self.log.warning(f"[补全清单文件] 方法2请求异常 {filename}: {method2_error}")

                            if api_attempt < method2_max_retries:
                                await asyncio.sleep(1.0 * api_attempt)

                if not content:
                    failed_names.append(filename)
                    self.log.error(f"[补全清单文件] 下载失败: {filename}（方法1/方法2/方法3重试后仍失败）")
                    continue

                (depotcache / filename).write_bytes(content)
                (config_depotcache / filename).write_bytes(content)
                downloaded += 1
                downloaded_names.append(filename)
                self.log.info(f"[补全清单文件] 已保存: {filename} -> {depotcache} / {config_depotcache} (来源: {used_url})")

            # 必须全量成功：只要有失败就回滚本次已下载文件并判定失败
            if failed_names or downloaded != total:
                _report(96, "补全清单文件：校验失败，正在回滚已下载文件")
                _rollback_downloaded_files()

                msg = f"补全清单文件失败：仅完成 {downloaded}/{total}，已回滚本次下载文件"
                self.log.error(f"[补全清单文件] {msg}，失败项: {failed_names}")
                return {
                    "success": False,
                    "message": msg,
                    "downloaded": downloaded,
                    "total": total,
                    "failed": failed_names
                }

            # 记录下载的 manifest
            if downloaded_names:
                self._record_manifests_for_app(str(app_id), downloaded_names)

            # 如果启用了 SteamTools 固定版本模式，更新 lua 文件添加 setManifestid 配置
            is_st_fixed_version = self.config.get("ST_Fixed_Version", False)
            if is_st_fixed_version and downloaded_names:
                await self._update_lua_for_fixed_version(app_id, depots)

            _report(100, f"游戏入库成功：{downloaded}/{total}（方法2命中 {method2_success_count}）")
            self.log.info(f"[补全清单文件] 完成，成功 {downloaded}/{total}")
            return {
                "success": True,
                "message": f"游戏入库成功：成功 {downloaded}/{total}",
                "downloaded": downloaded,
                "total": total,
                "failed": failed_names,
                "method2_used": method2_success_count
            }

        except Exception as e:
            msg = f"补全清单文件异常: {e}"
            self.log.error(f"[补全清单文件] {self.stack_error(e)}")
            return {"success": False, "message": msg, "downloaded": 0, "total": 0}

    async def sync_manifests_after_download(self, app_id: str, progress_callback=None, cancel_check=None) -> Dict:
        """兼容旧调用名：转发到补全清单文件流程。"""
        return await self.complete_manifest_files(app_id, progress_callback=progress_callback, cancel_check=cancel_check)