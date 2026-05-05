"""
Cai Install - Fluent Design 版本
使用 PyQt-Fluent-Widgets 框架
"""
import sys
import os
import asyncio
import logging
import json
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QUrl, QLocale, QTranslator, QObject, QTimer, QPoint, QRect
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QDialog
from PyQt6.QtGui import QIntValidator
from PyQt6.QtGui import QIcon, QPixmap, QFont, QDesktopServices
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6 import sip
from qfluentwidgets import (
    FluentIcon, NavigationItemPosition, MessageBox,
    setTheme, Theme, setThemeColor, isDarkTheme,
    MSFluentWindow, NavigationAvatarWidget,
    SubtitleLabel, BodyLabel, PushButton, LineEdit,
    ComboBox, SwitchButton, ProgressRing, InfoBar,
    InfoBarPosition, CardWidget, ScrollArea, CaptionLabel,
    TransparentToolButton, IconWidget, FlowLayout, SearchLineEdit,
    PrimaryPushButton, CheckBox, GroupHeaderCardWidget, InfoBarIcon,
    SpinBox, HyperlinkButton, MessageBoxBase, TitleLabel,
    RoundMenu, Action, TextEdit, SingleDirectionScrollArea, ProgressBar, ToolTipFilter, ToolTipPosition,
    Slider, SegmentedWidget, SmoothMode, AvatarWidget
)

# 项目根目录（兼容直接运行和 PyInstaller 打包）
def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，exe 所在目录
        return Path(sys.executable).parent
    # 开发模式，以本文件所在目录为根
    return Path(__file__).resolve().parent.parent

APP_ROOT = _get_app_root()

# 导入后端
from backend.cai_backend import CaiBackend, get_steam_lang, CURRENT_VERSION, GITHUB_REPO

import time as _time
# 模块级推荐缓存（进程内共享，避免切换页面重复请求）
_rec_cache: list = []
_rec_cache_ts: float = 0.0
_REC_CACHE_TTL = 3600  # 缓存有效期 1 小时

# 模块级封面图片缓存（进程内共享）
_cover_cache: dict = {}  # appid -> pixmap_data
_cover_cache_ts: dict = {}  # appid -> timestamp
_COVER_CACHE_TTL = 86400  # 封面缓存有效期 24 小时
_COVER_CACHE_MAX_SIZE = 500  # 最大缓存数量

# 磁盘缓存目录
_COVER_CACHE_DIR = APP_ROOT / "config" / "covers"
try:
    _COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # 如果无法创建缓存目录（权限问题等），回退到临时目录
    import tempfile
    _COVER_CACHE_DIR = Path(tempfile.gettempdir()) / "FluentInstall" / "covers"
    try:
        _COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # 如果还是无法创建，禁用磁盘缓存
        _COVER_CACHE_DIR = None

# 模块级游戏名称缓存（进程内共享）
_name_cache: dict = {}  # appid -> game_name
_name_cache_ts: dict = {}  # appid -> timestamp
_NAME_CACHE_TTL = 86400  # 名称缓存有效期 24 小时
_NAME_CACHE_MAX_SIZE = 1000  # 最大缓存数量

def _get_cached_name(appid: str) -> str:
    """获取缓存的游戏名称"""
    if appid in _name_cache:
        ts = _name_cache_ts.get(appid, 0)
        if (_time.time() - ts) < _NAME_CACHE_TTL:
            return _name_cache[appid]
        else:
            del _name_cache[appid]
            del _name_cache_ts[appid]
    return ""

def _cache_name(appid: str, name: str):
    """缓存游戏名称"""
    if len(_name_cache) >= _NAME_CACHE_MAX_SIZE:
        oldest_appid = min(_name_cache_ts, key=_name_cache_ts.get)
        del _name_cache[oldest_appid]
        del _name_cache_ts[oldest_appid]
    
    _name_cache[appid] = name
    _name_cache_ts[appid] = _time.time()

def _get_cached_cover(appid: str):
    """获取缓存的封面图片（先检查内存缓存，再检查磁盘缓存）"""
    # 先检查内存缓存
    if appid in _cover_cache:
        ts = _cover_cache_ts.get(appid, 0)
        if (_time.time() - ts) < _COVER_CACHE_TTL:
            return _cover_cache[appid]
        else:
            # 缓存过期，删除
            del _cover_cache[appid]
            del _cover_cache_ts[appid]
    
    # 检查磁盘缓存（如果磁盘缓存可用）
    if _COVER_CACHE_DIR is not None:
        cache_file = _COVER_CACHE_DIR / f"{appid}.jpg"
        if cache_file.exists():
            # 检查文件修改时间
            file_mtime = cache_file.stat().st_mtime
            if (_time.time() - file_mtime) < _COVER_CACHE_TTL:
                try:
                    with open(cache_file, 'rb') as f:
                        data = f.read()
                    # 同时加载到内存缓存
                    _cover_cache[appid] = data
                    _cover_cache_ts[appid] = _time.time()
                    return data
                except Exception:
                    pass
    
    return None

def _cache_cover(appid: str, data: bytes):
    """缓存封面图片（同时写入内存和磁盘）"""
    # 写入内存缓存
    if len(_cover_cache) >= _COVER_CACHE_MAX_SIZE:
        # 找到最早的缓存项
        oldest_appid = min(_cover_cache_ts, key=_cover_cache_ts.get)
        del _cover_cache[oldest_appid]
        del _cover_cache_ts[oldest_appid]
    
    _cover_cache[appid] = data
    _cover_cache_ts[appid] = _time.time()
    
    # 写入磁盘缓存（如果磁盘缓存可用）
    if _COVER_CACHE_DIR is not None:
        try:
            cache_file = _COVER_CACHE_DIR / f"{appid}.jpg"
            with open(cache_file, 'wb') as f:
                f.write(data)
        except Exception:
            pass


# 语言配置
LANGUAGES = {
    "zh_CN": {
        "name": "简体中文",
        "locale": QLocale(QLocale.Language.Chinese, QLocale.Country.China)
    },
    "en_US": {
        "name": "English",
        "locale": QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    },
    "zh_TW": {
        "name": "繁體中文",
        "locale": QLocale(QLocale.Language.Chinese, QLocale.Country.Taiwan)
    },
}

class QtLogHandler(QObject, logging.Handler):
    """将 logging 日志转发到 Qt 信号的 Handler"""
    log_record = pyqtSignal(str, str)  # (level, message)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        logging.Handler.__init__(self)
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_record.emit(record.levelname, msg)
        except Exception:
            pass

    def __exit__(self, *args):
        """阻止 with 语句自动释放，由 Python _python_exit() 统一释放"""
        pass


def load_theme_config():
    """加载主题配置"""
    try:
        config_path = APP_ROOT / 'config' / 'config.json'
        if config_path.exists():
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return {
                "theme_mode": config.get("theme_mode", "auto"),
                "theme_color": config.get("theme_color", "#0078d4")
            }
    except:
        pass
    return {"theme_mode": "auto", "theme_color": "#0078d4"}


def load_language_config():
    """加载语言配置"""
    try:
        config_path = APP_ROOT / 'config' / 'config.json'
        if config_path.exists():
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("language", "system")
    except:
        pass
    return "system"


# Simple text translation mapping
TEXTS = {
    "zh_CN": {
        "app_title": "流畅入库",
        "home": "主页",
        "search": "搜索入库",
        "settings": "设置",
        "default_page": "默认界面",
        "default_page_hint": "选择应用启动后显示的默认界面",
        "default_page_home": "主页",
        "default_page_search": "搜索入库",
        "restart_steam": "重启 Steam",
        "switch_steam_account": "Steam 换号",
        "installed_games": "已入库的游戏",
        "search_placeholder": "搜索游戏名称或 AppID",
        "loading": "加载中...",
        "no_games": "暂无游戏",
        "delete": "删除",
        "confirm_delete": "确认删除",
        "delete_message": "确定要删除 AppID {0} 吗？\n\n此操作不可撤销。",
        "deleting": "正在删除",
        "delete_success": "删除成功",
        "delete_failed": "删除失败",
        "search_and_add": "搜索并入库游戏",
        "game_name_or_appid": "输入游戏名称或 AppID / Steam 链接",
        "search_button": "搜索",
        "add_options": "入库选项",
        "add_all_dlc": "添加所有 DLC",
        "patch_depot_key": "修补 Depot Key",
        "patch_manifest": "修补 Manifest",
        "download_lua_only": "仅下载 Lua",
        "download_dlc_manifests": "下载 DLC 清单",
        "download_all_manifests": "下载所有清单 (Lua + DLC)",
        "manifest_source": "清单源:",
        "view_mode": "视图",
        "sort_mode": "排序",
        "view_list": "列表",
        "view_grid": "卡片",
        "sort_default": "默认",
        "sort_az": "A-Z",
        "sort_za": "Z-A",
        "add_game": "入库游戏",
        "steam_path": "Steam 路径",
        "steam_path_hint": "选择Steam安装路径，留空则自动检测",
        "github_token": "GitHub Personal Token",
        "github_token_hint": "可选，用于提高API请求限制",
        "basic_settings": "基本设置",
        "appearance": "外观",
        "theme_mode": "主题模式（重启生效）",
        "theme_color": "主题色",
        "language": "语言",
        "save_settings": "保存设置",
        "about": "关于",
        "thanks": "鸣谢",
        "restart_required": "需要重启",
        "language_changed": "语言已更改为 {0}\n\n是否立即重启应用以应用更改？",
        "theme_mode_changed": "主题模式已更改为 {0}\n\n是否立即重启应用以应用更改？",
        "theme_color_changed": "主题颜色已更改为 {0}\n\n是否立即重启应用以应用更改？",
        "restart_steam_confirm": "重启 Steam",
        "restart_steam_message": "确定要重启 Steam 吗？\n\n这将关闭当前运行的 Steam 并重新启动。",
        "restart_steam_select_account": "选择要切换的账号（可选）：",
        "restart_steam_no_switch": "不切换账号，仅重启",
        "switch_steam_account": "Steam 换号",
        "switch_account": "切换账号",
        "switch_account_title": "切换 Steam 账号",
        "switch_account_message": "请输入要切换到的 Steam 账号（用户名 或 用户名 密码）：",
        "switch_account_placeholder": "用户名 或 用户名 密码",
        "switching_account": "正在切换账号",
        "switching_account_message": "正在切换 Steam 账号，请稍候...",
        "switch_account_success": "切换账号成功",
        "switch_account_success_message": "Steam 账号已切换",
        "switch_account_failed": "切换账号失败",
        "switch_account_failed_message": "切换 Steam 账号失败，请检查账号信息",
        "switch_account_error_message": "切换账号时出错: {0}",
        "switch_account_select_message": "请选择要切换到的 Steam 账号：",
        "no_accounts_title": "未找到账号",
        "no_accounts_message": "未能从 loginusers.vdf 读取到已保存的 Steam 账号",
        "load_accounts_failed": "加载账号失败",
        "input_required": "输入不能为空",
        "account_required": "请输入 Steam 账号",
        "cancel": "取消",
        "confirm": "确定",
        "save": "保存",
        "steam_account_nav": "Steam 账号",
        "steam_account_manager": "Steam 账号管理",
        "refresh_accounts": "刷新账号列表",
        "toggle_view_mode": "切换视图模式",
        "no_note": "点击编辑备注",
        "current_account": "当前",
        "switch_to_this_account": "切换到该账号",
        "edit_note": "编辑备注",
        "edit_note_title": "编辑账号备注",
        "edit_note_message": "请输入该账号的备注信息：",
        "note_placeholder": "输入备注...",
        "note_saved": "备注已保存",
        "note_saved_message": "账号备注已成功保存",
        "switch_offline": "离线启动",
        "offline_mode": "离线模式",
        "online_mode": "在线模式",
        "more_actions": "更多操作",
        "delete_account": "删除账号",
        "confirm_delete_account": "确认删除账号",
        "delete_account_message": "确定要删除账号 {} 吗？\n\n这将从 Steam 中移除该账号的登录信息。",
        "delete_account_success": "删除成功",
        "delete_account_success_message": "账号已成功删除",
        "delete_account_failed": "删除失败",
        "delete_account_failed_message": "删除账号失败，请检查权限",
        "total_games": "共 {0} 个游戏 | SteamTools: {1} | GreenLuma: {2}",
        "load_failed": "加载失败: {0}",
        "reset_settings": "重置设置",
        "reset_settings_message": "确定要将所有设置重置为默认值吗？\n\n此操作不可撤销。",
        "reset_success": "重置成功",
        "reset_success_message": "配置已重置为默认值，请重新加载页面",
        "reset_failed": "重置失败",
        "restarting": "正在重启",
        "restarting_message": "正在重启 Steam，请稍候...",
        "restart_success": "重启成功",
        "restart_success_message": "Steam 已重启",
        "restart_failed": "重启失败",
        "restart_failed_message": "重启 Steam 失败，请手动重启",
        "restart_error_message": "重启 Steam 时出错: {0}",
        "application_config": "应用程序配置",
        "debug_mode": "调试模式",
        "debug_mode_hint": "启用详细的调试日志输出",
        "enable_debug_log": "启用详细的调试日志输出",
        "save_log_files": "保存日志文件",
        "save_logs_to_file": "将日志保存到文件中",
        "save_log_files_hint": "将日志保存到文件中",
        "unlocker_mode": "解锁工具模式",
        "auto_detect": "自动检测",
        "force_steamtools": "强制 SteamTools",
        "force_greenluma": "强制 GreenLuma",
        "force_opensteamtools": "强制 OpenSteamTools",
        "force_unlocker_hint": "强制使用指定的解锁工具",
        "download_timeout": "入库超时时间",
        "download_timeout_hint": "下载清单的超时时间（秒），网络较慢时可适当增大",
        "theme_mode_hint": "选择应用主题模式",
        "theme_color_hint": "选择主题颜色",
        "language_hint": "选择应用语言",
        "window_effect": "窗口特效",
        "window_effect_hint": "选择窗口背景特效",
        "effect_none": "无特效",
        "effect_mica": "云母 (Win11)",
        "smooth_scroll": "平滑滚动",
        "smooth_scroll_hint": "启用页面平滑滚动效果（关闭可减少卡顿）",
        "light_theme": "浅色",
        "dark_theme": "深色",
        "follow_system": "跟随系统",
        "default_blue": "默认蓝 (#0078d4)",
        "purple": "紫色 (#9b4dca)",
        "green": "绿色 (#10893e)",
        "orange": "橙色 (#ff8c00)",
        "red": "红色 (#e81123)",
        "pink": "粉色 (#e3008c)",
        "tip_source_fail": "提示: 如果某个源失败，请尝试其他源",
        "auto_select": "自动选择",
        "auto_search_github": "自动搜索GitHub",
        "sac-other": "sac分流 [废弃]",
        "walftech": "Walftech",
        "MHub": "MHub",
        "steamautocracks_v2": "SteamAutoCracks V2 (仅密钥) [废弃]",
        "sudama": "Sudama库 (仅密钥) [推荐]",
        "buqiuren": "清单不求人库 (仅清单)",
        "gmrc": "GMRC (仅清单)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_mau": "GitHub (MAU)",
        "github_mau": "GitHub (MAU)",
        "check_update": "检查更新",
        "checking": "检查中...",
        "update_available": "发现新版本",
        "current_version": "当前版本",
        "latest_version": "最新版本",
        "no_release_notes": "暂无更新说明",
        "go_to_download": "前往下载",
        "already_latest": "已是最新版本",
        "already_latest_content": "当前已是最新版本，无需更新。",
        "check_update_failed": "检查更新失败",
                "drm_page_title": "D加密授权器",
        "drm_step1": "步骤 1：获取授权文件",
        "drm_cw_file": "CW 文件",
        "drm_cw_file_hint": "选择本地 .cw 授权文件并解密",
        "drm_cw_placeholder": "选择 .cw 授权文件",
        "drm_browse": "浏览",
        "drm_decrypt": "解密",
        "drm_auth_code": "授权码",
        "drm_auth_code_hint": "通过授权码在线下载 CW 文件",
        "drm_auth_code_placeholder": "输入授权码",
        "drm_download_decrypt": "下载并解密",
        "drm_online_auth": "在线获取授权",
        "drm_online_auth_hint": "访问外部授权网站",
        "drm_extract_title": "获取 CW 文件（本地提取）",
        "drm_extract_hint": "需要已登录 Steam 且拥有该游戏",
        "drm_extract_placeholder": "输入游戏 AppID（当前账号必须拥有该游戏）",
        "drm_gen_authcode": "生成授权码",
        "drm_extract_cw": "本地提取 CW",
        "drm_info_title": "授权信息",
        "drm_valid_from": "生效时间",
        "drm_valid_to": "失效时间",
        "drm_step2": "步骤 2：GL 模式授权（SteamTools）",
        "drm_gl_hint": "将授权 ticket 写入 SteamTools 目录",
        "drm_gl_btn": "开始授权 (GL/SteamTools)",
        "drm_log": "日志",
        "drm_nav": "D加密",
        "drm_tip_select_cw": "请先选择 CW 文件",
        "drm_tip_enter_code": "请输入授权码",
        "drm_tip_decrypt_first": "请先解密 CW 文件",
        "drm_tip_valid_appid": "请输入有效的 AppID",
        "drm_missing_dep": "缺少依赖",
        "drm_missing_dep_hint": "请安装 pycryptodome: pip install pycryptodome",
        "drm_decrypt_failed": "解密失败",
        "drm_download_failed": "下载失败",
        "drm_auth_success": "授权成功",
        "drm_auth_failed": "授权失败","restart_steam_title": "重启 Steam",
        "restart_steam_confirm_message": "确定要重启 Steam 吗？\n\n这将关闭当前运行的 Steam 并重新启动。",
        
        # 缺失的翻译键
        "tip": "提示",
        "recognition_success": "识别成功",
        "game_not_found": "未找到匹配的游戏",
        "check_game_name": "请检查游戏名称或尝试使用 AppID",
        "search_failed": "搜索失败",
        "game_selected": "游戏已选择",
        "add_success": "入库成功",
        "add_success_content": "AppID {0} 已成功入库，重启 Steam 后生效",
        "adding_game": "正在入库游戏...",
        "please_wait_adding": "请稍候，正在处理入库操作",
        "process_failed": "处理失败",
        "check_logs": "请查看日志",
        "check_details": "处理失败，请查看详细信息或尝试其他清单源",
        "auto_detect_placeholder": "留空则自动检测",
        "token_placeholder": "可选，用于提高 API 请求限制",
        "load_config_failed": "加载配置失败",
        "save_success": "保存成功",
        "save_success_content": "配置已保存",
        "save_failed": "保存失败",
        "unknown_error": "未知错误",
        "data_process_failed": "处理数据失败",
        "please_wait": "Please wait",
        "unknown_game": "未知游戏",
        "reset_to_default": "重置为默认",
        "about_title": "关于",
        "thanks_title": "鸣谢",
        "about_text": "Cai Install - Fluent Design 版本\n\n版本: 1.7\n\n这是一个基于 PyQt6-Fluent-Widgets 的现代化 Steam 游戏解锁工具。\n\n功能特性:\n• Fluent Design 设计风格\n• 支持多种清单源\n• 游戏搜索和入库\n• 已入库游戏管理\n• 主题自定义\n\n项目地址: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "特别鸣谢\n\n开发者:\n• zhouchentao666 - 制作人员\n\n开源项目:\n• PyQt6 - Qt6 Python 绑定\n• PyQt-Fluent-Widgets - Fluent Design 组件库\n• Cai-install-Web-GUI - 原始项目作者\n• httpx - 异步 HTTP 客户端\n• Game-Cheats-Manager - 修改器数据来源 (https://github.com/dyang886/Game-Cheats-Manager)\n\n清单源提供:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• 清单不求人\n\n社区与联系:\n• GitHub: https://github.com/zhouchentao666/Fluent-Install\n• 加入 Q 群: https://qm.qq.com/q/gtTLap5Jw4\n• TG 群组: https://t.me/+vTrqXKpRJE9kNmVl\n• 感谢所有为本项目做出贡献的开发者和用户！",
        "donate": "捐赠",
        "donate_title": "支持开发者",
        "donate_desc": "如果本项目对你有帮助，欢迎请作者喝杯咖啡 ☕",
        "donate_wechat": "微信支付",
        "donate_alipay": "支付宝",
        "donate_loading": "加载中...",
        "donate_load_failed": "图片加载失败",
        "fixed_version": "固定版本",
        "auto_update": "自动更新",
        "toggle_version_mode": "切换版本模式",
        "st_settings": "SteamTools 设置",
        "st_settings_hint": "控制SteamTools文件的版本管理模式",
        "st_fixed_enable": "固定版本",
        "st_fixed_tooltip": "新添加的SteamTools文件默认使用固定版本模式",
        "st_fixed_manifest_mode": "固定版本Manifest修复",
        "st_fixed_manifest_mode_hint": "主页切换至固定版本时是否自动修复manifest",
        "st_fixed_manifest_always": "始终",
        "st_fixed_manifest_never": "从不",
        "st_fixed_manifest_ask": "询问",
        "patch_manifest_mode": "修补 Manifest",
        "patch_manifest_mode_hint": "入库后自动补全缺失的清单文件",
        "patch_manifest_always": "始终",
        "patch_manifest_never": "从不",
        "patch_manifest_ask": "询问",
        "patch_manifest_ask_hint": "是否补全缺失的清单文件？",
        "dlc_timeout": "DLC 联网超时时间",
        "dlc_timeout_hint": "获取DLC列表超时时间，网络较差时可适当调大（秒）",
        "show_progress_bar": "显示进度条",
        "show_progress_bar_hint": "在搜索和入库过程中显示进度条，提供更好的用户体验",
        "name_not_found": "名称未找到",
        "fetch_failed": "获取失败",
        
        # 内核检测相关
        "no_kernel_title": "未检测到解锁内核",
        "no_kernel_msg": "您还没有安装任何解锁内核，本软件目前支持以下三种内核，请您选择：",
        "auto_download": "自动下载",
        "manual_download": "手动下载",
        "force_kernel_select": "如果您已安装但未正确识别，可在此强制选择内核：",
        "force_apply": "强制使用",
        "ost_desc": "OpenSteamTools (推荐)",
        "st_desc": "SteamTools",
        "gl_desc": "GreenLuma (不推荐)",
        
        # 版本模式设置
        "st_settings": "版本模式设置",
        "st_settings_hint": "控制文件的版本管理模式（自动更新/固定版本）",
        "st_fixed_enable": "固定版本",
        "st_fixed_tooltip": "新添加的文件默认使用固定版本模式",
        "manifest_patch_source": "Manifest 修补库",
        "manifest_patch_source_hint": "用于固定版本模式缺失清单时的自动补全源",
        "patch_source_default": "默认 (Steam.run/GitHub)",
        "patch_source_gmrc": "GMRC",
        "patch_source_buqiuren": "清单不求人",
        
        # 通用
        "success": "成功",
        "failed": "失败",
        "install_success": "安装成功，请重启软件！",
        "download_failed": "下载失败",
        "launch_failed": "启动失败",
        "save_failed": "保存失败",
        
        "github_repos": "GitHub 仓库",
        "github_repos_desc": "添加自定义 GitHub 清单仓库",
        "zip_repos": "ZIP 清单库",
        "zip_repos_desc": "添加自定义 ZIP 清单下载地址",
        "add": "添加",
        "add_github_repo": "添加 GitHub 仓库",
        "add_zip_repo": "添加 ZIP 仓库",
        "repo_name": "显示名称",
        "repo_path": "仓库路径",
        "repo_url": "下载 URL",
        "repo_name_placeholder": "例如：我的自定义仓库",
        "github_repo_placeholder": "例如：username/repository",
        "zip_url_placeholder": "例如：https://example.com/download/{app_id}.zip",
        "github_repo_hint": "格式：用户名/仓库名，例如：Auiowu/ManifestAutoUpdate",
        "zip_url_hint": "URL 必须包含 {app_id} 占位符，程序会自动替换为实际的 AppID",
        "no_repos": "暂无配置的仓库",
        "repo_exists": "仓库已存在",
        "repo_already_added": "该仓库已被添加",
        "github_repo_added": "GitHub 仓库添加成功",
        "zip_repo_added": "ZIP 清单库添加成功",
        "input_incomplete": "输入不完整",
        "please_fill_all_fields": "请填写所有必填字段",
        "invalid_format": "格式不正确",
        "github_format_hint": "GitHub 仓库格式应为：用户名/仓库名",
        "zip_format_hint": "URL 必须包含 {app_id} 占位符",
        "save": "保存",
        "cancel": "取消",
    },
    "en_US": {
        "app_title": "FluentInstall",
        "home": "Home",
        "search": "Search",
        "settings": "Settings",
        "default_page": "Default Page",
        "default_page_hint": "Select the default page to display when the application starts",
        "default_page_home": "Home",
        "default_page_search": "Search Library",
        "restart_steam": "Restart Steam",
        "installed_games": "Installed Games",
        "search_placeholder": "Search game name or AppID",
        "loading": "Loading...",
        "no_games": "No games",
        "delete": "Delete",
        "confirm_delete": "Confirm Delete",
        "delete_message": "Are you sure you want to delete AppID {0}?\n\nThis action cannot be undone.",
        "deleting": "Deleting",
        "delete_success": "Delete Success",
        "delete_failed": "Delete Failed",
        "search_and_add": "Search and Add Games",
        "game_name_or_appid": "Enter game name or AppID / Steam link",
        "search_button": "Search",
        "add_options": "Add Options",
        "add_all_dlc": "Add All DLC",
        "patch_depot_key": "Patch Depot Key",
        "patch_manifest": "Patch Manifest",
        "download_lua_only": "Download Lua Only",
        "download_dlc_manifests": "Download DLC Manifests",
        "download_all_manifests": "Download All Manifests (Lua + DLC)",
        "manifest_source": "Manifest Source:",
        "add_game": "Add Game",
        "steam_path": "Steam Path",
        "github_token": "GitHub Personal Token",
        "appearance": "Appearance",
        "theme_mode": "Theme Mode",
        "theme_color": "Theme Color",
        "language": "Language",
        "save_settings": "Save Settings",
        "about": "About",
        "thanks": "Credits",
        "restart_required": "Restart Required",
        "language_changed": "Language changed to {0}\n\nRestart the application now to apply changes?",
        "theme_mode_changed": "Theme mode changed to {0}\n\nRestart the application now to apply changes?",
        "theme_color_changed": "Theme color changed to {0}\n\nRestart the application now to apply changes?",
        "restart_steam_confirm": "Restart Steam",
        "restart_steam_message": "Are you sure you want to restart Steam?\n\nThis will close the currently running Steam and restart it.",
        "restart_steam_select_account": "Select account to switch (optional):",
        "restart_steam_no_switch": "Don't switch, restart only",
        "switch_steam_account": "Switch Steam Account",
        "switch_account": "Switch Account",
        "switch_account_title": "Switch Steam Account",
        "switch_account_message": "Please enter the Steam account to switch to (username or username password):",
        "switch_account_placeholder": "username or username password",
        "switching_account": "Switching Account",
        "switching_account_message": "Switching Steam account, please wait...",
        "switch_account_success": "Account Switched",
        "switch_account_success_message": "Steam account has been switched",
        "switch_account_failed": "Switch Failed",
        "switch_account_failed_message": "Failed to switch Steam account, please check account info",
        "switch_account_error_message": "Error switching account: {0}",
        "switch_account_select_message": "Please select the Steam account to switch to:",
        "no_accounts_title": "No Accounts Found",
        "no_accounts_message": "No saved Steam accounts found in loginusers.vdf",
        "load_accounts_failed": "Failed to load accounts",
        "input_required": "Input Required",
        "account_required": "Please enter Steam account",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "save": "Save",
        "steam_account_nav": "Steam Accounts",
        "steam_account_manager": "Steam Account Manager",
        "refresh_accounts": "Refresh Account List",
        "toggle_view_mode": "Toggle View Mode",
        "no_note": "Click to add note",
        "current_account": "Current",
        "switch_to_this_account": "Switch to this account",
        "edit_note": "Edit Note",
        "edit_note_title": "Edit Account Note",
        "edit_note_message": "Please enter a note for this account:",
        "note_placeholder": "Enter note...",
        "note_saved": "Note Saved",
        "note_saved_message": "Account note has been saved successfully",
        "switch_offline": "Launch Offline",
        "offline_mode": "Offline Mode",
        "online_mode": "Online Mode",
        "more_actions": "More Actions",
        "delete_account": "Delete Account",
        "confirm_delete_account": "Confirm Delete Account",
        "delete_account_message": "Are you sure you want to delete account {}?\n\nThis will remove the account's login information from Steam.",
        "delete_account_success": "Delete Successful",
        "delete_account_success_message": "Account has been deleted successfully",
        "delete_account_failed": "Delete Failed",
        "delete_account_failed_message": "Failed to delete account, please check permissions",
        "total_games": "Total: {0} games | SteamTools: {1} | GreenLuma: {2}",
        "load_failed": "Load failed: {0}",
        "reset_settings": "Reset Settings",
        "reset_settings_message": "Are you sure you want to reset all settings to default?\n\nThis action cannot be undone.",
        "reset_success": "Reset Successful",
        "reset_success_message": "Settings have been reset to default, please reload the page",
        "reset_failed": "Reset Failed",
        "restarting": "Restarting",
        "restarting_message": "Restarting Steam, please wait...",
        "restart_success": "Restart Successful",
        "restart_success_message": "Steam has been restarted",
        "restart_failed": "Restart Failed",
        "restart_failed_message": "Failed to restart Steam, please restart manually",
        "restart_error_message": "Error restarting Steam: {0}",
        "application_config": "Application Configuration",
        "debug_mode": "Debug Mode",
        "enable_debug_log": "Enable detailed debug log output",
        "save_log_files": "Save Log Files",
        "save_logs_to_file": "Save logs to file",
        "unlocker_mode": "Unlocker Mode",
        "auto_detect": "Auto Detect",
        "force_steamtools": "Force SteamTools",
        "force_greenluma": "Force GreenLuma",
        "force_opensteamtools": "Force OpenSteamTools",
        "force_unlocker_hint": "Force use of specified unlocker",
        "download_timeout": "Download Timeout",
        "download_timeout_hint": "Timeout in seconds for manifest downloads, increase if network is slow",
        "light_theme": "Light",
        "dark_theme": "Dark",
        "follow_system": "Follow System",
        "window_effect": "Window Effect",
        "window_effect_hint": "Select window background effect",
        "effect_none": "None",
        "effect_mica": "Mica (Win11)",
        "effect_acrylic": "Acrylic (Win10+)",
        "effect_aero": "Aero Blur",
        "smooth_scroll": "Smooth Scroll",
        "smooth_scroll_hint": "Enable smooth scrolling effect (disable to reduce lag)",
        "default_blue": "Default Blue (#0078d4)",
        "purple": "Purple (#9b4dca)",
        "green": "Green (#10893e)",
        "orange": "Orange (#ff8c00)",
        "red": "Red (#e81123)",
        "pink": "Pink (#e3008c)",
        "auto_select": "Auto Select",
        "tip_source_fail": "Tip: If one source fails, try another",
        "auto_search_github": "Auto Search GitHub",
        "swa_v2": "SWA V2",
        "walftech": "Walftech",
        "steamautocracks_v2": "SteamAutoCracks V2 (Keys Only) [Deprecated]",
        "sudama": "Sudama Library (Keys Only) [Recommended]",
        "buqiuren": "Manifest Helper Library (Manifest Only)",
        "gmrc": "GMRC (Manifest Only)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_mau": "GitHub (MAU)",
        "check_update": "Check Update",
        "checking": "Checking...",
        "update_available": "New Version Available",
        "current_version": "Current Version",
        "latest_version": "Latest Version",
        "no_release_notes": "No release notes",
        "go_to_download": "Download",
        "already_latest": "Already Up to Date",
        "already_latest_content": "You are running the latest version.",
        "check_update_failed": "Check Update Failed",
                "drm_page_title": "D-Encryption Authorizer",
        "drm_step1": "Step 1: Get Authorization File",
        "drm_cw_file": "CW File",
        "drm_cw_file_hint": "Select local .cw file and decrypt",
        "drm_cw_placeholder": "Select .cw authorization file",
        "drm_browse": "Browse",
        "drm_decrypt": "Decrypt",
        "drm_auth_code": "Auth Code",
        "drm_auth_code_hint": "Download CW file online via auth code",
        "drm_auth_code_placeholder": "Enter auth code",
        "drm_download_decrypt": "Download & Decrypt",
        "drm_online_auth": "Get Auth Online",
        "drm_online_auth_hint": "Visit external authorization websites",
        "drm_extract_title": "Get CW File (Local Extract)",
        "drm_extract_hint": "Requires Steam login and game ownership",
        "drm_extract_placeholder": "Enter game AppID (must own the game)",
        "drm_gen_authcode": "Generate Auth Code",
        "drm_extract_cw": "Extract CW Locally",
        "drm_info_title": "Authorization Info",
        "drm_valid_from": "Valid From",
        "drm_valid_to": "Valid To",
        "drm_step2": "Step 2: GL Mode Authorization (SteamTools)",
        "drm_gl_hint": "Write authorization ticket to SteamTools directory",
        "drm_gl_btn": "Authorize (GL/SteamTools)",
        "drm_log": "Log",
        "drm_nav": "D-Encryption",
        "drm_tip_select_cw": "Please select a CW file first",
        "drm_tip_enter_code": "Please enter auth code",
        "drm_tip_decrypt_first": "Please decrypt CW file first",
        "drm_tip_valid_appid": "Please enter a valid AppID",
        "drm_missing_dep": "Missing Dependency",
        "drm_missing_dep_hint": "Please install pycryptodome: pip install pycryptodome",
        "drm_decrypt_failed": "Decrypt Failed",
        "drm_download_failed": "Download Failed",
        "drm_auth_success": "Authorization Successful",
        "drm_auth_failed": "Authorization Failed","restart_steam_title": "Restart Steam",
        "restart_steam_confirm_message": "Are you sure you want to restart Steam?\n\nThis will close the currently running Steam and restart it.",
        
        # 缺失的翻译键
        "tip": "Tip",
        "recognition_success": "Recognition Success",
        "game_not_found": "Game not found",
        "check_game_name": "Please check the game name or try using AppID",
        "search_failed": "Search Failed",
        "add_success": "Add Success",
        "add_success_content": "AppID {0} has been successfully added, restart Steam to take effect",
        "adding_game": "Adding game to library...",
        "please_wait_adding": "Please wait, processing add operation",
        "process_failed": "Process Failed",
        "check_logs": "Please check logs",
        "check_details": "Process failed, please check details or try other sources",
        "auto_detect_placeholder": "Leave empty for auto detection",
        "token_placeholder": "Optional, for increasing API request limits",
        "load_config_failed": "Load config failed",
        "save_success": "Save Success",
        "save_success_content": "Configuration saved",
        "save_failed": "Save Failed",
        "unknown_error": "Unknown error",
        "data_process_failed": "Data processing failed",
        "please_wait": "Please wait",
        "unknown_game": "Unknown game",
        "reset_to_default": "Reset Default",
        "about_title": "About",
        "thanks_title": "Credits",
        "about_text": "Cai Install - Fluent Design Version\n\nVersion: 1.7\n\nThis is a modern Steam game unlocking tool based on PyQt6-Fluent-Widgets.\n\nFeatures:\n• Fluent Design style\n• Support for multiple manifest sources\n• Game search and adding\n• Installed games management\n• Theme customization\n\nProject URL: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Special Thanks\n\nDevelopers:\n• zhouchentao666 - Developer\n\nOpen Source Projects:\n• PyQt6 - Qt6 Python Bindings\n• PyQt-Fluent-Widgets - Fluent Design Component Library\n• Cai-install-Web-GUI - Original Project Author\n• httpx - Async HTTP Client\n• Game-Cheats-Manager - Trainer data source (https://github.com/dyang886/Game-Cheats-Manager)\n\nManifest Sources:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Manifest Helper Library\n\nThanks to all developers and users who contributed to this project!",
        "donate": "Donate",
        "donate_title": "Support the Developer",
        "donate_desc": "If this project has been helpful, feel free to buy the author a coffee ☕",
        "donate_wechat": "WeChat Pay",
        "donate_alipay": "Alipay",
        "donate_loading": "Loading...",
        "donate_load_failed": "Failed to load image",
        "fixed_version": "Fixed Version",
        "auto_update": "Auto Update",
        "toggle_version_mode": "Toggle Version Mode",
        "st_settings": "SteamTools Settings",
        "st_settings_hint": "Control SteamTools file version management mode",
        "st_fixed_enable": "Enable SteamTools Fixed Version Mode",
        "st_fixed_tooltip": "New SteamTools files will use fixed version mode by default",
        "st_fixed_manifest_mode": "Fixed Version Manifest Repair",
        "st_fixed_manifest_mode_hint": "Whether to auto repair manifest when switching to fixed version on home page",
        "st_fixed_manifest_always": "Always",
        "st_fixed_manifest_never": "Never",
        "st_fixed_manifest_ask": "Ask",
        "patch_manifest_mode": "Patch Manifest",
        "patch_manifest_mode_hint": "Automatically complete missing manifest files after import",
        "patch_manifest_always": "Always",
        "patch_manifest_never": "Never",
        "patch_manifest_ask": "Ask",
        "patch_manifest_ask_hint": "Complete missing manifest files?",
        "dlc_timeout": "DLC Network Timeout",
        "dlc_timeout_hint": "Timeout for fetching DLC list, increase if network is slow (seconds)",
        "show_progress_bar": "Show Progress Bar",
        "show_progress_bar_hint": "Show progress bar during search and installation for better user experience",
        "name_not_found": "Name Not Found",
        "fetch_failed": "Fetch Failed",
        "github_repos": "GitHub Repositories",
        "github_repos_desc": "Add custom GitHub manifest repositories",
        "zip_repos": "ZIP Manifest Libraries",
        "zip_repos_desc": "Add custom ZIP manifest download URLs",
        "add": "Add",
        "add_github_repo": "Add GitHub Repo",
        "add_zip_repo": "Add ZIP Repo",
        "repo_name": "Display Name",
        "repo_path": "Repository Path",
        "repo_url": "Download URL",
        "repo_name_placeholder": "e.g., My Custom Repo",
        "github_repo_placeholder": "e.g., username/repository",
        "zip_url_placeholder": "e.g., https://example.com/download/{app_id}.zip",
        "github_repo_hint": "Format: username/repository, e.g., Auiowu/ManifestAutoUpdate",
        "zip_url_hint": "URL must contain {app_id} placeholder, which will be replaced with actual AppID",
        "no_repos": "No repositories configured",
        "repo_exists": "Repository Exists",
        "repo_already_added": "This repository has already been added",
        "github_repo_added": "GitHub repository added successfully",
        "zip_repo_added": "ZIP manifest library added successfully",
        "input_incomplete": "Incomplete Input",
        "please_fill_all_fields": "Please fill in all required fields",
        "invalid_format": "Invalid Format",
        "github_format_hint": "GitHub repository format should be: username/repository",
        "zip_format_hint": "URL must contain {app_id} placeholder",
        "save": "Save",
        "cancel": "Cancel",
        
        # Kernel Detection
        "no_kernel_title": "No Unlock Kernel Detected",
        "no_kernel_msg": "You haven't installed any unlock kernel yet. This software currently supports three kernels, please choose:",
        "auto_download": "Auto Download",
        "manual_download": "Manual Download",
        "force_kernel_select": "If installed but not recognized, you can force select kernel here:",
        "force_apply": "Force Apply",
        "ost_desc": "OpenSteamTools (Recommended)",
        "st_desc": "SteamTools",
        "gl_desc": "GreenLuma (Not Recommended)",
        
        # Version Mode Settings
        "st_settings": "Version Mode Settings",
        "st_settings_hint": "Control file version management mode (Auto Update/Fixed Version)",
        "st_fixed_enable": "Fixed Version",
        "st_fixed_tooltip": "New files will use fixed version mode by default",
        "manifest_patch_source": "Manifest Patch Source",
        "manifest_patch_source_hint": "Used for auto-completing missing manifests in fixed version mode",
        "patch_source_default": "Default (Steam.run/GitHub)",
        "patch_source_gmrc": "GMRC",
        "patch_source_buqiuren": "BuQiuRen",
        
        # Common
        "success": "Success",
        "failed": "Failed",
        "install_success": "installed successfully, please restart the software!",
        "download_failed": "Download failed",
        "launch_failed": "Launch failed",
        "save_failed": "Save failed",
    },
    "zh_TW": {
        "app_title": "流暢入库",
        "home": "主頁",
        "search": "搜尋入库",
        "settings": "設定",
        "default_page": "預設介面",
        "default_page_hint": "選擇應用啟動後顯示的預設介面",
        "default_page_home": "主頁",
        "default_page_search": "搜尋入库",
        "restart_steam": "重新啟動 Steam",
        "installed_games": "已入库的遊戲",
        "search_placeholder": "搜尋遊戲名稱或 AppID",
        "loading": "載入中...",
        "no_games": "暫無遊戲",
        "delete": "刪除",
        "confirm_delete": "確認刪除",
        "delete_message": "確定要刪除 AppID {0} 嗎？\n\n此操作無法復原。",
        "deleting": "正在刪除",
        "delete_success": "刪除成功",
        "delete_failed": "刪除失敗",
        "search_and_add": "搜尋並入库遊戲",
        "game_name_or_appid": "輸入遊戲名稱或 AppID / Steam 連結",
        "search_button": "搜尋",
        "add_options": "入库選項",
        "add_all_dlc": "加入所有 DLC",
        "patch_depot_key": "修補 Depot Key",
        "patch_manifest": "修補 Manifest",
        "download_lua_only": "僅下載 Lua",
        "download_dlc_manifests": "下載 DLC 清單",
        "download_all_manifests": "下載所有清單 (Lua + DLC)",
        "manifest_source": "清單來源:",
        "view_mode": "檢視模式",
        "sort_mode": "排序",
        "view_list": "清單",
        "view_grid": "卡片",
        "sort_default": "預設",
        "sort_az": "A-Z",
        "sort_za": "Z-A",
        "add_game": "入库遊戲",
        "steam_path": "Steam 路徑",
        "steam_path_hint": "選擇Steam安裝路徑，留空則自動偵測",
        "github_token": "GitHub 個人權杖",
        "github_token_hint": "選填，用於提高API請求限制",
        "basic_settings": "基本設定",
        "appearance": "外觀",
        "theme_mode": "佈景主題模式",
        "theme_color": "佈景主題顏色",
        "language": "語言",
        "save_settings": "儲存設定",
        "about": "關於",
        "thanks": "感謝",
        "restart_required": "需要重新啟動",
        "language_changed": "語言已變更為 {0}\n\n是否立即重新啟動應用以套用變更？",
        "theme_mode_changed": "主題模式已變更為 {0}\n\n是否立即重新啟動應用以套用變更？",
        "theme_color_changed": "主題顏色已變更為 {0}\n\n是否立即重新啟動應用以套用變更？",
        "restart_steam_confirm": "重新啟動 Steam",
        "restart_steam_message": "確定要重新啟動 Steam 嗎？\n\n這將關閉目前執行中的 Steam 並重新啟動。",
        "restart_steam_select_account": "選擇要切換的帳號（可選）：",
        "restart_steam_no_switch": "不切換帳號，僅重新啟動",
        "total_games": "共 {0} 個遊戲 | SteamTools: {1} | GreenLuma: {2}",
        "load_failed": "載入失敗: {0}",
        "reset_settings": "重設設定",
        "reset_settings_message": "確定要將所有設定重設為預設值嗎？\n\n此操作無法復原。",
        "reset_success": "重設成功",
        "reset_success_message": "設定已重設為預設值，請重新載入頁面",
        "reset_failed": "重設失敗",
        "restarting": "正在重新啟動",
        "restarting_message": "正在重新啟動 Steam，請稍候...",
        "restart_success": "重新啟動成功",
        "restart_success_message": "Steam 已重新啟動",
        "restart_failed": "重新啟動失敗",
        "restart_failed_message": "重新啟動 Steam 失敗，請手動重新啟動",
        "restart_error_message": "重新啟動 Steam 時發生錯誤: {0}",
        "application_config": "應用程式設定",
        "debug_mode": "偵錯模式",
        "debug_mode_hint": "啟用詳細的偵錯紀錄輸出",
        "enable_debug_log": "啟用詳細的偵錯紀錄輸出",
        "save_log_files": "儲存紀錄檔",
        "save_logs_to_file": "將紀錄儲存至檔案中",
        "save_log_files_hint": "將紀錄儲存至檔案中",
        "unlocker_mode": "解鎖工具模式",
        "auto_detect": "自動偵測",
        "force_steamtools": "強制 SteamTools",
        "force_greenluma": "強制 GreenLuma",
        "force_opensteamtools": "強制 OpenSteamTools",
        "force_unlocker_hint": "強制使用指定的解鎖工具",
        "download_timeout": "入库逾時時間",
        "download_timeout_hint": "下載清單的逾時時間（秒），網路較慢時可適度增加",
        "theme_mode_hint": "選擇應用佈景主題模式",
        "theme_color_hint": "選擇佈景主題顏色",
        "language_hint": "選擇應用語言",
        "window_effect": "視窗特效",
        "window_effect_hint": "選擇視窗背景特效",
        "effect_none": "無特效",
        "effect_mica": "雲母 (Win11)",
        "effect_acrylic": "壓克力 (Win10+)",
        "effect_aero": "Aero 毛玻璃",
        "smooth_scroll": "平滑捲動",
        "smooth_scroll_hint": "啟用頁面平滑捲動效果（關閉可減少卡頓）",
        "light_theme": "淺色",
        "dark_theme": "深色",
        "follow_system": "跟隨系統",
        "default_blue": "預設藍 (#0078d4)",
        "purple": "紫色 (#9b4dca)",
        "green": "綠色 (#10893e)",
        "orange": "橘色 (#ff8c00)",
        "red": "紅色 (#e81123)",
        "pink": "粉紅色 (#e3008c)",
        "tip_source_fail": "提示: 若某個來源失敗，請嘗試其他來源",
        "auto_select": "自動選取",
        "auto_search_github": "自動搜尋GitHub",
        "swa_v2": "SWA V2",
        "walftech": "Walftech",
        "steamautocracks_v2": "SteamAutoCracks V2 (僅金鑰) [已廢棄]",
        "sudama": "Sudama 資料庫 (僅金鑰) [推薦]",
        "buqiuren": "清單不求人資料庫 (僅清單)",
        "gmrc": "GMRC (僅清單)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_mau": "GitHub (MAU)",
        "check_update": "檢查更新",
        "checking": "檢查中...",
        "update_available": "發現新版本",
        "current_version": "目前版本",
        "latest_version": "最新版本",
        "no_release_notes": "暫無更新說明",
        "go_to_download": "前往下載",
        "already_latest": "已是最新版本",
        "already_latest_content": "目前已是最新版本，無需更新。",
        "check_update_failed": "檢查更新失敗",
        "restart_steam_title": "重新啟動 Steam",
        "restart_steam_confirm_message": "確定要重新啟動 Steam 嗎？\n\n這將關閉目前執行中的 Steam 並重新啟動。",
        "drm_page_title": "D加密授權器",
        "drm_step1": "步驟 1：取得授權檔案",
        "drm_cw_file": "CW 檔案",
        "drm_cw_file_hint": "選擇本機 .cw 授權檔案並解密",
        "drm_cw_placeholder": "選擇 .cw 授權檔案",
        "drm_browse": "瀏覽",
        "drm_decrypt": "解密",
        "drm_auth_code": "授權碼",
        "drm_auth_code_hint": "透過授權碼線上取得 CW 檔案",
        "drm_auth_code_placeholder": "輸入授權碼",
        "drm_download_decrypt": "下載並解密",
        "drm_online_auth": "線上取得授權",
        "drm_online_auth_hint": "造訪外部授權網站",
        "drm_extract_title": "取得 CW 檔案（本機提取）",
        "drm_extract_hint": "需要已登入 Steam 且擁有該遊戲",
        "drm_extract_placeholder": "輸入遊戲 AppID（目前帳號必須擁有該遊戲）",
        "drm_gen_authcode": "產生授權碼",
        "drm_extract_cw": "本機提取 CW",
        "drm_info_title": "授權資訊",
        "drm_valid_from": "生效時間",
        "drm_valid_to": "失效時間",
        "drm_step2": "步驟 2：GL 模式授權（SteamTools）",
        "drm_gl_hint": "將授權 ticket 寫入 SteamTools 目錄",
        "drm_gl_btn": "開始授權 (GL/SteamTools)",
        "drm_log": "紀錄",
        "drm_nav": "D加密",
        "drm_tip_select_cw": "請先選擇 CW 檔案",
        "drm_tip_enter_code": "請輸入授權碼",
        "drm_tip_decrypt_first": "請先解密 CW 檔案",
        "drm_tip_valid_appid": "請輸入有效的 AppID",
        "drm_missing_dep": "缺少依賴",
        "drm_missing_dep_hint": "請安裝 pycryptodome: pip install pycryptodome",
        "drm_decrypt_failed": "解密失敗",
        "drm_download_failed": "下載失敗",
        "drm_auth_success": "授權成功",
        "drm_auth_failed": "授權失敗",
        
        # 缺失的翻譯鍵
        "settings_log_title": "日誌",
        "tip": "提示",
        "recognition_success": "辨識成功",
        "game_not_found": "找不到相符的遊戲",
        "check_game_name": "請檢查遊戲名稱或嘗試使用 AppID",
        "search_failed": "搜尋失敗",
        "game_selected": "遊戲已選擇",
        "add_success": "入库成功",
        "add_success_content": "AppID {0} 已成功入库，重新啟動 Steam 後生效",
        "adding_game": "正在入库遊戲...",
        "please_wait_adding": "請稍候，正在處理入库作業",
        "process_failed": "處理失敗",
        "check_logs": "請檢查紀錄",
        "check_details": "處理失敗，請檢查詳細資訊或嘗試其他清單來源",
        "auto_detect_placeholder": "留空則自動偵測",
        "token_placeholder": "選填，用於提高 API 請求限制",
        "load_config_failed": "載入設定失敗",
        "save_success": "儲存成功",
        "save_success_content": "設定已儲存",
        "save_failed": "儲存失敗",
        "unknown_error": "未知錯誤",
        "data_process_failed": "處理資料失敗",
        "please_wait": "請稍候",
        "unknown_game": "未知遊戲",
        "reset_to_default": "重設為預設",
        "about_title": "關於",
        "thanks_title": "感謝",
        "about_text": "Cai Install - Fluent Design 版本\n\n版本: 1.7\n\n這是一套基於 PyQt6-Fluent-Widgets 的現代化 Steam 遊戲解鎖工具。\n\n功能特色:\n• Fluent Design 設計風格\n• 支援多種清單來源\n• 遊戲搜尋與入库\n• 已入库遊戲管理\n• 佈景主題自訂\n\n專案位址: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "特別感謝\n\n開發者:\n• zhouchentao666 - 製作人員\n\n開源專案:\n• PyQt6 - Qt6 Python 綁定\n• PyQt-Fluent-Widgets - Fluent Design 元件庫\n• Cai-install-Web-GUI - 原始專案作者\n• httpx - 非同步 HTTP 用戶端\n\n清單來源提供:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• 清單不求人\n\n感謝所有為本專案貢獻的開發者與使用者！",
        "donate": "捐贈",
        "donate_title": "支持開發者",
        "donate_desc": "如果本專案對你有幫助，歡迎請作者喝杯咖啡 ☕",
        "donate_wechat": "微信支付",
        "donate_alipay": "支付寶",
        "donate_loading": "載入中...",
        "donate_load_failed": "圖片載入失敗",
        "fixed_version": "固定版本",
        "auto_update": "自動更新",
        "toggle_version_mode": "切換版本模式",
        "st_settings": "SteamTools 設定",
        "st_settings_hint": "控制SteamTools檔案的版本管理模式",
        "st_fixed_enable": "啟用 SteamTools 固定版本模式",
        "st_fixed_tooltip": "新增的SteamTools檔案預設使用固定版本模式",
        "st_fixed_manifest_mode": "固定版本Manifest修復",
        "st_fixed_manifest_mode_hint": "主頁切換至固定版本時是否自動修復manifest",
        "st_fixed_manifest_always": "始終",
        "st_fixed_manifest_never": "從不",
        "st_fixed_manifest_ask": "詢問",
        "patch_manifest_mode": "修補 Manifest",
        "patch_manifest_mode_hint": "入库後自動補全缺失的清單檔案",
        "patch_manifest_always": "始終",
        "patch_manifest_never": "從不",
        "patch_manifest_ask": "詢問",
        "patch_manifest_ask_hint": "是否補全缺失的清單檔案？",
        "dlc_timeout": "DLC 聯網超時時間",
        "dlc_timeout_hint": "獲取DLC列表超時時間，網路較差時可適當調大（秒）",
        "show_progress_bar": "顯示進度條",
        "show_progress_bar_hint": "在搜尋和入库過程中顯示進度條，提供更好的使用者體驗",
        "sidebar_settings": "側欄顯示設定（重新啟動生效）",
        "hide_search": "隱藏搜尋入库",
        "hide_search_hint": "隱藏側欄中的搜尋入库選項",
        "hide_launcher": "隱藏連線遊戲",
        "hide_launcher_hint": "隱藏側欄中的連線遊戲選項",
        "hide_trainer": "隱藏修改器",
        "hide_trainer_hint": "隱藏側欄中的修改器選項",
        "hide_drm": "隱藏D加密",
        "hide_drm_hint": "隱藏側欄中的D加密選項",
        "name_not_found": "名稱未找到",
        "fetch_failed": "獲取失敗",
        
        # 内核检测相关
        "no_kernel_title": "未檢測到解鎖內核",
        "no_kernel_msg": "您還沒有安裝任何解鎖內核，本軟件目前支持以下三種內核，請您選擇：",
        "auto_download": "自動下載",
        "manual_download": "手動下載",
        "force_kernel_select": "如果您已安裝但未正確識別，可在此強制選擇內核：",
        "force_apply": "強制使用",
        "ost_desc": "OpenSteamTools (推薦)",
        "st_desc": "SteamTools",
        "gl_desc": "GreenLuma (不推薦)",
        
        # 版本模式设置
        "st_settings": "版本模式設置",
        "st_settings_hint": "控制文件的版本管理模式（自動更新/固定版本）",
        "st_fixed_enable": "固定版本",
        "st_fixed_tooltip": "新添加的文件默認使用固定版本模式",
        "manifest_patch_source": "Manifest 修補庫",
        "manifest_patch_source_hint": "用於固定版本模式缺失清單時的自動補全源",
        "patch_source_default": "默認 (Steam.run/GitHub)",
        "patch_source_gmrc": "GMRC",
        "patch_source_buqiuren": "清單不求人",
        
        # 通用
        "success": "成功",
        "failed": "失敗",
        "install_success": "安裝成功，請重啟軟件！",
        "download_failed": "下載失敗",
        "launch_failed": "啟動失敗",
        "save_failed": "保存失敗",
    },
}

# ===== 联机游戏翻译键 (追加到各语言) =====
_LAUNCHER_TEXTS = {
    "zh_CN": {
        "launcher": "联机游戏",
        "launcher_title": "联机启动器",
        "launcher_status_ready": "系统就绪",
        "launcher_status_running": "服务运行中",
        "launcher_game_exe": "游戏程序",
        "launcher_browse": "浏览",
        "launcher_app_id": "协议 ID (AppID)",
        "launcher_app_id_hint": "默认 480 (Spacewar)，可改为游戏实际 AppID",
        "launcher_start": "启动服务 & 运行游戏",
        "launcher_stop": "停止服务",
        "launcher_log": "运行日志",
        "launcher_clear_log": "清空日志",
        "launcher_method_a": "方法A: 设为 3170150 (中文环境推荐)",
        "launcher_method_b": "方法B: 强改 480 中文版 (杀进程)",
        "launcher_method_c": "方法C: BAT 脚本注入启动",
        "launcher_find_patch": "寻找联机补丁 (外部网站)",
        "launcher_no_exe": "请先选择游戏 .exe 文件",
        "launcher_service_started": "服务已启动",
        "launcher_service_stopped": "服务已停止",
        "launcher_cn_fix_done": "协议 ID 已设为 3170150",
        "launcher_bat_done": "BAT 脚本已生成并启动",
        "launcher_error": "启动失败",
        "launcher_install_hint": "安装 Spacewar (AppID 480)",
        # 三种联机模式
        "launcher_mode_label": "联机方式",
        "launcher_mode_dll": "DLL 注入联机 (推荐)",
        "launcher_mode_bat": "BAT 脚本注入联机",
        "launcher_mode_changer": "AppID Changer 联机",
        "launcher_mode_dll_desc": "扫描 Steam 库中的 steam_api.dll，加载后初始化 Steam API，再启动游戏。兼容性最佳。",
        "launcher_mode_bat_desc": "在游戏目录生成 BAT 脚本，通过环境变量注入 AppID 启动游戏。简单快速。",
        "launcher_mode_changer_desc": "直接修改游戏目录下的 steam_appid.txt 文件启动游戏，游戏关闭后自动恢复原 AppID。适用于大多数 Steam 游戏。",
        "launcher_bat_start": "生成脚本并启动",
        "launcher_changer_start": "修改 AppID 并启动",
        "launcher_mode_select": "选择联机方式",
        "launcher_changer_no_appid_txt": "游戏目录下未找到 steam_appid.txt 文件",
        "launcher_changer_backup_failed": "备份原始 AppID 失败",
        "launcher_changer_write_failed": "写入新 AppID 失败",
        "launcher_changer_launch_failed": "启动游戏失败",
        "launcher_changer_success": "AppID 修改成功，游戏已启动",
        "launcher_changer_restored": "原始 AppID 已恢复",
        "settings_log_title": "运行日志",
        "settings_clear_log": "清空日志",
    },
    "en_US": {
        "launcher": "Multiplayer",
        "launcher_title": "Multiplayer Launcher",
        "launcher_status_ready": "System Ready",
        "launcher_status_running": "Service Running",
        "launcher_game_exe": "Game Executable",
        "launcher_browse": "Browse",
        "launcher_app_id": "Protocol ID (AppID)",
        "launcher_app_id_hint": "Default 480 (Spacewar), can be changed to actual game AppID",
        "launcher_start": "Start Service & Launch Game",
        "launcher_stop": "Stop Service",
        "launcher_log": "Runtime Log",
        "launcher_clear_log": "Clear Log",
        "launcher_method_a": "Method A: Set to 3170150 (CN env recommended)",
        "launcher_method_b": "Method B: Force 480 CN version (kill process)",
        "launcher_method_c": "Method C: BAT script injection launch",
        "launcher_find_patch": "Find Multiplayer Patch (External Sites)",
        "launcher_no_exe": "Please select a game .exe file first",
        "launcher_service_started": "Service started",
        "launcher_service_stopped": "Service stopped",
        "launcher_cn_fix_done": "Protocol ID set to 3170150",
        "launcher_bat_done": "BAT script generated and launched",
        "launcher_error": "Launch failed",
        "launcher_install_hint": "Install Spacewar (AppID 480)",
        "launcher_mode_label": "Launch Mode",
        "launcher_mode_dll": "DLL Injection (Recommended)",
        "launcher_mode_bat": "BAT Script Injection",
        "launcher_mode_changer": "AppID Changer",
        "launcher_mode_dll_desc": "Scans Steam library for steam_api.dll, loads it to initialize Steam API, then launches the game. Best compatibility.",
        "launcher_mode_bat_desc": "Generates a BAT script in the game directory to inject AppID via environment variables. Simple and fast.",
        "launcher_mode_changer_desc": "Directly modifies the steam_appid.txt file in the game directory to launch the game, automatically restores the original AppID after the game closes. Suitable for most Steam games.",
        "launcher_bat_start": "Generate Script & Launch",
        "launcher_changer_start": "Change AppID & Launch",
        "launcher_mode_select": "Select Launch Mode",
        "launcher_changer_no_appid_txt": "steam_appid.txt not found in game directory",
        "launcher_changer_backup_failed": "Failed to backup original AppID",
        "launcher_changer_write_failed": "Failed to write new AppID",
        "launcher_changer_launch_failed": "Failed to launch game",
        "launcher_changer_success": "AppID changed successfully, game launched",
        "launcher_changer_restored": "Original AppID restored",
        "settings_log_title": "Runtime Log",
        "settings_clear_log": "Clear Log",
    },
    "zh_TW": {
        "launcher": "多人遊戲",
        "launcher_title": "多人遊戲啟動器",
        "launcher_status_ready": "系統準備就緒",
        "launcher_status_running": "服務運行中",
        "launcher_game_exe": "遊戲可執行檔",
        "launcher_browse": "瀏覽",
        "launcher_app_id": "協議 ID (AppID)",
        "launcher_app_id_hint": "預設為 480 (Spacewar)，可更改為實際遊戲 AppID",
        "launcher_start": "啟動服務並執行遊戲",
        "launcher_stop": "停止服務",
        "launcher_log": "執行日誌",
        "launcher_clear_log": "清除日誌",
        "launcher_method_a": "方法A：設為 3170150（中文環境推薦）",
        "launcher_method_b": "方法B：強改 480 中文版（殺程序）",
        "launcher_method_c": "方法C：BAT 指令碼注入啟動",
        "launcher_find_patch": "尋找多人遊戲修正檔（外部網站）",
        "launcher_no_exe": "請先選擇遊戲 .exe 檔案",
        "launcher_service_started": "服務已啟動",
        "launcher_service_stopped": "服務已停止",
        "launcher_cn_fix_done": "協議 ID 已設為 3170150",
        "launcher_bat_done": "BAT 指令碼已生成並啟動",
        "launcher_error": "啟動失敗",
        "launcher_install_hint": "安裝 Spacewar (AppID 480)",
        "launcher_mode_label": "多人遊戲方式",
        "launcher_mode_dll": "DLL 注入多人遊戲（推薦）",
        "launcher_mode_bat": "BAT 指令碼注入多人遊戲",
        "launcher_mode_changer": "AppID 變更器多人遊戲",
        "launcher_mode_dll_desc": "掃描 Steam 資料庫中的 steam_api.dll，載入後初始化 Steam API，再啟動遊戲。相容性最佳。",
        "launcher_mode_bat_desc": "在遊戲目錄生成 BAT 指令碼，透過環境變數注入 AppID 啟動遊戲。簡單快速。",
        "launcher_mode_changer_desc": "直接修改遊戲目錄下的 steam_appid.txt 檔案啟動遊戲，遊戲關閉後自動恢復原始 AppID。適用於大多數 Steam 遊戲。",
        "launcher_bat_start": "生成指令碼並啟動",
        "launcher_changer_start": "修改 AppID 並啟動",
        "launcher_mode_select": "選擇多人遊戲方式",
        "launcher_changer_no_appid_txt": "遊戲目錄下未找到 steam_appid.txt 檔案",
        "launcher_changer_backup_failed": "備份原始 AppID 失敗",
        "launcher_changer_write_failed": "寫入新 AppID 失敗",
        "launcher_changer_launch_failed": "啟動遊戲失敗",
        "launcher_changer_success": "AppID 修改成功，遊戲已啟動",
        "launcher_changer_restored": "原始 AppID 已恢復",
        "settings_log_title": "執行日誌",
        "settings_clear_log": "清除日誌",
    }

}
for _lang, _keys in _LAUNCHER_TEXTS.items():
    if _lang in TEXTS:
        TEXTS[_lang].update(_keys)
# fallback: copy zh_CN keys to other languages that don't have them
for _lang in TEXTS:
    if _lang not in _LAUNCHER_TEXTS:
        TEXTS[_lang].update(_LAUNCHER_TEXTS["zh_CN"])

# ===== 游戏推荐翻译键 =====
_EXTRA_TEXTS = {
    "zh_CN": {
        "recommended_games": "热门游戏推荐",
        "recommended_hint": "以下为 Steam 热门游戏，点击可直接入库",
        "loading_recommendations": "正在加载推荐...",
        "recommendations_failed": "加载推荐失败",
        "show_more": "显示更多",
    },
    "en_US": {
        "recommended_games": "Popular Game Recommendations",
        "recommended_hint": "Top Steam games below, click to add to library",
        "loading_recommendations": "Loading recommendations...",
        "recommendations_failed": "Failed to load recommendations",
        "show_more": "Show More",
    },
    "zh_TW": {
        "recommended_games": "熱門遊戲推薦",
        "recommended_hint": "以下為 Steam 熱門遊戲，點擊可直接入庫",
        "loading_recommendations": "正在載入推薦...",
        "recommendations_failed": "載入推薦失敗",
        "show_more": "顯示更多",
    },
}
for _lang, _keys in _EXTRA_TEXTS.items():
    if _lang in TEXTS:
        TEXTS[_lang].update(_keys)
for _lang in TEXTS:
    if _lang not in _EXTRA_TEXTS:
        TEXTS[_lang].update(_EXTRA_TEXTS["zh_CN"])

# ===== 游戏详情页翻译键 =====
_DETAIL_TEXTS = {
    "zh_CN": {
        "detail_loading": "加载中...",
        "detail_developer": "开发商",
        "detail_publisher": "发行商",
        "detail_release_date": "发布日期",
        "detail_unknown": "未知",
        "detail_coming_soon": "即将推出",
        "detail_free": "免费开玩",
        "detail_price_unavailable": "价格信息不可用",
        "detail_platform": "平台",
        "detail_screenshots": "游戏截图",
        "detail_about": "关于游戏",
        "detail_no_description": "暂无描述",
        "detail_system_requirements": "系统需求",
        "detail_min_requirements": "最低配置",
        "detail_rec_requirements": "推荐配置",
        "detail_no_requirements": "暂无系统需求信息",
        "detail_no_screenshots": "暂无截图",
        "detail_prev": "上一张",
        "detail_next": "下一张",
        "detail_close": "关闭",
        "detail_view_store": "在 Steam 商店查看",
        "detail_add_to_library": "入库",
        "detail_switch_auto": "切换为自动更新",
        "detail_switch_fixed": "切换为固定版本",
        "detail_delete": "删除",
        "detail_copy_appid": "复制 AppID",
        "detail_view_store_page": "查看商店页面",
        "detail_view_steamdb": "查看 SteamDB",
        "detail_view_detail": "查看详情",
        "detail_add_started": "开始入库",
        "detail_add_progress": "{0} 已开始入库",
        "detail_add_failed": "入库失败",
        "detail_add_failed_msg": "无法找到入库入口，请从搜索页面入库",
        "detail_switch_failed": "切换失败",
        "detail_switch_failed_msg": "无法找到切换版本入口",
        "detail_delete_failed": "删除失败",
        "detail_delete_failed_msg": "无法找到删除入口",
        "copy": "复制",
        "copy_cover": "复制封面",
        "copy_game_name": "复制游戏名称",
        "cover_unavailable": "此游戏暂时获取不到封面",
        "game_name_unavailable": "此游戏暂时获取不到游戏名",
    },
    "en_US": {
        "detail_loading": "Loading...",
        "detail_developer": "Developer",
        "detail_publisher": "Publisher",
        "detail_release_date": "Release Date",
        "detail_unknown": "Unknown",
        "detail_coming_soon": "Coming Soon",
        "detail_free": "Free to Play",
        "detail_price_unavailable": "Price unavailable",
        "detail_platform": "Platform",
        "detail_screenshots": "Screenshots",
        "detail_about": "About This Game",
        "detail_no_description": "No description available",
        "detail_system_requirements": "System Requirements",
        "detail_min_requirements": "Minimum",
        "detail_rec_requirements": "Recommended",
        "detail_no_requirements": "No system requirements available",
        "detail_no_screenshots": "No screenshots",
        "detail_prev": "Previous",
        "detail_next": "Next",
        "detail_close": "Close",
        "detail_view_store": "View on Steam Store",
        "detail_add_to_library": "Add to Library",
        "detail_switch_auto": "Switch to Auto Update",
        "detail_switch_fixed": "Switch to Fixed Version",
        "detail_delete": "Delete",
        "detail_copy_appid": "Copy AppID",
        "detail_view_store_page": "View Store Page",
        "detail_view_steamdb": "View SteamDB",
        "detail_view_detail": "View Details",
        "detail_add_started": "Adding to Library",
        "detail_add_progress": "{0} is being added to library",
        "detail_add_failed": "Add Failed",
        "detail_add_failed_msg": "Cannot find library entry, please add from search page",
        "detail_switch_failed": "Switch Failed",
        "detail_switch_failed_msg": "Cannot find version switch entry",
        "detail_delete_failed": "Delete Failed",
        "detail_delete_failed_msg": "Cannot find delete entry",
        "copy": "Copy",
        "copy_cover": "Copy Cover",
        "copy_game_name": "Copy Game Name",
        "cover_unavailable": "Cover image not available for this game",
        "game_name_unavailable": "Game name not available",
    },
    "zh_TW": {
        "detail_loading": "載入中...",
        "detail_developer": "開發商",
        "detail_publisher": "發行商",
        "detail_release_date": "發布日期",
        "detail_unknown": "未知",
        "detail_coming_soon": "即將推出",
        "detail_free": "免費開玩",
        "detail_price_unavailable": "價格資訊不可用",
        "detail_platform": "平台",
        "detail_screenshots": "遊戲截圖",
        "detail_about": "關於此遊戲",
        "detail_no_description": "暫無描述",
        "detail_system_requirements": "系統需求",
        "detail_min_requirements": "最低配置",
        "detail_rec_requirements": "推薦配置",
        "detail_no_requirements": "暫無系統需求資訊",
        "detail_no_screenshots": "暫無截圖",
        "detail_prev": "上一張",
        "detail_next": "下一張",
        "detail_close": "關閉",
        "detail_view_store": "在 Steam 商店查看",
        "detail_add_to_library": "入庫",
        "detail_switch_auto": "切換為自動更新",
        "detail_switch_fixed": "切換為固定版本",
        "detail_delete": "刪除",
        "detail_copy_appid": "複製 AppID",
        "detail_view_store_page": "查看商店頁面",
        "detail_view_steamdb": "查看 SteamDB",
        "detail_view_detail": "查看詳情",
        "detail_add_started": "開始入庫",
        "detail_add_progress": "{0} 已開始入庫",
        "detail_add_failed": "入庫失敗",
        "detail_add_failed_msg": "無法找到入庫入口，請從搜尋頁面入庫",
        "detail_switch_failed": "切換失敗",
        "detail_switch_failed_msg": "無法找到切換版本入口",
        "detail_delete_failed": "刪除失敗",
        "detail_delete_failed_msg": "無法找到刪除入口",
        "copy": "複製",
        "copy_cover": "複製封面",
        "copy_game_name": "複製遊戲名稱",
        "cover_unavailable": "此遊戲暫時獲取不到封面",
        "game_name_unavailable": "此遊戲暫時獲取不到遊戲名",
    },
}
for _lang, _keys in _DETAIL_TEXTS.items():
    if _lang in TEXTS:
        TEXTS[_lang].update(_keys)
for _lang in TEXTS:
    if _lang not in _DETAIL_TEXTS:
        TEXTS[_lang].update(_DETAIL_TEXTS["zh_CN"])

# ===== 修改器页面翻译键 =====
_TRAINER_TEXTS = {
    "zh_CN": {
        "trainer_nav": "修改器",
        "trainer_title": "游戏修改器",
        "trainer_search_placeholder": "搜索修改器（游戏名称）...",
        "trainer_search_btn": "搜索",
        "trainer_installed_title": "已安装的修改器",
        "trainer_search_results": "搜索结果",
        "trainer_download_btn": "下载",
        "trainer_launch_btn": "启动",
        "trainer_delete_btn": "删除",
        "trainer_refresh_btn": "刷新",
        "trainer_open_folder": "打开目录",
        "trainer_no_installed": "暂无已安装的修改器",
        "trainer_no_results": "未找到相关修改器(请关闭梯子重启后试试)",
        "trainer_searching": "正在搜索...",
        "trainer_downloading": "正在下载...",
        "trainer_download_success": "下载成功",
        "trainer_download_failed": "下载失败",
        "trainer_launch_failed": "启动失败",
        "trainer_delete_confirm": "确认删除",
        "trainer_delete_confirm_msg": "确定要删除 {0} 吗？",
        "trainer_deleted": "已删除",
        "trainer_db_missing": "未找到 GCM 数据库",
        "trainer_db_missing_hint": "请先安装并运行 Game Cheats Manager 以下载修改器数据库，或直接搜索（需要网络）",
        "trainer_version": "版本",
        "trainer_source": "来源",
        "trainer_log": "操作日志",
        "trainer_clear_log": "清空日志",
        "trainer_already_exists": "修改器已存在",
        "trainer_open_gcm": "打开 GCM",
        "trainer_progress": "下载进度",
    },
    "en_US": {
        "trainer_nav": "Trainers",
        "trainer_title": "Game Trainers",
        "trainer_search_placeholder": "Search trainers (game name)...",
        "trainer_search_btn": "Search",
        "trainer_installed_title": "Installed Trainers",
        "trainer_search_results": "Search Results",
        "trainer_download_btn": "Download",
        "trainer_launch_btn": "Launch",
        "trainer_delete_btn": "Delete",
        "trainer_refresh_btn": "Refresh",
        "trainer_open_folder": "Open Folder",
        "trainer_no_installed": "No trainers installed",
        "trainer_no_results": "No trainers found",
        "trainer_searching": "Searching...",
        "trainer_downloading": "Downloading...",
        "trainer_download_success": "Download successful",
        "trainer_download_failed": "Download failed",
        "trainer_launch_failed": "Launch failed",
        "trainer_delete_confirm": "Confirm Delete",
        "trainer_delete_confirm_msg": "Are you sure you want to delete {0}?",
        "trainer_deleted": "Deleted",
        "trainer_db_missing": "GCM Database Not Found",
        "trainer_db_missing_hint": "Please install and run Game Cheats Manager to download the trainer database, or search directly (requires internet)",
        "trainer_version": "Version",
        "trainer_source": "Source",
        "trainer_log": "Operation Log",
        "trainer_clear_log": "Clear Log",
        "trainer_already_exists": "Trainer already exists",
        "trainer_open_gcm": "Open GCM",
        "trainer_progress": "Download Progress",
    },
    "zh_TW": {
        "trainer_nav": "修改器",
        "trainer_title": "遊戲修改器",
        "trainer_search_placeholder": "搜尋修改器（遊戲名稱）...",
        "trainer_search_btn": "搜尋",
        "trainer_installed_title": "已安裝的修改器",
        "trainer_search_results": "搜尋結果",
        "trainer_download_btn": "下載",
        "trainer_launch_btn": "啟動",
        "trainer_delete_btn": "刪除",
        "trainer_refresh_btn": "重新整理",
        "trainer_open_folder": "開啟目錄",
        "trainer_no_installed": "暫無已安裝的修改器",
        "trainer_no_results": "未找到相關修改器（請關閉梯子重啟後試試）",
        "trainer_searching": "正在搜尋...",
        "trainer_downloading": "正在下載...",
        "trainer_download_success": "下載成功",
        "trainer_download_failed": "下載失敗",
        "trainer_launch_failed": "啟動失敗",
        "trainer_delete_confirm": "確認刪除",
        "trainer_delete_confirm_msg": "確定要刪除 {0} 嗎？",
        "trainer_deleted": "已刪除",
        "trainer_db_missing": "未找到 GCM 資料庫",
        "trainer_db_missing_hint": "請先安裝並執行 Game Cheats Manager 以下載修改器資料庫，或直接搜尋（需要網路）",
        "trainer_version": "版本",
        "trainer_source": "來源",
        "trainer_log": "操作日誌",
        "trainer_clear_log": "清空日誌",
        "trainer_already_exists": "修改器已存在",
        "trainer_open_gcm": "開啟 GCM",
        "trainer_progress": "下載進度",
    },
}
for _lang, _keys in _TRAINER_TEXTS.items():
    if _lang in TEXTS:
        TEXTS[_lang].update(_keys)
for _lang in TEXTS:
    if _lang not in _TRAINER_TEXTS:
        TEXTS[_lang].update(_TRAINER_TEXTS["zh_CN"])

# 全局语言变量
current_language = "zh_CN"

def tr(key, *args):
    """翻译函数"""
    text = TEXTS.get(current_language, TEXTS["zh_CN"]).get(key, key)
    if args:
        text = text.format(*args)
    return text

def set_language(lang):
    """设置当前语言"""
    global current_language
    if lang in TEXTS:
        current_language = lang


def safe_set_font_size(widget, size):
    """安全设置字体大小，避免负数或零值"""
    if size <= 0:
        size = 9  # 默认字体大小
    font = widget.font()
    font.setPointSize(size)
    widget.setFont(font)

class SafeFlowLayout(FlowLayout):
    """安全的FlowLayout，修复takeAt方法的问题"""
    
    def takeAt(self, index):
        """重写takeAt方法，确保返回QLayoutItem而不是QWidget"""
        if index >= 0 and index < self.count():
            item = super().takeAt(index)
            # 确保返回的是QLayoutItem，如果返回的是QWidget，则包装它
            if hasattr(item, 'widget'):
                return item
            elif hasattr(item, 'deleteLater'):  # 这是一个QWidget
                # 创建一个新的QLayoutItem来包装这个widget
                from PyQt6.QtWidgets import QWidgetItem
                return QWidgetItem(item)
            return item
        return None

class GameCard(CardWidget):
    """游戏卡片组件"""

    def __init__(self, appid, game_name, source_type, parent=None, mode="auto"):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name
        self.source_type = source_type  # 'st' 或 'gl'
        self.mode = mode  # 'auto' 或 'fixed'
        self.cover_loaded = False  # 封面是否已加载

        # 设置右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 创建布局
        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()
        
        # 游戏封面
        self.coverLabel = QLabel(self)
        self.coverLabel.setFixedSize(120, 56)
        self.coverLabel.setScaledContents(True)
        # 根据主题模式动态设置背景颜色
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        # 监听主题变化
        self.theme_changed()
        # 设置封面可点击，点击打开游戏详情
        self.coverLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coverLabel.mousePressEvent = lambda e: self.show_game_detail()
        
        # 游戏标题
        # 如果游戏名称为空或显示为"名称未找到"等，显示AppID
        display_name = game_name
        if not game_name or game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'), tr('unknown_game')):
            display_name = f"AppID: {appid}"
        self.titleLabel = BodyLabel(display_name, self)
        self.titleLabel.setWordWrap(False)
        
        # AppID 和来源
        source_text = "SteamTools / OST" if source_type == "st" else "GreenLuma"
        self.infoLabel = CaptionLabel(f"AppID: {appid} | {source_text}", self)
        self.infoLabel.setTextColor("#606060", "#d2d2d2")
        
        # 版本模式标签（仅SteamTools）
        self.modeLabel = None
        if source_type == "st":
            mode_text = tr("fixed_version") if mode == "fixed" else tr("auto_update")
            mode_color = "#ff9800" if mode == "fixed" else "#6ee7b7"
            self.modeLabel = CaptionLabel(mode_text, self)
            self.modeLabel.setTextColor(mode_color, mode_color)
        
        # 更多按钮
        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)
        self.moreButton.setFixedSize(32, 32)
        self.moreButton.setToolTip("更多")
        self.moreButton.installEventFilter(ToolTipFilter(self.moreButton, showDelay=150, position=ToolTipPosition.TOP))
        self.moreButton.clicked.connect(lambda: self._show_more_menu())

        # 版本切换按钮（仅SteamTools）
        self.toggleButton = None
        if source_type == "st":
            self.toggleButton = TransparentToolButton(FluentIcon.UPDATE, self)
            self.toggleButton.setFixedSize(32, 32)
            self.toggleButton.setToolTip(tr("toggle_version_mode"))
            self.toggleButton.installEventFilter(ToolTipFilter(self.toggleButton, showDelay=150, position=ToolTipPosition.TOP))
            self.toggleButton.clicked.connect(self.on_toggle_clicked)
        
        # 设置布局
        self.setFixedHeight(80)
        self.hBoxLayout.setContentsMargins(15, 12, 15, 12)
        self.hBoxLayout.setSpacing(15)
        
        self.hBoxLayout.addWidget(self.coverLabel)
        
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(4)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.vBoxLayout.addWidget(self.infoLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        if self.modeLabel:
            self.vBoxLayout.addWidget(self.modeLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.hBoxLayout.addLayout(self.vBoxLayout)
        self.hBoxLayout.addStretch(1)
        if self.toggleButton:
            self.hBoxLayout.addWidget(self.toggleButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addWidget(self.moreButton, 0, Qt.AlignmentFlag.AlignRight)
    
    def theme_changed(self):
        """主题变化时更新样式"""
        if isDarkTheme():
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
            self.setStyleSheet("GameCard { background-color: #2b2b2b; border: none; }")
        else:
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #f0f0f0;")
            self.setStyleSheet("GameCard { background-color: #ffffff; border: none; }")
    
    def load_cover(self, network_manager=None):
        """加载游戏封面（使用共享的网络管理器）"""
        if self.cover_loaded:
            return
        
        # 先检查缓存
        cached_data = _get_cached_cover(self.appid)
        if cached_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(cached_data):
                self.coverLabel.setPixmap(pixmap)
                self.cover_loaded = True
            return
        
        # 如果没有网络管理器，尝试从父页面获取
        if network_manager is None:
            parent = self.parent()
            while parent:
                if hasattr(parent, 'network_manager'):
                    network_manager = parent.network_manager
                    break
                parent = parent.parent()
        
        if network_manager:
            cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
            request = QNetworkRequest(QUrl(cover_url))
            reply = network_manager.get(request)
            reply.finished.connect(lambda r=reply: self.on_cover_loaded(r))
    
    def set_cover_pixmap(self, pixmap):
        """直接设置封面图片"""
        if pixmap:
            self.coverLabel.setPixmap(pixmap)
            self.cover_loaded = True
    
    @pyqtSlot(QNetworkReply)
    def on_cover_loaded(self, reply):
        """封面加载完成"""
        # 检查对象是否已被删除
        try:
            if not self.coverLabel or sip.isdeleted(self.coverLabel):
                reply.deleteLater()
                return
        except:
            reply.deleteLater()
            return
            
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            # 缓存封面数据
            _cache_cover(self.appid, bytes(data))
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                try:
                    self.coverLabel.setPixmap(pixmap)
                    self.cover_loaded = True
                except RuntimeError:
                    # 对象可能已被删除
                    pass
        reply.deleteLater()
    
    def on_delete_clicked(self):
        """删除按钮点击"""
        # 发送信号给父页面
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, HomePage):
                parent = parent.parent()
            if parent and hasattr(parent, 'delete_game_with_confirm'):
                # 获取游戏名称
                game_name = getattr(self, 'game_name', None)
                parent.delete_game_with_confirm(self.appid, self.source_type, game_name)
    
    def on_toggle_clicked(self):
        """版本切换按钮点击"""
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, HomePage):
                parent = parent.parent()
            if parent:
                # 构造ST文件名
                filename = f"{self.appid}.lua"
                parent.toggle_st_version(filename, self.appid)
    
    def update_mode_label(self, is_fixed):
        """更新版本模式标签"""
        if self.modeLabel:
            if is_fixed:
                self.modeLabel.setText(tr("fixed_version"))
                self.modeLabel.setTextColor("#ff9800", "#ff9800")
            else:
                self.modeLabel.setText(tr("auto_update"))
                self.modeLabel.setTextColor("#6ee7b7", "#6ee7b7")

    def show_game_detail(self):
        """显示游戏详情对话框"""
        dialog = GameDetailDialog(self.appid, self.game_name, self.window(), self.source_type, self.mode)
        dialog.exec()

    def on_toggle_clicked(self):
        """版本切换按钮点击"""
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, HomePage):
                parent = parent.parent()
            if parent:
                # 构造ST文件名
                filename = f"{self.appid}.lua"
                parent.toggle_st_version(filename, self.appid)

    def copy_cover(self):
        """复制封面URL到剪贴板"""
        cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        QApplication.clipboard().setText(cover_url)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="封面URL已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_appid(self):
        """复制AppID到剪贴板"""
        QApplication.clipboard().setText(self.appid)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="AppID已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_game_name(self):
        """复制游戏名称到剪贴板"""
        QApplication.clipboard().setText(self.game_name)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="游戏名称已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def _show_more_menu(self, pos=None):
        menu = RoundMenu(parent=self)

        # 查看详情
        menu.addAction(Action(FluentIcon.INFO, tr("detail_view_detail"), triggered=self.show_game_detail))
        menu.addSeparator()

        # 复制菜单（二级菜单）
        copy_menu = RoundMenu(parent=self)
        copy_menu.setTitle("复制")
        copy_menu.setIcon(FluentIcon.COPY)

        # 复制封面
        copy_cover_action = Action(FluentIcon.PHOTO, "复制封面", triggered=self.copy_cover)
        if not self.coverLabel.pixmap():
            copy_cover_action.setEnabled(False)
            copy_cover_action.setToolTip("此游戏暂时获取不到封面")
        copy_menu.addAction(copy_cover_action)

        # 复制AppID
        copy_menu.addAction(Action(FluentIcon.CODE, tr("detail_copy_appid"), triggered=self.copy_appid))

        # 复制游戏名称
        copy_name_action = Action(FluentIcon.TAG, "复制游戏名称", triggered=self.copy_game_name)
        if not self.game_name or self.game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'), tr('unknown_game')):
            copy_name_action.setEnabled(False)
            copy_name_action.setToolTip("此游戏暂时获取不到游戏名")
        copy_menu.addAction(copy_name_action)

        menu.addMenu(copy_menu)
        menu.addSeparator()

        menu.addAction(Action(FluentIcon.SHOPPING_CART, tr("detail_view_store_page"), triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://store.steampowered.com/app/{self.appid}"))))
        menu.addAction(Action(FluentIcon.LINK, tr("detail_view_steamdb"), triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://steamdb.info/app/{self.appid}"))))

        # SteamTools 游戏显示切换版本选项
        if self.source_type == "st":
            menu.addSeparator()
            menu.addAction(Action(FluentIcon.UPDATE, tr("toggle_version_mode"), triggered=self.on_toggle_clicked))

        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, tr("delete"), triggered=self.on_delete_clicked))

        # 根据是否有pos参数决定菜单显示位置
        if pos is not None:
            menu.exec(self.mapToGlobal(pos))
        else:
            menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        self._show_more_menu(pos)


class GameCardGrid(CardWidget):
    """游戏卡片组件 - 网格视图模式"""

    def __init__(self, appid, game_name, source_type, parent=None, mode="auto"):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name
        self.source_type = source_type  # 'st' 或 'gl'
        self.mode = mode  # 'auto' 或 'fixed'
        self.cover_loaded = False  # 封面是否已加载

        # 设置右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 创建垂直布局
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(10, 10, 10, 10)
        self.vBoxLayout.setSpacing(8)

        # 游戏封面
        self.coverLabel = QLabel(self)
        self.coverLabel.setFixedSize(180, 84)
        self.coverLabel.setScaledContents(True)
        # 根据主题模式动态设置背景颜色
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        # 监听主题变化
        self.theme_changed()
        # 设置封面可点击，点击打开游戏详情
        self.coverLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coverLabel.mousePressEvent = lambda e: self.show_game_detail()
        
        # 游戏标题
        display_name = game_name
        if not game_name or game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'), tr('unknown_game')):
            display_name = f"AppID: {appid}"
        self.titleLabel = BodyLabel(display_name, self)
        self.titleLabel.setWordWrap(True)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 设置标题的最大高度以允许多行显示，但限制过度增长
        self.titleLabel.setMaximumHeight(60)  # 大约3行文字
        
        # AppID 和来源
        source_text = "SteamTools / OST" if source_type == "st" else "GreenLuma"
        self.infoLabel = CaptionLabel(f"AppID: {appid} | {source_text}", self)
        self.infoLabel.setTextColor("#606060", "#d2d2d2")
        self.infoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 版本模式标签（仅SteamTools）
        self.modeLabel = None
        if source_type == "st":
            mode_text = tr("fixed_version") if mode == "fixed" else tr("auto_update")
            mode_color = "#ff9800" if mode == "fixed" else "#6ee7b7"
            self.modeLabel = CaptionLabel(mode_text, self)
            self.modeLabel.setTextColor(mode_color, mode_color)
            self.modeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 更多按钮
        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)
        self.moreButton.setFixedSize(32, 32)
        self.moreButton.setToolTip("更多")
        self.moreButton.installEventFilter(ToolTipFilter(self.moreButton, showDelay=150, position=ToolTipPosition.TOP))
        self.moreButton.clicked.connect(lambda: self._show_more_menu())

        # 版本切换按钮（仅SteamTools）
        self.toggleButton = None
        if source_type == "st":
            self.toggleButton = TransparentToolButton(FluentIcon.UPDATE, self)
            self.toggleButton.setFixedSize(32, 32)
            self.toggleButton.setToolTip(tr("toggle_version_mode"))
            self.toggleButton.installEventFilter(ToolTipFilter(self.toggleButton, showDelay=150, position=ToolTipPosition.TOP))
            self.toggleButton.clicked.connect(self.on_toggle_clicked)
        
        # 设置布局
        self.setFixedSize(200, 250)
        
        # 添加组件到布局
        self.vBoxLayout.addWidget(self.coverLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(5)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(3)
        self.vBoxLayout.addWidget(self.infoLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(8)
        btnLayout = QHBoxLayout()
        btnLayout.setSpacing(6)
        btnLayout.setContentsMargins(0, 0, 0, 0)
        if self.modeLabel:
            btnLayout.addWidget(self.modeLabel)
        if self.toggleButton:
            btnLayout.addWidget(self.toggleButton)
        btnLayout.addWidget(self.moreButton)
        self.vBoxLayout.addLayout(btnLayout)
        self.vBoxLayout.addSpacing(5)
    
    def theme_changed(self):
        """主题变化时更新样式"""
        if isDarkTheme():
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
            self.setStyleSheet("GameCardGrid { background-color: #2b2b2b; border: none; }")
        else:
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #f0f0f0;")
            self.setStyleSheet("GameCardGrid { background-color: #ffffff; border: none; }")

    def load_cover(self, network_manager=None):
        """加载游戏封面（使用共享的网络管理器）"""
        if self.cover_loaded:
            return
        
        # 先检查缓存
        cached_data = _get_cached_cover(self.appid)
        if cached_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(cached_data):
                self.coverLabel.setPixmap(pixmap)
                self.cover_loaded = True
            return
        
        # 如果没有网络管理器，尝试从父页面获取
        if network_manager is None:
            parent = self.parent()
            while parent:
                if hasattr(parent, 'network_manager'):
                    network_manager = parent.network_manager
                    break
                parent = parent.parent()
        
        if network_manager:
            cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
            request = QNetworkRequest(QUrl(cover_url))
            reply = network_manager.get(request)
            reply.finished.connect(lambda r=reply: self.on_cover_loaded(r))
    
    def set_cover_pixmap(self, pixmap):
        """直接设置封面图片"""
        if pixmap:
            self.coverLabel.setPixmap(pixmap)
            self.cover_loaded = True
    
    @pyqtSlot(QNetworkReply)
    def on_cover_loaded(self, reply):
        """封面加载完成"""
        # 检查对象是否已被删除
        try:
            if not self.coverLabel or sip.isdeleted(self.coverLabel):
                reply.deleteLater()
                return
        except:
            reply.deleteLater()
            return
            
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            # 缓存封面数据
            _cache_cover(self.appid, bytes(data))
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                try:
                    self.coverLabel.setPixmap(pixmap)
                    self.cover_loaded = True
                except RuntimeError:
                    # 对象可能已被删除
                    pass
        reply.deleteLater()
    
    def on_delete_clicked(self):
        """删除按钮点击"""
        # 发送信号给父页面
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, HomePage):
                parent = parent.parent()
            if parent and hasattr(parent, 'delete_game_with_confirm'):
                # 获取游戏名称
                game_name = getattr(self, 'game_name', None)
                parent.delete_game_with_confirm(self.appid, self.source_type, game_name)

    def on_toggle_clicked(self):
        """版本切换按钮点击"""
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, HomePage):
                parent = parent.parent()
            if parent:
                filename = f"{self.appid}.lua"
                parent.toggle_st_version(filename, self.appid)

    def update_mode_label(self, is_fixed):
        """更新版本模式标签"""
        if self.modeLabel:
            if is_fixed:
                self.modeLabel.setText(tr("fixed_version"))
                self.modeLabel.setTextColor("#ff9800", "#ff9800")
            else:
                self.modeLabel.setText(tr("auto_update"))
                self.modeLabel.setTextColor("#6ee7b7", "#6ee7b7")

    def show_game_detail(self):
        """显示游戏详情对话框"""
        dialog = GameDetailDialog(self.appid, self.game_name, self.window(), self.source_type, self.mode)
        dialog.exec()

    def copy_cover(self):
        """复制封面URL到剪贴板"""
        cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        QApplication.clipboard().setText(cover_url)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="封面URL已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_appid(self):
        """复制AppID到剪贴板"""
        QApplication.clipboard().setText(self.appid)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="AppID已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_game_name(self):
        """复制游戏名称到剪贴板"""
        QApplication.clipboard().setText(self.game_name)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="游戏名称已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def _show_more_menu(self, pos=None):
        menu = RoundMenu(parent=self)

        # 查看详情
        menu.addAction(Action(FluentIcon.INFO, tr("detail_view_detail"), triggered=self.show_game_detail))
        menu.addSeparator()

        # 复制菜单（二级菜单）
        copy_menu = RoundMenu(parent=self)
        copy_menu.setTitle("复制")
        copy_menu.setIcon(FluentIcon.COPY)

        # 复制封面
        copy_cover_action = Action(FluentIcon.PHOTO, "复制封面", triggered=self.copy_cover)
        if not self.coverLabel.pixmap():
            copy_cover_action.setEnabled(False)
            copy_cover_action.setToolTip("此游戏暂时获取不到封面")
        copy_menu.addAction(copy_cover_action)

        # 复制AppID
        copy_menu.addAction(Action(FluentIcon.CODE, tr("detail_copy_appid"), triggered=self.copy_appid))

        # 复制游戏名称
        copy_name_action = Action(FluentIcon.TAG, tr("copy_game_name"), triggered=self.copy_game_name)
        if not self.game_name or self.game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'), tr('unknown_game')):
            copy_name_action.setEnabled(False)
            copy_name_action.setToolTip(tr("game_name_unavailable"))
        copy_menu.addAction(copy_name_action)

        menu.addMenu(copy_menu)
        menu.addSeparator()

        menu.addAction(Action(FluentIcon.SHOPPING_CART, tr("detail_view_store_page"), triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://store.steampowered.com/app/{self.appid}"))))
        menu.addAction(Action(FluentIcon.LINK, tr("detail_view_steamdb"), triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://steamdb.info/app/{self.appid}"))))

        # SteamTools 游戏显示切换版本选项
        if self.source_type == "st":
            menu.addSeparator()
            menu.addAction(Action(FluentIcon.UPDATE, tr("toggle_version_mode"), triggered=self.on_toggle_clicked))

        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, tr("delete"), triggered=self.on_delete_clicked))

        # 根据是否有pos参数决定菜单显示位置
        if pos is not None:
            menu.exec(self.mapToGlobal(pos))
        else:
            menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        self._show_more_menu(pos)


# ===== 联机核心服务 (移植自 Cai-Install-Reborn) =====
import ctypes
import tempfile
import threading
import subprocess
import shutil
import re as _re

class SystemCoreService:
    """DLL 扫描注入联机服务"""

    def __init__(self, logger_func, custom_path=None):
        self.logger = logger_func
        self.custom_path = str(custom_path) if custom_path else None
        self.is_64bit = sys.maxsize > 2**32
        self.target_component = "steam_api64.dll" if self.is_64bit else "steam_api.dll"
        self.arch_code = "x64" if self.is_64bit else "x86"
        self.core_lib = None
        self.is_active = False
        self.cache_dir = None
        self.app_proc = None

    def _get_platform_path(self):
        if self.custom_path and os.path.exists(self.custom_path):
            return self.custom_path.replace("/", "\\")
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            return path.replace("/", "\\")
        except Exception:
            return None

    def _get_library_paths(self, base_steam_path):
        library_paths = set()
        if base_steam_path and os.path.exists(base_steam_path):
            library_paths.add(base_steam_path)
        vdf_candidates = [
            os.path.join(base_steam_path, "config", "libraryfolders.vdf"),
            os.path.join(base_steam_path, "steamapps", "libraryfolders.vdf"),
        ]
        for vdf in vdf_candidates:
            if os.path.exists(vdf):
                try:
                    with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for path_str in _re.findall(r'"path"\s+"(.+?)"', content, _re.IGNORECASE):
                        real_path = path_str.replace("\\\\", "\\")
                        if os.path.exists(real_path):
                            library_paths.add(real_path)
                except Exception:
                    pass
                break
        return list(library_paths)

    def _scan_system_components(self):
        main_path = self._get_platform_path()
        if not main_path:
            self.logger("❌ 未检测到 Steam 安装路径")
            return
        all_libraries = self._get_library_paths(main_path)
        self.logger(f"-> 检测到 {len(all_libraries)} 个 Steam 库目录")

        def is_valid_dll(dll_path):
            try:
                try:
                    lib = ctypes.CDLL(dll_path, winmode=0)
                except TypeError:
                    lib = ctypes.CDLL(dll_path)
                return hasattr(lib, "SteamAPI_Init") or bool(getattr(lib, "SteamAPI_Init", None))
            except Exception:
                return False

        yielded = 0
        # 策略1: 优先 Spacewar
        for lib_root in all_libraries:
            spacewar = os.path.join(lib_root, "steamapps", "common", "Spacewar")
            if os.path.exists(spacewar):
                for root, _, files in os.walk(spacewar):
                    if self.target_component in files:
                        found = os.path.join(root, self.target_component)
                        if is_valid_dll(found):
                            self.logger("-> [策略1] 找到 Spacewar DLL，校验通过")
                            yield found
                            yielded += 1
        # 策略2: 全库扫描
        for lib_root in all_libraries:
            search_root = os.path.join(lib_root, "steamapps", "common")
            if not os.path.exists(search_root):
                continue
            try:
                for root, dirs, files in os.walk(search_root):
                    depth = root[len(search_root):].count(os.sep)
                    if depth > 2:
                        del dirs[:]
                        continue
                    if self.target_component in files:
                        lower_root = root.lower()
                        skip = False
                        for x in ["crack", "fix", "emu", "goldberg", "smartsteam"]:
                            if x in lower_root:
                                skip = True
                                break
                        if skip:
                            continue
                        found = os.path.join(root, self.target_component)
                        if is_valid_dll(found):
                            self.logger(f"-> [策略2] 找到备用 DLL: {os.path.basename(root)}")
                            yield found
                            yielded += 1
                            if yielded >= 15:
                                return
            except Exception:
                pass

    def start_service(self, target_exe, app_id, on_finish_callback):
        self.is_active = True

        def _service_thread():
            dll_cookies = []
            original_cwd = os.getcwd()
            success = False
            try:
                self.logger(f"-> 配置协议 ID: {app_id}")
                for comp_path in self._scan_system_components():
                    self.logger(f"-> 尝试组件: {comp_path}")
                    self.cache_dir = tempfile.mkdtemp(prefix="SysCache_")
                    dest_path = os.path.join(self.cache_dir, os.path.basename(comp_path))
                    try:
                        shutil.copy2(comp_path, dest_path)
                        with open(os.path.join(self.cache_dir, "steam_appid.txt"), "w") as f:
                            f.write(str(app_id))
                    except Exception as e:
                        self.logger(f"   ❌ 缓存写入失败: {e}")
                        continue
                    os.chdir(self.cache_dir)
                    try:
                        if hasattr(os, "add_dll_directory"):
                            try:
                                dll_cookies.append(os.add_dll_directory(self.cache_dir))
                                dll_cookies.append(os.add_dll_directory(os.path.dirname(comp_path)))
                            except Exception:
                                pass
                        try:
                            self.core_lib = ctypes.CDLL(dest_path, winmode=0)
                        except TypeError:
                            self.core_lib = ctypes.CDLL(dest_path)
                        if not self.core_lib.SteamAPI_Init():
                            self.logger("   ❌ Steam API 初始化失败，尝试下一个...")
                            try:
                                import _ctypes
                                _ctypes.FreeLibrary(self.core_lib._handle)
                            except Exception:
                                pass
                            self.core_lib = None
                            os.chdir(original_cwd)
                            continue
                        self.logger("✅ Steam API 连接成功")
                        success = True
                        break
                    except OSError as e:
                        self.logger(f"   ❌ DLL 加载失败: {e}")
                        os.chdir(original_cwd)
                        continue
                os.chdir(original_cwd)
                if not success:
                    self.logger("❌ 所有 DLL 均无法连接 Steam，请确认 Steam 已登录")
                    on_finish_callback()
                    return
                if target_exe and os.path.exists(target_exe):
                    self.logger(f"-> 启动游戏: {os.path.basename(target_exe)}")
                    try:
                        self.app_proc = subprocess.Popen(
                            [target_exe], cwd=os.path.dirname(target_exe), shell=True
                        )
                        self.logger(f"-> 游戏运行中 (PID: {self.app_proc.pid})")
                    except Exception as e:
                        self.logger(f"❌ 启动游戏失败: {e}")
                self.logger("-> ⏳ 服务运行中，关闭游戏后自动停止...")
                import time
                while self.is_active:
                    if self.app_proc and self.app_proc.poll() is not None:
                        self.logger("-> 游戏已关闭")
                        break
                    time.sleep(1)
            except Exception as e:
                self.logger(f"系统错误: {e}")
            finally:
                os.chdir(original_cwd)
                for cookie in dll_cookies:
                    try:
                        cookie.close()
                    except Exception:
                        pass
                self.stop_routine()
                on_finish_callback()

        threading.Thread(target=_service_thread, daemon=True).start()

    def stop_routine(self):
        self.is_active = False
        if self.app_proc:
            try:
                if self.app_proc.poll() is None:
                    subprocess.call(
                        ["taskkill", "/F", "/T", "/PID", str(self.app_proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
            except Exception:
                pass
            self.app_proc = None
        if self.core_lib:
            try:
                self.core_lib.SteamAPI_Shutdown()
            except Exception:
                pass
            self.core_lib = None
        if self.cache_dir and os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir, ignore_errors=True)

    def stop(self):
        self.is_active = False


class AppIDChangerService:
    """AppID Changer 联机服务 - 直接修改 steam_appid.txt 文件"""

    def __init__(self, logger_func):
        self.logger = logger_func
        self.is_active = False
        self.app_proc = None
        self.original_appid = None
        self.appid_txt_path = None
        self._monitor_thread = None

    def start_service(self, exe_path: str, app_id: str, on_finish_callback):
        """启动 AppID Changer 服务"""
        self.is_active = True

        def _service_thread():
            try:
                if not exe_path or not os.path.exists(exe_path):
                    self.logger("❌ 游戏可执行文件不存在")
                    on_finish_callback()
                    return

                work_dir = os.path.dirname(exe_path)
                self.appid_txt_path = os.path.join(work_dir, "steam_appid.txt")

                # 检查 steam_appid.txt 是否存在
                if not os.path.exists(self.appid_txt_path):
                    self.logger(f"❌ {tr('launcher_changer_no_appid_txt')}")
                    on_finish_callback()
                    return

                # 读取原始 AppID
                try:
                    with open(self.appid_txt_path, "r", encoding="utf-8") as f:
                        self.original_appid = f.read().strip()
                    self.logger(f"-> 原始 AppID: {self.original_appid}")
                except Exception as e:
                    self.logger(f"❌ {tr('launcher_changer_backup_failed')}: {e}")
                    on_finish_callback()
                    return

                # 写入新的 AppID
                try:
                    with open(self.appid_txt_path, "w", encoding="utf-8") as f:
                        f.write(app_id)
                    self.logger(f"-> 已修改 AppID 为: {app_id}")
                except Exception as e:
                    self.logger(f"❌ {tr('launcher_changer_write_failed')}: {e}")
                    on_finish_callback()
                    return

                # 启动游戏
                try:
                    self.app_proc = subprocess.Popen(
                        [exe_path],
                        cwd=work_dir,
                        shell=True
                    )
                    self.logger(f"✅ {tr('launcher_changer_success')} (PID: {self.app_proc.pid})")
                except Exception as e:
                    self.logger(f"❌ {tr('launcher_changer_launch_failed')}: {e}")
                    # 恢复原始 AppID
                    self._restore_appid()
                    on_finish_callback()
                    return

                # 等待游戏关闭
                self.logger("-> ⏳ 等待游戏关闭...")
                while self.is_active:
                    if self.app_proc and self.app_proc.poll() is not None:
                        self.logger("-> 游戏已关闭")
                        break
                    import time
                    time.sleep(1)

                # 恢复原始 AppID
                self._restore_appid()

            except Exception as e:
                self.logger(f"系统错误: {e}")
            finally:
                on_finish_callback()

        self._monitor_thread = threading.Thread(target=_service_thread, daemon=True)
        self._monitor_thread.start()

    def _restore_appid(self):
        """恢复原始 AppID"""
        if self.appid_txt_path and self.original_appid is not None:
            try:
                with open(self.appid_txt_path, "w", encoding="utf-8") as f:
                    f.write(self.original_appid)
                self.logger(f"✅ {tr('launcher_changer_restored')}: {self.original_appid}")
            except Exception as e:
                self.logger(f"❌ 恢复原始 AppID 失败: {e}")

    def stop(self):
        """停止服务"""
        self.is_active = False
        if self.app_proc:
            try:
                if self.app_proc.poll() is None:
                    subprocess.call(
                        ["taskkill", "/F", "/T", "/PID", str(self.app_proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
            except Exception:
                pass
            self.app_proc = None


class AsyncWorker(QThread):
    """异步工作线程"""
    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, coro, parent=None):
        super().__init__(parent)
        self.coro = coro
        self._loop = None
        self._cancelled = False
        self._finished = False
    
    def cancel(self):
        """请求取消：取消所有 asyncio 任务并关闭事件循环"""
        self._cancelled = True
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._cancel_all_tasks)
            except Exception:
                pass

    def _cancel_all_tasks(self):
        if self._loop and not self._loop.is_closed():
            for task in asyncio.all_tasks(self._loop):
                task.cancel()

    def run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            result = self._loop.run_until_complete(self.coro)
            if not self._cancelled:
                self.result_ready.emit(result)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))
        finally:
            if self._loop:
                try:
                    pending = asyncio.all_tasks(self._loop)
                    if pending:
                        for task in pending:
                            task.cancel()
                        self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    if not self._loop.is_closed():
                        self._loop.close()
                except Exception:
                    pass
                finally:
                    self._loop = None
            self._finished = True
    
    def isFinished(self):
        """检查线程是否已完成"""
        return self._finished or super().isFinished()


def _replace_worker(old_worker):
    """安全停止旧 worker，等待线程真正结束后返回。"""
    if old_worker is not None:
        try:
            if old_worker.isRunning():
                old_worker.cancel()
                # 等待线程结束，最多等待5秒
                if not old_worker.wait(5000):
                    old_worker.terminate()
                    old_worker.wait(1000)
            # 确保线程已结束再删除
            if old_worker.isFinished():
                old_worker.deleteLater()
        except RuntimeError:
            pass
        except Exception:
            pass

class HomePage(ScrollArea):
    """已入库的游戏页面（主页）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        self.setWidgetResizable(True)
        
        # 共享的网络管理器（所有卡片共用一个）
        self.network_manager = QNetworkAccessManager(self)
        
        # 主容器
        container = QWidget()
        container.setObjectName("homeContainer")
        self.setWidget(container)
        
        self.mainLayout = QVBoxLayout(container)
        self.mainLayout.setContentsMargins(30, 30, 30, 30)
        self.mainLayout.setSpacing(20)
        
        # 标题和统计
        header_layout = QHBoxLayout()
        self.title = SubtitleLabel(tr("installed_games"), self)
        self.stats_label = CaptionLabel(tr("loading"), self)
        self.stats_label.setTextColor("#606060", "#d2d2d2")
        
        # 添加刷新按钮
        self.refresh_button = TransparentToolButton(FluentIcon.SYNC, self)
        self.refresh_button.setFixedSize(32, 32)
        self.refresh_button.clicked.connect(self.refresh_games)
        self.refresh_button.setToolTip("刷新游戏列表")
        
        header_layout.addWidget(self.title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.stats_label)
        header_layout.addWidget(self.refresh_button)
        self.mainLayout.addLayout(header_layout)
        
        # 搜索框和视图/排序选项
        search_row_layout = QHBoxLayout()
        
        # 搜索输入框
        self.filter_input = SearchLineEdit(self)
        self.filter_input.setPlaceholderText(tr("search_placeholder"))
        self.filter_input.setFixedHeight(35)
        self.filter_input.textChanged.connect(self.on_filter_changed)
        self.filter_input.searchSignal.connect(self.on_filter_changed)
        self.filter_input.clearSignal.connect(self.on_filter_cleared)
        search_row_layout.addWidget(self.filter_input)
        
        # 视图模式选择
        self.view_mode_label = QLabel(tr("view_mode") + ":", self)
        self.view_mode_label.setStyleSheet("color: #000000;" if not isDarkTheme() else "color: #ffffff;")
        self.view_mode_combo = ComboBox(self)
        self.view_mode_combo.addItems([tr("view_list"), tr("view_grid")])
        self.view_mode_combo.setCurrentIndex(0)
        self.view_mode_combo.setFixedWidth(100)
        self.view_mode_combo.currentIndexChanged.connect(self.on_view_mode_changed)
        search_row_layout.addWidget(self.view_mode_label)
        search_row_layout.addWidget(self.view_mode_combo)
        search_row_layout.addSpacing(10)
        
        # 排序选择
        self.sort_label = QLabel(tr("sort_mode") + ":", self)
        self.sort_label.setStyleSheet("color: #000000;" if not isDarkTheme() else "color: #ffffff;")
        self.sort_combo = ComboBox(self)
        self.sort_combo.addItems([tr("sort_default"), tr("sort_az"), tr("sort_za")])
        self.sort_combo.setCurrentIndex(0)
        self.sort_combo.setFixedWidth(100)
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        search_row_layout.addWidget(self.sort_label)
        search_row_layout.addWidget(self.sort_combo)
        
        self.mainLayout.addLayout(search_row_layout)
        
        # 游戏卡片容器 - 支持列表和卡片视图
        self.card_container = QWidget(self)
        self.list_layout = QVBoxLayout()
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        
        # 卡片视图使用网格布局
        self.grid_layout = SafeFlowLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(15)
        
        # 先读取保存的视图模式再设置布局，避免 Qt 忽略重复 setLayout 调用
        self.current_view_mode = self._read_view_mode_config("home_view_mode")
        if self.current_view_mode == "grid":
            self.card_layout = self.grid_layout
            self.card_container.setLayout(self.grid_layout)
        else:
            self.current_view_mode = "grid"
            self.card_layout = self.grid_layout
            self.card_container.setLayout(self.grid_layout)
        
        self.mainLayout.addWidget(self.card_container)
        self.mainLayout.addStretch(1)

        # 设置透明背景
        self.setStyleSheet("HomePage { background: transparent; }")
        container.setStyleSheet("QWidget#homeContainer { background: transparent; }")

        # 标记需要加载游戏列表
        self._games_loaded = False
        self.worker = None
        self.game_cards = []
        self.all_games_data = []  # 存储所有游戏数据用于过滤
        self.filtered_games_data = []  # 存储过滤后的游戏数据
        self._cover_load_timer = None  # 延迟加载定时器
        
        # 加载视图和排序设置（仅同步 combo UI，布局已在上方设置）
        self.load_view_mode_preference()
        self.load_sort_mode_preference()

        # 启动时立即加载游戏列表
        self.load_games()
    
    def showEvent(self, event):
        """页面显示时触发延迟加载"""
        super().showEvent(event)
        # 延迟加载可视区域内的封面
        QTimer.singleShot(100, self._load_visible_covers)
        
    def wheelEvent(self, event):
        """滚动时触发延迟加载"""
        super().wheelEvent(event)
        self._schedule_cover_load()
    
    def _schedule_cover_load(self):
        """调度封面延迟加载"""
        if self._cover_load_timer:
            self._cover_load_timer.stop()
        self._cover_load_timer = QTimer.singleShot(200, self._load_visible_covers)
    
    def _load_visible_covers(self):
        """加载可视区域内的封面图片"""
        if not self.game_cards:
            return
        
        viewport_rect = self.viewport().rect()
        
        for card in self.game_cards:
            # 检查卡片是否在可视区域内（扩大100像素的缓冲区域）
            card_global_pos = card.mapTo(self.viewport(), QPoint(0, 0))
            card_rect = QRect(card_global_pos, card.size())
            
            # 检查是否有重叠
            if viewport_rect.intersects(card_rect.adjusted(-100, -100, 100, 100)):
                card.load_cover(self.network_manager)
    
    def load_games(self):
        """加载游戏列表（两阶段：先快速显示文件列表，再后台加载游戏名称）"""
        async def _load():
            async with CaiBackend() as backend:
                await backend.initialize()
                files_data = await backend.get_managed_files(get_steam_lang(current_language))
                return files_data

        _replace_worker(getattr(self, 'worker', None))
        self.worker = AsyncWorker(_load())
        self.worker.result_ready.connect(self.on_games_loaded)
        self.worker.error.connect(self.on_load_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _load_missing_names(self, files_data):
        """后台加载缺失的游戏名称"""
        # 过滤掉没有有效appID的游戏，避免无效请求
        st_games = files_data.get('st', [])
        gl_games = files_data.get('gl', [])
        
        # 检查是否有需要加载名称的游戏（有有效appID且名称为空或未找到）
        needs_name_load = False
        for game in st_games + gl_games:
            appid = game.get('appid', '')
            game_name = game.get('game_name', '')
            if appid and appid != 'N/A' and (not game_name or game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'))):
                # 检查是否已在缓存中
                if not _get_cached_name(appid):
                    needs_name_load = True
                    break
        
        # 如果没有需要加载名称的游戏，直接返回
        if not needs_name_load:
            return
        
        async def _fetch():
            async with CaiBackend() as backend:
                await backend.initialize()
                info_result = await backend.fetch_game_info_batch(
                    files_data, 
                    get_steam_lang(current_language)
                )
                return info_result

        _replace_worker(getattr(self, '_name_worker', None))
        self._name_worker = AsyncWorker(_fetch())
        self._name_worker.result_ready.connect(lambda result: self._update_card_info(result))
        self._name_worker.finished.connect(self._name_worker.deleteLater)
        self._name_worker.start()

    def _update_card_info(self, info_result):
        """用后台加载的信息更新已显示的卡片（仅名称）"""
        if not info_result:
            return
        
        name_map = info_result.get('names', {})
        
        for card in self.game_cards:
            appid = getattr(card, 'appid', None)
            if not appid:
                continue
            
            # 更新名称并缓存
            if appid in name_map:
                name = name_map[appid]
                if name and name not in ('名称未找到', '获取失败', 'Unknown'):
                    # 保存到缓存
                    _cache_name(appid, name)
                if hasattr(card, 'titleLabel'):
                    card.titleLabel.setText(name)

    def __del__(self):
        """析构函数，确保清理所有worker"""
        self.cleanup_workers()
    
    def cleanup_workers(self):
        """清理所有worker线程"""
        for attr in ('worker', '_name_worker', 'delete_worker', 'toggle_worker'):
            worker = getattr(self, attr, None)
            if worker:
                try:
                    if worker.isRunning():
                        worker.cancel()
                        # 等待线程结束，最多等待5秒
                        if not worker.wait(5000):
                            worker.terminate()
                            worker.wait(1000)
                    # 确保线程已结束再删除
                    if worker.isFinished():
                        worker.deleteLater()
                except Exception:
                    pass
                setattr(self, attr, None)
    
    def refresh_games(self):
        """刷新游戏列表"""
        # 显示刷新动画
        self.refresh_button.setEnabled(False)
        if hasattr(self.refresh_button, 'setSpinning'):
            self.refresh_button.setSpinning(True)
        
        # 重新加载游戏列表
        self.load_games()
        
        # 恢复刷新按钮状态（在加载完成后）
        if self.worker:
            self.worker.result_ready.connect(lambda: self.on_refresh_complete())
            self.worker.error.connect(lambda: self.on_refresh_complete())
    
    def on_refresh_complete(self):
        """刷新完成"""
        self.refresh_button.setEnabled(True)
        if hasattr(self.refresh_button, 'setSpinning'):
            self.refresh_button.setSpinning(False)
    
    @pyqtSlot(object)
    def on_games_loaded(self, files_data):
        """游戏加载完成"""
        try:
            # 清空现有卡片（先从布局移除再销毁）
            for card in self.game_cards:
                self.card_layout.removeWidget(card)
                card.deleteLater()
            self.game_cards.clear()
            
            # 统计游戏数量
            st_games = files_data.get('st', [])
            gl_games = files_data.get('gl', [])
            total = len(st_games) + len(gl_games)
            
            self.stats_label.setText(tr("total_games", total, len(st_games), len(gl_games)))
            
            # 创建游戏数据列表
            self.all_games_data = []
            for game in st_games:
                if game.get('status') != 'core_file':  # 跳过核心文件
                    self.all_games_data.append(('st', game))
            for game in gl_games:
                self.all_games_data.append(('gl', game))
            
            # 按 AppID 排序（降序）
            def get_appid_sort_key(x):
                appid = x[1].get('appid', '0')
                if appid.isdigit():
                    return int(appid)
                return 0
            self.all_games_data.sort(key=get_appid_sort_key, reverse=True)
            
            # 显示所有游戏
            self.display_games(self.all_games_data)

            # 后台加载缺失的游戏名称
            self._load_missing_names(files_data)
                
        except Exception as e:
            self.stats_label.setText(f"{tr('data_process_failed')}: {str(e)}")
    
    def _load_cover_from_cache(self, card):
        """从缓存加载封面图片（同步加载，无网络请求）"""
        appid = getattr(card, 'appid', None)
        if not appid:
            return
        
        # 先检查内存缓存，再检查磁盘缓存
        cached_data = _get_cached_cover(appid)
        if cached_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(cached_data):
                card.set_cover_pixmap(pixmap)
    
    def display_games(self, games_data):
        """显示游戏列表"""
        # 清空现有卡片（先从布局移除再销毁，避免布局状态混乱导致图片不显示）
        for card in self.game_cards:
            self.card_layout.removeWidget(card)
            card.deleteLater()
        self.game_cards.clear()
        
        # 根据排序选项对游戏数据进行排序
        sorted_games = self.sort_games(games_data)
        
        # 添加卡片
        for source_type, game in sorted_games:
            appid = game.get('appid', 'N/A')
            game_name = game.get('game_name', '')
            mode = game.get('mode', 'auto')  # 获取版本模式信息
            
            # 如果游戏名称为空或显示为"名称未找到"，尝试从缓存获取
            if not game_name or game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed')):
                cached_name = _get_cached_name(appid)
                if cached_name:
                    game_name = cached_name
                else:
                    game_name = f"AppID {appid}"
            
            # 根据视图模式创建不同类型的卡片
            if self.current_view_mode == "grid":
                card = GameCardGrid(appid, game_name, source_type, self, mode)
            else:
                card = GameCard(appid, game_name, source_type, self, mode)
            
            # 立即从缓存加载封面（如果有缓存）
            self._load_cover_from_cache(card)
            
            self.card_layout.addWidget(card)
            self.game_cards.append(card)
        
        if not sorted_games:
            empty_label = BodyLabel(tr("no_games"), self)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(empty_label)
            self.game_cards.append(empty_label)
    
    def notify_theme_changed(self):
        """通知所有游戏卡片主题已变化"""
        # 更新所有游戏卡片的封面背景颜色
        for card in self.game_cards:
            if hasattr(card, 'theme_changed'):
                card.theme_changed()
    
    def sort_games(self, games_data):
        """根据排序选项对游戏进行排序"""
        sort_mode = self.sort_combo.currentText()

        def get_name_key(x):
            return x[1].get('game_name', f"AppID {x[1].get('appid', '0')}")

        def get_appid_key(x):
            appid = x[1].get('appid', '0')
            if appid.isdigit():
                return int(appid)
            return 0

        if sort_mode == tr("sort_az"):
            return sorted(games_data, key=get_name_key)
        elif sort_mode == tr("sort_za"):
            return sorted(games_data, key=get_name_key, reverse=True)
        else:  # 默认 - 按AppID降序
            return sorted(games_data, key=get_appid_key, reverse=True)
    
    def on_view_mode_changed(self):
        """视图模式改变"""
        view_mode = self.view_mode_combo.currentText()
        
        # 保存当前过滤状态
        current_filter = self.filter_input.text()
        
        # 先清空现有卡片，避免布局问题
        for card in self.game_cards:
            if hasattr(self, 'card_layout') and self.card_layout:
                self.card_layout.removeWidget(card)
            card.deleteLater()
        self.game_cards.clear()
        
        # 移除现有容器
        if hasattr(self, 'card_container') and self.card_container:
            self.mainLayout.removeWidget(self.card_container)
            self.card_container.deleteLater()
        
        # 创建新的容器和布局
        self.card_container = QWidget(self)
        
        if view_mode == tr("view_list"):
            self.current_view_mode = "list"
            self.list_layout = QVBoxLayout()  # 创建新布局
            self.list_layout.setContentsMargins(0, 0, 0, 0)
            self.list_layout.setSpacing(10)
            self.card_layout = self.list_layout
            self.card_container.setLayout(self.list_layout)
        else:  # 卡片视图
            self.current_view_mode = "grid"
            self.grid_layout = SafeFlowLayout()  # 创建新布局
            self.grid_layout.setContentsMargins(0, 0, 0, 0)
            self.grid_layout.setSpacing(15)
            self.card_layout = self.grid_layout
            self.card_container.setLayout(self.grid_layout)
        
        # 重新添加到布局
        self.mainLayout.insertWidget(2, self.card_container)
        
        # 保存视图模式偏好
        self.save_view_mode_preference()
        
        # 重新显示当前游戏
        self.filter_input.setText(current_filter)
        self.on_filter_changed()
    
    def on_sort_changed(self):
        """排序方式改变"""
        # 保存排序模式偏好
        self.save_sort_mode_preference()
        
        # 重新显示当前游戏
        self.on_filter_changed()
    
    def on_filter_changed(self):
        """搜索过滤"""
        query = self.filter_input.text().strip().lower()
        
        if not query:
            # 显示所有游戏
            self.display_games(self.all_games_data)
            return
        
        # 过滤游戏
        filtered_games = []
        for source_type, game in self.all_games_data:
            appid = game.get('appid', '')
            game_name = game.get('game_name', '').lower()
            
            # 匹配 AppID 或游戏名称
            if query in appid or query in game_name:
                filtered_games.append((source_type, game))
        
        self.display_games(filtered_games)
    
    def on_filter_cleared(self):
        """清除搜索"""
        self.display_games(self.all_games_data)
    
    def delete_game_with_confirm(self, appid, source_type, game_name=None):
        """在主窗口显示确认删除对话框并执行删除
        
        Args:
            appid: 游戏AppID
            source_type: 来源类型 ('st' 或 'gl')
            game_name: 游戏名称，用于显示在确认对话框中
        """
        display_name = game_name if game_name else f"AppID {appid}"
        
        # 在主窗口显示确认对话框
        dialog = MessageBox(
            tr("confirm_delete"),
            tr("delete_message", display_name),
            self
        )
        
        if dialog.exec():
            # 用户确认删除，调用删除方法
            self.delete_game(appid, source_type, None)
    
    def delete_game(self, appid, source_type, parent_widget=None):
        """删除游戏
        
        Args:
            appid: 游戏AppID
            source_type: 来源类型 ('st' 或 'gl')
            parent_widget: 可选的父窗口，用于显示提示。如果为None则使用self
        """
        # 确定父窗口
        info_parent = parent_widget if parent_widget else self
        
        # 直接执行删除（确认对话框已在 delete_game_with_confirm 中处理）
        async def _delete():
            async with CaiBackend() as backend:
                await backend.initialize()
                
                # 构造删除项
                items = [{
                    'appid': appid,
                    'filename': f'{appid}.lua' if source_type == 'st' else f'{appid}.txt'
                }]
                
                result = backend.delete_managed_files(source_type, items)
                return result
        
        _replace_worker(getattr(self, 'delete_worker', None))
        self.delete_worker = AsyncWorker(_delete())
        # 传递parent_widget给完成回调
        self.delete_worker.result_ready.connect(lambda result: self.on_delete_complete(result, appid, parent_widget))
        self.delete_worker.error.connect(lambda error: self.on_delete_error(error, parent_widget))
        self.delete_worker.finished.connect(self.delete_worker.deleteLater)
        self.delete_worker.start()
        
        InfoBar.info(
            title=tr("deleting"),
            content=f"{tr('deleting')} AppID {appid}...",
            parent=info_parent.window() if info_parent else self.window(),
            position=InfoBarPosition.TOP
        )
    
    @pyqtSlot(object)
    def on_delete_complete(self, result, appid, parent_widget=None):
        """删除完成"""
        info_parent = parent_widget if parent_widget else self
        
        if result.get('success'):
            InfoBar.success(
                title=tr("delete_success"),
                content=f"AppID {appid} {tr('delete_success')}",
                parent=info_parent,
                position=InfoBarPosition.TOP
            )
            # 重新加载游戏列表
            self._games_loaded = False
            self.load_games()
        else:
            InfoBar.error(
                title=tr("delete_failed"),
                content=result.get('message', tr('unknown_error')),
                parent=info_parent,
                position=InfoBarPosition.TOP
            )
    
    @pyqtSlot(str)
    def on_delete_error(self, error, parent_widget=None):
        """删除失败"""
        info_parent = parent_widget if parent_widget else self
        InfoBar.error(
            title=tr("delete_failed"),
            content=error,
            parent=info_parent,
            position=InfoBarPosition.TOP
        )

    def toggle_st_version(self, filename, appid, parent_widget=None):
        """切换ST文件版本模式（自动更新/固定版本）
        
        Args:
            filename: ST文件名
            appid: 游戏AppID
            parent_widget: 可选的父窗口，用于显示提示。如果为None则使用self
        """
        info_parent = parent_widget if parent_widget else self
        
        async def _toggle():
            async with CaiBackend() as backend:
                await backend.initialize()
                result = await backend.toggle_st_version(filename)
                return result
        
        _replace_worker(getattr(self, 'toggle_worker', None))
        self.toggle_worker = AsyncWorker(_toggle())
        self.toggle_worker.result_ready.connect(lambda result: self.on_toggle_st_version_complete(result, appid, parent_widget))
        self.toggle_worker.error.connect(lambda error: self.on_toggle_st_version_error(error, parent_widget))
        self.toggle_worker.finished.connect(self.toggle_worker.deleteLater)
        self.toggle_worker.start()
        
        InfoBar.info(
            title="版本切换",
            content=f"正在切换 AppID {appid} 的版本模式...",
            parent=info_parent,
            position=InfoBarPosition.TOP
        )
    
    @pyqtSlot(object)
    @pyqtSlot(object)
    def on_toggle_st_version_complete(self, result, appid, parent_widget=None):
        """ST文件版本切换完成"""
        info_parent = parent_widget if parent_widget else self

        if result.get('success'):
            InfoBar.success(
                title="切换成功",
                content=result.get('message', '版本模式已切换'),
                parent=info_parent,
                position=InfoBarPosition.TOP,
                duration=4000
            )
            for card in self.game_cards:
                if hasattr(card, 'appid') and card.appid == appid and hasattr(card, 'source_type') and card.source_type == 'st':
                    message = result.get('message', '')
                    is_fixed = '固定版本' in message
                    card.update_mode_label(is_fixed)
                    break
        else:
            InfoBar.error(
                title="切换失败",
                content=result.get('message', '未知错误'),
                parent=info_parent,
                position=InfoBarPosition.TOP
            )

    @pyqtSlot(str)
    def on_toggle_st_version_error(self, error, parent_widget=None):
        """ST文件版本切换失败"""
        info_parent = parent_widget if parent_widget else self
        InfoBar.error(
            title="切换失败",
            content=error,
            parent=info_parent,
            position=InfoBarPosition.TOP
        )

    def save_view_mode_preference(self):
        """保存视图模式设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 保存视图模式
            config["home_view_mode"] = self.current_view_mode
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存视图模式失败: {e}")
    
    def _read_view_mode_config(self, key):
        """从配置文件读取视图模式，不操作任何 UI"""
        try:
            import json
            config_path = APP_ROOT / 'config' / 'config.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get(key, "grid")
        except Exception:
            pass
        return "grid"

    def load_view_mode_preference(self):
        """同步 combo UI（布局已在 __init__ 中正确设置）"""
        try:
            self.view_mode_combo.currentIndexChanged.disconnect(self.on_view_mode_changed)
            self.view_mode_combo.setCurrentIndex(0 if self.current_view_mode == "list" else 1)
            self.view_mode_combo.currentIndexChanged.connect(self.on_view_mode_changed)
        except Exception as e:
            print(f"加载视图模式偏好失败: {e}")
    
    def load_sort_mode_preference(self):
        """加载排序模式设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的排序模式
                saved_sort_mode = config.get("home_sort_mode", "default")
                
                # 更新UI
                # 断开信号，避免触发保存
                self.sort_combo.currentIndexChanged.disconnect(self.on_sort_changed)
                if saved_sort_mode == "az":
                    self.sort_combo.setCurrentIndex(1)
                elif saved_sort_mode == "za":
                    self.sort_combo.setCurrentIndex(2)
                else:
                    self.sort_combo.setCurrentIndex(0)
                self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
                
        except Exception as e:
            print(f"加载排序模式偏好失败: {e}")
    
    def save_sort_mode_preference(self):
        """保存排序模式设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # 获取当前排序模式
            current_index = self.sort_combo.currentIndex()
            if current_index == 1:
                sort_mode = "az"
            elif current_index == 2:
                sort_mode = "za"
            else:
                sort_mode = "default"
            
            # 保存排序模式
            config["home_sort_mode"] = sort_mode
            
            # 写入配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"保存排序模式偏好失败: {e}")
    
    @pyqtSlot(str)
    def on_load_error(self, error):
        """加载失败"""
        self.stats_label.setText(tr("load_failed", error))


class SearchResultCard(CardWidget):
    """搜索结果卡片组件"""

    def __init__(self, appid, game_name, parent=None):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name

        # 设置透明边框
        self.setStyleSheet("""
            SearchResultCard {
                border: none;
                background: transparent;
            }
        """)
        
        # 设置右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 网络管理器
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self.on_cover_loaded)

        # 创建布局
        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()
        
        # 游戏封面
        self.coverLabel = QLabel(self)
        self.coverLabel.setFixedSize(120, 56)
        self.coverLabel.setScaledContents(True)
        # 根据主题模式动态设置背景颜色 - 暗色主题使用更深的颜色
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #1a1a1a;")
        # 监听主题变化
        self.theme_changed()
        # 设置封面可点击，点击打开游戏详情
        self.coverLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coverLabel.mousePressEvent = lambda e: self.show_game_detail()
        
        # 游戏标题
        self.titleLabel = BodyLabel(game_name, self)
        self.titleLabel.setWordWrap(False)
        
        # AppID
        self.infoLabel = CaptionLabel(f"AppID: {appid}", self)
        self.infoLabel.setTextColor("#606060", "#d2d2d2")
        
        # 入库按钮（图标样式，和主页删除按钮一致）
        self.selectButton = TransparentToolButton(FluentIcon.CLOUD_DOWNLOAD, self)
        self.selectButton.setFixedSize(32, 32)
        self.selectButton.setToolTip("入库")
        self.selectButton.installEventFilter(ToolTipFilter(self.selectButton, showDelay=150, position=ToolTipPosition.TOP))
        self.selectButton.clicked.connect(self.on_select_clicked)

        # 更多按钮
        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)
        self.moreButton.setFixedSize(32, 32)
        self.moreButton.setToolTip("更多")
        self.moreButton.installEventFilter(ToolTipFilter(self.moreButton, showDelay=150, position=ToolTipPosition.TOP))
        self.moreButton.clicked.connect(lambda: self._show_more_menu())

        # 设置布局
        self.setFixedHeight(80)
        self.hBoxLayout.setContentsMargins(15, 12, 15, 12)
        self.hBoxLayout.setSpacing(15)
        
        self.hBoxLayout.addWidget(self.coverLabel)
        
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(4)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.vBoxLayout.addWidget(self.infoLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.hBoxLayout.addLayout(self.vBoxLayout)
        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.selectButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addWidget(self.moreButton, 0, Qt.AlignmentFlag.AlignRight)
        
        # 加载封面
        self.load_cover()
    
    def theme_changed(self):
        """主题变化时更新样式"""
        if isDarkTheme():
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #1a1a1a;")
        else:
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #f0f0f0;")
    
    def load_cover(self):
        """加载游戏封面"""
        cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        request = QNetworkRequest(QUrl(cover_url))
        self.network_manager.get(request)
    
    @pyqtSlot(QNetworkReply)
    def on_cover_loaded(self, reply):
        """封面加载完成"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.coverLabel.setPixmap(pixmap)
        reply.deleteLater()
    
    def on_select_clicked(self):
        """入库按钮点击 - 直接入库"""
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, SearchPage):
                parent = parent.parent()
            if parent:
                parent.unlock_game_direct(self.appid, self.game_name)

    def copy_cover(self):
        """复制封面URL到剪贴板"""
        cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        QApplication.clipboard().setText(cover_url)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="封面URL已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_appid(self):
        """复制AppID到剪贴板"""
        QApplication.clipboard().setText(self.appid)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="AppID已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_game_name(self):
        """复制游戏名称到剪贴板"""
        QApplication.clipboard().setText(self.game_name)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="游戏名称已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def show_game_detail(self):
        """显示游戏详情对话框"""
        dialog = GameDetailDialog(self.appid, self.game_name, self.window())
        dialog.exec()

    def _show_more_menu(self, pos=None):
        menu = RoundMenu(parent=self)

        # 查看详情
        menu.addAction(Action(FluentIcon.INFO, tr("detail_view_detail"), triggered=self.show_game_detail))
        menu.addSeparator()

        # 入库选项
        menu.addAction(Action(FluentIcon.CLOUD_DOWNLOAD, tr("detail_add_to_library"), triggered=self.on_select_clicked))
        menu.addSeparator()

        # 复制菜单（二级菜单）
        copy_menu = RoundMenu(parent=self)
        copy_menu.setTitle(tr("copy"))
        copy_menu.setIcon(FluentIcon.COPY)

        # 复制封面
        copy_cover_action = Action(FluentIcon.PHOTO, tr("copy_cover"), triggered=self.copy_cover)
        if not self.coverLabel.pixmap():
            copy_cover_action.setEnabled(False)
            copy_cover_action.setToolTip(tr("cover_unavailable"))
        copy_menu.addAction(copy_cover_action)

        # 复制AppID
        copy_menu.addAction(Action(FluentIcon.CODE, tr("detail_copy_appid"), triggered=self.copy_appid))

        # 复制游戏名称
        copy_name_action = Action(FluentIcon.TAG, tr("copy_game_name"), triggered=self.copy_game_name)
        if not self.game_name or self.game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'), tr('unknown_game')):
            copy_name_action.setEnabled(False)
            copy_name_action.setToolTip(tr("game_name_unavailable"))
        copy_menu.addAction(copy_name_action)

        menu.addMenu(copy_menu)
        menu.addSeparator()

        menu.addAction(Action(FluentIcon.SHOPPING_CART, tr("detail_view_store_page"), triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://store.steampowered.com/app/{self.appid}"))))
        menu.addAction(Action(FluentIcon.LINK, tr("detail_view_steamdb"), triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://steamdb.info/app/{self.appid}"))))

        # 根据是否有pos参数决定菜单显示位置
        if pos is not None:
            menu.exec(self.mapToGlobal(pos))
        else:
            menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        self._show_more_menu(pos)


class SearchResultCardGrid(CardWidget):
    """搜索结果卡片组件 - 网格视图模式"""

    def __init__(self, appid, game_name, parent=None):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name

        # 设置透明边框
        self.setStyleSheet("""
            SearchResultCardGrid {
                border: none;
                background: transparent;
            }
        """)
        
        # 设置右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 网络管理器
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self.on_cover_loaded)

        # 创建垂直布局
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(10, 10, 10, 10)
        self.vBoxLayout.setSpacing(8)
        
        # 游戏封面
        self.coverLabel = QLabel(self)
        self.coverLabel.setFixedSize(180, 84)
        self.coverLabel.setScaledContents(True)
        # 根据主题模式动态设置背景颜色 - 暗色主题使用更深的颜色
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #1a1a1a;")
        # 监听主题变化
        self.theme_changed()
        # 设置封面可点击，点击打开游戏详情
        self.coverLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coverLabel.mousePressEvent = lambda e: self.show_game_detail()
        
        # 游戏标题
        self.titleLabel = BodyLabel(game_name, self)
        self.titleLabel.setWordWrap(True)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 设置标题的最大高度以允许多行显示，但限制过度增长
        self.titleLabel.setMaximumHeight(60)  # 大约3行文字
        
        # AppID
        self.infoLabel = CaptionLabel(f"AppID: {appid}", self)
        self.infoLabel.setTextColor("#606060", "#d2d2d2")
        self.infoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 入库按钮（图标样式）
        self.selectButton = TransparentToolButton(FluentIcon.CLOUD_DOWNLOAD, self)
        self.selectButton.setFixedSize(32, 32)
        self.selectButton.setToolTip("入库")
        self.selectButton.installEventFilter(ToolTipFilter(self.selectButton, showDelay=150, position=ToolTipPosition.TOP))
        self.selectButton.clicked.connect(self.on_select_clicked)

        # 更多按钮
        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)
        self.moreButton.setFixedSize(32, 32)
        self.moreButton.setToolTip("更多")
        self.moreButton.installEventFilter(ToolTipFilter(self.moreButton, showDelay=150, position=ToolTipPosition.TOP))
        self.moreButton.clicked.connect(lambda: self._show_more_menu())

        # 设置布局
        self.setFixedSize(200, 250)
        
        # 添加组件到布局
        self.vBoxLayout.addWidget(self.coverLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(5)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(3)
        self.vBoxLayout.addWidget(self.infoLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch(1)
        btn_row.addWidget(self.selectButton)
        btn_row.addWidget(self.moreButton)
        btn_row.addStretch(1)
        self.vBoxLayout.addLayout(btn_row)
        self.vBoxLayout.addSpacing(5)
        
        # 加载封面
        self.load_cover()
    
    def theme_changed(self):
        """主题变化时更新样式"""
        if isDarkTheme():
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #1a1a1a;")
        else:
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #f0f0f0;")
    
    def load_cover(self):
        """加载游戏封面"""
        cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        request = QNetworkRequest(QUrl(cover_url))
        self.network_manager.get(request)
    
    @pyqtSlot(QNetworkReply)
    def on_cover_loaded(self, reply):
        """封面加载完成"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.coverLabel.setPixmap(pixmap)
        reply.deleteLater()
    
    def on_select_clicked(self):
        """选择按钮点击"""
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, SearchPage):
                parent = parent.parent()
            if parent:
                parent.unlock_game_direct(self.appid, self.game_name)

    def copy_cover(self):
        """复制封面URL到剪贴板"""
        cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        QApplication.clipboard().setText(cover_url)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="封面URL已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_appid(self):
        """复制AppID到剪贴板"""
        QApplication.clipboard().setText(self.appid)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="AppID已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def copy_game_name(self):
        """复制游戏名称到剪贴板"""
        QApplication.clipboard().setText(self.game_name)
        
        # 显示成功提示
        InfoBar.success(
            title="复制成功",
            content="游戏名称已复制到剪贴板",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def show_game_detail(self):
        """显示游戏详情对话框"""
        dialog = GameDetailDialog(self.appid, self.game_name, self.window())
        dialog.exec()

    def _show_more_menu(self, pos=None):
        menu = RoundMenu(parent=self)

        # 查看详情
        menu.addAction(Action(FluentIcon.INFO, "查看详情", triggered=self.show_game_detail))
        menu.addSeparator()

        # 入库选项
        menu.addAction(Action(FluentIcon.CLOUD_DOWNLOAD, "入库", triggered=self.on_select_clicked))
        menu.addSeparator()

        # 复制菜单（二级菜单）
        copy_menu = RoundMenu(parent=self)
        copy_menu.setTitle("复制")
        copy_menu.setIcon(FluentIcon.COPY)

        # 复制封面
        copy_cover_action = Action(FluentIcon.PHOTO, "复制封面", triggered=self.copy_cover)
        if not self.coverLabel.pixmap():
            copy_cover_action.setEnabled(False)
            copy_cover_action.setToolTip("此游戏暂时获取不到封面")
        copy_menu.addAction(copy_cover_action)

        # 复制AppID
        copy_menu.addAction(Action(FluentIcon.CODE, "复制AppID", triggered=self.copy_appid))

        # 复制游戏名称
        copy_name_action = Action(FluentIcon.TAG, "复制游戏名称", triggered=self.copy_game_name)
        if not self.game_name or self.game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'), tr('unknown_game')):
            copy_name_action.setEnabled(False)
            copy_name_action.setToolTip("此游戏暂时获取不到游戏名")
        copy_menu.addAction(copy_name_action)

        menu.addMenu(copy_menu)
        menu.addSeparator()

        menu.addAction(Action(FluentIcon.SHOPPING_CART, "查看商店页面", triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://store.steampowered.com/app/{self.appid}"))))
        menu.addAction(Action(FluentIcon.LINK, "查看 SteamDB", triggered=lambda: QDesktopServices.openUrl(QUrl(f"https://steamdb.info/app/{self.appid}"))))

        # 根据是否有pos参数决定菜单显示位置
        if pos is not None:
            menu.exec(self.mapToGlobal(pos))
        else:
            menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        self._show_more_menu(pos)


class SearchPage(ScrollArea):
    """搜索和入库页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchPage")
        self.setWidgetResizable(True)
        
        # 主容器
        container = QWidget()
        container.setObjectName("searchContainer")
        self.setWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        self.main_layout = layout  # 保存布局引用
        
        # 标题
        title = SubtitleLabel(tr("search_and_add"), self)
        layout.addWidget(title)
        
        # 搜索输入框和视图/排序选项
        search_row_layout = QHBoxLayout()
        
        # 搜索输入框
        self.search_input = SearchLineEdit(self)
        self.search_input.setPlaceholderText(tr("game_name_or_appid"))
        self.search_input.setFixedHeight(40)
        self.search_input.searchSignal.connect(self.on_search)
        self.search_input.returnPressed.connect(self.on_search)
        search_row_layout.addWidget(self.search_input)
        
        # 视图模式选择
        self.view_mode_label = QLabel(tr("view_mode") + ":", self)
        self.view_mode_label.setStyleSheet("color: #000000;" if not isDarkTheme() else "color: #ffffff;")
        self.view_mode_combo = ComboBox(self)
        self.view_mode_combo.addItems([tr("view_list"), tr("view_grid")])
        self.view_mode_combo.setCurrentIndex(0)
        self.view_mode_combo.setFixedWidth(100)
        self.view_mode_combo.currentIndexChanged.connect(self.on_view_mode_changed)
        search_row_layout.addWidget(self.view_mode_label)
        search_row_layout.addWidget(self.view_mode_combo)
        search_row_layout.addSpacing(10)
        
        # 排序选择
        self.sort_label = QLabel(tr("sort_mode") + ":", self)
        self.sort_label.setStyleSheet("color: #000000;" if not isDarkTheme() else "color: #ffffff;")
        self.sort_combo = ComboBox(self)
        self.sort_combo.addItems([tr("sort_default"), tr("sort_az"), tr("sort_za")])
        self.sort_combo.setCurrentIndex(0)
        self.sort_combo.setFixedWidth(100)
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        search_row_layout.addWidget(self.sort_label)
        search_row_layout.addWidget(self.sort_combo)
        
        layout.addLayout(search_row_layout)
        
        # 搜索选项（清单源、DLC选项等）
        options_layout = QHBoxLayout()
        
        # 清单源选择
        self.manifest_source_label = QLabel(tr("manifest_source"), self)
        self.manifest_source_label.setStyleSheet("color: #000000;" if not isDarkTheme() else "color: #ffffff;")
        self.manifest_source_combo = ComboBox(self)
        self.manifest_source_combo.addItems([
            tr("auto_select"),
            "Cysaw",
            tr("gmrc"),
            "Walftech",
            tr("sudama"),
            tr("buqiuren"),
            tr("MHub"),
            tr("github_auiowu"),
            tr("github_mau"),
            "SteamAutoCracks V2 [废弃]",
            "SteamAutoCracks V1 [废弃]",
            tr("sac-other"),
        ])
        self.manifest_source_combo.setCurrentIndex(0)  # 默认自动选择
        self.manifest_source_combo.setFixedWidth(200)
        self.manifest_source_combo.currentIndexChanged.connect(self.on_manifest_source_changed)
        options_layout.addWidget(self.manifest_source_label)
        options_layout.addWidget(self.manifest_source_combo)
        options_layout.addSpacing(20)
        
        # 选项
        self.add_dlc_check = CheckBox(tr("add_all_dlc"), self)
        self.add_dlc_check.setChecked(True)  # 默认勾选添加所有 DLC
        self.add_dlc_check.stateChanged.connect(self.on_add_dlc_changed)
        options_layout.addWidget(self.add_dlc_check)
        
        self.patch_key_check = CheckBox(tr("patch_depot_key"), self)
        self.patch_key_check.setChecked(True)  # 默认勾选修补 Depot Key
        self.patch_key_check.stateChanged.connect(self.on_patch_key_changed)
        options_layout.addWidget(self.patch_key_check)

        options_layout.addStretch(1)
        layout.addLayout(options_layout)
        
        # 搜索进度条（搜索时显示）
        self.search_progress_label = CaptionLabel("", self)
        self.search_progress_label.setTextColor("#606060", "#d2d2d2")
        self.search_progress_label.hide()

        self.search_progress = ProgressRing(self)
        self.search_progress.setFixedSize(32, 32)
        self.search_progress.hide()

        # 进度条布局
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.search_progress)
        progress_layout.addWidget(self.search_progress_label)
        progress_layout.addStretch(1)
        
        layout.addLayout(progress_layout)
        
        # 下载进度条（点击入库后显示）
        self.download_progress_label = CaptionLabel("", self)
        self.download_progress_label.setTextColor("#606060", "#d2d2d2")
        self.download_progress_label.hide()

        self.download_progress = ProgressBar(self)
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.hide()

        self.cancel_download_btn = PushButton("取消任务", self)
        self.cancel_download_btn.setIcon(FluentIcon.CANCEL)
        self.cancel_download_btn.clicked.connect(self._request_cancel_download)
        self.cancel_download_btn.hide()

        layout.addWidget(self.download_progress_label)
        layout.addWidget(self.download_progress)
        layout.addWidget(self.cancel_download_btn)
        
        # 搜索结果卡片布局 - 支持列表和卡片视图
        self.list_results_layout = QVBoxLayout()
        self.list_results_layout.setContentsMargins(0, 0, 0, 0)
        self.list_results_layout.setSpacing(10)
        
        # 卡片视图使用网格布局
        self.grid_results_layout = SafeFlowLayout()
        self.grid_results_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_results_layout.setSpacing(15)
        
        # 创建容器部件来管理布局切换
        # 先读取保存的视图模式再设置布局，避免 Qt 忽略重复 setLayout 调用
        self.results_container = QWidget(self)
        self.current_view_mode = self._read_view_mode_config("search_view_mode")
        if self.current_view_mode == "grid":
            self.results_layout = self.grid_results_layout
            self.results_container.setLayout(self.grid_results_layout)
        else:
            self.current_view_mode = "grid"
            self.results_layout = self.grid_results_layout
            self.results_container.setLayout(self.grid_results_layout)
        
        layout.addWidget(self.results_container)
        layout.addStretch(1)
        
        # 设置透明背景
        self.setStyleSheet("SearchPage { background: transparent; }")
        container.setStyleSheet("QWidget#searchContainer { background: transparent; }")
        
        # 状态变量
        self.search_worker = None
        self.unlock_worker = None
        self.result_cards = []
        self.search_results = []  # 存储搜索结果用于排序
        self._rec_label = None
        self._rec_worker = None
        self._rec_games = []  # 缓存推荐游戏数据
        self._rec_shown = 0
        self._show_more_btn = None
        self._progress_lock = threading.Lock()
        self._progress_target = 0
        self._progress_text = ""
        self._download_cancel_requested = False
        self._progress_animating = False  # 是否处于动画进度模式（阶段3/6）
        self._progress_animation_value = 0  # 动画进度当前值
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(120)
        self._progress_timer.timeout.connect(self._flush_download_progress)
        
        # 加载保存的清单源选择（包括自定义仓库）
        self.refresh_manifest_source_combo()

        # 加载视图和排序设置
        self.load_view_mode_preference()
        self.load_sort_mode_preference()

        # 加载DLC和修补选项状态
        self.load_add_dlc_preference()
        self.load_patch_key_preference()

    def on_add_dlc_changed(self):
        """DLC选项改变时保存状态"""
        self.save_add_dlc_preference()

    def on_patch_key_changed(self):
        """修补Key选项改变时保存状态"""
        self.save_patch_key_preference()
    
    def save_add_dlc_preference(self):
        """保存DLC选项状态"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 保存DLC选项状态
            config["add_all_dlc_default"] = self.add_dlc_check.isChecked()
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存DLC选项失败: {e}")
    
    def load_add_dlc_preference(self):
        """加载DLC选项状态"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的DLC选项状态，如果没有配置则使用默认值True
                add_dlc_default = config.get("add_all_dlc_default", True)
                self.add_dlc_check.setChecked(add_dlc_default)
                
        except Exception as e:
            print(f"加载DLC选项失败: {e}")
    
    def save_patch_key_preference(self):
        """保存修补Key选项状态"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 保存修补Key选项状态
            config["patch_depot_key_default"] = self.patch_key_check.isChecked()
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存修补Key选项失败: {e}")
    
    def load_patch_key_preference(self):
        """加载修补Key选项状态"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的修补Key选项状态，如果没有配置则使用默认值True
                patch_key_default = config.get("patch_depot_key_default", True)
                self.patch_key_check.setChecked(patch_key_default)
                
        except Exception as e:
            print(f"加载修补Manifest选项失败: {e}")

    def _start_download_progress(self, title_text: str):
        """开始下载进度条"""
        # 检查是否启用了进度条显示
        if not self._should_show_progress():
            return
            
        self._download_cancel_requested = False
        self.download_progress.setValue(0)
        self.download_progress_label.setText(f"{title_text} - 准备任务环境...")
        self.download_progress.show()
        self.download_progress_label.show()
        self.cancel_download_btn.show()
        self.cancel_download_btn.setEnabled(True)
        with self._progress_lock:
            self._progress_target = 8
            self._progress_text = "阶段 1/6：初始化任务..."
        if not self._progress_timer.isActive():
            self._progress_timer.start()

    def _request_cancel_download(self):
        """请求取消下载"""
        if self._download_cancel_requested:
            return

        self._download_cancel_requested = True
        self.cancel_download_btn.setEnabled(False)
        if self.unlock_worker and self.unlock_worker.isRunning():
            self.unlock_worker.quit()
        self._update_download_progress_state(
            max(self.download_progress.value(), 30),
            "阶段 5/6：已请求取消，正在停止并回滚..."
        )

    def _is_download_cancelled(self) -> bool:
        """检查下载是否已取消"""
        return bool(self._download_cancel_requested)

    def _update_download_progress_state(self, value: int, text: str = ""):
        """更新下载进度状态"""
        with self._progress_lock:
            self._progress_target = max(0, min(100, int(value)))
            if text:
                self._progress_text = text

    def _flush_download_progress(self):
        """刷新下载进度显示"""
        current = self.download_progress.value()
        with self._progress_lock:
            target = self._progress_target
            text = self._progress_text

        if self._progress_animating:
            # 动画进度模式：在阶段3/6主入库流程期间缓慢递增进度
            self._progress_animation_value += 0.3  # 缓慢递增
            anim_val = int(self._progress_animation_value)
            # 限制在20-55之间（阶段3/6的范围）
            if anim_val > 55:
                self._progress_animation_value = 20
                anim_val = 20
            elif anim_val < 20:
                self._progress_animation_value = 20
                anim_val = 20
            self.download_progress.setValue(anim_val)
            self.download_progress_label.setText(text)
        elif current < target:
            step = 3 if target - current > 12 else 1
            self.download_progress.setValue(min(current + step, target))
            self.download_progress_label.setText(text)
        elif current > target:
            self.download_progress.setValue(max(current - 1, target))
        else:
            # 到达目标值，但继续动画效果
            self.download_progress.setValue(current + 1)

    def _should_show_progress(self) -> bool:
        """检查是否应该显示进度条"""
        try:
            # 读取配置检查是否启用了进度条显示
            config_path = APP_ROOT / 'config' / 'config.json'
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get("show_progress_bar", True)  # 默认启用
            return True  # 如果配置文件不存在，默认启用
        except Exception:
            return True  # 发生错误时默认启用

    def _finish_download_progress(self, success: bool, text: str):
        """完成下载进度"""
        # 检查是否启用了进度条显示
        if not self._should_show_progress():
            return

        if self._progress_timer.isActive():
            self._progress_timer.stop()
        self.download_progress.setValue(100 if success else min(95, max(0, self.download_progress.value())))
        self.download_progress_label.setText(text)
        # 延迟隐藏进度条，让用户看到完成状态
        QTimer.singleShot(2000, lambda: (
            self.download_progress.hide(),
            self.download_progress_label.hide(),
            self.cancel_download_btn.hide()
        ))

    def __del__(self):
        """析构函数，确保清理所有worker"""
        self.cleanup_workers()
    
    def cleanup_workers(self):
        """清理所有worker线程"""
        for attr in ('search_worker', 'unlock_worker', '_manifest_worker', '_rec_worker'):
            worker = getattr(self, attr, None)
            if worker:
                try:
                    if worker.isRunning():
                        worker.cancel()
                        # 等待线程结束，最多等待5秒
                        if not worker.wait(5000):
                            worker.terminate()
                            worker.wait(1000)
                    # 确保线程已结束再删除
                    if worker.isFinished():
                        worker.deleteLater()
                except Exception:
                    pass
                setattr(self, attr, None)
    
    def on_manifest_source_changed(self):
        """清单源选择改变时保存偏好"""
        self.save_manifest_source_preference()
    
    def save_manifest_source_preference(self):
        """保存清单源选择偏好"""
        async def _save():
            config_path = APP_ROOT / 'config' / 'config.json'
            import json

            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()

            # 基础源映射
            source_mapping = {
                0: "auto",
                1: "cysaw",
                2: "gmrc",
                3: "walftech",
                4: "sudama",
                5: "buqiuren",
                6: "MHub",
                7: "github_auiowu",
                8: "github_mau",
                9: "steamautocracks_v2",
                10: "steamautocracks_v1",
                11: "sac-other",
            }

            current_index = self.manifest_source_combo.currentIndex()
            current_text = self.manifest_source_combo.currentText()

            if current_index <= 11:
                # 基础源
                config["default_manifest_source"] = source_mapping.get(current_index, "auto")
            else:
                # 自定义仓库，保存名称
                config["default_manifest_source"] = current_text

            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        # 使用异步worker保存，并确保正确清理
        if hasattr(self, '_manifest_worker') and self._manifest_worker and self._manifest_worker.isRunning():
            self._manifest_worker.cancel()
            self._manifest_worker.wait()
            self._manifest_worker = None

        self._manifest_worker = AsyncWorker(_save())
        self._manifest_worker.result_ready.connect(self._on_manifest_save_complete)
        self._manifest_worker.error.connect(self._on_manifest_save_error)
        self._manifest_worker.finished.connect(self._manifest_worker.deleteLater)
        self._manifest_worker.start()
    
    def _on_manifest_save_complete(self, result):
        """清单源保存完成"""
        self._manifest_worker = None
    
    def _on_manifest_save_error(self, error):
        """保存清单源偏好失败"""
        print(f"保存清单源偏好失败: {error}")
        self._manifest_worker = None

    def refresh_manifest_source_combo(self):
        """刷新清单源下拉框，包括自定义仓库"""
        try:
            # 保存当前选中的索引（如果有）
            current_index = -1
            current_text = ""
            try:
                current_index = self.manifest_source_combo.currentIndex()
                current_text = self.manifest_source_combo.currentText()
            except:
                pass

            # 断开信号，避免触发保存
            try:
                self.manifest_source_combo.currentIndexChanged.disconnect(self.on_manifest_source_changed)
            except:
                pass

            # 清空下拉框
            self.manifest_source_combo.clear()

            # 添加基础选项
            base_items = [
                tr("auto_select"),
                "Cysaw",
                tr("gmrc"),
                "Walftech",
                tr("sudama"),
                tr("buqiuren"),
                tr("MHub"),
                tr("github_auiowu"),
                tr("github_mau"),
                "SteamAutoCracks V2 [废弃]",
                "SteamAutoCracks V1 [废弃]",
                tr("sac-other"),
            ]
            self.manifest_source_combo.addItems(base_items)

            # 从配置中加载自定义仓库和保存的清单源偏好
            config_path = APP_ROOT / 'config' / 'config.json'
            saved_source = "auto"  # 默认自动选择
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 获取保存的清单源偏好
                saved_source = config.get("default_manifest_source", "auto")

                custom_repos = config.get("Custom_Repos", {"github": [], "zip": []})

                # 添加自定义GitHub仓库
                for repo in custom_repos.get("github", []):
                    name = repo.get("name", "")
                    if name:
                        self.manifest_source_combo.addItem(name)

                # 添加自定义ZIP仓库
                for repo in custom_repos.get("zip", []):
                    name = repo.get("name", "")
                    if name:
                        self.manifest_source_combo.addItem(name)

            # 映射到combo索引
            source_mapping = {
                "auto": 0,
                "cysaw": 1,
                "gmrc": 2,
                "walftech": 3,
                "sudama": 4,
                "buqiuren": 5,
                "MHub": 6,
                "github_auiowu": 7,
                "github_mau": 8,
                "steamautocracks_v2": 9,
                "steamautocracks_v1": 10,
                "sac-other": 11,
            }

            # 优先使用保存的配置，其次尝试恢复之前的选择
            if saved_source:
                # 如果是内置源，使用映射
                if saved_source.lower() in source_mapping:
                    index = source_mapping.get(saved_source.lower(), 0)
                    if index < self.manifest_source_combo.count():
                        self.manifest_source_combo.setCurrentIndex(index)
                else:
                    # 自定义仓库，通过名称查找
                    index = self.manifest_source_combo.findText(saved_source)
                    if index >= 0:
                        self.manifest_source_combo.setCurrentIndex(index)
                    else:
                        self.manifest_source_combo.setCurrentIndex(0)
            elif current_text:
                # 尝试恢复之前的选择
                index = self.manifest_source_combo.findText(current_text)
                if index >= 0:
                    self.manifest_source_combo.setCurrentIndex(index)
                elif current_index < self.manifest_source_combo.count():
                    self.manifest_source_combo.setCurrentIndex(current_index)
            else:
                self.manifest_source_combo.setCurrentIndex(0)

            # 重新连接信号
            self.manifest_source_combo.currentIndexChanged.connect(self.on_manifest_source_changed)

        except Exception as e:
            print(f"刷新清单源下拉框失败: {e}")

    def save_view_mode_preference(self):
        """保存视图模式设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 保存视图模式
            config["search_view_mode"] = self.current_view_mode
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存视图模式失败: {e}")
    
    def _read_view_mode_config(self, key):
        """从配置文件读取视图模式，不操作任何 UI"""
        try:
            import json
            config_path = APP_ROOT / 'config' / 'config.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get(key, "grid")
        except Exception:
            pass
        return "grid"

    def load_view_mode_preference(self):
        """同步 combo UI（布局已在 __init__ 中正确设置）"""
        try:
            self.view_mode_combo.currentIndexChanged.disconnect(self.on_view_mode_changed)
            self.view_mode_combo.setCurrentIndex(0 if self.current_view_mode == "list" else 1)
            self.view_mode_combo.currentIndexChanged.connect(self.on_view_mode_changed)
        except Exception as e:
            print(f"加载视图模式偏好失败: {e}")
        """保存排序模式设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 保存排序模式
            sort_mode_text = self.sort_combo.currentText()
            if sort_mode_text == tr("sort_az"):
                config["search_sort_mode"] = "az"
            elif sort_mode_text == tr("sort_za"):
                config["search_sort_mode"] = "za"
            else:
                config["search_sort_mode"] = "default"
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存排序模式失败: {e}")
    
    def load_sort_mode_preference(self):
        """加载排序模式设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的排序模式
                saved_sort_mode = config.get("search_sort_mode", "default")
                
                # 更新UI
                # 断开信号，避免触发保存
                self.sort_combo.currentIndexChanged.disconnect(self.on_sort_changed)
                if saved_sort_mode == "az":
                    self.sort_combo.setCurrentIndex(1)
                elif saved_sort_mode == "za":
                    self.sort_combo.setCurrentIndex(2)
                else:
                    self.sort_combo.setCurrentIndex(0)
                self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
                
        except Exception as e:
            print(f"加载排序模式偏好失败: {e}")
    
    def showEvent(self, event):
        """页面显示时加载推荐"""
        super().showEvent(event)
        if not self.search_results and not self.search_input.text().strip():
            # 有未过期的模块级缓存，直接渲染，不发请求
            if _rec_cache and (_time.time() - _rec_cache_ts) < _REC_CACHE_TTL:
                if not self._rec_games:
                    self._rec_games = _rec_cache
                    self._rec_shown = 0
                if not self.result_cards:
                    if hasattr(self, '_rec_label') and self._rec_label:
                        self._rec_label.setText(tr("recommended_hint"))
                        self._rec_label.show()
                    self._render_recommendations()
            else:
                self._load_recommendations()

    def _load_recommendations(self):
        """加载热门游戏推荐"""
        # 清空现有卡片
        for card in self.result_cards:
            card.deleteLater()
        self.result_cards.clear()

        # 显示推荐标题标签
        if not hasattr(self, '_rec_label') or self._rec_label is None:
            from qfluentwidgets import CaptionLabel
            self._rec_label = CaptionLabel(tr("recommended_hint"), self)
            self._rec_label.setTextColor("#606060", "#d2d2d2")
            self.main_layout.insertWidget(3, self._rec_label)
        self._rec_label.setText(tr("loading_recommendations"))
        self._rec_label.show()

        # 已有未过期缓存，直接用
        if _rec_cache and (_time.time() - _rec_cache_ts) < _REC_CACHE_TTL:
            self._on_recommendations_loaded(_rec_cache)
            return

        async def _fetch():
            try:
                async with CaiBackend() as backend:
                    steam_lang = get_steam_lang(current_language)
                    cc = "TW" if current_language == "zh_TW" else ("US" if current_language == "en_US" else "CN")
                    r = await backend.client.get(
                        "https://store.steampowered.com/api/featuredcategories",
                        params={"cc": cc.lower(), "l": steam_lang},
                        timeout=15
                    )
                    data = r.json()
                    games = []
                    for section in ["top_sellers", "new_releases", "specials"]:
                        items = data.get(section, {}).get("items", [])
                        for item in items:
                            appid = str(item.get("id", ""))
                            name = item.get("name", "")
                            # 检查是否已存在
                            exists = False
                            for g in games:
                                if g["appid"] == appid:
                                    exists = True
                                    break
                            if appid and name and not exists:
                                games.append({"appid": appid, "name": name})
                    return games
            except Exception:
                return []

        if hasattr(self, '_rec_worker') and self._rec_worker and self._rec_worker.isRunning():
            return
        self._rec_worker = AsyncWorker(_fetch())
        self._rec_worker.result_ready.connect(self._on_recommendations_loaded)
        self._rec_worker.error.connect(lambda e: self._rec_label.setText(tr("recommendations_failed")) if self._rec_label else None)
        self._rec_worker.finished.connect(self._rec_worker.deleteLater)
        self._rec_worker.start()

    def _on_recommendations_loaded(self, games):
        """推荐加载完成"""
        global _rec_cache, _rec_cache_ts
        self._rec_worker = None
        if not games:
            if hasattr(self, '_rec_label') and self._rec_label:
                self._rec_label.setText(tr("recommendations_failed"))
            return
        if hasattr(self, '_rec_label') and self._rec_label:
            self._rec_label.setText(tr("recommended_hint"))
        # 更新模块级缓存
        _rec_cache = games
        _rec_cache_ts = _time.time()
        # 缓存推荐数据
        self._rec_games = games
        self._rec_shown = 0
        # 只在没有搜索结果时显示推荐
        if not self.search_results:
            self._render_recommendations()

    def _render_recommendations(self):
        """将缓存的推荐数据渲染到当前布局"""
        # 清空现有卡片和"显示更多"按钮
        for card in self.result_cards:
            card.deleteLater()
        self.result_cards.clear()
        if hasattr(self, '_show_more_btn') and self._show_more_btn:
            self._show_more_btn.deleteLater()
            self._show_more_btn = None

        self._rec_shown = 0
        self._append_recommendations(20)

    def _append_recommendations(self, count):
        """追加显示 count 个推荐游戏"""
        games = getattr(self, '_rec_games', [])
        start = self._rec_shown
        end = min(start + count, len(games))

        for game in games[start:end]:
            if self.current_view_mode == "grid":
                card = SearchResultCardGrid(game["appid"], game["name"], self)
            else:
                card = SearchResultCard(game["appid"], game["name"], self)
            self.results_layout.addWidget(card)
            self.result_cards.append(card)

        self._rec_shown = end

        # 移除旧的"显示更多"按钮（如果有）
        if hasattr(self, '_show_more_btn') and self._show_more_btn:
            self._show_more_btn.deleteLater()
            self._show_more_btn = None

        # 如果还有更多，添加"显示更多"按钮
        if self._rec_shown < len(games):
            btn = PushButton(tr("show_more"), self)
            btn.setFixedWidth(160)
            btn.clicked.connect(lambda: self._append_recommendations(20))
            wrapper = QWidget(self)
            wrapper_layout = QHBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 4, 0, 4)
            wrapper_layout.addStretch(1)
            wrapper_layout.addWidget(btn)
            wrapper_layout.addStretch(1)
            self._show_more_btn = wrapper
            self.results_layout.addWidget(wrapper)
        else:
            self._show_more_btn = None

    def on_search(self):
        """搜索游戏"""
        query = self.search_input.text().strip()
        # 清掉"显示更多"按钮
        if hasattr(self, '_show_more_btn') and self._show_more_btn:
            self._show_more_btn.deleteLater()
            self._show_more_btn = None
        if not query:
            for card in self.result_cards:
                card.deleteLater()
            self.result_cards.clear()
            self.search_results = []
            self._load_recommendations()
            return
        
        # 清空之前的结果卡片
        for card in self.result_cards:
            card.deleteLater()
        self.result_cards.clear()
        
        # 显示搜索进度条（如果启用了进度条显示）
        if self._should_show_progress():
            self.search_progress_label.setText("正在搜索游戏...")
            self.search_progress_label.show()
            self.search_progress.show()
        
        # 检查是否是纯数字（AppID）
        if query.isdigit():
            # 直接处理 AppID
            self.search_worker = AsyncWorker(self._search_appid(query))
            self.search_worker.result_ready.connect(self.on_search_complete)
            self.search_worker.error.connect(self.on_search_error)
            self.search_worker.start()
        else:
            # 搜索游戏名称
            self.search_worker = AsyncWorker(self._search_games(query))
            self.search_worker.result_ready.connect(self.on_search_complete)
            self.search_worker.error.connect(self.on_search_error)
            self.search_worker.start()
    
    async def _search_appid(self, appid: str):
        """搜索 AppID"""
        return {'type': 'appid', 'appid': appid}
    
    async def _search_games(self, query: str):
        """搜索游戏名称"""
        # 创建后端实例（与其他页面保持一致）
        async with CaiBackend() as backend:
            await backend.initialize()
            
            # 获取当前语言设置（使用全局变量）
            lang = get_steam_lang(current_language)
            
            # 调用后端搜索功能
            results = await backend.find_appid_by_name(query, lang)
            return {'type': 'games', 'results': results}
    
    def notify_theme_changed(self):
        """通知所有搜索结果卡片主题已变化"""
        # 更新所有搜索结果卡片的封面背景颜色
        for card in self.result_cards:
            if hasattr(card, 'theme_changed'):
                card.theme_changed()
    

    
    @pyqtSlot(object)
    def on_search_complete(self, result):
        """搜索完成"""
        # 隐藏搜索进度条
        self.search_progress.hide()
        self.search_progress_label.hide()
        
        worker = self.search_worker
        self.search_worker = None
        if worker:
            try:
                worker.deleteLater()
            except RuntimeError:
                pass
        
        if result['type'] == 'appid':
            # 直接是 AppID，自动开始入库
            self.unlock_game_direct(result['appid'], None)
        else:
            results = result['results']
            if not results:
                InfoBar.warning(
                    title=tr("game_not_found"),
                    content=tr("check_game_name"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                return
            
            self.search_results = results
            self.display_search_results(results)
            
            InfoBar.success(
                title=tr("recognition_success"),
                content=tr("tip_source_fail") if len(results) > 1 else results[0]['name'],
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2500
            )
    
    def display_search_results(self, results):
        """显示搜索结果"""
        # 隐藏推荐标签
        if hasattr(self, '_rec_label') and self._rec_label:
            self._rec_label.hide()
        # 清空现有卡片
        for card in self.result_cards:
            card.deleteLater()
        self.result_cards.clear()
        
        # 根据排序选项对结果进行排序
        sorted_results = self.sort_search_results(results)
        
        # 创建结果卡片
        for game in sorted_results:
            # 根据视图模式创建不同类型的卡片
            if self.current_view_mode == "grid":
                card = SearchResultCardGrid(game['appid'], game['name'], self)
            else:
                card = SearchResultCard(game['appid'], game['name'], self)
            
            self.results_layout.addWidget(card)
            self.result_cards.append(card)
    

    
    def sort_search_results(self, results):
        """根据排序选项对搜索结果进行排序"""
        sort_mode = self.sort_combo.currentText()

        def get_name(x):
            return x['name']

        if sort_mode == tr("sort_az"):
            return sorted(results, key=get_name)
        elif sort_mode == tr("sort_za"):
            return sorted(results, key=get_name, reverse=True)
        else:  # 默认 - 保持原始顺序
            return results
    
    def on_view_mode_changed(self):
        """视图模式改变"""
        view_mode = self.view_mode_combo.currentText()
        
        # 保存当前搜索结果
        current_results = self.search_results.copy() if self.search_results else []
        
        # 先清空现有卡片，避免布局问题
        for card in self.result_cards:
            if hasattr(self, 'results_layout') and self.results_layout:
                self.results_layout.removeWidget(card)
            card.deleteLater()
        self.result_cards.clear()
        
        # 移除现有容器
        if hasattr(self, 'results_container') and self.results_container:
            self.main_layout.removeWidget(self.results_container)
            self.results_container.deleteLater()
        
        # 创建新的容器和布局
        self.results_container = QWidget(self)
        
        if view_mode == tr("view_list"):
            self.current_view_mode = "list"
            self.list_results_layout = QVBoxLayout()  # 创建新布局
            self.list_results_layout.setContentsMargins(0, 0, 0, 0)
            self.list_results_layout.setSpacing(10)
            self.results_layout = self.list_results_layout
            self.results_container.setLayout(self.list_results_layout)
        else:  # 卡片视图
            self.current_view_mode = "grid"
            self.grid_results_layout = SafeFlowLayout()  # 创建新布局
            self.grid_results_layout.setContentsMargins(0, 0, 0, 0)
            self.grid_results_layout.setSpacing(15)
            self.results_layout = self.grid_results_layout
            self.results_container.setLayout(self.grid_results_layout)
        
        # 重新添加到布局（title=0, search_row=1, options=2, [rec_label=3], results=3 or 4）
        insert_idx = 4 if (hasattr(self, '_rec_label') and self._rec_label and self._rec_label.isVisible()) else 3
        self.main_layout.insertWidget(insert_idx, self.results_container)
        
        # 保存视图模式偏好
        self.save_view_mode_preference()
        
        # 重新显示搜索结果或推荐
        if current_results:
            self.display_search_results(current_results)
        elif not self.search_results and self._rec_games:
            self._render_recommendations()
    
    def on_sort_changed(self):
        """排序方式改变"""
        # 保存排序模式偏好
        self.save_sort_mode_preference()
        
        # 重新显示搜索结果或推荐
        if self.search_results:
            self.display_search_results(self.search_results)
        elif self._rec_games:
            self._render_recommendations()
    
    def save_sort_mode_preference(self):
        """保存排序模式设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # 获取当前排序模式
            current_index = self.sort_combo.currentIndex()
            if current_index == 1:
                sort_mode = "az"
            elif current_index == 2:
                sort_mode = "za"
            else:
                sort_mode = "default"
            
            # 保存排序模式
            config["search_sort_mode"] = sort_mode
            
            # 写入配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"保存搜索排序模式偏好失败: {e}")
    
    @pyqtSlot(str)
    def on_search_error(self, error):
        """搜索失败"""
        # 隐藏搜索进度条
        self.search_progress.hide()
        self.search_progress_label.hide()
        
        worker = self.search_worker
        self.search_worker = None
        if worker:
            try:
                worker.deleteLater()
            except RuntimeError:
                pass
        
        InfoBar.error(
            title=tr("search_failed"),
            content=error,
            parent=self,
            position=InfoBarPosition.TOP
        )
    
    def notify_home_refresh(self):
        """通知主页刷新游戏列表"""
        # 获取主窗口
        main_window = self.window()
        if hasattr(main_window, 'home_page'):
            # 延迟刷新，确保入库操作完全完成
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, main_window.home_page.refresh_games)
    
    def unlock_game_direct(self, appid, game_name):
        """直接入库游戏（新的直接入库方法）"""
        if not appid:
            return
        
        # 获取选项
        add_all_dlc = self.add_dlc_check.isChecked()
        patch_depot_key = self.patch_key_check.isChecked()

        # 获取用户选择的清单源（用索引避免文本翻译不一致问题）
        index_to_source = {
            0: "auto",
            1: "cysaw",
            2: "gmrc",
            3: "walftech",
            4: "sudama",
            5: "buqiuren",
            6: "MHub",
            7: "github_auiowu",
            8: "github_mau",
            9: "steamautocracks_v2",
            10: "steamautocracks_v1",
            11: "sac-other",
        }

        current_index = self.manifest_source_combo.currentIndex()
        if current_index <= 11:
            tool_type = index_to_source.get(current_index, "auto")
        else:
            # 自定义仓库，使用名称作为 tool_type
            tool_type = self.manifest_source_combo.currentText()
        
        # 显示入库提示
        display_name = game_name or f"AppID {appid}"
        
        # 开始下载进度条
        self._start_download_progress(display_name)
        
        InfoBar.info(
            title=tr("adding_game"),
            content=f"{display_name} - {tr('please_wait_adding')}",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000  # 2秒后自动消失
        )
        
        async def _unlock():
            async with CaiBackend() as backend:
                unlocker_type = await backend.initialize()
                if not unlocker_type:
                    raise Exception("解锁工具类型未能确定，请检查配置或Steam路径")
                
                await backend.checkcn()
                
                # 读取固定版本配置：ST_Fixed_Version=True 时 use_st_auto_update=False
                use_st_auto_update = not backend.config.get("ST_Fixed_Version", False)
                
                tool_type_actual = tool_type
                
                # 进度回调函数
                def _progress_cb(value: int, text: str = ""):
                    # 其他进度信息保持原样
                    self._update_download_progress_state(value, text)

                # 自动选择模式：依次尝试所有源（sudama优先，然后是GitHub源，最后是其他ZIP源）
                if tool_type_actual == "auto":
                    # 定义所有源，按优先级排序
                    # 格式: (类型, 键/名称, 仓库/源标识)
                    all_sources = [
                        ("zip", "sudama", None),  # 第1: sudama (ZIP源)
                        ("github", "github_auiowu", "Auiowu/ManifestAutoUpdate"),  # 第2: GitHub Auiowu
                        ("github", "github_mau", "satisl/MAU"),  # 第3: GitHub MAU
                        ("zip", "cysaw", None),
                        ("zip", "walftech", None),
                        ("zip", "MHub", None),
                        ("zip", "steamautocracks_v1", None),
                        ("zip", "sac-other", None),
                    ]

                    total_sources = len(all_sources)

                    # 更新进度条状态
                    self._update_download_progress_state(20, f"阶段 3/6：自动选择模式（{total_sources}个源）")

                    # 依次尝试所有源
                    for i, (source_type, source_key, repo) in enumerate(all_sources):
                        progress_value = 20 + (i * 60 // total_sources)

                        if source_type == "github":
                            backend.log.info(f"[自动选择] 正在尝试GitHub源: {repo}")
                            self._update_download_progress_state(progress_value, f"阶段 3/6：尝试源 {i+1}/{total_sources} - GitHub ({repo.split('/')[-1]})")
                            # 启用动画进度模式
                            self._progress_animating = True
                            self._progress_animation_value = float(progress_value)

                            ok = False
                            try:
                                ok = await backend.process_github_manifest(
                                    appid, repo, unlocker_type,
                                    use_st_auto_update, add_all_dlc, patch_depot_key
                                )
                            except Exception as e:
                                backend.log.warning(f"[自动选择] GitHub源 {repo} 失败: {e}")
                            finally:
                                # 禁用动画进度模式
                                self._progress_animating = False

                            if ok:
                                backend.log.info(f"[自动选择] GitHub源 {repo} 成功")
                                self._update_download_progress_state(90, "阶段 4/6：主入库完成")
                                return True
                        else:
                            # ZIP源
                            backend.log.info(f"[自动选择] 正在尝试ZIP源: {source_key}")
                            self._update_download_progress_state(progress_value, f"阶段 3/6：尝试源 {i+1}/{total_sources} - {source_key}")
                            # 启用动画进度模式
                            self._progress_animating = True
                            self._progress_animation_value = float(progress_value)

                            ok = False
                            try:
                                ok = await backend.process_zip_source(
                                    appid, source_key, unlocker_type,
                                    use_st_auto_update, add_all_dlc, patch_depot_key
                                )
                            except Exception as e:
                                backend.log.warning(f"[自动选择] ZIP源 {source_key} 失败: {e}")
                            finally:
                                # 禁用动画进度模式
                                self._progress_animating = False

                            if ok:
                                backend.log.info(f"[自动选择] ZIP源 {source_key} 成功")
                                self._update_download_progress_state(90, "阶段 4/6：主入库完成")
                                return True

                    # 所有源都失败
                    self._update_download_progress_state(80, "阶段 3/6：所有源尝试失败")
                    return False
                
                # 指定源模式
                github_repo_map = {
                    "github_auiowu": "Auiowu/ManifestAutoUpdate",
                }
                zip_sources = ["cysaw", "gmrc", "sac-other", "walftech", "steamautocracks_v2", "steamautocracks_v1", "sudama", "buqiuren", "MHub"]

                # 检查是否为自定义仓库（索引大于10）
                is_custom_repo = self.manifest_source_combo.currentIndex() > 10

                if is_custom_repo:
                    # 自定义仓库处理
                    repo_name = tool_type_actual
                    self._update_download_progress_state(20, f"阶段 3/6：主入库流程（自定义源：{repo_name}）")
                    self._progress_animating = True
                    self._progress_animation_value = 20.0
                    try:
                        # 获取自定义仓库配置
                        config_path = APP_ROOT / 'config' / 'config.json'
                        custom_github_repos = []
                        custom_zip_repos = []
                        if config_path.exists():
                            import json
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                            custom_repos = config.get("Custom_Repos", {"github": [], "zip": []})
                            custom_github_repos = custom_repos.get("github", [])
                            custom_zip_repos = custom_repos.get("zip", [])

                        # 检查是否为自定义GitHub仓库
                        github_repo = None
                        for repo in custom_github_repos:
                            if repo.get("name") == repo_name:
                                github_repo = repo.get("repo")
                                break

                        if github_repo:
                            # 自定义GitHub仓库
                            success = await backend.process_github_manifest(
                                appid, github_repo, unlocker_type,
                                use_st_auto_update, add_all_dlc, patch_depot_key
                            )
                        else:
                            # 检查是否为自定义ZIP仓库
                            zip_repo_config = None
                            for repo in custom_zip_repos:
                                if repo.get("name") == repo_name:
                                    zip_repo_config = repo
                                    break

                            if zip_repo_config:
                                # 自定义ZIP仓库
                                success = await backend.process_custom_zip_manifest(
                                    appid, zip_repo_config, add_all_dlc, patch_depot_key
                                )
                            else:
                                backend.log.error(f"未找到自定义仓库配置: {repo_name}")
                                success = False
                    finally:
                        self._progress_animating = False
                elif tool_type_actual in zip_sources:
                    self._update_download_progress_state(20, f"阶段 3/6：主入库流程（清单源：{tool_type_actual}）")
                    # 启用动画进度模式
                    self._progress_animating = True
                    self._progress_animation_value = 20.0
                    try:
                        success = await backend.process_zip_source(
                            appid, tool_type_actual, unlocker_type,
                            use_st_auto_update, add_all_dlc, patch_depot_key
                        )
                    finally:
                        # 禁用动画进度模式
                        self._progress_animating = False
                else:
                    self._update_download_progress_state(20, f"阶段 3/6：主入库流程（GitHub 源：{tool_type_actual}）")
                    # 启用动画进度模式
                    self._progress_animating = True
                    self._progress_animation_value = 20.0
                    try:
                        repo = github_repo_map.get(tool_type_actual, tool_type_actual)
                        success = await backend.process_github_manifest(
                            appid, repo, unlocker_type,
                            use_st_auto_update, add_all_dlc, patch_depot_key
                        )
                    finally:
                        # 禁用动画进度模式
                        self._progress_animating = False
                
                # 主入库成功后，根据选项决定是否补全清单文件
                if success:
                    backend.log.info(f"主入库成功")
                    self._update_download_progress_state(90, "阶段 4/6：主入库完成")
                    return True
                
                return success
        
        # 检查是否有正在进行的入库任务
        if hasattr(self, 'unlock_worker') and self.unlock_worker and self.unlock_worker.isRunning():
            from qfluentwidgets import MessageBox
            msg_box = MessageBox(
                "入库进行中",
                f"当前正在处理入库任务，请选择操作：\n\n"
                f"• 取消入库：停止当前任务\n"
                f"• 继续入库：等待当前任务完成\n"
                f"• 换成当前清单入库：停止当前任务并使用新选择的清单源重新入库",
                self.window()
            )
            msg_box.yesButton.setText("换成当前清单入库")
            msg_box.cancelButton.setText("继续入库")
            # 添加第三个按钮"取消入库"
            cancel_btn = PushButton("取消入库", msg_box.buttonGroup)
            msg_box.buttonLayout.insertWidget(0, cancel_btn, 1)
            msg_box.buttonGroup.setFixedHeight(81)  # 保持高度不变，三按钮水平排列

            choice = [None]  # 用列表存储选择，避免闭包问题

            def on_cancel_import():
                choice[0] = "cancel"
                msg_box.accept()

            cancel_btn.clicked.connect(on_cancel_import)

            result = msg_box.exec()

            if choice[0] == "cancel":
                # 取消入库：停止当前任务，不启动新任务
                self.unlock_worker.cancel()
                self.unlock_worker.wait()
                self.unlock_worker.deleteLater()
                self.unlock_worker = None
                InfoBar.info(
                    title="已取消",
                    content="入库任务已取消",
                    parent=self.window(),
                    position=InfoBarPosition.TOP,
                    duration=2000
                )
                return
            elif result == 0:
                # 继续入库（cancelButton）：不做任何事
                return
            else:
                # 换成当前清单入库（yesButton）：取消当前任务后启动新任务
                old_worker = self.unlock_worker
                self.unlock_worker = None
                old_worker.cancel()
                old_worker.wait()  # 阻塞直到线程真正结束
                old_worker.deleteLater()

                new_worker = AsyncWorker(_unlock())
                new_worker.result_ready.connect(self.on_unlock_complete)
                new_worker.error.connect(self.on_unlock_error)
                new_worker.finished.connect(new_worker.deleteLater)
                self.unlock_worker = new_worker
                new_worker.start()
                return

        self.unlock_worker = AsyncWorker(_unlock())
        self.unlock_worker.result_ready.connect(self.on_unlock_complete)
        self.unlock_worker.error.connect(self.on_unlock_error)
        self.unlock_worker.finished.connect(self.unlock_worker.deleteLater)
        self.unlock_worker.start()
    
    @pyqtSlot(object)
    def on_unlock_complete(self, success):
        """入库完成"""
        self.unlock_worker = None

        # 完成下载进度条
        if success:
            self._finish_download_progress(True, "入库完成！")
        else:
            self._finish_download_progress(False, "入库失败，请查看日志或尝试其他清单源")

        # 始终显示在主窗口，不受当前页面限制
        bar_parent = self.window()

        if success:
            InfoBar.success(
                title=tr("add_success"),
                content=tr("add_success_content").format(self.current_appid if hasattr(self, 'current_appid') else '游戏'),
                parent=bar_parent,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            self.notify_home_refresh()
            
            # 后台获取并缓存游戏封面和名称
            if hasattr(self, 'current_appid') and self.current_appid:
                self._cache_game_info_after_add(self.current_appid)
        else:
            InfoBar.error(
                title=tr("delete_failed"),
                content=tr("process_failed") + "，" + tr("check_logs"),
                parent=bar_parent,
                position=InfoBarPosition.TOP
            )
    
    def _cache_game_info_after_add(self, appid: str):
        """入库成功后后台获取并缓存游戏封面和名称"""
        async def _fetch_and_cache():
            from backend.cai_backend import CaiBackend
            
            try:
                async with CaiBackend() as backend:
                    await backend.initialize()
                    
                    # 获取游戏信息
                    game_info = await backend.get_game_info_by_appid(appid)
                    if game_info:
                        # 缓存游戏名称
                        game_name = game_info.get("name", "")
                        if game_name:
                            _cache_name(appid, game_name)
                        
                        # 获取封面图片URL
                        cover_url = game_info.get("header_image", f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg")
                        
                        # 下载并缓存封面图片
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(cover_url, timeout=10) as response:
                                    if response.status == 200:
                                        cover_data = await response.read()
                                        _cache_cover(appid, cover_data)
                        except Exception:
                            pass
            except Exception:
                pass
        
        # 在后台执行，不阻塞UI
        worker = AsyncWorker(_fetch_and_cache())
        worker.finished.connect(worker.deleteLater)
        worker.start()
    
    @pyqtSlot(str)
    def on_unlock_error(self, error):
        """入库失败"""
        self.unlock_worker = None
        
        # 完成下载进度条（失败状态）
        self._finish_download_progress(False, f"入库失败: {error[:50]}...")
        
        if "Server disconnected" in error or "RemoteProtocolError" in error:
            error_msg = "网络连接失败，服务器断开连接\n\n可能的原因：\n1. 清单源服务器不稳定\n2. 网络连接问题\n\n建议：\n- 尝试切换其他清单源\n- 检查网络连接\n- 稍后重试"
        elif "404" in error or "not found" in error.lower():
            current_appid = getattr(self, 'current_appid', '当前游戏')
            current_source = self.manifest_source_combo.currentText()
            error_msg = f"未在 {current_source} 中找到 AppID {current_appid} 的清单\n\n建议：\n- 尝试切换其他清单源\n- 使用「自动搜索GitHub」选项\n- 确认游戏是否存在"
        elif "未找到" in error or "not found" in error.lower():
            current_appid = getattr(self, 'current_appid', '当前游戏')
            error_msg = f"未找到 AppID {current_appid} 的清单\n\n建议：\n- 尝试切换其他清单源\n- 使用「自动搜索GitHub」选项"
        elif "GitHub API" in error:
            error_msg = "GitHub API 请求次数已用尽\n\n建议：\n- 在设置中配置 GitHub Token\n- 使用其他清单源"
        else:
            error_msg = error
        
        InfoBar.error(
            title=tr("delete_failed"),
            content=tr("check_details"),
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=5000
        )


class SettinsCard(GroupHeaderCardWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(tr("basic_settings"))
        self.setBorderRadius(8)
        self.setStyleSheet("""
            SettinsCard {
                border: none;
                background: transparent;
            }
        """)

        # Steam路径设置
        self.steam_path_edit = LineEdit()
        self.steam_path_edit.setPlaceholderText(tr("auto_detect_placeholder"))
        self.steam_path_edit.setFixedWidth(280)
        
        # 文件夹选择按钮
        self.steam_path_button = TransparentToolButton(FluentIcon.FOLDER, self)
        self.steam_path_button.setFixedSize(32, 32)
        self.steam_path_button.setToolTip("选择Steam安装路径")
        self.steam_path_button.clicked.connect(self.select_steam_path)
        
        # 创建水平布局容器
        steam_path_layout = QHBoxLayout()
        steam_path_layout.addWidget(self.steam_path_edit)
        steam_path_layout.addWidget(self.steam_path_button)
        steam_path_layout.setContentsMargins(0, 0, 0, 0)
        
        steam_path_widget = QWidget()
        steam_path_widget.setLayout(steam_path_layout)
        
        # GitHub Token设置
        self.token_edit = LineEdit()
        self.token_edit.setPlaceholderText(tr("token_placeholder"))
        self.token_edit.setFixedWidth(320)

        # Manifest API Key设置
        self.manifest_api_key_edit = LineEdit()
        self.manifest_api_key_edit.setPlaceholderText("请输入 Manifest API Key")
        self.manifest_api_key_edit.setFixedWidth(320)
        
        # 创建链接按钮
        self.manifest_api_link = HyperlinkButton(
            "https://manifesthub1.filegear-sg.me/",
            "获取地址"
        )
        self.manifest_api_link.setFixedWidth(80)
        
        # 创建水平布局容器
        manifest_api_layout = QHBoxLayout()
        manifest_api_layout.addWidget(self.manifest_api_key_edit)
        manifest_api_layout.addWidget(self.manifest_api_link)
        manifest_api_layout.setContentsMargins(0, 0, 0, 0)
        
        manifest_api_widget = QWidget()
        manifest_api_widget.setLayout(manifest_api_layout)

        # 添加组件到分组中
        self.addGroup(FluentIcon.FOLDER, tr("steam_path"), tr("steam_path_hint"), steam_path_widget)
        self.addGroup(FluentIcon.GITHUB, tr("github_token"), tr("github_token_hint"), self.token_edit)
        self.addGroup(FluentIcon.CERTIFICATE, "Manifest API Key", "用于方法2的API拉取清单", manifest_api_widget)
    
    def select_steam_path(self):
        """选择Steam安装路径"""
        from PyQt6.QtWidgets import QFileDialog
        
        # 获取当前路径作为初始目录
        current_path = self.steam_path_edit.text().strip()
        if current_path:
            initial_dir = current_path
        else:
            # 尝试自动检测Steam路径
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\\Valve\\Steam')
                steam_path, _ = winreg.QueryValueEx(key, 'SteamPath')
                winreg.CloseKey(key)
                initial_dir = steam_path
            except:
                initial_dir = ""
        
        # 打开文件夹选择对话框
        folder_path = QFileDialog.getExistingDirectory(
            self, 
            "选择Steam安装路径",
            initial_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if folder_path:
            self.steam_path_edit.setText(folder_path)


class RepoListItem(CardWidget):
    """仓库列表项 - 自定义卡片样式"""
    delete_clicked = pyqtSignal()  # 删除按钮点击信号

    def __init__(self, name: str, path: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.path = path
        self.setFixedHeight(60)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.name_label = BodyLabel(self.name)
        info_layout.addWidget(self.name_label)

        self.path_label = CaptionLabel(self.path)
        self.path_label.setStyleSheet("color: gray;")
        info_layout.addWidget(self.path_label)

        layout.addLayout(info_layout, 1)

        # 删除按钮
        self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(32, 32)
        self.delete_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self.delete_btn)


class RepoListCard(CardWidget):
    """仓库列表卡片 - 完全自定义实现"""

    folderChanged = pyqtSignal(list)  # 仓库列表变化信号

    def __init__(self, title: str, desc: str, icon=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.desc = desc
        self.icon = icon or FluentIcon.LIBRARY
        self.repos = []
        self._setup_ui()

    def _setup_ui(self):
        self.setBorderRadius(8)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题区域
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # 图标
        icon_widget = IconWidget(self.icon)
        icon_widget.setFixedSize(20, 20)
        header_layout.addWidget(icon_widget)

        # 标题和描述
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title_label = BodyLabel(self.title)
        title_label.setStyleSheet("font-weight: bold;")
        title_layout.addWidget(title_label)

        if self.desc:
            desc_label = CaptionLabel(self.desc)
            desc_label.setStyleSheet("color: gray;")
            title_layout.addWidget(desc_label)

        header_layout.addLayout(title_layout, 1)

        # 添加按钮
        self.add_btn = PushButton(tr("add"))
        self.add_btn.setFixedWidth(80)
        self.add_btn.setIcon(FluentIcon.ADD)
        self.add_btn.clicked.connect(self._show_add_dialog)
        header_layout.addWidget(self.add_btn)

        layout.addLayout(header_layout)

        # 分隔线
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(128, 128, 128, 0.2);")
        layout.addWidget(line)

        # 仓库列表区域
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 8, 0, 8)
        self.list_layout.setSpacing(8)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self.list_widget)
        layout.addStretch(1)

    def set_repos(self, repos: list):
        """设置仓库列表"""
        self.repos = repos.copy()
        self._refresh_list()

    def get_repos(self) -> list:
        """获取仓库列表"""
        return self.repos.copy()

    def _refresh_list(self):
        """刷新列表显示"""
        # 清空现有项 - 使用递归删除确保彻底清理
        self._clear_layout(self.list_layout)

        # 添加仓库项
        if not self.repos:
            empty_label = CaptionLabel(tr("no_repos"))
            empty_label.setStyleSheet("color: gray; padding: 16px 0;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_label)
        else:
            for i, repo in enumerate(self.repos):
                name = repo.get("name", "")
                path = repo.get("repo", "") or repo.get("url", "")
                item = RepoListItem(name, path)
                item.delete_clicked.connect(lambda checked=False, idx=i: self._delete_repo(idx))
                self.list_layout.addWidget(item)
        
        # 强制更新布局
        self.list_widget.update()
        self.update()

    def _clear_layout(self, layout):
        """递归清空布局中的所有 widget"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _delete_repo(self, index: int):
        """删除仓库"""
        if 0 <= index < len(self.repos):
            self.repos.pop(index)
            self._refresh_list()
            self.folderChanged.emit(self.repos)

    def _show_add_dialog(self):
        """显示添加对话框 - 子类实现"""
        pass


class AddRepoDialog(QDialog):
    """添加仓库对话框 - 独立窗口"""

    def __init__(self, title: str, is_github: bool = True, parent=None):
        super().__init__(parent)
        self.is_github = is_github
        self.setWindowTitle(title)
        self.setFixedSize(500, 280)
        self._setup_ui()

    def _setup_ui(self):
        # 根据主题设置背景色
        if isDarkTheme():
            bg_color = "#2b2b2b"
            text_color = "#ffffff"
        else:
            bg_color = "#f5f5f5"
            text_color = "#333333"
        
        # 设置对话框背景色 - 不使用WA_TranslucentBackground
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_label = SubtitleLabel(self.windowTitle())
        layout.addWidget(title_label)

        # 名称输入
        name_layout = QHBoxLayout()
        name_label = BodyLabel(tr("repo_name"))
        name_label.setFixedWidth(80)
        name_layout.addWidget(name_label)
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText(tr("repo_name_placeholder"))
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 路径/URL输入
        path_layout = QHBoxLayout()
        if self.is_github:
            path_label = BodyLabel(tr("repo_path"))
            self.path_edit = LineEdit()
            self.path_edit.setPlaceholderText(tr("github_repo_placeholder"))
        else:
            path_label = BodyLabel(tr("repo_url"))
            self.path_edit = LineEdit()
            self.path_edit.setPlaceholderText(tr("zip_url_placeholder"))
        path_label.setFixedWidth(80)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_edit)
        layout.addLayout(path_layout)

        # 提示文本
        if self.is_github:
            hint_label = CaptionLabel(tr("github_repo_hint"))
        else:
            hint_label = CaptionLabel(tr("zip_url_hint"))
        hint_label.setStyleSheet("color: gray;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        layout.addStretch(1)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        
        self.cancel_btn = PushButton(tr("cancel"))
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = PrimaryPushButton(tr("save"))
        self.save_btn.setFixedWidth(100)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def get_data(self):
        """获取输入的数据"""
        return self.name_edit.text().strip(), self.path_edit.text().strip()


class GitHubRepoCard(RepoListCard):
    """GitHub仓库列表卡片"""

    def __init__(self, parent=None):
        super().__init__(
            tr("github_repos"),
            tr("github_repos_desc"),
            FluentIcon.GITHUB,
            parent
        )

    def _show_add_dialog(self):
        """显示添加GitHub仓库对话框"""
        dialog = AddRepoDialog(tr("add_github_repo"), is_github=True, parent=self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, repo_path = dialog.get_data()

            if not name or not repo_path:
                InfoBar.warning(
                    title=tr("input_incomplete"),
                    content=tr("please_fill_all_fields"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                return

            if "/" not in repo_path:
                InfoBar.warning(
                    title=tr("invalid_format"),
                    content=tr("github_format_hint"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                return

            # 检查重复
            for repo in self.repos:
                if repo.get("name") == name or repo.get("repo") == repo_path:
                    InfoBar.warning(
                        title=tr("repo_exists"),
                        content=tr("repo_already_added"),
                        parent=self,
                        position=InfoBarPosition.TOP
                    )
                    return

            self.repos.append({"name": name, "repo": repo_path})
            self._refresh_list()
            self.folderChanged.emit(self.repos)

            InfoBar.success(
                title=tr("add_success"),
                content=tr("github_repo_added"),
                parent=self,
                position=InfoBarPosition.TOP
            )


class ZipRepoCard(RepoListCard):
    """ZIP仓库列表卡片"""

    def __init__(self, parent=None):
        super().__init__(
            tr("zip_repos"),
            tr("zip_repos_desc"),
            FluentIcon.ZIP_FOLDER,
            parent
        )

    def _show_add_dialog(self):
        """显示添加ZIP仓库对话框"""
        dialog = AddRepoDialog(tr("add_zip_repo"), is_github=False, parent=self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, url = dialog.get_data()

            if not name or not url:
                InfoBar.warning(
                    title=tr("input_incomplete"),
                    content=tr("please_fill_all_fields"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                return

            if "{app_id}" not in url:
                InfoBar.warning(
                    title=tr("invalid_format"),
                    content=tr("zip_format_hint"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                return

            # 检查重复
            for repo in self.repos:
                if repo.get("name") == name or repo.get("url") == url:
                    InfoBar.warning(
                        title=tr("repo_exists"),
                        content=tr("repo_already_added"),
                        parent=self,
                        position=InfoBarPosition.TOP
                    )
                    return

            self.repos.append({"name": name, "url": url})
            self._refresh_list()
            self.folderChanged.emit(self.repos)

            InfoBar.success(
                title=tr("add_success"),
                content=tr("zip_repo_added"),
                parent=self,
                position=InfoBarPosition.TOP
            )


class CustomReposCard(QWidget):
    """自定义清单库卡片 - 包含GitHub和ZIP两种仓库列表"""

    repos_changed = pyqtSignal()  # 仓库列表变化信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.github_repos = []
        self.zip_repos = []
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(16)

        # GitHub仓库列表卡片
        self.github_card = GitHubRepoCard(self)
        self.github_card.folderChanged.connect(self._on_github_changed)
        self.layout.addWidget(self.github_card)

        # ZIP仓库列表卡片
        self.zip_card = ZipRepoCard(self)
        self.zip_card.folderChanged.connect(self._on_zip_changed)
        self.layout.addWidget(self.zip_card)

    def set_repos(self, github_repos: list, zip_repos: list):
        """设置仓库列表"""
        self.github_repos = github_repos.copy()
        self.zip_repos = zip_repos.copy()
        self.github_card.set_repos(self.github_repos)
        self.zip_card.set_repos(self.zip_repos)

    def get_repos(self):
        """获取仓库列表"""
        return self.github_card.get_repos(), self.zip_card.get_repos()

    def _on_github_changed(self, repos: list):
        """GitHub仓库列表变化"""
        self.github_repos = repos
        self.repos_changed.emit()

    def _on_zip_changed(self, repos: list):
        """ZIP仓库列表变化"""
        self.zip_repos = repos
        self.repos_changed.emit()


# ===== 联机游戏页面 =====
class LauncherLogWorker(QThread):
    """联机日志轮询线程"""
    log_received = pyqtSignal(str)
    service_stopped = pyqtSignal()

    def __init__(self, service: SystemCoreService):
        super().__init__()
        self._service = service
        self._running = True

    def run(self):
        import time
        while self._running and self._service.is_active:
            time.sleep(0.5)
        if self._running:
            self.service_stopped.emit()

    def stop(self):
        self._running = False


class LauncherPage(ScrollArea):
    """联机游戏页面 - 支持 DLL 注入 / BAT 脚本 / AppID Changer 三种方式"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("launcherPage")
        self.setWidgetResizable(True)

        self._service: Optional[SystemCoreService] = None
        self._changer_service: Optional[AppIDChangerService] = None
        self._log_worker: Optional[LauncherLogWorker] = None
        self._running = False
        self._log_lines = []

        container = QWidget()
        container.setObjectName("launcherContainer")
        self.setWidget(container)
        self.setStyleSheet("LauncherPage { background: transparent; }")
        container.setStyleSheet("QWidget#launcherContainer { background: transparent; }")

        self.mainLayout = QVBoxLayout(container)
        self.mainLayout.setContentsMargins(30, 30, 30, 30)
        self.mainLayout.setSpacing(16)

        # 标题行
        header = QHBoxLayout()
        self.title_label = SubtitleLabel(tr("launcher_title"), self)
        self.status_label = CaptionLabel(tr("launcher_status_ready"), self)
        self.status_label.setTextColor("#10b981", "#10b981")
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.status_label)
        self.mainLayout.addLayout(header)

        # ── 模式选择卡片 ──
        mode_card = CardWidget(self)
        mode_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(20, 16, 20, 16)
        mode_layout.setSpacing(10)
        mode_layout.addWidget(BodyLabel(tr("launcher_mode_select"), mode_card))

        self.mode_dll_btn = PushButton(tr("launcher_mode_dll"), mode_card)
        self.mode_bat_btn = PushButton(tr("launcher_mode_bat"), mode_card)
        self.mode_changer_btn = PushButton(tr("launcher_mode_changer"), mode_card)
        self.mode_dll_btn.setCheckable(True)
        self.mode_bat_btn.setCheckable(True)
        self.mode_changer_btn.setCheckable(True)
        self.mode_dll_btn.setChecked(True)  # 默认 DLL 模式
        self.mode_dll_btn.clicked.connect(lambda: self._select_mode("dll"))
        self.mode_bat_btn.clicked.connect(lambda: self._select_mode("bat"))
        self.mode_changer_btn.clicked.connect(lambda: self._select_mode("changer"))

        mode_btn_row = QHBoxLayout()
        mode_btn_row.addWidget(self.mode_dll_btn)
        mode_btn_row.addWidget(self.mode_bat_btn)
        mode_btn_row.addWidget(self.mode_changer_btn)
        mode_layout.addLayout(mode_btn_row)

        self.mode_desc_label = CaptionLabel(tr("launcher_mode_dll_desc"), mode_card)
        self.mode_desc_label.setWordWrap(True)
        self.mode_desc_label.setTextColor("#606060", "#a0a0a0")
        mode_layout.addWidget(self.mode_desc_label)
        self.mainLayout.addWidget(mode_card)

        # ── 游戏路径卡片 ──
        path_card = CardWidget(self)
        path_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        path_layout = QVBoxLayout(path_card)
        path_layout.setContentsMargins(20, 16, 20, 16)
        path_layout.setSpacing(10)
        path_layout.addWidget(BodyLabel(tr("launcher_game_exe"), path_card))

        path_row = QHBoxLayout()
        self.exe_input = LineEdit(path_card)
        self.exe_input.setPlaceholderText("请选择游戏 .exe 文件...")
        self.exe_input.setReadOnly(True)
        self.browse_btn = PushButton(tr("launcher_browse"), path_card)
        self.browse_btn.setIcon(FluentIcon.FOLDER)
        self.browse_btn.clicked.connect(self._browse_exe)
        path_row.addWidget(self.exe_input)
        path_row.addWidget(self.browse_btn)
        path_layout.addLayout(path_row)

        # AppID 输入
        appid_row = QHBoxLayout()
        appid_row.addWidget(CaptionLabel(tr("launcher_app_id") + ":", path_card))
        self.appid_input = LineEdit(path_card)
        self.appid_input.setText("480")
        self.appid_input.setFixedWidth(120)
        appid_hint = CaptionLabel(tr("launcher_app_id_hint"), path_card)
        appid_hint.setTextColor("#606060", "#a0a0a0")
        appid_row.addWidget(self.appid_input)
        appid_row.addWidget(appid_hint)
        appid_row.addStretch(1)
        path_layout.addLayout(appid_row)
        self.mainLayout.addWidget(path_card)

        # ── 操作按钮 ──
        self.action_btn = PrimaryPushButton(tr("launcher_start"), self)
        self.action_btn.setIcon(FluentIcon.PLAY)
        self.action_btn.setFixedHeight(40)
        self.action_btn.clicked.connect(self._on_action)
        self.mainLayout.addWidget(self.action_btn)

        # ── 日志卡片 ──
        log_card = CardWidget(self)
        log_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 16, 20, 16)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_header.addWidget(BodyLabel(tr("launcher_log"), log_card))
        log_header.addStretch(1)
        clear_btn = TransparentToolButton(FluentIcon.DELETE, log_card)
        clear_btn.setToolTip(tr("launcher_clear_log"))
        clear_btn.clicked.connect(self._clear_log)
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)

        self.log_view = TextEdit(log_card)
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(220)
        # 根据主题模式动态设置背景颜色
        if isDarkTheme():
            self.log_view.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.15); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        else:
            self.log_view.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        log_layout.addWidget(self.log_view)
        self.mainLayout.addWidget(log_card)
        self.mainLayout.addStretch(1)

        self._current_mode = "dll"
        self._log("系统初始化完成，等待操作...")

    # ── 内部方法 ──

    def _select_mode(self, mode: str):
        self._current_mode = mode
        self.mode_dll_btn.setChecked(mode == "dll")
        self.mode_bat_btn.setChecked(mode == "bat")
        self.mode_changer_btn.setChecked(mode == "changer")
        if mode == "dll":
            self.mode_desc_label.setText(tr("launcher_mode_dll_desc"))
            self.action_btn.setText(tr("launcher_start"))
            self.action_btn.setIcon(FluentIcon.PLAY)
        elif mode == "bat":
            self.mode_desc_label.setText(tr("launcher_mode_bat_desc"))
            self.action_btn.setText(tr("launcher_bat_start"))
            self.action_btn.setIcon(FluentIcon.PLAY)
        else:  # changer
            self.mode_desc_label.setText(tr("launcher_mode_changer_desc"))
            self.action_btn.setText(tr("launcher_changer_start"))
            self.action_btn.setIcon(FluentIcon.PLAY)

    def _log(self, msg: str):
        import time as _time
        ts = _time.strftime("%H:%M:%S")
        self._log_lines.append(f"[{ts}] {msg}")
        # 根据主题模式设置文字颜色
        if isDarkTheme():
            self.log_view.append(f"<span style='color:#888'>[{ts}]</span> <span style='color:#fff'>{msg}</span>")
        else:
            self.log_view.append(f"<span style='color:#666'>[{ts}]</span> <span style='color:#000'>{msg}</span>")
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self):
        self._log_lines.clear()
        self.log_view.clear()
    
    def notify_theme_changed(self):
        """通知日志显示组件主题已变化"""
        # 更新日志显示组件的样式
        if hasattr(self, 'log_view') and self.log_view:
            if isDarkTheme():
                self.log_view.setStyleSheet(
                    "TextEdit { background: rgba(0,0,0,0.15); border-radius: 6px; "
                    "font-size: 12px; padding: 8px; color: #ffffff; }"
                )
            else:
                self.log_view.setStyleSheet(
                    "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                    "font-size: 12px; padding: 8px; color: #000000; }"
                )
            
            # 强制刷新日志内容
            self.log_view.update()
            self.log_view.repaint()

    def _browse_exe(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "选择游戏程序", "", "可执行文件 (*.exe)"
        )
        if path:
            self.exe_input.setText(path)
            self._log(f"已选择: {path}")

    def _set_running(self, running: bool):
        self._running = running
        self.exe_input.setEnabled(not running)
        self.appid_input.setEnabled(not running)
        self.browse_btn.setEnabled(not running)
        self.mode_dll_btn.setEnabled(not running)
        self.mode_bat_btn.setEnabled(not running)
        self.mode_changer_btn.setEnabled(not running)
        if running:
            self.action_btn.setText(tr("launcher_stop"))
            self.action_btn.setIcon(FluentIcon.CLOSE)
            self.status_label.setText(tr("launcher_status_running"))
            self.status_label.setTextColor("#f59e0b", "#f59e0b")
        else:
            if self._current_mode == "dll":
                self.action_btn.setText(tr("launcher_start"))
            elif self._current_mode == "bat":
                self.action_btn.setText(tr("launcher_bat_start"))
            else:  # changer
                self.action_btn.setText(tr("launcher_changer_start"))
            self.action_btn.setIcon(FluentIcon.PLAY)
            self.status_label.setText(tr("launcher_status_ready"))
            self.status_label.setTextColor("#10b981", "#10b981")

    def _on_action(self):
        if self._running:
            self._stop_service()
        elif self._current_mode == "dll":
            self._start_dll_service()
        elif self._current_mode == "bat":
            self._start_bat_service()
        else:  # changer
            self._start_changer_service()

    # ── DLL 注入模式 ──

    def _start_dll_service(self):
        exe_path = self.exe_input.text().strip()
        app_id = self.appid_input.text().strip() or "480"
        if not app_id.isdigit():
            InfoBar.warning(title="参数错误", content="AppID 必须为数字", parent=self, position=InfoBarPosition.TOP)
            return

        # 读取 Steam 路径
        steam_path = None
        try:
            config_path = APP_ROOT / "config" / "config.json"
            if config_path.exists():
                import json as _json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = _json.load(f)
                steam_path = cfg.get("Custom_Steam_Path", "").strip() or None
        except Exception:
            pass

        self._service = SystemCoreService(self._log, steam_path)
        self._set_running(True)
        self._log(f"-> 启动 DLL 注入联机 | AppID: {app_id}")

        def on_finish():
            # 回到主线程更新 UI
            from PyQt6.QtCore import QMetaObject, Qt as _Qt
            QMetaObject.invokeMethod(self, "_on_service_finished", _Qt.ConnectionType.QueuedConnection)

        self._service.start_service(exe_path if exe_path else None, app_id, on_finish)

    @pyqtSlot()
    def _on_service_finished(self):
        self._set_running(False)
        self._log(tr("launcher_service_stopped"))

    def _stop_service(self):
        if self._service:
            self._service.stop()
            self._service.stop_routine()
            self._service = None
        if self._changer_service:
            self._changer_service.stop()
            self._changer_service = None
        self._set_running(False)
        self._log(tr("launcher_service_stopped"))

    # ── BAT 脚本模式 ──

    def _start_bat_service(self):
        exe_path = self.exe_input.text().strip()
        app_id = self.appid_input.text().strip() or "480"
        if not exe_path or not os.path.exists(exe_path):
            InfoBar.warning(title="提示", content=tr("launcher_no_exe"), parent=self, position=InfoBarPosition.TOP)
            return
        if not app_id.isdigit():
            InfoBar.warning(title="参数错误", content="AppID 必须为数字", parent=self, position=InfoBarPosition.TOP)
            return

        try:
            work_dir = os.path.dirname(exe_path)
            exe_name = os.path.basename(exe_path)
            bat_name = "Cai_Inject_Start.bat"
            bat_path = os.path.join(work_dir, bat_name)
            bat_content = (
                f"@echo off\n"
                f"set SteamAppId={app_id}\n"
                f"set SteamGameId={app_id}\n"
                f'start "" "{exe_name}"\n'
                f"exit\n"
            )
            with open(bat_path, "w", encoding="gbk") as f:
                f.write(bat_content)
            self._log(f"-> 已生成启动脚本: {bat_name}")
            subprocess.Popen(
                ["cmd.exe", "/c", bat_name],
                cwd=work_dir,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._log(f"✅ 游戏已通过 BAT 注入启动 (AppID: {app_id})")
            InfoBar.success(title=tr("launcher_service_started"), content=tr("launcher_bat_done"), parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            self._log(f"❌ BAT 启动失败: {e}")
            InfoBar.error(title=tr("launcher_error"), content=str(e), parent=self, position=InfoBarPosition.TOP)

    # ── AppID Changer 模式 ──

    def _start_changer_service(self):
        exe_path = self.exe_input.text().strip()
        app_id = self.appid_input.text().strip() or "480"
        if not exe_path or not os.path.exists(exe_path):
            InfoBar.warning(title="提示", content=tr("launcher_no_exe"), parent=self, position=InfoBarPosition.TOP)
            return
        if not app_id.isdigit():
            InfoBar.warning(title="参数错误", content="AppID 必须为数字", parent=self, position=InfoBarPosition.TOP)
            return

        self._changer_service = AppIDChangerService(self._log)
        self._set_running(True)
        self._log(f"-> 启动 AppID Changer 联机 | AppID: {app_id}")

        def on_finish():
            # 回到主线程更新 UI
            from PyQt6.QtCore import QMetaObject, Qt as _Qt
            QMetaObject.invokeMethod(self, "_on_service_finished", _Qt.ConnectionType.QueuedConnection)

        self._changer_service.start_service(exe_path, app_id, on_finish)


# ============================================================
# 修改器页面
# ============================================================

class TrainerSearchWorker(QThread):
    """修改器搜索工作线程"""
    result_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, keyword: str):
        super().__init__()
        self.keyword = keyword
        self._stop_flag = False

    def stop(self):
        """请求停止线程"""
        self._stop_flag = True

    def run(self):
        try:
            from backend.trainer_backend import search_trainers
            results = search_trainers(self.keyword)
            if not self._stop_flag:
                self.result_ready.emit(results)
        except Exception as e:
            if not self._stop_flag:
                self.error.emit(str(e))


class TrainerDownloadWorker(QThread):
    """修改器下载工作线程"""
    progress = pyqtSignal(int, int)   # downloaded, total
    log_msg = pyqtSignal(str)
    finished = pyqtSignal(dict)       # result dict

    def __init__(self, trainer: dict):
        super().__init__()
        self.trainer = trainer

    def run(self):
        try:
            from backend.trainer_backend import download_trainer
            result = download_trainer(
                self.trainer,
                progress_cb=lambda d, t: self.progress.emit(d, t),
                log_cb=lambda m: self.log_msg.emit(m),
            )
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"success": False, "path": "", "message": str(e)})


class TrainerPage(ScrollArea):
    """游戏修改器页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trainerPage")
        self.setWidgetResizable(True)

        self._search_worker: Optional[TrainerSearchWorker] = None
        self._download_worker: Optional[TrainerDownloadWorker] = None
        self._search_results: list = []
        self._installed: list = []

        container = QWidget()
        container.setObjectName("trainerContainer")
        self.setWidget(container)
        self.setStyleSheet("TrainerPage { background: transparent; }")
        container.setStyleSheet("QWidget#trainerContainer { background: transparent; }")

        main = QVBoxLayout(container)
        main.setContentsMargins(30, 30, 30, 30)
        main.setSpacing(16)

        # 标题
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel(tr("trainer_title"), self))
        header.addStretch(1)
        refresh_btn = TransparentToolButton(FluentIcon.SYNC, self)
        refresh_btn.setToolTip(tr("trainer_refresh_btn"))
        refresh_btn.clicked.connect(self._load_installed)
        open_folder_btn = TransparentToolButton(FluentIcon.FOLDER, self)
        open_folder_btn.setToolTip(tr("trainer_open_folder"))
        open_folder_btn.clicked.connect(self._open_folder)
        header.addWidget(refresh_btn)
        header.addWidget(open_folder_btn)
        main.addLayout(header)

        # 搜索卡片
        search_card = CardWidget(self)
        search_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        search_layout = QVBoxLayout(search_card)
        search_layout.setContentsMargins(20, 16, 20, 16)
        search_layout.setSpacing(10)
        search_layout.addWidget(BodyLabel(tr("trainer_search_results"), search_card))

        search_row = QHBoxLayout()
        self.search_input = SearchLineEdit(search_card)
        self.search_input.setPlaceholderText(tr("trainer_search_placeholder"))
        self.search_input.returnPressed.connect(self._on_search)
        self.search_btn = PrimaryPushButton(tr("trainer_search_btn"), search_card)
        self.search_btn.setIcon(FluentIcon.SEARCH)
        self.search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_btn)
        search_layout.addLayout(search_row)

        # 搜索结果列表
        from qfluentwidgets import ListWidget
        self.result_list = ListWidget(search_card)
        self.result_list.setFixedHeight(200)
        self.result_list.itemDoubleClicked.connect(self._on_download_selected)
        search_layout.addWidget(self.result_list)

        # 下载按钮行
        dl_row = QHBoxLayout()
        self.download_btn = PushButton(tr("trainer_download_btn"), search_card)
        self.download_btn.setIcon(FluentIcon.DOWNLOAD)
        self.download_btn.clicked.connect(self._on_download_selected)
        self.download_btn.setEnabled(False)
        self.result_list.currentRowChanged.connect(lambda i: self.download_btn.setEnabled(i >= 0))
        dl_row.addStretch(1)
        dl_row.addWidget(self.download_btn)
        search_layout.addLayout(dl_row)

        # 进度条
        self.progress_bar = ProgressBar(search_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        search_layout.addWidget(self.progress_bar)

        main.addWidget(search_card)

        # 已安装修改器卡片
        installed_card = CardWidget(self)
        installed_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        installed_layout = QVBoxLayout(installed_card)
        installed_layout.setContentsMargins(20, 16, 20, 16)
        installed_layout.setSpacing(10)
        installed_layout.addWidget(BodyLabel(tr("trainer_installed_title"), installed_card))

        self.installed_list = ListWidget(installed_card)
        self.installed_list.setFixedHeight(200)
        installed_layout.addWidget(self.installed_list)

        btn_row = QHBoxLayout()
        self.launch_btn = PrimaryPushButton(tr("trainer_launch_btn"), installed_card)
        self.launch_btn.setIcon(FluentIcon.PLAY)
        self.launch_btn.clicked.connect(self._on_launch)
        self.launch_btn.setEnabled(False)
        self.delete_btn = PushButton(tr("trainer_delete_btn"), installed_card)
        self.delete_btn.setIcon(FluentIcon.DELETE)
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        self.installed_list.currentRowChanged.connect(self._on_installed_selection)
        btn_row.addStretch(1)
        btn_row.addWidget(self.launch_btn)
        btn_row.addWidget(self.delete_btn)
        installed_layout.addLayout(btn_row)
        main.addWidget(installed_card)

        # 日志卡片
        log_card = CardWidget(self)
        log_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 16, 20, 16)
        log_layout.setSpacing(8)
        log_header = QHBoxLayout()
        log_header.addWidget(BodyLabel(tr("trainer_log"), log_card))
        log_header.addStretch(1)
        clear_btn = TransparentToolButton(FluentIcon.DELETE, log_card)
        clear_btn.setToolTip(tr("trainer_clear_log"))
        clear_btn.clicked.connect(lambda: self.log_view.clear())
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)
        self.log_view = TextEdit(log_card)
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(160)
        log_layout.addWidget(self.log_view)
        main.addWidget(log_card)
        main.addStretch(1)

        self._load_installed()
        self._check_db()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_installed()

    def _log(self, msg: str):
        import time as _t
        ts = _t.strftime("%H:%M:%S")
        if isDarkTheme():
            self.log_view.append(f"<span style='color:#888'>[{ts}]</span> <span style='color:#fff'>{msg}</span>")
        else:
            self.log_view.append(f"<span style='color:#666'>[{ts}]</span> <span style='color:#000'>{msg}</span>")
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _check_db(self):
        self._log("修改器功能已就绪，首次搜索会从 FLiNG 官网拉取列表（约 3-5 秒），之后 24h 内走本地缓存")

    def _load_installed(self):
        from backend.trainer_backend import list_installed_trainers
        self._installed = list_installed_trainers()
        self.installed_list.clear()
        if not self._installed:
            self.installed_list.addItem(tr("trainer_no_installed"))
        else:
            for t in self._installed:
                ver = f"  [{t['version']}]" if t.get("version") else ""
                self.installed_list.addItem(f"{t['name']}{ver}")
        self.launch_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

    def _on_installed_selection(self, idx: int):
        has = idx >= 0 and bool(self._installed)
        self.launch_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _open_folder(self):
        from backend.trainer_backend import get_trainer_dir
        path = get_trainer_dir()
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def _on_search(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        self.result_list.clear()
        self.result_list.addItem(tr("trainer_searching"))
        self.search_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self._search_results = []

        # 强制终止旧线程
        old_worker = self._search_worker
        self._search_worker = None
        if old_worker is not None:
            try:
                if old_worker.isRunning():
                    old_worker.stop()
                    old_worker.terminate()
                    old_worker.wait(500)
                old_worker.deleteLater()
            except RuntimeError:
                pass

        self._search_worker = TrainerSearchWorker(keyword)
        self._search_worker.result_ready.connect(self._on_search_done)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.finished.connect(self._on_worker_finished)
        self._search_worker.start()

    def _on_search_done(self, results: list):
        self.search_btn.setEnabled(True)
        self.result_list.clear()
        self._search_results = results
        if not results:
            self.result_list.addItem(tr("trainer_no_results"))
            self._log(tr("trainer_no_results"))
        else:
            for r in results:
                ver = f"  [{r['version']}]" if r.get("version") else ""
                self.result_list.addItem(f"{r['trainer_name']}{ver}")
            self._log(f"找到 {len(results)} 个修改器")

    def _on_search_error(self, err: str):
        self.search_btn.setEnabled(True)
        self.result_list.clear()
        self.result_list.addItem(f"搜索失败: {err}")
        self._log(f"❌ 搜索失败: {err}")

    def _on_worker_finished(self):
        """Worker完成后清理"""
        if self._search_worker:
            self._search_worker.deleteLater()
            self._search_worker = None

    def _on_download_selected(self):
        idx = self.result_list.currentRow()
        if idx < 0 or idx >= len(self._search_results):
            return
        trainer = self._search_results[idx]
        if not trainer.get("url"):
            InfoBar.warning(title="提示", content="该修改器暂无下载链接", parent=self, position=InfoBarPosition.TOP)
            return

        self.download_btn.setEnabled(False)
        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._log(f"开始下载: {trainer['trainer_name']}")

        # 强制终止旧线程
        old_worker = self._download_worker
        self._download_worker = None
        if old_worker is not None:
            try:
                if old_worker.isRunning():
                    old_worker.terminate()
                    old_worker.wait(500)
                old_worker.deleteLater()
            except RuntimeError:
                pass

        self._download_worker = TrainerDownloadWorker(trainer)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.log_msg.connect(self._log)
        self._download_worker.finished.connect(self._on_download_done)
        self._download_worker.finished.connect(self._on_download_worker_finished)
        self._download_worker.start()

    def _on_download_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int(downloaded * 100 / total)
            self.progress_bar.setValue(pct)

    def _on_download_done(self, result: dict):
        self.download_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if result.get("success"):
            InfoBar.success(
                title=tr("trainer_download_success"),
                content=result.get("message", ""),
                parent=self,
                position=InfoBarPosition.TOP,
            )
            self._load_installed()
        else:
            InfoBar.error(
                title=tr("trainer_download_failed"),
                content=result.get("message", ""),
                parent=self,
                position=InfoBarPosition.TOP,
            )

    def _on_download_worker_finished(self):
        """下载Worker完成后清理"""
        if self._download_worker:
            self._download_worker.deleteLater()
            self._download_worker = None

    def _on_launch(self):
        idx = self.installed_list.currentRow()
        if idx < 0 or idx >= len(self._installed):
            return
        trainer = self._installed[idx]
        from backend.trainer_backend import launch_trainer
        ok = launch_trainer(trainer["exe"])
        if ok:
            self._log(f"✅ 已启动: {trainer['name']}")
        else:
            InfoBar.error(title=tr("trainer_launch_failed"), content=trainer["name"], parent=self, position=InfoBarPosition.TOP)

    def _on_delete(self):
        idx = self.installed_list.currentRow()
        if idx < 0 or idx >= len(self._installed):
            return
        trainer = self._installed[idx]
        dialog = MessageBox(
            tr("trainer_delete_confirm"),
            tr("trainer_delete_confirm_msg", trainer["name"]),
            self,
        )
        if dialog.exec():
            from backend.trainer_backend import delete_trainer
            ok = delete_trainer(trainer["path"])
            if ok:
                self._log(f"🗑️ 已删除: {trainer['name']}")
                self._load_installed()
            else:
                InfoBar.error(title="删除失败", content=trainer["name"], parent=self, position=InfoBarPosition.TOP)

    def notify_theme_changed(self):
        pass


class DrmPage(ScrollArea):
    """D加密授权页面 - 使用 SegmentedWidget 切换功能模块"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drmPage")
        self.setWidgetResizable(True)
        self._cw_result = None

        container = QWidget()
        container.setObjectName("drmContainer")
        self.setWidget(container)
        self.setStyleSheet("DrmPage { background: transparent; }")
        container.setStyleSheet("QWidget#drmContainer { background: transparent; }")

        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(30, 60, 30, 8)
        self.main_layout.setSpacing(2)

        self.main_layout.addWidget(SubtitleLabel(tr("drm_page_title"), self))

        # 创建 SegmentedWidget 用于切换功能模块
        self.segmented_widget = SegmentedWidget(self)
        self.segmented_widget.setStyleSheet("""
            SegmentedWidget {
                background: transparent;
            }
        """)
        self.main_layout.addWidget(self.segmented_widget)

        # 创建 QStackedWidget 用于切换页面内容
        self.stacked_widget = QStackedWidget(self)
        self.main_layout.addWidget(self.stacked_widget)

        # 创建三个功能页面
        self._init_gbe_page()
        self._init_gl_page()
        self._init_extractor_page()

        # 添加标签项到 SegmentedWidget
        self.segmented_widget.addItem(
            routeKey="gbe",
            text="GBE模式",
            onClick=lambda: self.stacked_widget.setCurrentIndex(0)
        )
        self.segmented_widget.addItem(
            routeKey="gl",
            text="GL模式",
            onClick=lambda: self.stacked_widget.setCurrentIndex(1)
        )
        self.segmented_widget.addItem(
            routeKey="extractor",
            text="CW提取工具",
            onClick=lambda: self.stacked_widget.setCurrentIndex(2)
        )

        # 设置默认选中项
        self.segmented_widget.setCurrentItem("gbe")
        self.stacked_widget.setCurrentIndex(0)

        # 连接信号
        self.stacked_widget.currentChanged.connect(self._on_page_changed)

    def _on_page_changed(self, index):
        """页面切换时更新 SegmentedWidget"""
        route_keys = ["gbe", "gl", "extractor"]
        if 0 <= index < len(route_keys):
            self.segmented_widget.setCurrentItem(route_keys[index])

    def _init_gbe_page(self):
        """初始化 GBE 模式页面"""
        page = QWidget()
        page.setObjectName("gbePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        # 授权获取卡片
        auth_card = GroupHeaderCardWidget(page)
        auth_card.setTitle("步骤 1: 获取授权文件")
        auth_card.setBorderRadius(8)
        auth_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        # 选择 CW 文件
        file_row = QWidget()
        file_row_layout = QHBoxLayout(file_row)
        file_row_layout.setContentsMargins(0, 0, 0, 0)
        self.cw_path_edit = LineEdit()
        self.cw_path_edit.setPlaceholderText(tr("drm_cw_placeholder"))
        self.cw_path_edit.setReadOnly(True)
        browse_btn = PushButton(tr("drm_browse"))
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_cw)
        decrypt_btn = PrimaryPushButton(tr("drm_decrypt"))
        decrypt_btn.setFixedWidth(70)
        decrypt_btn.clicked.connect(self._decrypt_cw)
        file_row_layout.addWidget(self.cw_path_edit)
        file_row_layout.addWidget(browse_btn)
        file_row_layout.addWidget(decrypt_btn)
        auth_card.addGroup(FluentIcon.DOCUMENT, tr("drm_cw_file"), tr("drm_cw_file_hint"), file_row)

        # 授权码下载
        code_row = QWidget()
        code_row_layout = QHBoxLayout(code_row)
        code_row_layout.setContentsMargins(0, 0, 0, 0)
        self.auth_code_edit = LineEdit()
        self.auth_code_edit.setPlaceholderText(tr("drm_auth_code_placeholder"))
        dl_btn = PrimaryPushButton(tr("drm_download_decrypt"))
        dl_btn.setFixedWidth(100)
        dl_btn.clicked.connect(self._download_by_code)
        code_row_layout.addWidget(self.auth_code_edit)
        code_row_layout.addWidget(dl_btn)
        auth_card.addGroup(FluentIcon.CLOUD_DOWNLOAD, tr("drm_auth_code"), tr("drm_auth_code_hint"), code_row)

        # 授权网站链接
        links_row = QWidget()
        links_layout = QHBoxLayout(links_row)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.addWidget(HyperlinkButton("https://drm.steam.run", "stool 授权网站"))
        links_layout.addWidget(HyperlinkButton("https://steam.sakuranoyuki.de5.net", "四星授权网站"))
        links_layout.addStretch(1)
        auth_card.addGroup(FluentIcon.LINK, tr("drm_online_auth"), tr("drm_online_auth_hint"), links_row)

        layout.addWidget(auth_card)

        # 授权信息展示卡片
        self.info_card = GroupHeaderCardWidget(page)
        self.info_card.setTitle(tr("drm_info_title"))
        self.info_card.setBorderRadius(8)
        self.info_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)
        self.info_card.hide()

        self.info_appid = BodyLabel("-")
        self.info_steamid = BodyLabel("-")
        self.info_start = BodyLabel("-")
        self.info_end = BodyLabel("-")
        self.info_card.addGroup(FluentIcon.TAG, "AppID", "", self.info_appid)
        self.info_card.addGroup(FluentIcon.PEOPLE, "SteamID", "", self.info_steamid)
        self.info_card.addGroup(FluentIcon.CALENDAR, tr("drm_valid_from"), "", self.info_start)
        self.info_card.addGroup(FluentIcon.CALENDAR, tr("drm_valid_to"), "", self.info_end)
        layout.addWidget(self.info_card)

        # GBE 模式配置卡片
        gbe_config_card = GroupHeaderCardWidget(page)
        gbe_config_card.setTitle("步骤 2: GBE模式配置")
        gbe_config_card.setBorderRadius(8)
        gbe_config_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        # 游戏启动程序选择
        exe_row = QWidget()
        exe_row_layout = QHBoxLayout(exe_row)
        exe_row_layout.setContentsMargins(0, 0, 0, 0)
        self.gbe_exe_edit = LineEdit()
        self.gbe_exe_edit.setPlaceholderText("选择游戏的 .exe 文件")
        self.gbe_exe_edit.setReadOnly(True)
        exe_browse_btn = PushButton("浏览")
        exe_browse_btn.setFixedWidth(70)
        exe_browse_btn.clicked.connect(self._browse_gbe_exe)
        exe_row_layout.addWidget(self.gbe_exe_edit)
        exe_row_layout.addWidget(exe_browse_btn)
        gbe_config_card.addGroup(FluentIcon.FOLDER, "游戏启动程序", "选择需要授权的游戏可执行文件", exe_row)

        # DLC 列表配置
        dlc_row = QWidget()
        dlc_row_layout = QHBoxLayout(dlc_row)
        dlc_row_layout.setContentsMargins(0, 0, 0, 0)
        self.gbe_dlc_edit = LineEdit()
        self.gbe_dlc_edit.setPlaceholderText("输入DLC ID，多个用逗号分隔 (如: 123,456,789)")
        self.gbe_lua_check = CheckBox("使用LUA DLC")
        dlc_row_layout.addWidget(self.gbe_dlc_edit, stretch=1)
        dlc_row_layout.addWidget(self.gbe_lua_check)
        gbe_config_card.addGroup(FluentIcon.TAG, "DLC列表 (可选)", "输入额外的DLC ID", dlc_row)

        layout.addWidget(gbe_config_card)

        # 开始授权按钮
        self.gbe_auth_btn = PrimaryPushButton("开始授权 (GBE模式)")
        self.gbe_auth_btn.setIcon(FluentIcon.CERTIFICATE)
        self.gbe_auth_btn.setEnabled(False)
        self.gbe_auth_btn.clicked.connect(self._authorize_gbe)
        layout.addWidget(self.gbe_auth_btn)

        # 日志卡片
        log_card = CardWidget(page)
        log_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 12)
        log_layout.setSpacing(6)
        log_header = QHBoxLayout()
        log_header.addWidget(BodyLabel("运行日志"))
        log_header.addStretch(1)
        clear_btn = TransparentToolButton(FluentIcon.DELETE, log_card)
        clear_btn.clicked.connect(lambda: self.drm_log.clear())
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)
        self.drm_log = TextEdit(log_card)
        self.drm_log.setReadOnly(True)
        self.drm_log.setFixedHeight(150)
        if isDarkTheme():
            self.drm_log.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.12); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        else:
            self.drm_log.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        log_layout.addWidget(self.drm_log)
        layout.addWidget(log_card)

        layout.addStretch(1)
        self.stacked_widget.addWidget(page)

    def _init_gl_page(self):
        """初始化 GL 模式页面"""
        page = QWidget()
        page.setObjectName("glPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        # 授权获取卡片（与GBE页面共享组件）
        auth_card = GroupHeaderCardWidget(page)
        auth_card.setTitle("步骤 1: 获取授权文件")
        auth_card.setBorderRadius(8)
        auth_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        # 使用 GL 页面独立的输入框
        file_row = QWidget()
        file_row_layout = QHBoxLayout(file_row)
        file_row_layout.setContentsMargins(0, 0, 0, 0)
        self.gl_cw_path_edit = LineEdit()
        self.gl_cw_path_edit.setPlaceholderText(tr("drm_cw_placeholder"))
        self.gl_cw_path_edit.setReadOnly(True)
        browse_btn = PushButton(tr("drm_browse"))
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_cw_gl)
        decrypt_btn = PrimaryPushButton(tr("drm_decrypt"))
        decrypt_btn.setFixedWidth(70)
        decrypt_btn.clicked.connect(self._decrypt_cw_gl)
        file_row_layout.addWidget(self.gl_cw_path_edit)
        file_row_layout.addWidget(browse_btn)
        file_row_layout.addWidget(decrypt_btn)
        auth_card.addGroup(FluentIcon.DOCUMENT, tr("drm_cw_file"), tr("drm_cw_file_hint"), file_row)

        # 授权码下载
        code_row = QWidget()
        code_row_layout = QHBoxLayout(code_row)
        code_row_layout.setContentsMargins(0, 0, 0, 0)
        self.gl_auth_code_edit = LineEdit()
        self.gl_auth_code_edit.setPlaceholderText(tr("drm_auth_code_placeholder"))
        dl_btn = PrimaryPushButton(tr("drm_download_decrypt"))
        dl_btn.setFixedWidth(100)
        dl_btn.clicked.connect(self._download_by_code_gl)
        code_row_layout.addWidget(self.gl_auth_code_edit)
        code_row_layout.addWidget(dl_btn)
        auth_card.addGroup(FluentIcon.CLOUD_DOWNLOAD, tr("drm_auth_code"), tr("drm_auth_code_hint"), code_row)

        # 授权网站链接
        links_row = QWidget()
        links_layout = QHBoxLayout(links_row)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.addWidget(HyperlinkButton("https://drm.steam.run", "stool 授权网站"))
        links_layout.addWidget(HyperlinkButton("https://steam.sakuranoyuki.de5.net", "四星授权网站"))
        links_layout.addStretch(1)
        auth_card.addGroup(FluentIcon.LINK, tr("drm_online_auth"), tr("drm_online_auth_hint"), links_row)

        layout.addWidget(auth_card)

        # 授权信息展示卡片（GL页面独立）
        self.gl_info_card = GroupHeaderCardWidget(page)
        self.gl_info_card.setTitle(tr("drm_info_title"))
        self.gl_info_card.setBorderRadius(8)
        self.gl_info_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)
        self.gl_info_card.hide()

        self.gl_info_appid = BodyLabel("-")
        self.gl_info_steamid = BodyLabel("-")
        self.gl_info_start = BodyLabel("-")
        self.gl_info_end = BodyLabel("-")
        self.gl_info_card.addGroup(FluentIcon.TAG, "AppID", "", self.gl_info_appid)
        self.gl_info_card.addGroup(FluentIcon.PEOPLE, "SteamID", "", self.gl_info_steamid)
        self.gl_info_card.addGroup(FluentIcon.CALENDAR, tr("drm_valid_from"), "", self.gl_info_start)
        self.gl_info_card.addGroup(FluentIcon.CALENDAR, tr("drm_valid_to"), "", self.gl_info_end)
        layout.addWidget(self.gl_info_card)

        # GL 模式配置卡片
        gl_config_card = GroupHeaderCardWidget(page)
        gl_config_card.setTitle("步骤 2: GL模式配置")
        gl_config_card.setBorderRadius(8)
        gl_config_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        desc_label = BodyLabel("GL模式将授权文件写入SteamTools目录，无需选择游戏exe。")
        gl_config_card.addGroup(FluentIcon.INFO, "说明", "", desc_label)

        layout.addWidget(gl_config_card)

        # 开始授权按钮
        self.gl_auth_btn = PrimaryPushButton("开始授权 (GL模式/Steamtools)")
        self.gl_auth_btn.setIcon(FluentIcon.CERTIFICATE)
        self.gl_auth_btn.setEnabled(False)
        self.gl_auth_btn.clicked.connect(self._authorize_gl)
        layout.addWidget(self.gl_auth_btn)

        # 日志卡片
        log_card = CardWidget(page)
        log_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 12)
        log_layout.setSpacing(6)
        log_header = QHBoxLayout()
        log_header.addWidget(BodyLabel("运行日志"))
        log_header.addStretch(1)
        clear_btn = TransparentToolButton(FluentIcon.DELETE, log_card)
        clear_btn.clicked.connect(lambda: self.gl_drm_log.clear())
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)
        self.gl_drm_log = TextEdit(log_card)
        self.gl_drm_log.setReadOnly(True)
        self.gl_drm_log.setFixedHeight(150)
        if isDarkTheme():
            self.gl_drm_log.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.12); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        else:
            self.gl_drm_log.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        log_layout.addWidget(self.gl_drm_log)
        layout.addWidget(log_card)

        layout.addStretch(1)
        self.stacked_widget.addWidget(page)

    def _init_extractor_page(self):
        """初始化 CW 提取工具页面"""
        page = QWidget()
        page.setObjectName("extractorPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        # CW 提取工具卡片
        extract_card = GroupHeaderCardWidget(page)
        extract_card.setTitle("CW 提取工具")
        extract_card.setBorderRadius(8)
        extract_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        # AppID 输入
        appid_row = QWidget()
        appid_row_layout = QHBoxLayout(appid_row)
        appid_row_layout.setContentsMargins(0, 0, 0, 0)
        self.extract_appid_edit = LineEdit()
        self.extract_appid_edit.setPlaceholderText("输入游戏 AppID (当前账号必须拥有该游戏)")
        appid_row_layout.addWidget(self.extract_appid_edit)
        extract_card.addGroup(FluentIcon.TAG, "游戏 AppID", "", appid_row)

        # 操作按钮
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(12)

        extract_authcode_btn = PushButton("生成 Tools 授权码")
        extract_authcode_btn.setIcon(FluentIcon.CERTIFICATE)
        extract_authcode_btn.setToolTip("此授权码用于 Tools 客户端，非 CW 平台授权码")
        extract_authcode_btn.clicked.connect(self._extract_auth_code)

        extract_cw_btn = PrimaryPushButton("本地提取 CW")
        extract_cw_btn.setIcon(FluentIcon.SAVE_AS)
        extract_cw_btn.clicked.connect(self._extract_cw_file)

        btn_row_layout.addWidget(extract_authcode_btn)
        btn_row_layout.addWidget(extract_cw_btn)
        btn_row_layout.addStretch(1)

        extract_card.addGroup(FluentIcon.CERTIFICATE, "操作", "将票证提交到服务器换取 Tools 授权码，或在本地直接加密生成 .cw 文件", btn_row)

        layout.addWidget(extract_card)

        # 工具箱卡片
        toolbox_card = GroupHeaderCardWidget(page)
        toolbox_card.setTitle("工具箱")
        toolbox_card.setBorderRadius(8)
        toolbox_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        fix_btn = PushButton("修复 e0 报错")
        fix_btn.setIcon(FluentIcon.HEART)
        fix_btn.clicked.connect(self._fix_e0_error)
        toolbox_card.addGroup(FluentIcon.HEART, "修复工具", "删除Steam缓存文件修复e0错误", fix_btn)

        layout.addWidget(toolbox_card)

        # 日志卡片
        log_card = CardWidget(page)
        log_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 12)
        log_layout.setSpacing(6)
        log_header = QHBoxLayout()
        log_header.addWidget(BodyLabel("运行日志"))
        log_header.addStretch(1)
        clear_btn = TransparentToolButton(FluentIcon.DELETE, log_card)
        clear_btn.clicked.connect(lambda: self.extractor_log.clear())
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)
        self.extractor_log = TextEdit(log_card)
        self.extractor_log.setReadOnly(True)
        self.extractor_log.setFixedHeight(200)
        if isDarkTheme():
            self.extractor_log.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.12); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        else:
            self.extractor_log.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        log_layout.addWidget(self.extractor_log)
        layout.addWidget(log_card)

        layout.addStretch(1)
        self.stacked_widget.addWidget(page)

    def _log(self, msg: str, log_widget=None):
        """输出日志到指定日志组件"""
        target_log = log_widget or self.drm_log
        if target_log:
            if isDarkTheme():
                target_log.append(f"<span style='color:#fff'>{msg}</span>")
            else:
                target_log.append(f"<span style='color:#000'>{msg}</span>")
            sb = target_log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _log_gbe(self, msg: str):
        """输出到 GBE 页面日志"""
        self._log(msg, self.drm_log)

    def _log_gl(self, msg: str):
        """输出到 GL 页面日志"""
        self._log(msg, self.gl_drm_log)

    def _log_extractor(self, msg: str):
        """输出到提取工具页面日志"""
        self._log(msg, self.extractor_log)

    def notify_theme_changed(self):
        """通知日志显示组件主题已变化"""
        # 更新日志显示组件的样式
        if hasattr(self, 'drm_log') and self.drm_log:
            if isDarkTheme():
                self.drm_log.setStyleSheet(
                    "TextEdit { background: rgba(0,0,0,0.12); border-radius: 6px; "
                    "font-size: 12px; padding: 8px; }"
                )
            else:
                self.drm_log.setStyleSheet(
                    "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                    "font-size: 12px; padding: 8px; }"
                )

    def _browse_cw(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, tr("drm_cw_file"), "", "CW Files (*.cw);;All Files (*)")
        if path:
            self.cw_path_edit.setText(path)

    def _browse_cw_gl(self):
        """GL页面浏览CW文件"""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, tr("drm_cw_file"), "", "CW Files (*.cw);;All Files (*)")
        if path:
            self.gl_cw_path_edit.setText(path)

    def _browse_gbe_exe(self):
        """浏览GBE模式游戏exe"""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择游戏程序", "", "Executable Files (*.exe);;All Files (*)")
        if path:
            self.gbe_exe_edit.setText(path)

    def _decrypt_cw(self):
        path = self.cw_path_edit.text().strip()
        if not path:
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_select_cw"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return
        try:
            from backend.drm_backend import DrmBackend
            drm = DrmBackend()
            result = drm.decrypt_cw_file(path)
            self._cw_result = result
            self._show_cw_info(result)
            self._log_gbe(f"解密成功！AppID: {result.appid}, SteamID: {result.steam_id}")
            # 启用授权按钮
            self.gbe_auth_btn.setEnabled(True)
        except ImportError:
            InfoBar.error(title=tr("drm_missing_dep"), content=tr("drm_missing_dep_hint"), parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            self._log_gbe(f"解密失败: {e}")
            InfoBar.error(title=tr("drm_decrypt_failed"), content=str(e), parent=self, position=InfoBarPosition.TOP)

    def _decrypt_cw_gl(self):
        """GL页面解密CW文件"""
        path = self.gl_cw_path_edit.text().strip()
        if not path:
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_select_cw"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return
        try:
            from backend.drm_backend import DrmBackend
            drm = DrmBackend()
            result = drm.decrypt_cw_file(path)
            self._cw_result = result
            self._show_cw_info_gl(result)
            self._log_gl(f"解密成功！AppID: {result.appid}, SteamID: {result.steam_id}")
            # 启用授权按钮
            self.gl_auth_btn.setEnabled(True)
        except ImportError:
            InfoBar.error(title=tr("drm_missing_dep"), content=tr("drm_missing_dep_hint"), parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            self._log_gl(f"解密失败: {e}")
            InfoBar.error(title=tr("drm_decrypt_failed"), content=str(e), parent=self, position=InfoBarPosition.TOP)

    def _download_by_code(self):
        """GBE页面通过授权码下载"""
        code = self.auth_code_edit.text().strip()
        if not code:
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_enter_code"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        async def _dl():
            from backend.drm_backend import DrmBackend
            drm = DrmBackend()
            ok, msg, tmp_path = await drm.download_cw_by_auth_code(code, logger=self._log_gbe)
            if ok and tmp_path:
                result = drm.decrypt_cw_file(tmp_path)
                try:
                    tmp_path.unlink()
                except:
                    pass
                return result
            raise Exception(msg)

        _replace_worker(getattr(self, '_drm_worker', None))
        worker = AsyncWorker(_dl())
        self._drm_worker = worker

        def on_result(result):
            self._drm_worker = None
            self._cw_result = result
            self._show_cw_info(result)
            self._log_gbe(f"下载解密成功！AppID: {result.appid}")
            self.gbe_auth_btn.setEnabled(True)

        def on_error(err):
            self._drm_worker = None
            self._log_gbe(f"下载失败: {err}")
            InfoBar.error(title=tr("drm_download_failed"), content=str(err), parent=self, position=InfoBarPosition.TOP)

        worker.result_ready.connect(on_result)
        worker.error.connect(on_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _download_by_code_gl(self):
        """GL页面通过授权码下载"""
        code = self.gl_auth_code_edit.text().strip()
        if not code:
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_enter_code"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        async def _dl():
            from backend.drm_backend import DrmBackend
            drm = DrmBackend()
            ok, msg, tmp_path = await drm.download_cw_by_auth_code(code, logger=self._log_gl)
            if ok and tmp_path:
                result = drm.decrypt_cw_file(tmp_path)
                try:
                    tmp_path.unlink()
                except:
                    pass
                return result
            raise Exception(msg)

        _replace_worker(getattr(self, '_drm_worker', None))
        worker = AsyncWorker(_dl())
        self._drm_worker = worker

        def on_result(result):
            self._drm_worker = None
            self._cw_result = result
            self._show_cw_info_gl(result)
            self._log_gl(f"下载解密成功！AppID: {result.appid}")
            self.gl_auth_btn.setEnabled(True)

        def on_error(err):
            self._drm_worker = None
            self._log_gl(f"下载失败: {err}")
            InfoBar.error(title=tr("drm_download_failed"), content=str(err), parent=self, position=InfoBarPosition.TOP)

        worker.result_ready.connect(on_result)
        worker.error.connect(on_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _show_cw_info(self, result):
        """显示GBE页面的CW信息"""
        from backend.drm_backend import DrmBackend
        self.info_appid.setText(str(result.appid))
        self.info_steamid.setText(str(result.steam_id))
        self.info_start.setText(DrmBackend.ts_to_str(result.timeout_start))
        self.info_end.setText(DrmBackend.ts_to_str(result.timeout_end))
        self.info_card.show()

    def _show_cw_info_gl(self, result):
        """显示GL页面的CW信息"""
        from backend.drm_backend import DrmBackend
        self.gl_info_appid.setText(str(result.appid))
        self.gl_info_steamid.setText(str(result.steam_id))
        self.gl_info_start.setText(DrmBackend.ts_to_str(result.timeout_start))
        self.gl_info_end.setText(DrmBackend.ts_to_str(result.timeout_end))
        self.gl_info_card.show()

    def _authorize_gl(self):
        """GL模式授权"""
        if not self._cw_result:
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_decrypt_first"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        async def _auth():
            from backend.drm_backend import DrmBackend
            drm = DrmBackend()
            ok, msg = await drm.authorize_gl_mode(self._cw_result)
            return ok, msg

        _replace_worker(getattr(self, '_drm_worker', None))
        self.gl_auth_btn.setEnabled(False)
        worker = AsyncWorker(_auth())
        self._drm_worker = worker

        def on_result(res):
            self._drm_worker = None
            self.gl_auth_btn.setEnabled(True)
            ok, msg = res
            self._log_gl(msg)
            if ok:
                InfoBar.success(title=tr("drm_auth_success"), content=msg, parent=self, position=InfoBarPosition.TOP, duration=3000)
            else:
                InfoBar.error(title=tr("drm_auth_failed"), content=msg, parent=self, position=InfoBarPosition.TOP)

        def on_error(err):
            self._drm_worker = None
            self.gl_auth_btn.setEnabled(True)
            self._log_gl(f"授权失败: {err}")
            InfoBar.error(title=tr("drm_auth_failed"), content=err, parent=self, position=InfoBarPosition.TOP)

        worker.result_ready.connect(on_result)
        worker.error.connect(on_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _authorize_gbe(self):
        """GBE模式授权"""
        if not self._cw_result:
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_decrypt_first"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        game_exe = self.gbe_exe_edit.text().strip()
        if not game_exe:
            InfoBar.warning(title=tr("tip"), content="请选择游戏启动程序", parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        dlc_ids = self.gbe_dlc_edit.text().strip()
        use_lua_dlc = self.gbe_lua_check.isChecked()

        async def _auth():
            from backend.drm_backend import DrmBackend
            drm = DrmBackend()
            ok, msg = await drm.authorize_gbe_mode(
                self._cw_result,
                game_exe,
                dlc_ids=dlc_ids,
                used_lua_dlc=use_lua_dlc
            )
            return ok, msg

        _replace_worker(getattr(self, '_drm_worker', None))
        self.gbe_auth_btn.setEnabled(False)
        worker = AsyncWorker(_auth())
        self._drm_worker = worker

        def on_result(res):
            self._drm_worker = None
            self.gbe_auth_btn.setEnabled(True)
            ok, msg = res
            self._log_gbe(msg)
            if ok:
                InfoBar.success(title=tr("drm_auth_success"), content=msg, parent=self, position=InfoBarPosition.TOP, duration=3000)
            else:
                InfoBar.error(title=tr("drm_auth_failed"), content=msg, parent=self, position=InfoBarPosition.TOP)

        def on_error(err):
            self._drm_worker = None
            self.gbe_auth_btn.setEnabled(True)
            self._log_gbe(f"授权失败: {err}")
            InfoBar.error(title=tr("drm_auth_failed"), content=err, parent=self, position=InfoBarPosition.TOP)

        worker.result_ready.connect(on_result)
        worker.error.connect(on_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _fix_e0_error(self):
        """修复e0错误"""
        if not self._cw_result:
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_decrypt_first"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        from backend.drm_backend import DrmBackend
        drm = DrmBackend()
        ok, msg = drm.fix_e0_error(
            str(self._cw_result.appid),
            str(self._cw_result.steam_id)
        )
        
        if ok:
            InfoBar.success(title="修复成功", content=msg, parent=self, position=InfoBarPosition.TOP, duration=3000)
        else:
            InfoBar.error(title="修复失败", content=msg, parent=self, position=InfoBarPosition.TOP)

    def _extract_auth_code(self):
        app_id = self.extract_appid_edit.text().strip()
        if not app_id or not app_id.isdigit():
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_valid_appid"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        def _run():
            try:
                from backend.cw_extractor_core import LocalExtractor
                extractor = LocalExtractor(int(app_id), self._log)
                return extractor.extract_to_authcode()
            except ImportError:
                return {"success": False, "message": "缺少 DRM.cw_extractor_core 模块"}
            except Exception as e:
                return {"success": False, "message": str(e)}

        import concurrent.futures
        self._log(f"开始提取 AppID {app_id} 的授权码...")

        def _do():
            with concurrent.futures.ThreadPoolExecutor() as ex:
                return ex.submit(_run).result()

        _replace_worker(getattr(self, '_drm_worker', None))
        worker = AsyncWorker(_do())  # 包一层 async 壳
        self._drm_worker = worker

        # 直接用线程跑，不走 asyncio
        import threading
        def _thread_run():
            result = _run()
            if result.get("success"):
                auth_code = result.get("auth_code", "")
                self._log_extractor(f"Tools 授权码: {auth_code}")
                self._log_extractor(">>> Tools 授权码已生成，请在 Tools 客户端中使用 <<<")
                try:
                    from PyQt6.QtWidgets import QApplication
                    QApplication.clipboard().setText(auth_code)
                    self._log_extractor(">>> 已自动复制到剪贴板 <<<")
                except Exception:
                    pass
            else:
                self._log_extractor(f"提取失败: {result.get('message', '未知错误')}")

        t = threading.Thread(target=_thread_run, daemon=True)
        t.start()
        self._drm_worker = None  # 线程方式不用 worker

    def _extract_cw_file(self):
        app_id = self.extract_appid_edit.text().strip()
        if not app_id or not app_id.isdigit():
            InfoBar.warning(title=tr("tip"), content=tr("drm_tip_valid_appid"), parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        from PyQt6.QtWidgets import QFileDialog
        output_dir, _ = QFileDialog.getSaveFileName(self, "保存 CW 文件", f"{app_id}.cw", "CW Files (*.cw)")
        if not output_dir:
            return

        import threading
        self._log_extractor(f"开始生成 AppID {app_id} 的 CW 文件...")

        def _thread_run():
            try:
                from backend.cw_extractor_core import LocalExtractor, HAVE_PYCRYPTODOME
                if not HAVE_PYCRYPTODOME:
                    self._log_extractor("错误: 需要安装 pycryptodome: pip install pycryptodome")
                    return
                extractor = LocalExtractor(int(app_id), self._log_extractor)
                result = extractor.extract_to_cw_file(output_dir)
                if result.get("success"):
                    self._log_extractor(f"CW 文件已生成: {result.get('file_path')}")
                    self._log_extractor(f"包含 {result.get('dlc_count', 0)} 个 DLC")
                else:
                    self._log_extractor(f"生成失败: {result.get('message', '未知错误')}")
            except ImportError:
                self._log_extractor("错误: 缺少 cw_extractor_core 模块")
            except Exception as e:
                self._log_extractor(f"发生错误: {e}")

        threading.Thread(target=_thread_run, daemon=True).start()


class SteamAccountPage(ScrollArea):
    """Steam 账号管理页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("steamAccountPage")
        self.setWidgetResizable(True)

        # 初始化头像网络管理器和缓存
        self.network_manager = QNetworkAccessManager(self)
        self._avatar_cache = {}

        # 主容器
        container = QWidget()
        container.setObjectName("steamAccountContainer")
        self.setWidget(container)

        self.mainLayout = QVBoxLayout(container)
        self.mainLayout.setContentsMargins(30, 30, 30, 30)
        self.mainLayout.setSpacing(20)

        # 标题栏
        header_layout = QHBoxLayout()
        self.title = SubtitleLabel(tr("steam_account_manager"), self)

        # 刷新按钮
        self.refresh_button = TransparentToolButton(FluentIcon.SYNC, self)
        self.refresh_button.setFixedSize(32, 32)
        self.refresh_button.clicked.connect(self.load_accounts)
        self.refresh_button.setToolTip(tr("refresh_accounts"))

        # 视图切换按钮 - 使用 MENU 和 EMBED 图标代替 GRID/LIST
        self.view_mode_button = TransparentToolButton(FluentIcon.MENU, self)
        self.view_mode_button.setFixedSize(32, 32)
        self.view_mode_button.clicked.connect(self.toggle_view_mode)
        self.view_mode_button.setToolTip(tr("toggle_view_mode"))
        
        header_layout.addWidget(self.title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.view_mode_button)
        header_layout.addWidget(self.refresh_button)
        self.mainLayout.addLayout(header_layout)
        
        # 账号容器 - 使用 QStackedWidget 支持视图切换
        self.view_stack = QStackedWidget(self)
        self.current_view_mode = "grid"  # grid 或 list
        
        # 网格视图容器
        self.grid_container = QWidget()
        self.grid_layout = SafeFlowLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(15)
        
        # 列表视图容器
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch(1)
        
        # 添加到堆叠部件
        self.view_stack.addWidget(self.grid_container)
        self.view_stack.addWidget(self.list_container)
        self.mainLayout.addWidget(self.view_stack)
        self.mainLayout.addStretch(1)
        
        # 账号数据
        self.accounts = []
        self.account_notes = {}  # 存储备注
        self.load_notes()
        
        # 设置透明背景
        self.setStyleSheet("SteamAccountPage { background: transparent; }")
        container.setStyleSheet("QWidget#steamAccountContainer { background: transparent; }")
        
        # 延迟加载账号
        QTimer.singleShot(100, self.load_accounts)
    
    def load_notes(self):
        """加载账号备注"""
        self.account_notes = {}
        try:
            notes_path = APP_ROOT / 'config' / 'account_notes.json'
            print(f"[DEBUG] 尝试加载备注文件: {notes_path}")
            if notes_path.exists():
                with open(notes_path, 'r', encoding='utf-8') as f:
                    self.account_notes = json.load(f)
                print(f"[DEBUG] 已加载备注: {self.account_notes}")
            else:
                print(f"[DEBUG] 备注文件不存在: {notes_path}")
        except Exception as e:
            print(f"[DEBUG] 加载备注失败: {e}")
            pass
    
    def save_notes(self):
        """保存账号备注"""
        try:
            notes_path = APP_ROOT / 'config' / 'account_notes.json'
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            with open(notes_path, 'w', encoding='utf-8') as f:
                json.dump(self.account_notes, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] 备注已保存到: {notes_path}")
            print(f"[DEBUG] 保存的内容: {self.account_notes}")
        except Exception as e:
            print(f"[DEBUG] 保存备注失败: {e}")
    
    def toggle_view_mode(self):
        """切换视图模式"""
        if self.current_view_mode == "grid":
            self.current_view_mode = "list"
            self.view_mode_button.setIcon(FluentIcon.EMBED)
            self.view_stack.setCurrentWidget(self.list_container)
        else:
            self.current_view_mode = "grid"
            self.view_mode_button.setIcon(FluentIcon.MENU)
            self.view_stack.setCurrentWidget(self.grid_container)
        self.refresh_account_display()
    
    def load_accounts(self):
        """加载账号列表"""
        async def _load():
            async with CaiBackend() as backend:
                await backend.initialize()
                accounts = backend.get_steam_accounts()
                return accounts
        
        def on_loaded(accounts):
            self.accounts = accounts
            self.refresh_account_display()
        
        def on_error(error):
            InfoBar.error(
                title=tr("load_accounts_failed"),
                content=str(error),
                parent=self,
                position=InfoBarPosition.TOP
            )
        
        _replace_worker(getattr(self, 'load_worker', None))
        self.load_worker = AsyncWorker(_load())
        self.load_worker.result_ready.connect(on_loaded)
        self.load_worker.error.connect(on_error)
        self.load_worker.finished.connect(self.load_worker.deleteLater)
        self.load_worker.start()
    
    def refresh_account_display(self):
        """刷新账号显示"""
        # 清除网格布局内容
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 清除列表布局内容（保留最后的 stretch）
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加账号卡片到两个布局
        for account_info in self.accounts:
            grid_card = self.create_account_card(account_info)
            list_card = self.create_account_card(account_info)
            self.grid_layout.addWidget(grid_card)
            self.list_layout.insertWidget(self.list_layout.count() - 1, list_card)
    
    def create_account_card(self, account_info):
        """创建账号卡片"""
        account = account_info['account']
        persona_name = account_info['persona_name']
        steamid = account_info['steamid']
        most_recent = account_info['most_recent']
        remember_pwd = account_info.get('remember_password', False)

        # 获取备注
        note = self.account_notes.get(account, "")
        print(f"[DEBUG] 创建卡片，账号: {account}, 备注: {note}")

        # 根据视图模式设置不同尺寸
        if self.current_view_mode == "grid":
            card = CardWidget(self)
            card.setFixedSize(320, 140)

            layout = QHBoxLayout(card)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(10)

            # 1. 头像区域
            avatar = AvatarWidget(self)
            avatar.setFixedSize(50, 50)
            self.load_avatar(avatar, steamid)
            layout.addWidget(avatar)

            # 2. 信息区域
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            # 昵称
            name_label = BodyLabel(persona_name or account, self)
            name_label.setStyleSheet("font-weight: bold; font-size: 13px;")

            # 账号名
            account_label = CaptionLabel(f"账号: {account}", self)
            account_label.setTextColor("#606060", "#a0a0a0")

            # 备注
            note_label = CaptionLabel(f"备注: {note}" if note else tr("no_note"), self)
            note_label.setTextColor("#808080", "#808080")

            # 密码状态
            pwd_status = CaptionLabel("✅ 可自动上号" if remember_pwd else "❌ 未保存密码", self)
            pwd_status.setStyleSheet("color: #10b981; font-size: 11px;" if remember_pwd else "color: #ef4444; font-size: 11px;")

            info_layout.addWidget(name_label)
            info_layout.addWidget(account_label)
            info_layout.addWidget(note_label)
            info_layout.addWidget(pwd_status)
            layout.addLayout(info_layout, 1)

            # 3. 操作按钮区域 - 垂直布局
            btn_layout = QVBoxLayout()
            btn_layout.setSpacing(4)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if most_recent:
                current_label = CaptionLabel("当前登录", self)
                current_label.setStyleSheet("color: #0078d4; font-size: 10px;")
                current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                btn_layout.addWidget(current_label)

            # 登录按钮
            login_btn = PrimaryPushButton("一键上号" if remember_pwd else "手动上号", self)
            login_btn.setFixedSize(85, 28)
            login_btn.setStyleSheet("font-size: 11px;")
            login_btn.clicked.connect(lambda checked=False, acc=account: self.switch_account(acc, offline=False))
            btn_layout.addWidget(login_btn)

            # 更多按钮
            more_btn = TransparentToolButton(FluentIcon.MORE, self)
            more_btn.setFixedSize(28, 28)
            more_btn.clicked.connect(lambda checked=False, acc=account, lbl=note_label, btn=more_btn: self.show_account_menu(acc, lbl, btn))
            btn_layout.addWidget(more_btn, alignment=Qt.AlignmentFlag.AlignCenter)

            layout.addLayout(btn_layout)

        else:
            # 列表视图
            card = CardWidget(self)
            card.setFixedHeight(120)

            layout = QHBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(12)

            # 1. 头像区域 - 列表视图用更小的头像
            avatar = AvatarWidget(self)
            avatar.setFixedSize(40, 40)
            self.load_avatar(avatar, steamid)
            layout.addWidget(avatar)

            # 2. 信息区域 - 列表视图简化显示
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            # 昵称和账号在同一行
            name_layout = QHBoxLayout()
            name_label = BodyLabel(persona_name or account, self)
            name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
            name_layout.addWidget(name_label)

            account_label = CaptionLabel(f"({account})", self)
            account_label.setTextColor("#606060", "#a0a0a0")
            name_layout.addWidget(account_label)
            name_layout.addStretch(1)

            # 第二行：备注和密码状态
            status_layout = QHBoxLayout()
            note_label = CaptionLabel(note if note else tr("no_note"), self)
            note_label.setTextColor("#808080", "#808080")
            status_layout.addWidget(note_label)

            pwd_status = CaptionLabel("✅ 可自动上号" if remember_pwd else "❌ 未保存密码", self)
            pwd_status.setStyleSheet("color: #10b981; font-size: 11px;" if remember_pwd else "color: #ef4444; font-size: 11px;")
            status_layout.addWidget(pwd_status)
            status_layout.addStretch(1)

            info_layout.addLayout(name_layout)
            info_layout.addLayout(status_layout)
            layout.addLayout(info_layout, 1)

            # 3. 操作按钮区域 - 列表视图水平排列
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(6)

            if most_recent:
                current_label = CaptionLabel("当前登录", self)
                current_label.setStyleSheet("color: #0078d4; font-size: 10px;")
                btn_layout.addWidget(current_label)

            # 登录按钮
            login_btn = PrimaryPushButton("一键上号" if remember_pwd else "手动上号", self)
            login_btn.setFixedSize(80, 28)
            login_btn.setStyleSheet("font-size: 11px;")
            login_btn.clicked.connect(lambda checked=False, acc=account: self.switch_account(acc, offline=False))
            btn_layout.addWidget(login_btn)

            # 更多按钮
            more_btn = TransparentToolButton(FluentIcon.MORE, self)
            more_btn.setFixedSize(28, 28)
            more_btn.clicked.connect(lambda checked=False, acc=account, lbl=note_label, btn=more_btn: self.show_account_menu(acc, lbl, btn))
            btn_layout.addWidget(more_btn)

            layout.addLayout(btn_layout)

        # 右键菜单 (闭包传参修复)
        card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        card.customContextMenuRequested.connect(
            lambda pos, acc=account, lbl=note_label, c=card: self.show_account_context_menu(acc, lbl, c.mapToGlobal(pos))
        )

        return card
    
    def load_avatar(self, avatar_widget, steamid):
        """异步获取 Steam 真实高清头像"""
        # 如果缓存里有，直接使用
        if steamid in self._avatar_cache:
            from PyQt6.QtGui import QImage
            avatar_widget.setImage(QImage.fromData(self._avatar_cache[steamid]))
            return

        # 1. 访问 Steam XML API 获取头像链接
        url = f"https://steamcommunity.com/profiles/{steamid}?xml=1"
        request = QNetworkRequest(QUrl(url))
        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._on_avatar_xml_loaded(reply, avatar_widget, steamid))

    def _on_avatar_xml_loaded(self, reply, avatar_widget, steamid):
        """解析 XML 拿到图片 URL 后下载图片"""
        # 检查 widget 是否已被删除
        if sip.isdeleted(avatar_widget):
            reply.deleteLater()
            return
        if reply.error() == QNetworkReply.NetworkError.NoError:
            xml_data = reply.readAll().data().decode('utf-8', errors='ignore')
            import re
            # 提取 avatarFull 高清头像
            match = re.search(r'<avatarFull><!\[CDATA\[(.*?)\]\]></avatarFull>', xml_data)
            if match:
                avatar_url = match.group(1)
                # 2. 发起图片下载请求
                img_req = QNetworkRequest(QUrl(avatar_url))
                img_reply = self.network_manager.get(img_req)
                img_reply.finished.connect(lambda: self._on_avatar_img_loaded(img_reply, avatar_widget, steamid))
        reply.deleteLater()

    def _on_avatar_img_loaded(self, reply, avatar_widget, steamid):
        """图片下载完成，渲染到 UI 并缓存"""
        # 检查 widget 是否已被删除
        if sip.isdeleted(avatar_widget):
            reply.deleteLater()
            return
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll().data()
            from PyQt6.QtGui import QImage
            image = QImage.fromData(data)
            if not image.isNull():
                self._avatar_cache[steamid] = data
                avatar_widget.setImage(image)
        reply.deleteLater()
    
    def edit_note(self, account, note_label):
        """编辑备注"""
        from qfluentwidgets import MessageBoxBase, LineEdit, BodyLabel
        
        class NoteDialog(MessageBoxBase):
            def __init__(self, current_note, parent=None):
                super().__init__(parent)
                self.titleLabel = TitleLabel(tr("edit_note_title"), self)
                self.bodyLabel = BodyLabel(tr("edit_note_message"), self)
                
                self.noteInput = LineEdit(self)
                self.noteInput.setText(current_note)
                self.noteInput.setPlaceholderText(tr("note_placeholder"))
                self.noteInput.setMinimumWidth(300)
                
                self.viewLayout.addWidget(self.titleLabel)
                self.viewLayout.addWidget(self.bodyLabel)
                self.viewLayout.addWidget(self.noteInput)
                
                self.yesButton.setText(tr("save"))
                self.cancelButton.setText(tr("cancel"))
                self.widget.setMinimumWidth(350)
            
            def get_note(self):
                return self.noteInput.text().strip()
        
        current_note = self.account_notes.get(account, "")
        dialog = NoteDialog(current_note, self)
        
        if dialog.exec():
            new_note = dialog.get_note()
            self.account_notes[account] = new_note
            self.save_notes()
            note_label.setText(new_note if new_note else tr("no_note"))
            InfoBar.success(
                title=tr("note_saved"),
                content=tr("note_saved_message"),
                parent=self,
                position=InfoBarPosition.TOP
            )
    
    def switch_account(self, account, offline=False):
        """切换到指定账号"""
        async def _switch():
            async with CaiBackend() as backend:
                await backend.initialize()
                success = backend.switch_steam_account(account, offline=offline)
                return success
        
        def on_complete(success):
            if success:
                mode_text = tr("offline_mode") if offline else tr("online_mode")
                InfoBar.success(
                    title=tr("switch_account_success"),
                    content=f"{tr('switch_account_success_message')} ({mode_text})",
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                # 刷新列表以更新当前登录状态
                QTimer.singleShot(2000, self.load_accounts)
            else:
                InfoBar.error(
                    title=tr("switch_account_failed"),
                    content=tr("switch_account_failed_message"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
        
        def on_error(error):
            InfoBar.error(
                title=tr("switch_account_failed"),
                content=str(error),
                parent=self,
                position=InfoBarPosition.TOP
            )
        
        _replace_worker(getattr(self, 'switch_worker', None))
        self.switch_worker = AsyncWorker(_switch())
        self.switch_worker.result_ready.connect(on_complete)
        self.switch_worker.error.connect(on_error)
        self.switch_worker.finished.connect(self.switch_worker.deleteLater)
        self.switch_worker.start()
        
        mode_text = tr("offline_mode") if offline else tr("online_mode")
        InfoBar.info(
            title=tr("switching_account"),
            content=f"{tr('switching_account_message')} ({mode_text})",
            parent=self,
            position=InfoBarPosition.TOP
        )
    
    def delete_account(self, account):
        """删除账号"""
        # 确认对话框
        dialog = MessageBox(
            tr("confirm_delete_account"),
            tr("delete_account_message").format(account),
            self
        )
        
        if dialog.exec():
            async def _delete():
                async with CaiBackend() as backend:
                    await backend.initialize()
                    # 从 loginusers.vdf 删除
                    success = backend.delete_steam_account(account)
                    return success
            
            def on_complete(success):
                if success:
                    # 同时删除备注
                    if account in self.account_notes:
                        del self.account_notes[account]
                        self.save_notes()
                    # 刷新列表
                    self.load_accounts()
                    InfoBar.success(
                        title=tr("delete_account_success"),
                        content=tr("delete_account_success_message"),
                        parent=self,
                        position=InfoBarPosition.TOP
                    )
                else:
                    InfoBar.error(
                        title=tr("delete_account_failed"),
                        content=tr("delete_account_failed_message"),
                        parent=self,
                        position=InfoBarPosition.TOP
                    )
            
            def on_error(error):
                InfoBar.error(
                    title=tr("delete_account_failed"),
                    content=str(error),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
            
            _replace_worker(getattr(self, 'delete_worker', None))
            self.delete_worker = AsyncWorker(_delete())
            self.delete_worker.result_ready.connect(on_complete)
            self.delete_worker.error.connect(on_error)
            self.delete_worker.finished.connect(self.delete_worker.deleteLater)
            self.delete_worker.start()
    
    def show_account_menu(self, account, note_label, parent_widget):
        """显示账号操作菜单"""
        menu = RoundMenu()
        
        # 离线启动
        offline_action = Action(FluentIcon.CLOUD, tr("switch_offline"))
        offline_action.triggered.connect(lambda: self.switch_account(account, offline=True))
        menu.addAction(offline_action)
        
        menu.addSeparator()
        
        # 编辑备注
        note_action = Action(FluentIcon.EDIT, tr("edit_note"))
        note_action.triggered.connect(lambda: self.edit_note(account, note_label))
        menu.addAction(note_action)
        
        menu.addSeparator()
        
        # 删除账号
        delete_action = Action(FluentIcon.DELETE, tr("delete_account"))
        delete_action.triggered.connect(lambda: self.delete_account(account))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(parent_widget.mapToGlobal(QPoint(0, parent_widget.height())))
    
    def show_account_context_menu(self, account, note_label, global_pos):
        """显示账号右键菜单"""
        menu = RoundMenu()
        
        # 在线启动
        online_action = Action(FluentIcon.POWER_BUTTON, tr("switch_to_this_account"))
        online_action.triggered.connect(lambda: self.switch_account(account, offline=False))
        menu.addAction(online_action)
        
        # 离线启动
        offline_action = Action(FluentIcon.CLOUD, tr("switch_offline"))
        offline_action.triggered.connect(lambda: self.switch_account(account, offline=True))
        menu.addAction(offline_action)
        
        menu.addSeparator()
        
        # 编辑备注
        note_action = Action(FluentIcon.EDIT, tr("edit_note"))
        note_action.triggered.connect(lambda: self.edit_note(account, note_label))
        menu.addAction(note_action)
        
        menu.addSeparator()
        
        # 删除账号
        delete_action = Action(FluentIcon.DELETE, tr("delete_account"))
        delete_action.triggered.connect(lambda: self.delete_account(account))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(global_pos)


class SettingsPage(ScrollArea):
    """设置页面"""

    custom_repos_changed = pyqtSignal()  # 自定义仓库列表变化信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.setWidgetResizable(True)
        
        # 占位容器，真正内容在首次显示时构建
        self._container = QWidget()
        self._container.setObjectName("settingsContainer")
        self.setWidget(self._container)
        self.setStyleSheet("SettingsPage { background: transparent; }")
        self._container.setStyleSheet("QWidget#settingsContainer { background: transparent; }")

        # 控件引用（懒初始化后赋值）
        self.steam_path_edit = None
        self.token_edit = None
        self.manifest_api_key_edit = None
        self.debug_check = None
        self.logging_check = None
        self.unlocker_combo = None
        self.timeout_spinbox = None
        self.theme_combo = None
        self.color_combo = None
        self.lang_combo = None
        self.effect_combo = None
        self.st_mode_combo = None
        self.st_fixed_manifest_combo = None
        self.dlc_timeout_spinbox = None
        self.log_view = None
        self.default_page_combo = None
        self.show_progress_check = None
        self.hide_search_check = None
        self.hide_launcher_check = None
        self.hide_trainer_check = None
        self.hide_drm_check = None
        self.sidebar_group = None
        self.smooth_scroll_check = None
        self.custom_repos_card = None

        self._config_loaded = False
        self.worker = None
        self._save_timer = None
        self._ui_built = False
        self._log_handler = None
        # 提前注册日志 handler，缓冲 UI 构建前的日志
        self._pending_logs: list = []
        self._log_handler = QtLogHandler(self)
        self._log_handler.log_record.connect(self._append_log)
        logging.getLogger(' Cai install').addHandler(self._log_handler)

    def _build_ui(self):
        """兼容 _prebuild_settings 调用，直接触发分帧构建"""
        self._build_and_load()
    

    def _append_log(self, level: str, msg: str):
        """将日志追加到日志视图"""
        if self.log_view is None:
            self._pending_logs.append((level, msg))
            return
        
        try:
            color = "#cccccc" if isDarkTheme() else "#333333"
            self.log_view.append(f"<span style='color:{color}'>{msg}</span>")
            sb = self.log_view.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        except RuntimeError:
            pass

    def _clear_log(self):
        """清空日志视图"""
        self.log_view.clear()

    def showEvent(self, event):
        """页面显示时懒构建 UI 并加载配置"""
        super().showEvent(event)
        if not self._ui_built:
            self._ui_built = True
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._build_and_load)
        # _config_loaded 由 _prebuild_settings 或 _build_and_load 负责，showEvent 不重复加载

    def _build_and_load(self):
        """分帧构建 UI，避免主线程卡顿"""
        from PyQt6.QtCore import QTimer

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        self._build_layout = layout

        # 第1帧：标题 + Steam路径卡片
        title = SubtitleLabel(tr("settings"), self)
        layout.addWidget(title)
        
        settings_card = SettinsCard(self)
        layout.addWidget(settings_card)
        self.steam_path_edit = settings_card.steam_path_edit
        self.token_edit = settings_card.token_edit
        self.manifest_api_key_edit = settings_card.manifest_api_key_edit

        QTimer.singleShot(0, self._build_phase2)

    def _build_phase2(self):
        """第2帧：应用配置卡片"""
        from PyQt6.QtCore import QTimer
        layout = self._build_layout

        app_config_card = GroupHeaderCardWidget(self)
        app_config_card.setTitle(tr("application_config"))
        app_config_card.setBorderRadius(8)
        app_config_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        self.debug_check = SwitchButton()
        self.debug_check.setChecked(False)
        app_config_card.addGroup(FluentIcon.DEVELOPER_TOOLS, tr("debug_mode"), tr("debug_mode_hint"), self.debug_check)

        self.logging_check = SwitchButton()
        self.logging_check.setChecked(True)
        app_config_card.addGroup(FluentIcon.SAVE, tr("save_log_files"), tr("save_log_files_hint"), self.logging_check)

        self.unlocker_combo = ComboBox()
        self.unlocker_combo.addItems([tr("auto_detect"), tr("force_steamtools"), tr("force_greenluma"), tr("force_opensteamtools")])
        self.unlocker_combo.setCurrentIndex(0)
        self.unlocker_combo.setFixedWidth(180)
        app_config_card.addGroup(FluentIcon.SETTING, tr("unlocker_mode"), tr("force_unlocker_hint"), self.unlocker_combo)

        self.st_mode_combo = ComboBox()
        self.st_mode_combo.addItems([tr("auto_update"), tr("st_fixed_enable")])
        self.st_mode_combo.setCurrentIndex(0)  # 默认选中自动更新
        self.st_mode_combo.setFixedWidth(180)
        self.st_mode_combo.setToolTip(tr("st_fixed_tooltip"))
        app_config_card.addGroup(FluentIcon.SETTING, tr("st_settings"), tr("st_settings_hint"), self.st_mode_combo)

        # 固定版本manifest修复选项（信号在 _setup_auto_save_listeners 中连接）
        self.st_fixed_manifest_combo = ComboBox()
        self.st_fixed_manifest_combo.addItems([tr("st_fixed_manifest_always"), tr("st_fixed_manifest_never"), tr("st_fixed_manifest_ask")])
        self.st_fixed_manifest_combo.setCurrentIndex(2)  # 默认选中询问
        self.st_fixed_manifest_combo.setFixedWidth(180)
        self.st_fixed_manifest_combo.setToolTip(tr("st_fixed_manifest_mode_hint"))
        # 注意：信号连接移到 _setup_auto_save_listeners，避免配置加载前触发保存
        app_config_card.addGroup(FluentIcon.DOCUMENT, tr("st_fixed_manifest_mode"), tr("st_fixed_manifest_mode_hint"), self.st_fixed_manifest_combo)

        # 显示进度条选项（信号在 _setup_auto_save_listeners 中连接）
        self.show_progress_check = SwitchButton()
        self.show_progress_check.setChecked(True)
        # 注意：信号连接移到 _setup_auto_save_listeners，避免配置加载前触发保存
        app_config_card.addGroup(FluentIcon.SYNC, tr("show_progress_bar"), tr("show_progress_bar_hint"), self.show_progress_check)

        # 平滑滚动选项（信号在 _setup_auto_save_listeners 中连接）
        self.smooth_scroll_check = SwitchButton()
        self.smooth_scroll_check.setChecked(True)
        # 注意：信号连接移到 _setup_auto_save_listeners，避免配置加载前触发保存
        app_config_card.addGroup(FluentIcon.SCROLL, tr("smooth_scroll"), tr("smooth_scroll_hint"), self.smooth_scroll_check)

        # 创建 DLC 超时时间设置（左边输入框，右边滑块）
        self.dlc_timeout_edit = LineEdit()
        self.dlc_timeout_edit.setText("60")
        self.dlc_timeout_edit.setPlaceholderText("5-600")
        self.dlc_timeout_edit.setFixedWidth(80)  # 缩小宽度
        # 设置输入验证器，限制只能输入数字
        self.dlc_timeout_edit.setValidator(QIntValidator(5, 600, self.dlc_timeout_edit))
        
        # 创建单位标签
        self.dlc_timeout_label = QLabel(" s")
        
        # 创建滑块控件
        self.dlc_timeout_slider = Slider(Qt.Orientation.Horizontal)
        self.dlc_timeout_slider.setRange(5, 600)
        self.dlc_timeout_slider.setValue(60)
        self.dlc_timeout_slider.setFixedWidth(200)
        
        # 创建水平布局容器
        dlc_timeout_layout = QHBoxLayout()
        dlc_timeout_layout.addWidget(self.dlc_timeout_edit)
        dlc_timeout_layout.addWidget(self.dlc_timeout_label)
        dlc_timeout_layout.addStretch(1)
        dlc_timeout_layout.addWidget(self.dlc_timeout_slider)
        dlc_timeout_layout.setContentsMargins(0, 0, 0, 0)
        
        dlc_timeout_widget = QWidget()
        dlc_timeout_widget.setLayout(dlc_timeout_layout)
        app_config_card.addGroup(FluentIcon.SPEED_HIGH, tr("dlc_timeout"), tr("dlc_timeout_hint"), dlc_timeout_widget)

        # 创建下载超时时间设置（左边输入框，右边滑块）
        self.timeout_edit = LineEdit()
        self.timeout_edit.setText("30")
        self.timeout_edit.setPlaceholderText("10-300")
        self.timeout_edit.setFixedWidth(80)  # 缩小宽度
        # 设置输入验证器，限制只能输入数字
        self.timeout_edit.setValidator(QIntValidator(10, 300, self.timeout_edit))
        
        # 创建单位标签
        self.timeout_label = QLabel(" s")
        
        # 创建滑块控件
        self.timeout_slider = Slider(Qt.Orientation.Horizontal)
        self.timeout_slider.setRange(10, 300)
        self.timeout_slider.setValue(30)
        self.timeout_slider.setFixedWidth(200)
        
        # 创建水平布局容器
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(self.timeout_edit)
        timeout_layout.addWidget(self.timeout_label)
        timeout_layout.addStretch(1)
        timeout_layout.addWidget(self.timeout_slider)
        timeout_layout.setContentsMargins(0, 0, 0, 0)
        
        timeout_widget = QWidget()
        timeout_widget.setLayout(timeout_layout)
        app_config_card.addGroup(FluentIcon.SPEED_HIGH, tr("download_timeout"), tr("download_timeout_hint"), timeout_widget)

        layout.addWidget(app_config_card)

        # 添加自定义仓库卡片
        self.custom_repos_card = CustomReposCard(self)
        self.custom_repos_card.repos_changed.connect(self._on_custom_repos_changed)
        layout.addWidget(self.custom_repos_card)

        QTimer.singleShot(0, self._build_phase3)

        # 设置同步逻辑
        self._setup_sync_connections()

    def _setup_sync_connections(self):
        """设置输入框和滑块之间的同步连接"""
        # DLC 超时时间同步
        if self.dlc_timeout_edit and self.dlc_timeout_slider:
            # 输入框文本改变时同步滑块
            self.dlc_timeout_edit.textChanged.connect(self._on_dlc_timeout_edit_changed)
            # 滑块值改变时同步输入框
            self.dlc_timeout_slider.valueChanged.connect(self._on_dlc_timeout_slider_changed)
            
        # 下载超时时间同步
        if self.timeout_edit and self.timeout_slider:
            # 输入框文本改变时同步滑块
            self.timeout_edit.textChanged.connect(self._on_timeout_edit_changed)
            # 滑块值改变时同步输入框
            self.timeout_slider.valueChanged.connect(self._on_timeout_slider_changed)
    
    def _on_dlc_timeout_edit_changed(self, text):
        """DLC 超时时间输入框改变"""
        if text and text.isdigit():
            value = int(text)
            # 确保值在有效范围内
            if value < 5:
                value = 5
            elif value > 600:
                value = 600
            self.dlc_timeout_slider.setValue(value)
            # 如果输入的值超出范围，自动修正输入框的值
            if int(text) != value:
                self.dlc_timeout_edit.setText(str(value))
    
    def _on_dlc_timeout_slider_changed(self, value):
        """DLC 超时时间滑块改变"""
        self.dlc_timeout_edit.setText(str(value))
    
    def _on_timeout_edit_changed(self, text):
        """下载超时时间输入框改变"""
        if text and text.isdigit():
            value = int(text)
            # 确保值在有效范围内
            if value < 10:
                value = 10
            elif value > 300:
                value = 300
            self.timeout_slider.setValue(value)
            # 如果输入的值超出范围，自动修正输入框的值
            if int(text) != value:
                self.timeout_edit.setText(str(value))
    
    def _on_timeout_slider_changed(self, value):
        """下载超时时间滑块改变"""
        self.timeout_edit.setText(str(value))

    def _build_phase3(self):
        """第3帧：外观卡片"""
        from PyQt6.QtCore import QTimer
        layout = self._build_layout

        appearance_card = GroupHeaderCardWidget(self)
        appearance_card.setTitle(tr("appearance"))
        appearance_card.setBorderRadius(8)
        appearance_card.setStyleSheet("""
            GroupHeaderCardWidget {
                border: none;
                background: transparent;
            }
        """)

        self.theme_combo = ComboBox()
        self.theme_combo.addItems([tr("light_theme"), tr("dark_theme"), tr("follow_system")])
        self.theme_combo.setCurrentIndex(2 if not isDarkTheme() else 1)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_mode_changed)
        self.theme_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.PALETTE, tr("theme_mode"), tr("theme_mode_hint"), self.theme_combo)

        self.color_combo = ComboBox()
        self.color_combo.addItems([tr("default_blue"), tr("purple"), tr("green"), tr("orange"), tr("red"), tr("pink")])
        self.color_combo.currentIndexChanged.connect(self.on_theme_color_changed)
        self.color_combo.setFixedWidth(200)
        appearance_card.addGroup(FluentIcon.BRUSH, tr("theme_color"), tr("theme_color_hint"), self.color_combo)

        self.default_page_combo = ComboBox()
        self.default_page_combo.addItems([tr("default_page_home"), tr("default_page_search")])
        self.default_page_combo.currentIndexChanged.connect(self.on_default_page_changed)
        self.default_page_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.HOME, tr("default_page"), tr("default_page_hint"), self.default_page_combo)

        self.lang_combo = ComboBox()
        self.lang_combo.addItems(["系统默认", "简体中文", "繁體中文", "English"])
        self.lang_combo.setCurrentIndex(0)
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self.lang_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.LANGUAGE, tr("language"), tr("language_hint"), self.lang_combo)

        self.effect_combo = ComboBox()
        self.effect_combo.addItems([tr("effect_none"), tr("effect_mica")])
        self.effect_combo.currentIndexChanged.connect(self.on_window_effect_changed)
        self.effect_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.PALETTE, tr("window_effect"), tr("window_effect_hint"), self.effect_combo)

        layout.addWidget(appearance_card)
        QTimer.singleShot(0, self._build_phase4)

    def _build_phase4(self):
        """第4帧：日志卡片 + 按钮行，完成后加载配置"""
        layout = self._build_layout

        log_card = CardWidget(self)
        log_card.setStyleSheet("""
            CardWidget {
                border: none;
                background: transparent;
            }
        """)
        log_card_layout = QVBoxLayout(log_card)
        log_card_layout.setContentsMargins(20, 16, 20, 16)
        log_card_layout.setSpacing(8)
        log_header = QHBoxLayout()
        log_header.addWidget(BodyLabel(tr("settings_log_title"), log_card))
        log_header.addStretch(1)
        clear_log_btn = TransparentToolButton(FluentIcon.DELETE, log_card)
        clear_log_btn.setToolTip(tr("settings_clear_log"))
        clear_log_btn.clicked.connect(self._clear_log)
        log_header.addWidget(clear_log_btn)
        log_card_layout.addLayout(log_header)
        self.log_view = TextEdit(log_card)
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(200)
        # 根据主题模式动态设置背景颜色
        if isDarkTheme():
            self.log_view.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.12); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        else:
            self.log_view.setStyleSheet(
                "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                "font-size: 12px; padding: 8px; }"
            )
        log_card_layout.addWidget(self.log_view)
        layout.addWidget(log_card)

        button_layout = QHBoxLayout()
        self.reset_btn = PushButton(tr("reset_to_default"))
        self.reset_btn.clicked.connect(self.reset_settings)
        self.reset_btn.setFixedWidth(120)
        button_layout.addWidget(self.reset_btn)
        self.check_update_btn = PushButton(tr("check_update"))
        self.check_update_btn.clicked.connect(self.check_for_updates)
        self.check_update_btn.setFixedWidth(100)
        button_layout.addWidget(self.check_update_btn)
        self.thanks_btn = PushButton(tr("thanks"))
        self.thanks_btn.clicked.connect(self.show_thanks)
        self.thanks_btn.setFixedWidth(80)
        button_layout.addWidget(self.thanks_btn)
        self.donate_btn = PushButton(tr("donate"))
        self.donate_btn.clicked.connect(self.show_donate)
        self.donate_btn.setFixedWidth(80)
        button_layout.addWidget(self.donate_btn)
        self.github_btn = HyperlinkButton("https://github.com/zhouchentao666/Fluent-Install", "GitHub")
        self.github_btn.setFixedWidth(70)
        button_layout.addWidget(self.github_btn)
        self.document_btn = HyperlinkButton("https://zhouchentao666.github.io/Fluent-Install/", "文档")
        self.document_btn.setFixedWidth(70)
        button_layout.addWidget(self.document_btn)
        self.qq_btn = HyperlinkButton("https://qm.qq.com/q/gtTLap5Jw4", "Q群")
        self.qq_btn.setFixedWidth(50)
        button_layout.addWidget(self.qq_btn)
        self.tg_group_btn = HyperlinkButton("https://t.me/+vTrqXKpRJE9kNmVl", "TG")
        self.tg_group_btn.setFixedWidth(50)
        button_layout.addWidget(self.tg_group_btn)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)
        layout.addStretch(1)

        # 刷入缓冲日志
        for level, msg in self._pending_logs:
            self._append_log(level, msg)
        self._pending_logs.clear()

        # UI 全部就绪，加载配置
        if not self._config_loaded:
            self._config_loaded = True
            self.load_config()
            self._setup_auto_save_listeners()
        else:
            # 配置已加载过（可能是预构建时），但控件刚创建，需要重新加载配置到控件
            self.load_config()
            # 重新连接信号监听器（控件是新创建的）
            self._setup_auto_save_listeners()
    
    def _setup_auto_save_listeners(self):
        """设置自动保存监听器"""
        # Steam路径和Token输入框
        if self.steam_path_edit:
            self.steam_path_edit.textChanged.connect(self._on_setting_changed_delayed)
        if self.token_edit:
            self.token_edit.textChanged.connect(self._on_setting_changed_delayed)
        if self.manifest_api_key_edit:
            self.manifest_api_key_edit.textChanged.connect(self._on_setting_changed_delayed)
        
        # 复选框
        if self.debug_check:
            self.debug_check.checkedChanged.connect(self._on_setting_changed)
        if self.logging_check:
            self.logging_check.checkedChanged.connect(self._on_setting_changed)
        if self.show_progress_check:
            self.show_progress_check.checkedChanged.connect(self._on_setting_changed)
        if self.smooth_scroll_check:
            self.smooth_scroll_check.checkedChanged.connect(self._on_smooth_scroll_changed)
        
        # 下拉框
        if self.unlocker_combo:
            self.unlocker_combo.currentIndexChanged.connect(self._on_setting_changed)
        
        if self.st_mode_combo:
            self.st_mode_combo.currentIndexChanged.connect(self._on_setting_changed)
        
        if self.st_fixed_manifest_combo:
            self.st_fixed_manifest_combo.currentIndexChanged.connect(self._on_setting_changed)

        # DLC 超时时间
        if self.dlc_timeout_spinbox:
            self.dlc_timeout_spinbox.valueChanged.connect(self._on_setting_changed)

        # 入库超时时间
        if self.timeout_spinbox:
            self.timeout_spinbox.valueChanged.connect(self._on_setting_changed)
        
        # 窗口特效
        if self.effect_combo:
            self.effect_combo.currentIndexChanged.connect(self._on_setting_changed)

    def _on_setting_changed(self):
        """设置改变时立即保存"""
        self.save_settings()
    
    def _on_setting_changed_delayed(self):
        """设置改变时延迟保存（用于文本输入）"""
        # 取消之前的定时器
        if self._save_timer:
            self._save_timer.stop()
        else:
            from PyQt6.QtCore import QTimer
            self._save_timer = QTimer()
            self._save_timer.timeout.connect(self.save_settings)
            self._save_timer.setSingleShot(True)
        
        # 延迟500ms保存，避免频繁保存
        self._save_timer.start(500)

    def _on_smooth_scroll_changed(self):
        """平滑滚动设置改变"""
        # 获取当前设置值
        smooth_scroll = self.smooth_scroll_check.isChecked()
        # 保存设置
        self.save_settings()
        # 通知主窗口更新所有页面的平滑滚动状态（直接传递设置值，避免异步读取）
        main_window = self.window()
        if hasattr(main_window, 'update_smooth_scroll_for_all_pages'):
            main_window.update_smooth_scroll_for_all_pages(smooth_scroll)

    def _on_custom_repos_changed(self):
        """自定义仓库列表变化时保存并通知"""
        self.save_settings()
        # 发射信号通知主窗口更新搜索页面的清单源下拉框
        self.custom_repos_changed.emit()

    def on_theme_mode_changed(self, index):
        """主题模式切换"""
        theme_map = {0: "light", 1: "dark", 2: "auto"}
        selected_theme = theme_map.get(index, "auto")
        
        # 保存主题设置
        self.save_theme_setting("theme_mode", selected_theme)
        
        # 立即应用主题更改
        if selected_theme == "auto":
            setTheme(Theme.AUTO)
        elif selected_theme == "light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)
        
        # 通知所有组件主题已变化
        self.notify_theme_changed()
    
    def on_theme_color_changed(self, index):
        """主题色切换"""
        colors = ["#0078d4", "#9b4dca", "#10893e", "#ff8c00", "#e81123", "#e3008c"]
        
        if 0 <= index < len(colors):
            selected_color = colors[index]
            
            # 保存主题色设置
            self.save_theme_setting("theme_color", selected_color)
            
            # 立即应用主题颜色更改
            setThemeColor(selected_color)
            
            # 通知所有组件主题已变化
            self.notify_theme_changed()
    
    def notify_theme_changed(self):
        """通知所有卡片组件主题已变化"""
        # 更新日志显示组件的样式
        if hasattr(self, 'log_view') and self.log_view:
            if isDarkTheme():
                self.log_view.setStyleSheet(
                    "TextEdit { background: rgba(0,0,0,0.12); border-radius: 6px; "
                    "font-size: 12px; padding: 8px; color: #ffffff; }"
                )
            else:
                self.log_view.setStyleSheet(
                    "TextEdit { background: rgba(0,0,0,0.05); border-radius: 6px; "
                    "font-size: 12px; padding: 8px; color: #000000; }"
                )
            
            # 强制刷新日志内容
            self.log_view.update()
            self.log_view.repaint()
    
    def save_theme_setting(self, key, value):
        """保存单个主题设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            config[key] = value
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存主题设置失败: {e}")
    
    def load_theme_setting(self, key):
        """加载单个主题设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get(key)
        except:
            pass
        
        # 返回默认值
        from backend.cai_backend import DEFAULT_CONFIG
        return DEFAULT_CONFIG.get(key)
    
    def on_language_changed(self, index):
        """语言切换"""
        lang_map = {0: "system", 1: "zh_CN", 2: "zh_TW", 3: "en_US"}
        lang_name_map = {0: "系统默认", 1: "简体中文", 2: "繁體中文", 3: "English"}
        selected_lang = lang_map.get(index, "system")
        lang_name = lang_name_map.get(index, "系统默认")
        
        # 立即应用语言设置，使对话框显示新语言
        set_language(selected_lang)
        
        # 显示重启提示
        dialog = MessageBox(
            tr("restart_required"),
            tr("language_changed", lang_name),
            self.window()
        )
        
        if dialog.exec():
            # 保存语言设置
            self.save_language_setting(selected_lang)
            # 重启应用
            import sys
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
            import os
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            # 用户取消，恢复原来的语言设置
            current_lang = self.load_language_setting()
            set_language(current_lang)
            reverse_map = {"system": 0, "zh_CN": 1, "zh_TW": 2, "en_US": 3}
            self.lang_combo.setCurrentIndex(reverse_map.get(current_lang, 0))
    
    def on_default_page_changed(self, index):
        """默认界面切换"""
        page_map = {0: "home", 1: "search"}
        page_type = page_map.get(index, "home")
        
        # 保存设置
        self.save_theme_setting("default_page", page_type)
    
    def on_window_effect_changed(self, index):
        """窗口特效切换"""
        effect_map = {0: "none", 1: "mica"}
        effect_type = effect_map.get(index, "none")
        
        # 立即应用特效
        if hasattr(self.window(), 'apply_window_effect'):
            self.window().apply_window_effect(effect_type)
        
        # 保存设置
        self.save_theme_setting("window_effect", effect_type)
    
    def save_language_setting(self, lang):
        """保存语言设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            config["language"] = lang
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存语言设置失败: {e}")
    
    def load_language_setting(self):
        """加载语言设置"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get("language", "zh_CN")
        except:
            pass
        return "zh_CN"
    
    def check_for_updates(self):
        """检查更新"""
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText(tr("checking"))

        async def _check():
            async with CaiBackend() as backend:
                has_update, info = await backend.check_for_updates()
                return has_update, info

        _replace_worker(getattr(self, '_update_worker', None))
        worker = AsyncWorker(_check())
        self._update_worker = worker

        def on_result(result):
            self._update_worker = None
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText(tr("check_update"))
            has_update, info = result
            if has_update:
                # 使用非模态方式显示更新提示，避免卡死
                msg = MessageBox(
                    tr("update_available"),
                    f"{tr('current_version')}: {info.get('current_version', '')}\n"
                    f"{tr('latest_version')}: {info.get('latest_version', '')}\n\n"
                    f"{info.get('release_body', '') or tr('no_release_notes')}",
                    self.window()
                )
                msg.yesButton.setText(tr("go_to_download"))
                msg.cancelButton.setText(tr("cancel"))
                if msg.exec():
                    # 获取镜像化的下载链接，直接跳转到具体的下载链接
                    download_url = self._get_mirror_download_url(
                        info.get('release_url', f"https://github.com/{GITHUB_REPO}/releases"),
                        info.get('latest_version', '')
                    )
                    QDesktopServices.openUrl(QUrl(download_url))
            else:
                InfoBar.success(
                    title=tr("already_latest"),
                    content=tr("already_latest_content"),
                    parent=self.window(),
                    position=InfoBarPosition.TOP,
                    duration=3000
                )

        def on_error(error):
            self._update_worker = None
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText(tr("check_update"))
            InfoBar.error(
                title=tr("check_update_failed"),
                content=error,
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=4000
            )

        worker.result_ready.connect(on_result)
        worker.error.connect(on_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def show_thanks(self):
        """显示鸣谢对话框"""
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget
        from PyQt6.QtCore import Qt

        def add_section(layout, title):
            lbl = BodyLabel(title)
            lbl.setStyleSheet("font-weight: bold; margin-top: 8px;")
            layout.addWidget(lbl)

        def add_text(layout, text):
            lbl = BodyLabel(text)
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        def add_link(layout, label, url):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            prefix = BodyLabel("•")
            btn = HyperlinkButton(url, label)
            row.addWidget(prefix)
            row.addWidget(btn)
            row.addStretch(1)
            layout.addLayout(row)

        class ThanksDialog(MessageBoxBase):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.titleLabel = TitleLabel(tr("thanks_title"), self)

                scroll = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical)
                scroll.setWidgetResizable(True)
                scroll.setFixedHeight(360)
                scroll.enableTransparentBackground()

                inner = QWidget()
                inner.setStyleSheet("background: transparent;")
                inner_layout = QVBoxLayout(inner)
                inner_layout.setContentsMargins(4, 4, 4, 4)
                inner_layout.setSpacing(2)

                add_section(inner_layout, "开发者")
                add_text(inner_layout, "• zhouchentao666 - 制作人员")

                add_section(inner_layout, "开源项目")
                add_link(inner_layout, "PyQt6", "https://pypi.org/project/PyQt6/")
                add_link(inner_layout, "PyQt-Fluent-Widgets", "https://github.com/zhiyiYo/PyQt-Fluent-Widgets")
                add_link(inner_layout, "Cai-install-Web-GUI", "https://github.com/ikunshare/Onekey")
                add_link(inner_layout, "Game-Cheats-Manager", "https://github.com/dyang886/Game-Cheats-Manager")
                add_link(inner_layout, "httpx", "https://www.python-httpx.org/")

                add_section(inner_layout, "清单源提供")
                for src in ["SWA V2", "Walftech", "SteamAutoCracks", "Sudama", "清单不求人"]:
                    add_text(inner_layout, f"• {src}")

                add_section(inner_layout, "社区与联系")
                add_link(inner_layout, "GitHub", "https://github.com/zhouchentao666/Fluent-Install")
                add_link(inner_layout, "加入 Q 群", "https://qm.qq.com/q/gtTLap5Jw4")
                add_link(inner_layout, "TG 群组", "https://t.me/+vTrqXKpRJE9kNmVl")

                add_text(inner_layout, "\n感谢所有为本项目做出贡献的开发者和用户！")
                inner_layout.addStretch(1)

                scroll.setWidget(inner)

                self.viewLayout.addWidget(self.titleLabel)
                self.viewLayout.addWidget(scroll)

                self.yesButton.setText("OK")
                self.cancelButton.hide()
                self.widget.setMinimumWidth(420)

        ThanksDialog(self.window()).exec()
    
    def show_donate(self):
        """显示捐赠对话框（滑动布局，我的在上，原作者在下）"""
        from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

        # 收款码数据：(section_title, wechat_url, alipay_url)
        sections = [
            (
                tr("donate_title"),
                "https://camo.githubusercontent.com/04109c585ad05e20dcd31440afca895f1d79f27714ab16fe8e7a572df6c6f111/68747470733a2f2f7075622d31343138333165363165363934343532383932323239373661313562366662332e72322e6465762f496d6167655f746f5f75726c5f56322f363138383233373537363837363030333036385f3132312d696d616765746f75726c2e636c6f75642d313737343030353531313830322d7369757738372e6a7067",
                "https://camo.githubusercontent.com/f8b910605f13a067d233bc5ceeee2601cd44d2939f7613c299e4007e2fe76cbf/68747470733a2f2f7075622d31343138333165363165363934343532383932323239373661313562366662332e72322e6465762f496d6167655f746f5f75726c5f56322f363138383233373537363837363030333036395f3132312d696d616765746f75726c2e636c6f75642d313737343030353531333934352d33356e7979652e6a7067",
            ),
            (
                "赞助原项目作者及资源代码帮助",
                "https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/D802B1D90E33AFCF696B5F13BAB74457-imagetourl.cloud-1774703169429-179e1b.png",
                "https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/756ED1C8EA7FF43FBE304E86B1C58C49-imagetourl.cloud-1774703169610-iod0j3.jpg",
            ),
        ]

        class DonateDialog(MessageBoxBase):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.titleLabel = TitleLabel(tr("donate_title"), self)
                self._nam = QNetworkAccessManager(self)

                scroll = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical)
                scroll.setWidgetResizable(True)
                scroll.setFixedHeight(420)
                scroll.enableTransparentBackground()

                inner = QWidget()
                inner.setStyleSheet("background: transparent;")
                inner_layout = QVBoxLayout(inner)
                inner_layout.setContentsMargins(4, 4, 4, 4)
                inner_layout.setSpacing(20)

                self._img_labels = []

                for section_title, wechat_url, alipay_url in sections:
                    sec_label = BodyLabel(section_title)
                    sec_label.setStyleSheet("font-weight: bold;")
                    sec_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    inner_layout.addWidget(sec_label)

                    qr_layout = QHBoxLayout()
                    qr_layout.setSpacing(24)
                    qr_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

                    for col_title, url in [(tr("donate_wechat"), wechat_url), (tr("donate_alipay"), alipay_url)]:
                        col = QVBoxLayout()
                        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                        lbl_title = BodyLabel(col_title)
                        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        img = QLabel(tr("donate_loading"))
                        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        img.setFixedSize(240, 240)
                        img.setStyleSheet("border: 1px solid rgba(128,128,128,0.3); border-radius: 6px;")
                        col.addWidget(lbl_title)
                        col.addWidget(img)
                        qr_layout.addLayout(col)
                        self._img_labels.append((img, url))

                    inner_layout.addLayout(qr_layout)

                inner_layout.addStretch(1)
                scroll.setWidget(inner)

                self.viewLayout.addWidget(self.titleLabel)
                self.viewLayout.addWidget(scroll)
                self.yesButton.setText("OK")
                self.cancelButton.hide()
                self.widget.setMinimumWidth(500)

                for img, url in self._img_labels:
                    self._load_image(url, img)

            def _load_image(self, url, label):
                reply = self._nam.get(QNetworkRequest(QUrl(url)))

                def on_finished():
                    try:
                        if reply.error() == QNetworkReply.NetworkError.NoError:
                            pixmap = QPixmap()
                            pixmap.loadFromData(reply.readAll())
                            if not pixmap.isNull():
                                # 按 label 实际像素尺寸缩放，保持清晰
                                dpr = label.devicePixelRatio()
                                target = int(240 * dpr)
                                scaled = pixmap.scaled(
                                    target, target,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation
                                )
                                scaled.setDevicePixelRatio(dpr)
                                label.setPixmap(scaled)
                                label.setText("")
                                return
                        label.setText(tr("donate_load_failed"))
                    except RuntimeError:
                        pass
                    finally:
                        reply.deleteLater()

                reply.finished.connect(on_finished)

        DonateDialog(self.window()).exec()
    
    def load_config(self):
        """加载配置（同步读取本地文件，避免卡顿）"""
        try:
            import json as _json
            config_path = APP_ROOT / 'config' / 'config.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = _json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            # 使用 QTimer 延迟调用，避免Nuitka编译后的信号问题
            QTimer.singleShot(0, lambda: self.on_config_loaded(config))
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            # 使用 QTimer 延迟调用，避免Nuitka编译后的信号问题
            QTimer.singleShot(0, lambda: self.on_load_error(error_msg))
    
    def on_config_loaded(self, config):
        """配置加载完成"""
        if not config:
            return
        
        # 获取主设置卡片
        settings_card = self.findChild(SettinsCard)
        if settings_card:
            settings_card.steam_path_edit.setText(config.get("Custom_Steam_Path", ""))
            settings_card.token_edit.setText(config.get("Github_Personal_Token", ""))
            settings_card.manifest_api_key_edit.setText(config.get("ManifestAPIKey", ""))
        
        # 加载应用程序配置
        if self.debug_check:
            new_val = config.get("debug_mode", False)
            if self.debug_check.isChecked() != new_val:
                try:
                    self.debug_check.checkedChanged.disconnect(self._on_setting_changed)
                except:
                    pass
                self.debug_check.setChecked(new_val)
                self.debug_check.checkedChanged.connect(self._on_setting_changed)
        if self.logging_check:
            new_val = config.get("logging_files", True)
            if self.logging_check.isChecked() != new_val:
                try:
                    self.logging_check.checkedChanged.disconnect(self._on_setting_changed)
                except:
                    pass
                self.logging_check.setChecked(new_val)
                self.logging_check.checkedChanged.connect(self._on_setting_changed)
        
        # 加载解锁工具模式
        if self.unlocker_combo:
            force_unlocker = config.get("force_unlocker_type", "auto")
            if force_unlocker == "steamtools":
                new_idx = 1
            elif force_unlocker == "greenluma":
                new_idx = 2
            elif force_unlocker == "opensteamtools":
                new_idx = 3
            else:
                new_idx = 0
            if self.unlocker_combo.currentIndex() != new_idx:
                try:
                    self.unlocker_combo.currentIndexChanged.disconnect(self._on_setting_changed)
                except:
                    pass
                self.unlocker_combo.setCurrentIndex(new_idx)
                self.unlocker_combo.currentIndexChanged.connect(self._on_setting_changed)
        
        # 加载SteamTools版本模式设置
        if self.st_mode_combo:
            is_fixed = config.get("ST_Fixed_Version", False)  # 默认自动更新
            new_index = 1 if is_fixed else 0
            # 只在需要改变时才设置，避免不必要的信号触发
            if self.st_mode_combo.currentIndex() != new_index:
                # 临时断开信号，避免触发保存
                try:
                    self.st_mode_combo.currentIndexChanged.disconnect(self._on_setting_changed)
                except:
                    pass
                self.st_mode_combo.setCurrentIndex(new_index)
                # 重新连接信号
                self.st_mode_combo.currentIndexChanged.connect(self._on_setting_changed)
        
        # 加载固定版本manifest修复模式设置
        if self.st_fixed_manifest_combo:
            manifest_mode = config.get("ST_Fixed_Manifest_Mode", "ask")  # 默认询问
            mode_map = {"always": 0, "never": 1, "ask": 2}
            new_idx = mode_map.get(manifest_mode, 2)
            if self.st_fixed_manifest_combo.currentIndex() != new_idx:
                try:
                    self.st_fixed_manifest_combo.currentIndexChanged.disconnect(self._on_setting_changed)
                except:
                    pass
                self.st_fixed_manifest_combo.setCurrentIndex(new_idx)
                self.st_fixed_manifest_combo.currentIndexChanged.connect(self._on_setting_changed)

        # 加载DLC超时时间
        if self.dlc_timeout_spinbox:
            self.dlc_timeout_spinbox.setValue(config.get("DLCTimeout", 60))

        # 加载入库超时时间
        if self.timeout_spinbox:
            self.timeout_spinbox.setValue(config.get("download_timeout", 30))
        
        # 加载显示进度条选项
        if self.show_progress_check:
            new_val = config.get("show_progress_bar", True)
            if self.show_progress_check.isChecked() != new_val:
                try:
                    self.show_progress_check.checkedChanged.disconnect(self._on_setting_changed)
                except:
                    pass
                self.show_progress_check.setChecked(new_val)
                self.show_progress_check.checkedChanged.connect(self._on_setting_changed)

        # 加载语言设置
        if self.lang_combo:
            # 先断开信号连接，避免触发 on_language_changed
            self.lang_combo.currentIndexChanged.disconnect(self.on_language_changed)
            
            lang = config.get("language", "system")
            if lang == "system":
                # 检测系统语言
                system_locale = QLocale.system()
                if system_locale.language() == QLocale.Language.Chinese:
                    self.lang_combo.setCurrentIndex(0)  # 系统默认，实际为中文
                else:
                    self.lang_combo.setCurrentIndex(0)  # 系统默认
            elif lang == "zh_CN":
                self.lang_combo.setCurrentIndex(1)
            elif lang == "zh_TW":
                self.lang_combo.setCurrentIndex(2)
            elif lang == "en_US":
                self.lang_combo.setCurrentIndex(3)
            else:
                self.lang_combo.setCurrentIndex(3)  # 默认英文
            
            # 重新连接信号
            self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        
        # 加载主题模式设置
        if self.theme_combo:
            theme_mode = config.get("theme_mode", "auto")
            if theme_mode == "light":
                self.theme_combo.setCurrentIndex(0)
            elif theme_mode == "dark":
                self.theme_combo.setCurrentIndex(1)
            else:
                self.theme_combo.setCurrentIndex(2)
        
        # 加载主题色设置
        if self.color_combo:
            theme_color = config.get("theme_color", "#0078d4")
            color_map = {
                "#0078d4": 0,
                "#9b4dca": 1,
                "#10893e": 2,
                "#ff8c00": 3,
                "#e81123": 4,
                "#e3008c": 5
            }
            color_index = color_map.get(theme_color, 0)
            self.color_combo.setCurrentIndex(color_index)
        
        # 加载默认界面设置
        if self.default_page_combo:
            default_page = config.get("default_page", "home")
            page_map = {
                "home": 0,
                "search": 1
            }
            page_index = page_map.get(default_page, 0)
            self.default_page_combo.setCurrentIndex(page_index)
        
        # 加载窗口特效设置
        if self.effect_combo:
            window_effect = config.get("window_effect", "mica")
            effect_map = {
                "none": 0,
                "mica": 1
            }
            effect_index = effect_map.get(window_effect, 1)  # 默认为云母效果
            self.effect_combo.setCurrentIndex(effect_index)

        # 加载平滑滚动设置
        if self.smooth_scroll_check:
            smooth_scroll = config.get("smooth_scroll", True)  # 默认开启平滑滚动
            # 先断开信号，避免触发保存
            try:
                self.smooth_scroll_check.checkedChanged.disconnect(self._on_smooth_scroll_changed)
            except:
                pass
            self.smooth_scroll_check.setChecked(smooth_scroll)
            # 信号将在 _setup_auto_save_listeners 中重新连接

        # 应用窗口特效
        window_effect = config.get("window_effect", "mica")
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, 'apply_window_effect'):
                main_window.apply_window_effect(window_effect)
        except Exception as e:
            print(f"应用窗口特效失败: {e}")

        # 加载自定义仓库配置
        if self.custom_repos_card:
            custom_repos = config.get("Custom_Repos", {"github": [], "zip": []})
            github_repos = custom_repos.get("github", [])
            zip_repos = custom_repos.get("zip", [])
            self.custom_repos_card.set_repos(github_repos, zip_repos)

    def on_load_error(self, error):
        """加载失败"""
        InfoBar.error(
            title=tr("load_config_failed"),
            content=str(error),
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000
        )
    
    def save_settings(self):
        """保存设置"""
        async def _save():
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend.cai_backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 更新配置
            settings_card = self.findChild(SettinsCard)
            if settings_card:
                config["Custom_Steam_Path"] = settings_card.steam_path_edit.text().strip()
                config["Github_Personal_Token"] = settings_card.token_edit.text().strip()
                config["ManifestAPIKey"] = settings_card.manifest_api_key_edit.text().strip()
            
            # 保存应用程序配置
            if self.debug_check:
                config["debug_mode"] = self.debug_check.isChecked()
            if self.logging_check:
                config["logging_files"] = self.logging_check.isChecked()
            
            # 保存解锁工具模式
            if self.unlocker_combo:
                unlocker_map = {0: "auto", 1: "steamtools", 2: "greenluma", 3: "opensteamtools"}
                config["force_unlocker_type"] = unlocker_map.get(self.unlocker_combo.currentIndex(), "auto")
            
            # 保存SteamTools版本模式设置
            if self.st_mode_combo:
                config["ST_Fixed_Version"] = self.st_mode_combo.currentIndex() == 1
            
            # 保存固定版本manifest修复模式设置
            if self.st_fixed_manifest_combo:
                mode_map = {0: "always", 1: "never", 2: "ask"}
                config["ST_Fixed_Manifest_Mode"] = mode_map.get(self.st_fixed_manifest_combo.currentIndex(), "ask")

            # 保存DLC超时时间
            if self.dlc_timeout_spinbox:
                dlc_timeout = self.dlc_timeout_spinbox.value()
                config["DLCTimeout"] = dlc_timeout if dlc_timeout >= 5 else 60

            # 保存入库超时时间
            if self.timeout_spinbox:
                config["download_timeout"] = self.timeout_spinbox.value()
            
            # 保存显示进度条选项
            if self.show_progress_check:
                config["show_progress_bar"] = self.show_progress_check.isChecked()

            # 保存主题模式
            if self.theme_combo:
                theme_mode_map = {0: "light", 1: "dark", 2: "auto"}
                config["theme_mode"] = theme_mode_map.get(self.theme_combo.currentIndex(), "auto")
            
            # 保存主题色
            if self.color_combo:
                colors = ["#0078d4", "#9b4dca", "#10893e", "#ff8c00", "#e81123", "#e3008c"]
                color_index = self.color_combo.currentIndex()
                if 0 <= color_index < len(colors):
                    config["theme_color"] = colors[color_index]
            
            # 保存默认界面设置
            if self.default_page_combo:
                page_map = {0: "home", 1: "search"}
                config["default_page"] = page_map.get(self.default_page_combo.currentIndex(), "home")
            
            # 保存语言（已经在 on_language_changed 中保存了，这里也保存一次以防万一）
            lang_map = {0: "system", 1: "zh_CN", 2: "zh_TW", 3: "en_US"}
            config["language"] = lang_map.get(self.lang_combo.currentIndex(), "system")
            
            # 保存窗口特效
            if self.effect_combo:
                effect_map = {0: "none", 1: "mica"}
                config["window_effect"] = effect_map.get(self.effect_combo.currentIndex(), "none")

            # 保存平滑滚动设置
            if self.smooth_scroll_check:
                config["smooth_scroll"] = self.smooth_scroll_check.isChecked()

            # 保存自定义仓库配置
            if self.custom_repos_card:
                github_repos, zip_repos = self.custom_repos_card.get_repos()
                config["Custom_Repos"] = {
                    "github": github_repos,
                    "zip": zip_repos
                }

            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
        
        _replace_worker(getattr(self, 'worker', None))
        self.worker = AsyncWorker(_save())
        self.worker.result_ready.connect(self.on_save_success)
        self.worker.error.connect(self.on_save_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()
    
    @pyqtSlot(object)
    def on_save_success(self, result):
        """保存成功"""
        # 自动保存时不显示提示，保持界面简洁
        pass
    
    @pyqtSlot(str)
    def on_save_error(self, error):
        """保存失败"""
        InfoBar.error(
                title=tr("save_failed"),
                content=error,
            parent=self,
            position=InfoBarPosition.TOP
        )
    
    def reset_settings(self):
        """重置设置为默认值"""
        dialog = MessageBox(
            tr("reset_settings"),
            tr("reset_settings_message"),
            self.window()
        )
        
        if dialog.exec():
            async def _reset():
                config_path = APP_ROOT / 'config' / 'config.json'
                from backend.cai_backend import DEFAULT_CONFIG
                import json
                
                # 保留背景设置（如果有）
                existing_bg_settings = {}
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            current_config = json.load(f)
                        bg_keys = ["background_image_path", "background_blur", "background_saturation", "background_brightness"]
                        for key in bg_keys:
                            if key in current_config:
                                existing_bg_settings[key] = current_config[key]
                    except:
                        pass
                
                # 创建新配置
                new_config = DEFAULT_CONFIG.copy()
                new_config.update(existing_bg_settings)
                
                # 保存配置
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(new_config, f, indent=2, ensure_ascii=False)
                
                return True
            
            _replace_worker(getattr(self, 'worker', None))
            self.worker = AsyncWorker(_reset())
            self.worker.result_ready.connect(self.on_reset_success)
            self.worker.error.connect(self.on_reset_error)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.start()
    
    @pyqtSlot(object)
    def on_reset_success(self, result):
        """重置成功"""
        InfoBar.success(
            title=tr("reset_success"),
            content=tr("reset_success_message"),
            parent=self,
            position=InfoBarPosition.TOP
        )
        # 重新加载配置
        self._config_loaded = False
        self.load_config()
    
    @pyqtSlot(str)
    def on_reset_error(self, error):
        """重置失败"""
        InfoBar.error(
            title=tr("reset_failed"),
            content=error,
            parent=self,
            position=InfoBarPosition.TOP
        )




class MainWindow(MSFluentWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app_title") + f"  v{CURRENT_VERSION}")
        self.resize(1000, 700)

        # 设置窗口图标为Fluent内置的下载图标
        self.setWindowIcon(FluentIcon.CLOUD_DOWNLOAD.icon())

        # 设置标题栏（避免按钮重叠）
        self.titleBar.raise_()

        # 创建页面
        self.home_page = HomePage(self)
        self.search_page = SearchPage(self)
        self.launcher_page = LauncherPage(self)
        self.trainer_page = TrainerPage(self)
        self.drm_page = DrmPage(self)
        self.settings_page = SettingsPage(self)

        # 连接设置页面的自定义仓库变化信号到搜索页面的刷新方法
        self.settings_page.custom_repos_changed.connect(self.search_page.refresh_manifest_source_combo)

        # 添加导航项
        self.addSubInterface(
            self.home_page,
            FluentIcon.HOME,
            tr("home")
        )

        # 添加搜索入库
        self.addSubInterface(
            self.search_page,
            FluentIcon.SEARCH,
            tr("search")
        )

        # 添加联机游戏
        self.addSubInterface(
            self.launcher_page,
            FluentIcon.GAME,
            tr("launcher")
        )

        # 添加修改器
        self.addSubInterface(
            self.trainer_page,
            FluentIcon.LIBRARY,
            tr("trainer_nav")
        )

        # 添加D加密
        self.addSubInterface(
            self.drm_page,
            FluentIcon.CERTIFICATE,
            tr("drm_nav")
        )

        # 在导航栏底部添加设置
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            tr("settings"),
            position=NavigationItemPosition.BOTTOM
        )
        
        # 在导航栏底部添加重启 Steam 按钮
        self.navigationInterface.addItem(
            routeKey="restart_steam",
            icon=FluentIcon.POWER_BUTTON,
            text=tr("restart_steam"),
            onClick=self.on_restart_steam,
            selectable=False,
            position=NavigationItemPosition.BOTTOM
        )
        
        # 设置窗口效果
        # navigationInterface 在 MSFluentWindow 中已经配置好了
        # 不需要手动设置宽度

        # 设置透明背景
        self.setStyleSheet("""
            MSFluentWindow {
                background: transparent;
            }
        """)

        # 应用平滑滚动设置
        self.update_smooth_scroll_for_all_pages()

        # 根据配置切换到默认界面
        self.switch_to_default_page()

        # 启动后台预构建设置页 UI，避免首次点击卡顿
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, self._prebuild_settings)

        # 启动时检测内核（延迟1秒，避免影响界面加载速度）
        QTimer.singleShot(1000, self._check_kernel_on_startup)

        # 启动时自动检查更新（延迟3秒，避免影响界面加载速度）
        QTimer.singleShot(3000, self._check_update_on_startup)

    def _get_mirror_download_url(self, original_url: str, latest_version: str = "") -> str:
        """
        获取镜像化的下载链接，中国大陆用户自动跳转镜像
        优化：直接跳转到具体的下载链接而不是发布页面
        """
        # 检查当前是否在中国大陆
        try:
            import os
            is_cn = os.environ.get('IS_CN', '').lower() == 'yes'

            # 如果有版本号，直接生成下载链接
            if latest_version:
                # 生成具体的下载链接格式：https://github.com/zhouchentao666/Fluent-Install/releases/download/{version}/FluentInstall-v{version}.zip
                download_url = f"https://github.com/{GITHUB_REPO}/releases/download/{latest_version}/FluentInstall-v{latest_version}.zip"

                if is_cn:
                    # 中国大陆用户使用镜像
                    mirror_urls = [
                        f"https://gh-proxy.org/{download_url}",
                        f"https://cdn.gh-proxy.org/{download_url}",
                        f"https://edgeone.gh-proxy.org/{download_url}",
                        f"https://ghp.ci/{download_url}",
                    ]
                    # 返回第一个镜像URL
                    return mirror_urls[0]
                else:
                    # 非中国大陆用户使用原始链接
                    return download_url

            # 如果没有版本号，使用原来的逻辑
            if '/releases' in original_url and '/latest' not in original_url:
                original_url = original_url.replace('/releases', '/releases/latest')

            if is_cn:
                mirror_urls = [
                    f"https://gh-proxy.org/{original_url}",
                    f"https://cdn.gh-proxy.org/{original_url}",
                    f"https://edgeone.gh-proxy.org/{original_url}",
                    f"https://ghp.ci/{original_url}",
                ]
                return mirror_urls[0]
            else:
                return original_url

        except Exception:
            return original_url

    def switch_to_default_page(self):
        """切换到默认界面"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                default_page = config.get("default_page", "home")
            else:
                default_page = "home"

            # 切换到对应的界面
            if default_page == "search":
                self.switchTo(self.search_page)
            else:
                self.switchTo(self.home_page)

        except Exception:
            # 出错时默认显示主页
            self.switchTo(self.home_page)

    def _check_kernel_on_startup(self):
        """启动时检测内核"""
        async def _check():
            from backend.cai_backend import CaiBackend
            async with CaiBackend() as backend:
                # 检测内核
                unlocker_type = await backend.initialize()
                return unlocker_type

        self._kernel_check_worker = AsyncWorker(_check())

        def on_result(result):
            self._kernel_check_worker = None
            if not result:
                # 未检测到内核，显示对话框
                steam_path = self.settings_page.steam_path_edit.text() if hasattr(self.settings_page, 'steam_path_edit') else ""
                dialog = NoKernelDialog(steam_path, self)
                dialog.exec()

        def on_error(error):
            self._kernel_check_worker = None

        self._kernel_check_worker.result_ready.connect(on_result)
        self._kernel_check_worker.error.connect(on_error)
        self._kernel_check_worker.finished.connect(self._kernel_check_worker.deleteLater)
        self._kernel_check_worker.start()

    def _prebuild_settings(self):
        """应用启动后预构建设置页 UI 并预加载配置，消除首次点击卡顿"""
        if not self.settings_page._ui_built:
            self.settings_page._ui_built = True
            self.settings_page._build_ui()
        if not self.settings_page._config_loaded:
            self.settings_page._config_loaded = True
            self.settings_page.load_config()
            self.settings_page._setup_auto_save_listeners()

    def _check_update_on_startup(self):
        """启动时自动检查更新（静默模式，只有发现更新时才提示）"""
        async def _check():
            async with CaiBackend() as backend:
                has_update, info = await backend.check_for_updates()
                return has_update, info

        # 使用类属性保存 worker，避免被垃圾回收
        self._startup_update_worker = AsyncWorker(_check())

        def on_result(result):
            has_update, info = result
            if has_update:
                # 发现更新，显示提示
                msg = MessageBox(
                    tr("update_available"),
                    f"{tr('current_version')}: {info.get('current_version', '')}\n"
                    f"{tr('latest_version')}: {info.get('latest_version', '')}\n\n"
                    f"{info.get('release_body', '') or tr('no_release_notes')}",
                    self
                )
                msg.yesButton.setText(tr("go_to_download"))
                msg.cancelButton.setText(tr("cancel"))
                if msg.exec():
                    # 获取镜像化的下载链接
                    download_url = self._get_mirror_download_url(
                        info.get('release_url', f"https://github.com/{GITHUB_REPO}/releases"),
                        info.get('latest_version', '')
                    )
                    QDesktopServices.openUrl(QUrl(download_url))
            # 清理 worker 引用
            self._startup_update_worker = None

        def on_error(error):
            # 检查更新失败时静默处理，不打扰用户
            # 清理 worker 引用
            self._startup_update_worker = None

        self._startup_update_worker.result_ready.connect(on_result)
        self._startup_update_worker.error.connect(on_error)
        self._startup_update_worker.finished.connect(self._startup_update_worker.deleteLater)
        self._startup_update_worker.start()

    def on_restart_steam(self):
        """重启 Steam（带账号切换功能）"""
        # 创建自定义对话框
        from qfluentwidgets import MessageBoxBase, BodyLabel, ListWidget, CheckBox, RoundMenu, Action, LineEdit
        
        class RestartSteamDialog(MessageBoxBase):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.parent_window = parent
                self.titleLabel = TitleLabel(tr("restart_steam_confirm"), self)
                self.bodyLabel = BodyLabel(tr("restart_steam_select_account"), self)
                
                # 账号列表
                self.account_list = ListWidget(self)
                self.account_list.setFixedHeight(150)
                self.account_list.setFrameShape(self.account_list.Shape.NoFrame)
                self.account_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self.account_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                
                # 加载账号备注
                self.account_notes = {}
                self._load_notes()
                
                # 加载账号列表
                self.accounts = []
                self.account_map = {}  # 用于存储显示文本到账号的映射
                self._refresh_account_list()
                
                # 设置右键菜单
                self.account_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                self.account_list.customContextMenuRequested.connect(self._show_context_menu)
                
                # 离线模式选项
                self.offline_checkbox = CheckBox(tr("offline_mode"), self)
                
                self.viewLayout.addWidget(self.titleLabel)
                self.viewLayout.addWidget(self.bodyLabel)
                self.viewLayout.addWidget(self.account_list)
                self.viewLayout.addWidget(self.offline_checkbox)
                
                self.yesButton.setText(tr("confirm"))
                self.cancelButton.setText(tr("cancel"))
                self.widget.setMinimumWidth(380)
            
            def _load_notes(self):
                """加载账号备注"""
                try:
                    notes_path = APP_ROOT / 'config' / 'account_notes.json'
                    if notes_path.exists():
                        with open(notes_path, 'r', encoding='utf-8') as f:
                            self.account_notes = json.load(f)
                except Exception as e:
                    print(f"加载备注失败: {e}")
                    self.account_notes = {}
            
            def _save_notes(self):
                """保存账号备注"""
                try:
                    notes_path = APP_ROOT / 'config' / 'account_notes.json'
                    notes_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(notes_path, 'w', encoding='utf-8') as f:
                        json.dump(self.account_notes, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"保存备注失败: {e}")
            
            def _refresh_account_list(self):
                """刷新账号列表"""
                self.account_list.clear()
                self.account_map.clear()
                self.accounts = []
                
                try:
                    from backend.steam_account_manager import SteamAccountManager
                    manager = SteamAccountManager()
                    self.accounts = manager.get_steam_accounts()
                    
                    # 添加"不切换账号"选项
                    self.account_list.addItem(tr("restart_steam_no_switch"))
                    self.account_map[0] = ""
                    
                    for idx, acc in enumerate(self.accounts, start=1):
                        account = acc['account']
                        note = self.account_notes.get(account, "")
                        display_text = f"{acc['persona_name'] or account} ({account})"
                        if note:
                            display_text += f" [{note}]"
                        if acc.get('remember_password'):
                            display_text += " [自动登录]"
                        if acc.get('most_recent'):
                            display_text += " [当前]"
                        self.account_list.addItem(display_text)
                        self.account_map[idx] = account
                    
                    # 默认选中第一项（不切换）
                    self.account_list.setCurrentRow(0)
                except Exception as e:
                    print(f"加载账号列表失败: {e}")
                    self.account_list.addItem(tr("restart_steam_no_switch"))
                    self.account_map[0] = ""
            
            def _show_context_menu(self, pos):
                """显示右键菜单"""
                # 根据鼠标位置获取对应的项
                item = self.account_list.itemAt(pos)
                if not item:
                    return
                
                row = self.account_list.row(item)
                if row <= 0 or row not in self.account_map:
                    return
                
                account = self.account_map.get(row)
                if not account:
                    return
                
                # 选中当前项
                self.account_list.setCurrentRow(row)
                
                menu = RoundMenu("", self)
                
                # 编辑备注
                note_action = Action(FluentIcon.EDIT, tr("edit_note"))
                note_action.triggered.connect(lambda: self._edit_note(account))
                menu.addAction(note_action)
                
                # 删除账号
                delete_action = Action(FluentIcon.DELETE, tr("delete_account"))
                delete_action.triggered.connect(lambda: self._delete_account(account))
                menu.addAction(delete_action)
                
                menu.exec(self.account_list.mapToGlobal(pos))
            
            def _edit_note(self, account):
                """编辑备注"""
                class NoteDialog(MessageBoxBase):
                    def __init__(self, current_note, parent=None):
                        super().__init__(parent)
                        self.titleLabel = TitleLabel(tr("edit_note_title"), self)
                        self.bodyLabel = BodyLabel(tr("edit_note_message"), self)
                        
                        self.noteInput = LineEdit(self)
                        self.noteInput.setText(current_note)
                        self.noteInput.setPlaceholderText(tr("note_placeholder"))
                        self.noteInput.setMinimumWidth(300)
                        
                        self.viewLayout.addWidget(self.titleLabel)
                        self.viewLayout.addWidget(self.bodyLabel)
                        self.viewLayout.addWidget(self.noteInput)
                        
                        self.yesButton.setText(tr("save"))
                        self.cancelButton.setText(tr("cancel"))
                        self.widget.setMinimumWidth(350)
                    
                    def get_note(self):
                        return self.noteInput.text().strip()
                
                current_note = self.account_notes.get(account, "")
                dialog = NoteDialog(current_note, self)
                
                if dialog.exec():
                    new_note = dialog.get_note()
                    self.account_notes[account] = new_note
                    self._save_notes()
                    self._refresh_account_list()
                    if self.parent_window:
                        InfoBar.success(
                            title=tr("note_saved"),
                            content=tr("note_saved_message"),
                            parent=self.parent_window,
                            position=InfoBarPosition.TOP
                        )
            
            def _delete_account(self, account):
                """删除账号"""
                dialog = MessageBox(
                    tr("confirm_delete_account"),
                    tr("delete_account_message").format(account),
                    self
                )
                
                if dialog.exec():
                    def on_complete(success):
                        if success:
                            # 同时删除备注
                            if account in self.account_notes:
                                del self.account_notes[account]
                                self._save_notes()
                            # 刷新列表
                            self._refresh_account_list()
                            if self.parent_window:
                                InfoBar.success(
                                    title=tr("delete_account_success"),
                                    content=tr("delete_account_success_message"),
                                    parent=self.parent_window,
                                    position=InfoBarPosition.TOP
                                )
                        else:
                            if self.parent_window:
                                InfoBar.error(
                                    title=tr("delete_account_failed"),
                                    content=tr("delete_account_failed_message"),
                                    parent=self.parent_window,
                                    position=InfoBarPosition.TOP
                                )
                    
                    def on_error(error):
                        if self.parent_window:
                            InfoBar.error(
                                title=tr("delete_account_failed"),
                                content=str(error),
                                parent=self.parent_window,
                                position=InfoBarPosition.TOP
                            )
                    
                    self.delete_worker = SteamAccountDeleteWorker(account)
                    self.delete_worker.result_ready.connect(on_complete)
                    self.delete_worker.error.connect(on_error)
                    self.delete_worker.finished.connect(self.delete_worker.deleteLater)
                    self.delete_worker.start()
            
            def get_selected_account(self):
                current_row = self.account_list.currentRow()
                return self.account_map.get(current_row, "")
            
            def is_offline_mode(self):
                return self.offline_checkbox.isChecked()
        
        dialog = RestartSteamDialog(self)
        
        if dialog.exec():
            selected_account = dialog.get_selected_account()
            offline_mode = dialog.is_offline_mode()
            
            async def _restart():
                async with CaiBackend() as backend:
                    await backend.initialize()
                    if selected_account:
                        # 切换账号并重启
                        success = backend.switch_steam_account(selected_account, offline=offline_mode)
                    else:
                        # 仅重启
                        success = backend.restart_steam()
                    return success

            _replace_worker(getattr(self, 'restart_steam_worker', None))
            self.restart_steam_worker = AsyncWorker(_restart())
            self.restart_steam_worker.result_ready.connect(self.on_restart_complete)
            self.restart_steam_worker.error.connect(self.on_restart_error)
            self.restart_steam_worker.finished.connect(self.restart_steam_worker.deleteLater)
            self.restart_steam_worker.start()
            
            if selected_account:
                InfoBar.info(
                    title=tr("switching_account"),
                    content=f"{tr('switching_account_message')} -> {selected_account}",
                    parent=self,
                    position=InfoBarPosition.TOP
                )
            else:
                InfoBar.info(
                    title=tr("restarting"),
                    content=tr("restarting_message"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
    
    @pyqtSlot(object)
    def on_restart_complete(self, success):
        """重启完成"""
        if success:
            InfoBar.success(
             title=tr("restart_success"),
                content=tr("restart_success_message"),
                parent=self,
                position=InfoBarPosition.TOP
            )
        else:
            InfoBar.error(
                title=tr("restart_failed"),
                content=tr("restart_failed_message"),
                parent=self,
                position=InfoBarPosition.TOP
            )
    
    @pyqtSlot(str)
    def on_restart_error(self, error):
        """重启失败"""
        InfoBar.error(
            title=tr("restart_failed"),
            content=tr("restart_error_message", error),
            parent=self,
            position=InfoBarPosition.TOP
        )
    
    def apply_window_effect(self, effect_type):
        """应用窗口特效"""
        import platform
        import sys
        if platform.system() != 'Windows':
            return
        
        # 检查 Windows 版本，云母特效仅支持 Windows 11 (Build 22000+)
        try:
            win_ver = sys.getwindowsversion()
            is_win11 = win_ver.major >= 10 and win_ver.build >= 22000
        except:
            is_win11 = False
        
        if effect_type == "mica":
            # 启用云母特效（仅Windows 11）
            if is_win11:
                try:
                    self.setMicaEffectEnabled(True)
                except Exception as e:
                    print(f"启用云母特效失败: {e}")
            # 不设置全局透明背景，避免标题栏出现问题
        elif effect_type == "none":
            # 禁用特效
            try:
                self.setMicaEffectEnabled(False)
            except Exception as e:
                print(f"禁用窗口特效失败: {e}")
        
        # 保存设置
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            config["window_effect"] = effect_type
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存窗口特效设置失败: {e}")
    
    def notify_theme_changed(self):
        """通知所有页面主题已变化"""
        # 通知所有页面更新主题
        pages = [
            self.home_page,
            self.search_page,
            self.launcher_page,
            self.trainer_page,
            self.drm_page,
            self.settings_page
        ]

        for page in pages:
            if hasattr(page, 'notify_theme_changed'):
                page.notify_theme_changed()

        # 强制刷新所有页面布局
        for page in pages:
            if hasattr(page, 'update'):
                page.update()
            if hasattr(page, 'repaint'):
                page.repaint()

    def update_smooth_scroll_for_all_pages(self, smooth_scroll=None):
        """更新所有页面的平滑滚动设置
        
        Args:
            smooth_scroll: 是否开启平滑滚动，None 时从配置读取
        """
        # 如果未传入参数，从配置读取
        if smooth_scroll is None:
            smooth_scroll = True  # 默认开启
            try:
                config_path = APP_ROOT / 'config' / 'config.json'
                if config_path.exists():
                    import json
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    smooth_scroll = config.get("smooth_scroll", True)
            except Exception:
                pass

        # 更新所有页面的平滑滚动状态
        pages = [
            self.home_page,
            self.search_page,
            self.launcher_page,
            self.trainer_page,
            self.drm_page,
            self.settings_page
        ]

        for page in pages:
            # 直接使用 ScrollArea 的 setSmoothMode 方法
            try:
                print(f"[DEBUG] 设置页面 {page.objectName()} 平滑滚动: {smooth_scroll}")
                if smooth_scroll:
                    page.setSmoothMode(SmoothMode.COSINE, Qt.Orientation.Vertical)
                    page.setSmoothMode(SmoothMode.COSINE, Qt.Orientation.Horizontal)
                else:
                    page.setSmoothMode(SmoothMode.NO_SMOOTH, Qt.Orientation.Vertical)
                    page.setSmoothMode(SmoothMode.NO_SMOOTH, Qt.Orientation.Horizontal)
                print(f"[DEBUG] 页面 {page.objectName()} 平滑滚动设置完成")
            except Exception as e:
                print(f"[DEBUG] 设置页面 {page.objectName()} 平滑滚动失败: {e}")


class DownloadOSTWorker(QThread):
    """下载 OpenSteamTools 工作线程"""
    finished_sig = pyqtSignal(bool, str)

    def __init__(self, steam_path, parent=None):
        super().__init__(parent)
        self.steam_path = steam_path

    def run(self):
        try:
            import requests
            import zipfile
            import io
            r = requests.get("https://gitee.com/pvzcxw/cai-install-support/releases/download/v1/OpenSteamTool.zip", timeout=30)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                for file_info in z.infolist():
                    if file_info.filename.endswith('dwmapi.dll') or file_info.filename.endswith('OpenSteamTool.dll'):
                        file_info.filename = os.path.basename(file_info.filename)
                        z.extract(file_info, str(self.steam_path))
            self.finished_sig.emit(True, "")
        except Exception as e:
            self.finished_sig.emit(False, str(e))


class NoKernelDialog(MessageBoxBase):
    """未检测到内核对话框"""
    def __init__(self, steam_path, parent=None):
        super().__init__(parent)
        self.steam_path = steam_path
        self.titleLabel = TitleLabel(tr("no_kernel_title"), self)
        self.bodyLabel = BodyLabel(tr("no_kernel_msg"), self)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)
        self.viewLayout.addSpacing(10)

        # OpenSteamTools
        ost_layout = QHBoxLayout()
        ost_layout.addWidget(BodyLabel(tr("ost_desc"), self))
        ost_layout.addStretch(1)
        self.btn_ost_auto = PrimaryPushButton(tr("auto_download"), self)
        self.btn_ost_auto.clicked.connect(self.download_ost)
        btn_ost_manual = PushButton(tr("manual_download"), self)
        btn_ost_manual.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/OpenSteam001/OpenSteamTool/releases")))
        ost_layout.addWidget(self.btn_ost_auto)
        ost_layout.addWidget(btn_ost_manual)
        self.viewLayout.addLayout(ost_layout)

        # SteamTools
        st_layout = QHBoxLayout()
        st_layout.addWidget(BodyLabel(tr("st_desc"), self))
        st_layout.addStretch(1)
        self.btn_st_auto = PrimaryPushButton(tr("auto_download"), self)
        self.btn_st_auto.clicked.connect(self.download_st)
        btn_st_manual = PushButton(tr("manual_download"), self)
        btn_st_manual.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://steamtools.net/")))
        st_layout.addWidget(self.btn_st_auto)
        st_layout.addWidget(btn_st_manual)
        self.viewLayout.addLayout(st_layout)

        # GreenLuma
        gl_layout = QHBoxLayout()
        gl_layout.addWidget(BodyLabel(tr("gl_desc"), self))
        gl_layout.addStretch(1)
        btn_gl_manual = PushButton(tr("manual_download"), self)
        btn_gl_manual.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://cs.rin.ru/forum/viewtopic.php?f=29&t=103709")))
        gl_layout.addWidget(btn_gl_manual)
        self.viewLayout.addLayout(gl_layout)

        self.viewLayout.addSpacing(10)
        self.viewLayout.addWidget(BodyLabel(tr("force_kernel_select"), self))

        # 强制选择
        force_layout = QHBoxLayout()
        self.force_combo = ComboBox(self)
        self.force_combo.addItems(["OpenSteamTools", "SteamTools", "GreenLuma"])
        force_layout.addWidget(self.force_combo)
        btn_force = PushButton(tr("force_apply"), self)
        btn_force.clicked.connect(self.apply_force)
        force_layout.addWidget(btn_force)
        self.viewLayout.addLayout(force_layout)

        self.yesButton.hide()
        self.cancelButton.setText(tr("cancel"))
        self.widget.setMinimumWidth(550)

    def download_ost(self):
        self.btn_ost_auto.setEnabled(False)
        self.btn_ost_auto.setText(tr("loading"))
        self.worker = DownloadOSTWorker(self.steam_path, self)
        self.worker.finished_sig.connect(self.on_ost_finished)
        self.worker.start()

    def on_ost_finished(self, success, error):
        if success:
            InfoBar.success(
                title=tr("success"),
                content="OpenSteamTools " + tr("install_success"),
                parent=self.window(),
                position=InfoBarPosition.TOP
            )
            self.accept()
        else:
            InfoBar.error(
                title=tr("failed"),
                content=f"{tr('download_failed')}: {error}",
                parent=self.window(),
                position=InfoBarPosition.TOP
            )
            self.btn_ost_auto.setEnabled(True)
            self.btn_ost_auto.setText(tr("auto_download"))

    def download_st(self):
        try:
            import subprocess
            subprocess.Popen(["powershell", "-NoProfile", "-Command", "irm steam.run | iex"])
            InfoBar.success(
                title=tr("success"),
                content="SteamTools " + tr("install_success"),
                parent=self.window(),
                position=InfoBarPosition.TOP
            )
            self.accept()
        except Exception as e:
            InfoBar.error(
                title=tr("failed"),
                content=f"{tr('launch_failed')}: {e}",
                parent=self.window(),
                position=InfoBarPosition.TOP
            )

    def apply_force(self):
        sel = self.force_combo.currentText()
        type_map = {"OpenSteamTools": "opensteamtools", "SteamTools": "steamtools", "GreenLuma": "greenluma"}
        val = type_map.get(sel, "auto")

        config_path = APP_ROOT / 'config' / 'config.json'
        try:
            import json
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            config["force_unlocker_type"] = val
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            InfoBar.success(
                title=tr("success"),
                content=f"{tr('force_apply')} {sel}",
                parent=self.window(),
                position=InfoBarPosition.TOP
            )
            self.accept()
        except Exception as e:
            InfoBar.error(
                title=tr("failed"),
                content=f"{tr('save_failed')}: {e}",
                parent=self.window(),
                position=InfoBarPosition.TOP
            )


class GameInfoLoader(QThread):
    """游戏信息加载线程"""
    data_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, appid, parent=None):
        super().__init__(parent)
        self.appid = appid

    def run(self):
        import asyncio
        import httpx
        from backend.cai_backend import get_steam_lang

        async def fetch():
            steam_lang = get_steam_lang(current_language)
            cc = "TW" if current_language == "zh_TW" else ("US" if current_language == "en_US" else "CN")
            url = f"https://store.steampowered.com/api/appdetails?appids={self.appid}&l={steam_lang}&cc={cc}"
            client = httpx.AsyncClient()
            try:
                response = await client.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if data.get(self.appid, {}).get("success"):
                        return data[self.appid]["data"]
                return None
            finally:
                await client.aclose()

        try:
            result = asyncio.run(fetch())
            if result:
                self.data_ready.emit(result)
            else:
                self.error_occurred.emit("Failed to fetch game info")
        except Exception as e:
            self.error_occurred.emit(str(e))


class SteamAccountDeleteWorker(QThread):
    """Steam账号删除工作线程"""
    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, account, parent=None):
        super().__init__(parent)
        self.account = account

    def run(self):
        import asyncio
        from backend.cai_backend import CaiBackend

        async def _delete():
            backend = CaiBackend()
            try:
                await backend.initialize()
                success = backend.delete_steam_account(self.account)
                return success
            finally:
                await backend.close()

        try:
            result = asyncio.run(_delete())
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class GameDetailDialog(QDialog):
    """游戏详情对话框 - 游戏盒子形式"""
    
    def __init__(self, appid: str, game_name: str, parent=None, source_type: str = None, mode: str = None):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name
        self.source_type = source_type  # 'st' 或 'gl'，None 表示从搜索打开
        self.mode = mode  # 'auto' 或 'fixed'
        self.game_data = None
        self.screenshots = []
        self.current_screenshot = 0
        self._screenshot_cache = {}  # 截图缓存: index -> pixmap
        self._max_cache_size = 6  # 最多缓存6张截图（当前3张+预加载3张）

        self.setWindowTitle(game_name if game_name else f"AppID: {appid}")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)

        self.setup_ui()
        self.load_game_info()
    
    def setup_ui(self):
        """设置UI布局"""
        # 根据主题设置样式
        if isDarkTheme():
            bg_color = "#1e1e1e"
            text_color = "#ffffff"
            top_bg = "#252525"
            cover_bg = "#1a1a1a"
            scroll_bg = "#2a2a2a"
            scroll_handle = "#5a5a5a"
            scroll_handle_hover = "#6a6a6a"
        else:
            bg_color = "#f5f5f5"
            text_color = "#333333"
            top_bg = "#ffffff"
            cover_bg = "#e0e0e0"
            scroll_bg = "#e0e0e0"
            scroll_handle = "#c0c0c0"
            scroll_handle_hover = "#a0a0a0"
        
        self.setStyleSheet(f"""
            GameDetailDialog {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
            }}
        """)
        
        self._text_color = text_color
        self._top_bg = top_bg
        self._cover_bg = cover_bg
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            ScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {scroll_bg};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scroll_handle_hover};
            }}
        """)
        
        # 内容容器
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # ===== 顶部区域：封面和基本信息 =====
        top_widget = QWidget()
        top_widget.setStyleSheet(f"background: {self._top_bg}; border-radius: 12px;")
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(20, 20, 20, 20)
        top_layout.setSpacing(20)
        
        # 左侧封面
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(460, 215)
        self.cover_label.setScaledContents(True)
        self.cover_label.setStyleSheet(f"""
            QLabel {{
                border-radius: 8px;
                background: {self._cover_bg};
            }}
        """)
        # 加载封面
        self.load_cover()
        top_layout.addWidget(self.cover_label)
        
        # 右侧信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(12)
        
        # 根据主题设置标签颜色
        secondary_color = "#a0a0a0" if isDarkTheme() else "#666666"
        
        # 游戏标题
        self.title_label = TitleLabel(self.game_name if self.game_name else f"AppID: {self.appid}")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"color: {self._text_color}; font-size: 24px; font-weight: bold;")
        info_layout.addWidget(self.title_label)
        
        # 开发商和发行商
        self.dev_label = BodyLabel(f"{tr('detail_developer')}: {tr('detail_loading')}")
        self.dev_label.setStyleSheet(f"color: {secondary_color}; font-size: 13px;")
        info_layout.addWidget(self.dev_label)
        
        self.pub_label = BodyLabel(f"{tr('detail_publisher')}: {tr('detail_loading')}")
        self.pub_label.setStyleSheet(f"color: {secondary_color}; font-size: 13px;")
        info_layout.addWidget(self.pub_label)
        
        # 发布日期
        self.date_label = BodyLabel(f"{tr('detail_release_date')}: {tr('detail_loading')}")
        self.date_label.setStyleSheet(f"color: {secondary_color}; font-size: 13px;")
        info_layout.addWidget(self.date_label)
        
        # 价格
        self.price_label = BodyLabel("")
        self.price_label.setStyleSheet("color: #a4d007; font-size: 18px; font-weight: bold;")
        info_layout.addWidget(self.price_label)
        
        # 平台支持
        self.platform_label = BodyLabel("")
        self.platform_label.setStyleSheet(f"color: {secondary_color}; font-size: 13px;")
        info_layout.addWidget(self.platform_label)
        
        info_layout.addStretch()
        
        # 按钮行：根据来源显示不同按钮
        btn_layout = QHBoxLayout()

        if self.source_type == "st":
            # SteamTools 模式：显示切换版本和删除按钮
            # 切换版本按钮
            toggle_text = tr("detail_switch_auto") if self.mode == "fixed" else tr("detail_switch_fixed")
            self.toggle_btn = PrimaryPushButton(toggle_text)
            self.toggle_btn.setIcon(FluentIcon.UPDATE)
            self.toggle_btn.clicked.connect(self.toggle_version_mode)
            btn_layout.addWidget(self.toggle_btn)
            
            btn_layout.addSpacing(10)
            
            # 删除按钮（仅图标）
            self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
            self.delete_btn.setFixedSize(32, 32)
            self.delete_btn.setToolTip(tr("detail_delete"))
            self.delete_btn.installEventFilter(ToolTipFilter(self.delete_btn, showDelay=150, position=ToolTipPosition.TOP))
            self.delete_btn.clicked.connect(self.delete_game)
            btn_layout.addWidget(self.delete_btn)
            
        elif self.source_type == "gl":
            # GreenLuma 模式：只显示删除按钮（仅图标）
            self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
            self.delete_btn.setFixedSize(32, 32)
            self.delete_btn.setToolTip(tr("detail_delete"))
            self.delete_btn.installEventFilter(ToolTipFilter(self.delete_btn, showDelay=150, position=ToolTipPosition.TOP))
            self.delete_btn.clicked.connect(self.delete_game)
            btn_layout.addWidget(self.delete_btn)
            
        else:
            # 搜索模式：显示入库按钮
            self.add_btn = PrimaryPushButton(tr("detail_add_to_library"))
            self.add_btn.setIcon(FluentIcon.CLOUD_DOWNLOAD)
            self.add_btn.clicked.connect(self.add_to_library)
            btn_layout.addWidget(self.add_btn)
        
        btn_layout.addSpacing(10)
        
        # Steam商店链接按钮
        self.steam_btn = PushButton(tr("detail_view_store"))
        self.steam_btn.setIcon(FluentIcon.LINK)
        self.steam_btn.clicked.connect(self.open_steam_store)
        btn_layout.addWidget(self.steam_btn)
        
        btn_layout.addStretch()
        info_layout.addLayout(btn_layout)
        
        top_layout.addLayout(info_layout, 1)
        content_layout.addWidget(top_widget)
        
        # 根据主题设置卡片背景色
        card_bg = self._top_bg
        inner_bg = self._cover_bg
        
        # ===== 截图轮播区域 =====
        screenshot_widget = QWidget()
        screenshot_widget.setStyleSheet(f"background: {card_bg}; border-radius: 12px;")
        screenshot_layout = QVBoxLayout(screenshot_widget)
        screenshot_layout.setContentsMargins(20, 20, 20, 20)
        
        screenshot_title = SubtitleLabel(tr("detail_screenshots"))
        screenshot_title.setStyleSheet(f"color: {self._text_color}; font-size: 18px;")
        screenshot_layout.addWidget(screenshot_title)
        
        # 截图显示区
        self.screenshot_label = QLabel()
        self.screenshot_label.setFixedSize(860, 484)
        self.screenshot_label.setScaledContents(True)
        self.screenshot_label.setStyleSheet(f"""
            QLabel {{
                border-radius: 8px;
                background: {inner_bg};
            }}
        """)
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        screenshot_layout.addWidget(self.screenshot_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 截图导航按钮
        nav_layout = QHBoxLayout()
        nav_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.prev_btn = PushButton(tr("detail_prev"))
        self.prev_btn.setIcon(FluentIcon.LEFT_ARROW)
        self.prev_btn.clicked.connect(self.show_prev_screenshot)
        self.prev_btn.setEnabled(False)
        
        self.screenshot_counter = CaptionLabel("0 / 0")
        self.screenshot_counter.setStyleSheet(f"color: {secondary_color};")
        
        self.next_btn = PushButton(tr("detail_next"))
        self.next_btn.setIcon(FluentIcon.RIGHT_ARROW)
        self.next_btn.clicked.connect(self.show_next_screenshot)
        self.next_btn.setEnabled(False)
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addSpacing(20)
        nav_layout.addWidget(self.screenshot_counter)
        nav_layout.addSpacing(20)
        nav_layout.addWidget(self.next_btn)
        
        screenshot_layout.addLayout(nav_layout)
        content_layout.addWidget(screenshot_widget)
        
        # 根据主题设置文本编辑框样式
        if isDarkTheme():
            text_bg = "#1a1a1a"
            text_color_edit = "#d0d0d0"
        else:
            text_bg = "#f0f0f0"
            text_color_edit = "#333333"
        
        # ===== 游戏描述区域 =====
        desc_widget = QWidget()
        desc_widget.setStyleSheet(f"background: {card_bg}; border-radius: 12px;")
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.setContentsMargins(20, 20, 20, 20)
        
        desc_title = SubtitleLabel(tr("detail_about"))
        desc_title.setStyleSheet(f"color: {self._text_color}; font-size: 18px;")
        desc_layout.addWidget(desc_title)
        
        self.desc_text = TextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMinimumHeight(200)
        self.desc_text.setStyleSheet(f"""
            TextEdit {{
                background: {text_bg};
                border: none;
                border-radius: 8px;
                color: {text_color_edit};
                padding: 10px;
                font-size: 14px;
                line-height: 1.6;
            }}
        """)
        self.desc_text.setText(tr("detail_loading"))
        desc_layout.addWidget(self.desc_text)
        
        content_layout.addWidget(desc_widget)
        
        # ===== 系统需求区域 =====
        req_widget = QWidget()
        req_widget.setStyleSheet(f"background: {card_bg}; border-radius: 12px;")
        req_layout = QVBoxLayout(req_widget)
        req_layout.setContentsMargins(20, 20, 20, 20)
        
        req_title = SubtitleLabel(tr("detail_system_requirements"))
        req_title.setStyleSheet(f"color: {self._text_color}; font-size: 18px;")
        req_layout.addWidget(req_title)
        
        self.req_text = TextEdit()
        self.req_text.setReadOnly(True)
        self.req_text.setMinimumHeight(150)
        self.req_text.setStyleSheet(f"""
            TextEdit {{
                background: {text_bg};
                border: none;
                border-radius: 8px;
                color: {text_color_edit};
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        self.req_text.setText(tr("detail_loading"))
        req_layout.addWidget(self.req_text)
        
        content_layout.addWidget(req_widget)
        
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 10, 20, 20)
        
        close_btn = PrimaryPushButton(tr("detail_close"))
        close_btn.setIcon(FluentIcon.CLOSE)
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        main_layout.addLayout(btn_layout)
    
    def load_cover(self):
        """加载游戏封面"""
        # 先尝试从缓存加载
        cached_data = _get_cached_cover(self.appid)
        if cached_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(cached_data):
                self.cover_label.setPixmap(pixmap)
                return
        
        # 从网络加载
        cover_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        
        def on_cover_loaded(reply):
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    self.cover_label.setPixmap(pixmap)
                    _cache_cover(self.appid, bytes(data))
            reply.deleteLater()
        
        # 创建临时网络管理器
        from PyQt6.QtNetwork import QNetworkAccessManager
        nm = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(cover_url))
        reply = nm.get(request)
        reply.finished.connect(lambda: on_cover_loaded(reply))
    
    def load_game_info(self):
        """加载游戏详细信息"""
        def on_data_ready(data):
            if data:
                self.game_data = data
                self.update_ui_with_data()

        def on_error(error):
            self.desc_text.setText(f"Load failed: {error}")
            self.req_text.setText(tr("detail_no_requirements"))

        # 使用独立的 GameInfoLoader 类
        self.loader = GameInfoLoader(self.appid, self)
        self.loader.data_ready.connect(on_data_ready)
        self.loader.error_occurred.connect(on_error)
        self.loader.start()
    
    def update_ui_with_data(self):
        """使用获取的数据更新UI"""
        data = self.game_data
        
        # 更新标题
        name = data.get("name", self.game_name)
        if name:
            self.setWindowTitle(name)
            self.title_label.setText(name)
        
        # 开发商和发行商
        developers = data.get("developers", [])
        publishers = data.get("publishers", [])
        self.dev_label.setText(f"{tr('detail_developer')}: {', '.join(developers) if developers else tr('detail_unknown')}")
        self.pub_label.setText(f"{tr('detail_publisher')}: {', '.join(publishers) if publishers else tr('detail_unknown')}")
        
        # 发布日期
        release_date = data.get("release_date", {})
        date_str = release_date.get("date", tr("detail_unknown"))
        coming_soon = release_date.get("coming_soon", False)
        if coming_soon:
            date_str += f" ({tr('detail_coming_soon')})"
        self.date_label.setText(f"{tr('detail_release_date')}: {date_str}")
        
        # 价格
        price_data = data.get("price_overview", {})
        if price_data:
            final_price = price_data.get("final_formatted", "")
            discount = price_data.get("discount_percent", 0)
            if discount > 0:
                self.price_label.setText(f"¥{final_price}  (-{discount}%)")
            else:
                self.price_label.setText(f"¥{final_price}" if final_price else tr("detail_free"))
        elif data.get("is_free", False):
            self.price_label.setText(tr("detail_free"))
        else:
            self.price_label.setText(tr("detail_price_unavailable"))
        
        # 平台支持
        platforms = data.get("platforms", {})
        platform_texts = []
        if platforms.get("windows"):
            platform_texts.append("Windows")
        if platforms.get("mac"):
            platform_texts.append("Mac")
        if platforms.get("linux"):
            platform_texts.append("Linux")
        self.platform_label.setText(f"{tr('detail_platform')}: {', '.join(platform_texts) if platform_texts else tr('detail_unknown')}")
        
        # 描述
        description = data.get("detailed_description", data.get("short_description", tr("detail_no_description")))
        # 移除 HTML 标签
        import re
        description = re.sub(r'<[^>]+>', '', description)
        description = description.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        self.desc_text.setText(description)
        
        # 系统需求
        pc_requirements = data.get("pc_requirements", {})
        if pc_requirements:
            min_req = pc_requirements.get("minimum", "")
            rec_req = pc_requirements.get("recommended", "")
            req_text = ""
            if min_req:
                min_req = re.sub(r'<[^>]+>', '', min_req)
                min_req = min_req.replace('&quot;', '"').replace('&amp;', '&')
                req_text += f"【{tr('detail_min_requirements')}】\n{min_req}\n\n"
            if rec_req:
                rec_req = re.sub(r'<[^>]+>', '', rec_req)
                rec_req = rec_req.replace('&quot;', '"').replace('&amp;', '&')
                req_text += f"【{tr('detail_rec_requirements')}】\n{rec_req}"
            self.req_text.setText(req_text if req_text else tr("detail_no_requirements"))
        else:
            self.req_text.setText(tr("detail_no_requirements"))
        
        # 截图
        screenshots = data.get("screenshots", [])
        if screenshots:
            self.screenshots = screenshots[:10]  # 最多10张
            self.current_screenshot = 0
            self._screenshot_cache = {}  # 清空缓存
            # 加载前3张截图
            self.load_screenshot_batch(0, 3)
            self.update_screenshot_counter()
            self.prev_btn.setEnabled(len(self.screenshots) > 1)
            self.next_btn.setEnabled(len(self.screenshots) > 1)
        else:
            self.screenshot_label.setText(tr("detail_no_screenshots"))
            self.screenshot_counter.setText("0 / 0")

    def load_screenshot_batch(self, start_index: int, count: int, direction: str = "forward"):
        """批量加载截图
        
        Args:
            start_index: 起始索引
            count: 加载数量
            direction: 'forward' 向后加载, 'backward' 向前加载, 'both' 双向加载
        """
        if not self.screenshots:
            return

        # 先显示当前索引的图片（如果已缓存）
        if start_index in self._screenshot_cache:
            self.screenshot_label.setPixmap(self._screenshot_cache[start_index])

        indices_to_load = set()
        n = len(self.screenshots)

        if direction == "forward":
            # 向后加载：当前及后面count-1张
            for i in range(count):
                idx = (start_index + i) % n
                indices_to_load.add(idx)
        elif direction == "backward":
            # 向前加载：当前及前面count-1张
            for i in range(count):
                idx = (start_index - i) % n
                indices_to_load.add(idx)
        else:  # both
            # 双向加载：前后各一半
            half = count // 2
            for i in range(half + 1):  # 当前及后面
                idx = (start_index + i) % n
                indices_to_load.add(idx)
            for i in range(1, half + 1):  # 前面
                idx = (start_index - i) % n
                indices_to_load.add(idx)

        # 加载所有需要加载的截图
        for idx in indices_to_load:
            if idx not in self._screenshot_cache:
                self._load_single_screenshot(idx)

    def _load_single_screenshot(self, index: int):
        """加载单张截图到缓存"""
        if not self.screenshots or index < 0 or index >= len(self.screenshots):
            return

        screenshot = self.screenshots[index]
        image_url = screenshot.get("path_full", screenshot.get("path_thumbnail", ""))

        if not image_url:
            return

        def on_image_loaded(reply, idx=index):
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    self._screenshot_cache[idx] = pixmap
                    # 如果是当前显示的截图，更新显示
                    if idx == self.current_screenshot:
                        self.screenshot_label.setPixmap(pixmap)
                    # 清理旧缓存
                    self._cleanup_screenshot_cache()
            reply.deleteLater()

        from PyQt6.QtNetwork import QNetworkAccessManager
        nm = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(image_url))
        reply = nm.get(request)
        reply.finished.connect(lambda: on_image_loaded(reply))

    def _cleanup_screenshot_cache(self):
        """清理截图缓存，只保留最近的6张"""
        if len(self._screenshot_cache) > self._max_cache_size:
            # 计算需要保留的索引范围（当前前后各3张）
            keep_indices = set()
            for offset in range(-2, 4):  # -2, -1, 0, 1, 2, 3
                idx = (self.current_screenshot + offset) % len(self.screenshots)
                keep_indices.add(idx)

            # 删除不在保留范围内的缓存
            keys_to_remove = [k for k in self._screenshot_cache.keys() if k not in keep_indices]
            for k in keys_to_remove:
                del self._screenshot_cache[k]
    
    def update_screenshot_counter(self):
        """更新截图计数器"""
        if self.screenshots:
            self.screenshot_counter.setText(f"{self.current_screenshot + 1} / {len(self.screenshots)}")
        else:
            self.screenshot_counter.setText("0 / 0")
    
    def show_prev_screenshot(self):
        """显示上一张截图"""
        if self.screenshots:
            n = len(self.screenshots)
            self.current_screenshot = (self.current_screenshot - 1) % n
            # 显示缓存中的图片（如果已加载）
            if self.current_screenshot in self._screenshot_cache:
                self.screenshot_label.setPixmap(self._screenshot_cache[self.current_screenshot])
            else:
                # 如果未缓存，加载当前及前面2张
                self.load_screenshot_batch(self.current_screenshot, 3, direction="backward")
            # 预加载再往前一张（例如翻到第2张时预加载第4张）
            preload_idx = (self.current_screenshot - 2) % n
            if preload_idx not in self._screenshot_cache:
                self._load_single_screenshot(preload_idx)
            self.update_screenshot_counter()

    def show_next_screenshot(self):
        """显示下一张截图"""
        if self.screenshots:
            n = len(self.screenshots)
            self.current_screenshot = (self.current_screenshot + 1) % n
            # 显示缓存中的图片（如果已加载）
            if self.current_screenshot in self._screenshot_cache:
                self.screenshot_label.setPixmap(self._screenshot_cache[self.current_screenshot])
            else:
                # 如果未缓存，加载当前及后面2张
                self.load_screenshot_batch(self.current_screenshot, 3, direction="forward")
            # 预加载再往后一张（例如翻到第3张时预加载第5张）
            preload_idx = (self.current_screenshot + 2) % n
            if preload_idx not in self._screenshot_cache:
                self._load_single_screenshot(preload_idx)
            self.update_screenshot_counter()
    
    def open_steam_store(self):
        """打开 Steam 商店页面"""
        url = f"https://store.steampowered.com/app/{self.appid}/"
        QDesktopServices.openUrl(QUrl(url))

    def add_to_library(self):
        """将游戏入库"""
        # 通过父窗口链查找主窗口
        from qfluentwidgets import MSFluentWindow
        main_window = None
        parent = self.parent()
        while parent:
            if isinstance(parent, MSFluentWindow):
                main_window = parent
                break
            parent = parent.parent()
        
        if main_window and hasattr(main_window, 'search_page'):
            search_page = main_window.search_page
            if hasattr(search_page, 'unlock_game_direct'):
                # 调用入库方法
                search_page.unlock_game_direct(self.appid, self.game_name)
                InfoBar.success(
                    title=tr("detail_add_started"),
                    content=tr("detail_add_progress").format(self.game_name or self.appid),
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000
                )
                self.accept()  # 关闭对话框
                return
        
        # 如果没找到合适的页面，显示错误
        InfoBar.error(
            title=tr("detail_add_failed"),
            content=tr("detail_add_failed_msg"),
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000
        )

    def toggle_version_mode(self):
        """切换版本模式（自动更新/固定版本）"""
        # 通过父窗口链查找主窗口
        from qfluentwidgets import MSFluentWindow
        main_window = None
        parent = self.parent()
        while parent:
            if isinstance(parent, MSFluentWindow):
                main_window = parent
                break
            parent = parent.parent()
        
        if main_window and hasattr(main_window, 'home_page'):
            home_page = main_window.home_page
            if hasattr(home_page, 'toggle_st_version'):
                # 先关闭对话框，然后调用切换版本方法，让提示显示在主窗口上
                filename = f"{self.appid}.lua"
                self.accept()
                home_page.toggle_st_version(filename, self.appid, None)
                return
        
        InfoBar.error(
            title=tr("detail_switch_failed"),
            content=tr("detail_switch_failed_msg"),
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000
        )

    def delete_game(self):
        """删除游戏"""
        # 通过父窗口链查找主窗口
        from qfluentwidgets import MSFluentWindow
        main_window = None
        parent = self.parent()
        while parent:
            if isinstance(parent, MSFluentWindow):
                main_window = parent
                break
            parent = parent.parent()
        
        if main_window and hasattr(main_window, 'home_page'):
            home_page = main_window.home_page
            if hasattr(home_page, 'delete_game_with_confirm'):
                # 先关闭详情对话框，然后在主窗口显示确认删除对话框
                self.accept()
                home_page.delete_game_with_confirm(self.appid, self.source_type, self.game_name)
                return
        
        InfoBar.error(
            title=tr("detail_delete_failed"),
            content=tr("detail_delete_failed_msg"),
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000
        )


def main():
    """主函数"""
    # 加载语言设置
    lang = load_language_config()
    
    # 如果是系统默认，检测系统语言
    if lang == "system":
        system_locale = QLocale.system()
        if system_locale.language() == QLocale.Language.Chinese:
            if system_locale.country() in (QLocale.Country.Taiwan, QLocale.Country.HongKong):
                lang = "zh_TW"
            else:
                lang = "zh_CN"
        elif system_locale.language() == QLocale.Language.French:
            lang = "fr_FR"
        elif system_locale.language() == QLocale.Language.Russian:
            lang = "ru_RU"
        elif system_locale.language() == QLocale.Language.German:
            lang = "de_DE"
        elif system_locale.language() == QLocale.Language.Japanese:
            lang = "ja_JP"
        else:
            lang = "en_US"
    
    set_language(lang)
    
    # 加载主题设置
    theme_config = load_theme_config()
    
    app = QApplication(sys.argv)
    
    # fluent 使用 setPixelSize 设置字体，导致 pointSize() 返回 -1
    # Qt 内部在字体继承时读取 pointSize 并尝试 setPointSize(-1) 触发警告
    # 用消息过滤器屏蔽这条无害警告
    import ctypes
    def qt_message_handler(mode, context, message):
        if "Point size <= 0" in message or "setPointSize" in message:
            return
        # 其他消息正常输出
        if mode == QtMsgType.QtWarningMsg:
            print(f"[Qt Warning] {message}")
        elif mode == QtMsgType.QtCriticalMsg:
            print(f"[Qt Critical] {message}")
        elif mode == QtMsgType.QtFatalMsg:
            print(f"[Qt Fatal] {message}")

    from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
    qInstallMessageHandler(qt_message_handler)

    from PyQt6.QtWidgets import QToolTip
    from PyQt6.QtGui import QFont
    tooltip_font = QFont()
    tooltip_font.setPointSize(9)
    QToolTip.setFont(tooltip_font)
    
    # 设置语言环境
    if lang in LANGUAGES:
        locale = LANGUAGES[lang]["locale"]
        QLocale.setDefault(locale)
        
        # 尝试加载 Qt 翻译
        translator = QTranslator()
        if lang == "zh_CN":
            # 加载 Qt 自带的中文翻译
            if translator.load("qtbase_zh_CN", ":/translations"):
                app.installTranslator(translator)
    
    # 应用主题设置
    theme_mode = theme_config["theme_mode"]
    if theme_mode == "light":
        setTheme(Theme.LIGHT)
    elif theme_mode == "dark":
        setTheme(Theme.DARK)
    else:
        setTheme(Theme.AUTO)
    
    # 应用主题色
    setThemeColor(theme_config["theme_color"])
    
    # 创建主窗口
    window = MainWindow()
    
    # 加载并应用窗口特效
    try:
        config_path = APP_ROOT / 'config' / 'config.json'
        if config_path.exists():
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                window_effect = config.get("window_effect", "none")
                window.apply_window_effect(window_effect)
    except Exception as e:
        print(f"加载窗口特效失败: {e}")
    
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

