"""
Cai Install - Fluent Design 版本
使用 PyQt-Fluent-Widgets 框架
"""
import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QUrl, QLocale, QTranslator, QObject, QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QIntValidator
from PyQt6.QtGui import QIcon, QPixmap, QFont, QDesktopServices
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
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
    Slider
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
    "fr_FR": {
        "name": "Français",
        "locale": QLocale(QLocale.Language.French, QLocale.Country.France)
    },
    "ru_RU": {
        "name": "Русский",
        "locale": QLocale(QLocale.Language.Russian, QLocale.Country.Russia)
    },
    "de_DE": {
        "name": "Deutsch",
        "locale": QLocale(QLocale.Language.German, QLocale.Country.Germany)
    },
    "ja_JP": {
        "name": "日本語",
        "locale": QLocale(QLocale.Language.Japanese, QLocale.Country.Japan)
    },
    "zh_TW": {
        "name": "繁體中文",
        "locale": QLocale(QLocale.Language.Chinese, QLocale.Country.Taiwan)
    },
    "ko_KR": {
        "name": "한국어",
        "locale": QLocale(QLocale.Language.Korean, QLocale.Country.SouthKorea)
    },
    "es_ES": {
        "name": "Español",
        "locale": QLocale(QLocale.Language.Spanish, QLocale.Country.Spain)
    }
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
        "sac-other": "sac分流",
        "walftech": "Walftech",
        "MHub": "MHub",
        "steamautocracks_v2": "SteamAutoCracks V2 (仅密钥)",
        "sudama": "Sudama库 (仅密钥)",
        "buqiuren": "清单不求人库 (仅清单)",
        "github_auiowu": "GitHub (Auiowu)",
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
        "dlc_timeout": "DLC 联网超时时间",
        "dlc_timeout_hint": "获取DLC列表超时时间，网络较差时可适当调大（秒）",
        "show_progress_bar": "显示进度条",
        "show_progress_bar_hint": "在搜索和入库过程中显示进度条，提供更好的用户体验",
        "name_not_found": "名称未找到",
        "fetch_failed": "获取失败",
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
        "steamautocracks_v2": "SteamAutoCracks V2 (Keys Only)",
        "sudama": "Sudama Library (Keys Only)",
        "buqiuren": "Manifest Helper Library (Manifest Only)",
        "github_auiowu": "GitHub (Auiowu)",
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
        "dlc_timeout": "DLC Network Timeout",
        "dlc_timeout_hint": "Timeout for fetching DLC list, increase if network is slow (seconds)",
        "show_progress_bar": "Show Progress Bar",
        "show_progress_bar_hint": "Show progress bar during search and installation for better user experience",
        "name_not_found": "Name Not Found",
        "fetch_failed": "Fetch Failed",
    },
    "fr_FR": {
        "app_title": "FluentInstall",
        "home": "Accueil",
        "search": "Rechercher",
        "settings": "Paramètres",
        "default_page": "Page par défaut",
        "default_page_hint": "Sélectionnez la page par défaut à afficher au démarrage",
        "default_page_home": "Accueil",
        "default_page_search": "Recherche",
        "restart_steam": "Redémarrer Steam",
        "installed_games": "Jeux installés",
        "search_placeholder": "Rechercher un nom de jeu ou AppID",
        "loading": "Chargement...",
        "no_games": "Aucun jeu",
        "delete": "Supprimer",
        "confirm_delete": "Confirmer la suppression",
        "delete_message": "Êtes-vous sûr de vouloir supprimer l'AppID {0}?\n\nCette action ne peut pas être annulée.",
        "deleting": "Suppression en cours",
        "delete_success": "Suppression réussie",
        "delete_failed": "Échec de la suppression",
        "search_and_add": "Rechercher et ajouter des jeux",
        "game_name_or_appid": "Entrez le nom du jeu ou AppID / lien Steam",
        "search_button": "Rechercher",
        "add_options": "Options d'ajout",
        "add_all_dlc": "Ajouter tous les DLC",
        "patch_depot_key": "Patch clé de dépôt",
        "patch_manifest": "Patch Manifest",
        "manifest_source": "Source du manifeste:",
        "add_game": "Ajouter un jeu",
        "steam_path": "Chemin Steam",
        "steam_path_hint": "Sélectionnez le chemin d'installation Steam, laissez vide pour détection automatique",
        "github_token": "Jeton personnel GitHub",
        "github_token_hint": "Optionnel, pour augmenter les limites de requêtes API",
        "basic_settings": "Paramètres de base",
        "appearance": "Apparence",
        "theme_mode": "Mode du thème",
        "theme_color": "Couleur du thème",
        "language": "Langue",
        "save_settings": "Enregistrer les paramètres",
        "about": "À propos",
        "thanks": "Crédits",
        "restart_required": "Redémarrage requis",
        "language_changed": "Langue changée en {0}\n\nRedémarrer l'application maintenant pour appliquer les changements?",
        "theme_mode_changed": "Mode du thème changé en {0}\n\nRedémarrer l'application maintenant pour appliquer les changements?",
        "theme_color_changed": "Couleur du thème changée en {0}\n\nRedémarrer l'application maintenant pour appliquer les changements?",
        "restart_steam_confirm": "Redémarrer Steam",
        "restart_steam_message": "Êtes-vous sûr de vouloir redémarrer Steam?\n\nCela fermera Steam en cours et le redémarrera.",
        "total_games": "Total: {0} jeux | SteamTools: {1} | GreenLuma: {2}",
        "load_failed": "Échec du chargement: {0}",
        "reset_settings": "Réinitialiser les paramètres",
        "reset_settings_message": "Êtes-vous sûr de vouloir réinitialiser tous les paramètres par défaut?\n\nCette action ne peut pas être annulée.",
        "reset_success": "Réinitialisation réussie",
        "reset_success_message": "Les paramètres ont été réinitialisés, veuillez recharger la page",
        "reset_failed": "Échec de la réinitialisation",
        "restarting": "Redémarrage en cours",
        "restarting_message": "Redémarrage de Steam, veuillez patienter...",
        "restart_success": "Redémarrage réussi",
        "restart_success_message": "Steam a été redémarré",
        "restart_failed": "Échec du redémarrage",
        "restart_failed_message": "Échec du redémarrage de Steam, veuillez redémarrer manuellement",
        "restart_error_message": "Erreur lors du redémarrage de Steam: {0}",
        "application_config": "Configuration de l'application",
        "debug_mode": "Mode débogage",
        "debug_mode_hint": "Activer la sortie détaillée du journal de débogage",
        "enable_debug_log": "Activer la sortie détaillée du journal de débogage",
        "save_log_files": "Enregistrer les fichiers journaux",
        "save_logs_to_file": "Enregistrer les journaux dans un fichier",
        "save_log_files_hint": "Enregistrer les journaux dans un fichier",
        "unlocker_mode": "Mode de déverrouillage",
        "auto_detect": "Détection automatique",
        "force_steamtools": "Forcer SteamTools",
        "force_greenluma": "Forcer GreenLuma",
        "force_unlocker_hint": "Forcer l'utilisation du déverrouilleur spécifié",
        "download_timeout": "Délai de téléchargement",
        "download_timeout_hint": "Délai d'attente pour les téléchargements de manifestes (secondes), augmentez si le réseau est lent",
        "theme_mode_hint": "Sélectionnez le mode du thème de l'application",
        "theme_color_hint": "Sélectionnez la couleur du thème",
        "language_hint": "Sélectionnez la langue de l'application",
        "window_effect": "Effet de fenêtre",
        "window_effect_hint": "Sélectionnez l'effet d'arrière-plan de la fenêtre",
        "effect_none": "Aucun effet",
        "effect_mica": "Mica (Win11)",
        "effect_acrylic": "Acrylic (Win10+)",
        "effect_aero": "Aero Blur",
        "light_theme": "Clair",
        "dark_theme": "Sombre",
        "follow_system": "Suivre le système",
        "default_blue": "Bleu par défaut (#0078d4)",
        "purple": "Violet (#9b4dca)",
        "green": "Vert (#10893e)",
        "orange": "Orange (#ff8c00)",
        "red": "Rouge (#e81123)",
        "pink": "Rose (#e3008c)",
        "tip_source_fail": "Astuce: Si une source échoue, essayez-en une autre",
        "auto_select": "Sélection automatique",
        "auto_search_github": "Recherche automatique GitHub",
        "swa_v2": "SWA V2",
        "walftech": "Walftech",
        "steamautocracks_v2": "SteamAutoCracks V2 (Clés seulement)",
        "sudama": "Bibliothèque Sudama (Clés seulement)",
        "buqiuren": "Bibliothèque d'aide de manifeste (Manifeste seulement)",
        "github_auiowu": "GitHub (Auiowu)",
        "check_update": "Vérifier les mises à jour",
        "checking": "Vérification...",
        "update_available": "Nouvelle version disponible",
        "current_version": "Version actuelle",
        "latest_version": "Dernière version",
        "no_release_notes": "Pas de notes de version",
        "go_to_download": "Télécharger",
        "already_latest": "Déjà à jour",
        "already_latest_content": "Vous utilisez la dernière version.",
        "check_update_failed": "Échec de la vérification",
        "restart_steam_title": "Redémarrer Steam",
        "restart_steam_confirm_message": "Êtes-vous sûr de vouloir redémarrer Steam?\n\nCela fermera Steam en cours et le redémarrera.",
        "tip": "Astuce",
        "recognition_success": "Reconnaissance réussie",
        "game_not_found": "Jeu non trouvé",
        "check_game_name": "Vérifiez le nom du jeu ou essayez d'utiliser l'AppID",
        "search_failed": "Échec de la recherche",
        "game_selected": "Jeu sélectionné",
        "add_success": "Ajout réussi",
        "add_success_content": "L'AppID {0} a été ajouté avec succès, redémarrez Steam pour prendre effet",
        "adding_game": "Ajout du jeu en cours...",
        "please_wait_adding": "Veuillez patienter, traitement de l'ajout",
        "process_failed": "Échec du traitement",
        "check_logs": "Veuillez consulter les journaux",
        "check_details": "Échec du traitement, veuillez consulter les détails ou essayer d'autres sources",
        "auto_detect_placeholder": "Laisser vide pour détection automatique",
        "token_placeholder": "Optionnel, pour augmenter les limites de requêtes API",
        "load_config_failed": "Échec du chargement de la configuration",
        "save_success": "Enregistrement réussi",
        "save_success_content": "Configuration enregistrée",
        "save_failed": "Échec de l'enregistrement",
        "unknown_error": "Erreur inconnue",
        "data_process_failed": "Échec du traitement des données",
        "please_wait": "Veuillez patienter",
        "unknown_game": "Jeu inconnu",
        "reset_to_default": "Réinitialiser par défaut",
        "about_title": "À propos",
        "thanks_title": "Crédits",
        "about_text": "Cai Install - Version Fluent Design\n\nVersion: 1.7\n\nCeci est un outil de déverrouillage de jeu Steam moderne basé sur PyQt6-Fluent-Widgets.\n\nFonctionnalités:\n• Style Fluent Design\n• Support de plusieurs sources de manifestes\n• Recherche et ajout de jeux\n• Gestion des jeux installés\n• Personnalisation du thème\n\nURL du projet: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Remerciements spéciaux\n\nDéveloppeurs:\n• zhouchentao666 - Développeur\n\nProjets open source:\n• PyQt6 - Bindings Python Qt6\n• PyQt-Fluent-Widgets - Bibliothèque de composants Fluent Design\n• Cai-install-Web-GUI - Auteur du projet original\n• httpx - Client HTTP asynchrone\n\nSources de manifestes:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Bibliothèque d'aide de manifeste\n\nMerci à tous les développeurs et utilisateurs qui ont contribué à ce projet!",
        "donate": "Faire un don",
        "donate_title": "Soutenir le développeur",
        "donate_desc": "Si ce projet vous a été utile, n'hésitez pas à offrir un café à l'auteur ☕",
        "donate_wechat": "WeChat Pay",
        "donate_alipay": "Alipay",
        "donate_loading": "Chargement...",
        "donate_load_failed": "Échec du chargement de l'image",
        "fixed_version": "Version fixe",
        "auto_update": "Mise à jour auto",
        "toggle_version_mode": "Changer le mode de version",
        "st_settings": "Paramètres SteamTools",
        "st_settings_hint": "Contrôler le mode de gestion des versions des fichiers SteamTools",
        "st_fixed_enable": "Activer le mode version fixe SteamTools",
        "st_fixed_tooltip": "Les nouveaux fichiers SteamTools utiliseront le mode version fixe par défaut",
        "st_fixed_manifest_mode": "Réparation Manifest version fixe",
        "st_fixed_manifest_mode_hint": "Réparer automatiquement le manifest lors du passage en version fixe",
        "st_fixed_manifest_always": "Toujours",
        "st_fixed_manifest_never": "Jamais",
        "st_fixed_manifest_ask": "Demander",
        "dlc_timeout": "Délai réseau DLC",
        "dlc_timeout_hint": "Délai d'attente pour récupérer la liste DLC, augmenter si le réseau est lent (secondes)",
        "show_progress_bar": "Afficher la barre de progression",
        "show_progress_bar_hint": "Afficher la barre de progression pendant la recherche et l'ajout pour une meilleure expérience",


        "hide_search_hint": "Masquer l'option de recherche dans la barre latérale",

        "name_not_found": "Nom introuvable",
        "fetch_failed": "Échec de récupération",
    },
    "ru_RU": {
        "app_title": "FluentInstall",
        "home": "Главная",
        "search": "Поиск",
        "settings": "Настройки",
        "default_page": "Страница по умолчанию",
        "default_page_hint": "Выберите страницу по умолчанию для отображения при запуске",
        "default_page_home": "Главная",
        "default_page_search": "Поиск",
        "restart_steam": "Перезапустить Steam",
        "installed_games": "Установленные игры",
        "search_placeholder": "Поиск названия игры или AppID",
        "loading": "Загрузка...",
        "no_games": "Нет игр",
        "delete": "Удалить",
        "confirm_delete": "Подтвердить удаление",
        "delete_message": "Вы уверены, что хотите удалить AppID {0}?\n\nЭто действие нельзя отменить.",
        "deleting": "Удаление",
        "delete_success": "Удаление успешно",
        "delete_failed": "Ошибка удаления",
        "search_and_add": "Поиск и добавление игр",
        "game_name_or_appid": "Введите название игры или AppID / ссылку Steam",
        "search_button": "Поиск",
        "add_options": "Опции добавления",
        "add_all_dlc": "Добавить все DLC",
        "patch_depot_key": "Патч ключ депо",
        "patch_manifest": "Патч манифеста",
        "manifest_source": "Источник манифеста:",
        "add_game": "Добавить игру",
        "steam_path": "Путь Steam",
        "steam_path_hint": "Выберите путь установки Steam, оставьте пустым для автоматического обнаружения",
        "github_token": "Персональный токен GitHub",
        "github_token_hint": "Необязательно, для увеличения лимитов API запросов",
        "basic_settings": "Базовые настройки",
        "appearance": "Внешний вид",
        "theme_mode": "Режим темы",
        "theme_color": "Цвет темы",
        "language": "Язык",
        "save_settings": "Сохранить настройки",
        "about": "О программе",
        "thanks": "Благодарности",
        "restart_required": "Требуется перезапуск",
        "language_changed": "Язык изменен на {0}\n\nПерезапустить приложение сейчас для применения изменений?",
        "theme_mode_changed": "Режим темы изменен на {0}\n\nПерезапустить приложение сейчас для применения изменений?",
        "theme_color_changed": "Цвет темы изменен на {0}\n\nПерезапустить приложение сейчас для применения изменений?",
        "restart_steam_confirm": "Перезапустить Steam",
        "restart_steam_message": "Вы уверены, что хотите перезапустить Steam?\n\nЭто закроет текущий Steam и перезапустит его.",
        "total_games": "Всего: {0} игр | SteamTools: {1} | GreenLuma: {2}",
        "load_failed": "Ошибка загрузки: {0}",
        "reset_settings": "Сбросить настройки",
        "reset_settings_message": "Вы уверены, что хотите сбросить все настройки по умолчанию?\n\nЭто действие нельзя отменить.",
        "reset_success": "Сброс успешен",
        "reset_success_message": "Настройки сброшены по умолчанию, пожалуйста, перезагрузите страницу",
        "reset_failed": "Ошибка сброса",
        "restarting": "Перезапуск",
        "restarting_message": "Перезапуск Steam, пожалуйста подождите...",
        "restart_success": "Перезапуск успешен",
        "restart_success_message": "Steam был перезапущен",
        "restart_failed": "Ошибка перезапуска",
        "restart_failed_message": "Ошибка перезапуска Steam, пожалуйста перезапустите вручную",
        "restart_error_message": "Ошибка при перезапуске Steam: {0}",
        "application_config": "Конфигурация приложения",
        "debug_mode": "Режим отладки",
        "debug_mode_hint": "Включить подробный вывод журнала отладки",
        "enable_debug_log": "Включить подробный вывод журнала отладки",
        "save_log_files": "Сохранить файлы журналов",
        "save_logs_to_file": "Сохранить журналы в файл",
        "save_log_files_hint": "Сохранить журналы в файл",
        "unlocker_mode": "Режим разблокировки",
        "auto_detect": "Автоопределение",
        "force_steamtools": "Принудительно SteamTools",
        "force_greenluma": "Принудительно GreenLuma",
        "force_unlocker_hint": "Принудительно использовать указанный инструмент разблокировки",
        "download_timeout": "Таймаут загрузки",
        "download_timeout_hint": "Таймаут в секундах для загрузки манифестов, увеличьте при медленной сети",
        "theme_mode_hint": "Выберите режим темы приложения",
        "theme_color_hint": "Выберите цвет темы",
        "language_hint": "Выберите язык приложения",
        "window_effect": "Эффект окна",
        "window_effect_hint": "Выберите эффект фона окна",
        "effect_none": "Без эффекта",
        "effect_mica": "Мика (Win11)",
        "effect_acrylic": "Акрил (Win10+)",
        "effect_aero": "Aero Размытие",
        "light_theme": "Светлая",
        "dark_theme": "Темная",
        "follow_system": "Следовать системе",
        "default_blue": "Синий по умолчанию (#0078d4)",
        "purple": "Фиолетовый (#9b4dca)",
        "green": "Зеленый (#10893e)",
        "orange": "Оранжевый (#ff8c00)",
        "red": "Красный (#e81123)",
        "pink": "Розовый (#e3008c)",
        "tip_source_fail": "Совет: Если один источник не работает, попробуйте другой",
        "auto_select": "Автоматический выбор",
        "auto_search_github": "Автопоиск GitHub",
        "swa_v2": "SWA V2",
        "walftech": "Walftech",
        "steamautocracks_v2": "SteamAutoCracks V2 (Только ключи)",
        "sudama": "Библиотека Sudama (Только ключи)",
        "buqiuren": "Библиотека помощи манифеста (Только манифест)",
        "github_auiowu": "GitHub (Auiowu)",
        "check_update": "Проверить обновления",
        "checking": "Проверка...",
        "update_available": "Доступна новая версия",
        "current_version": "Текущая версия",
        "latest_version": "Последняя версия",
        "no_release_notes": "Нет примечаний",
        "go_to_download": "Скачать",
        "already_latest": "Уже актуально",
        "already_latest_content": "У вас установлена последняя версия.",
        "check_update_failed": "Ошибка проверки",
        "restart_steam_title": "Перезапустить Steam",
        "restart_steam_confirm_message": "Вы уверены, что хотите перезапустить Steam?\n\nЭто закроет текущий Steam и перезапустит его.",
        "tip": "Совет",
        "recognition_success": "Успешное распознавание",
        "game_not_found": "Игра не найдена",
        "check_game_name": "Пожалуйста, проверьте название игры или попробуйте использовать AppID",
        "search_failed": "Ошибка поиска",
        "game_selected": "Игра выбрана",
        "add_success": "Успешное добавление",
        "add_success_content": "AppID {0} успешно добавлен, перезапустите Steam для применения",
        "adding_game": "Добавление игры...",
        "please_wait_adding": "Пожалуйста подождите, обработка добавления",
        "process_failed": "Ошибка обработки",
        "check_logs": "Пожалуйста, проверьте журналы",
        "check_details": "Ошибка обработки, пожалуйста, проверьте детали или попробуйте другие источники",
        "auto_detect_placeholder": "Оставьте пустым для автоматического обнаружения",
        "token_placeholder": "Необязательно, для увеличения лимитов API запросов",
        "load_config_failed": "Ошибка загрузки конфигурации",
        "save_success": "Сохранение успешно",
        "save_success_content": "Конфигурация сохранена",
        "save_failed": "Ошибка сохранения",
        "unknown_error": "Неизвестная ошибка",
        "data_process_failed": "Ошибка обработки данных",
        "please_wait": "Пожалуйста подождите",
        "unknown_game": "Неизвестная игра",
        "reset_to_default": "Сбросить по умолчанию",
        "about_title": "О программе",
        "thanks_title": "Благодарности",
        "about_text": "Cai Install - Версия Fluent Design\n\nВерсия: 1.7\n\nЭто современный инструмент разблокировки игр Steam на основе PyQt6-Fluent-Widgets.\n\nФункции:\n• Стиль Fluent Design\n• Поддержка нескольких источников манифестов\n• Поиск и добавление игр\n• Управление установленными играми\n• Настройка темы\n\nURL проекта: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Особая благодарность\n\nРазработчики:\n• zhouchentao666 - Разработчик\n\nПроекты с открытым исходным кодом:\n• PyQt6 - Привязки Python Qt6\n• PyQt-Fluent-Widgets - Библиотека компонентов Fluent Design\n• Cai-install-Web-GUI - Автор оригинального проекта\n• httpx - Асинхронный HTTP клиент\n\nИсточники манифестов:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Библиотека помощи манифеста\n\nСпасибо всем разработчикам и пользователям, внесшим вклад в этот проект!",
        "donate": "Пожертвовать",
        "donate_title": "Поддержать разработчика",
        "donate_desc": "Если проект оказался полезным, угостите автора кофе ☕",
        "donate_wechat": "WeChat Pay",
        "donate_alipay": "Alipay",
        "donate_loading": "Загрузка...",
        "donate_load_failed": "Не удалось загрузить изображение",
        "fixed_version": "Фиксированная версия",
        "auto_update": "Авто обновление",
        "toggle_version_mode": "Переключить режим версии",
        "st_settings": "Настройки SteamTools",
        "st_settings_hint": "Управление режимом версий файлов SteamTools",
        "st_fixed_enable": "Включить режим фиксированной версии SteamTools",
        "st_fixed_tooltip": "Новые файлы SteamTools будут использовать режим фиксированной версии по умолчанию",
        "st_fixed_manifest_mode": "Исправление манифеста фикс. версии",
        "st_fixed_manifest_mode_hint": "Автоматически исправлять манифест при переключении на фиксированную версию",
        "st_fixed_manifest_always": "Всегда",
        "st_fixed_manifest_never": "Никогда",
        "st_fixed_manifest_ask": "Спрашивать",
        "dlc_timeout": "Тайм-аут сети DLC",
        "dlc_timeout_hint": "Тайм-аут получения списка DLC, увеличьте при медленной сети (секунды)",
        "show_progress_bar": "Показывать индикатор прогресса",
        "show_progress_bar_hint": "Показывать индикатор прогресса во время поиска и добавления для лучшего опыта",

        "hide_search": "Скрыть поиск",
        "hide_search_hint": "Скрыть опцию поиска в боковой панели",

        "name_not_found": "Имя не найдено",
        "fetch_failed": "Ошибка получения",
    },
    "de_DE": {
        "app_title": "FluentInstall",
        "home": "Startseite",
        "search": "Suchen",
        "settings": "Einstellungen",
        "default_page": "Standardseite",
        "default_page_hint": "Wählen Sie die Standardseite, die beim Start angezeigt wird",
        "default_page_home": "Startseite",
        "default_page_search": "Suche",
        "restart_steam": "Steam neu starten",
        "installed_games": "Installierte Spiele",
        "search_placeholder": "Spielname oder AppID suchen",
        "loading": "Laden...",
        "no_games": "Keine Spiele",
        "delete": "Löschen",
        "confirm_delete": "Löschung bestätigen",
        "delete_message": "Sind Sie sicher, dass Sie AppID {0} löschen möchten?\n\nDiese Aktion kann nicht rückgängig gemacht werden.",
        "deleting": "Löschen",
        "delete_success": "Löschung erfolgreich",
        "delete_failed": "Löschung fehlgeschlagen",
        "search_and_add": "Spiele suchen und hinzufügen",
        "game_name_or_appid": "Spielnamen oder AppID / Steam-Link eingeben",
        "search_button": "Suchen",
        "add_options": "Hinzufügen-Optionen",
        "add_all_dlc": "Alle DLCs hinzufügen",
        "patch_depot_key": "Depot-Schlüssel patchen",
        "patch_manifest": "Manifest patchen",
        "manifest_source": "Manifest-Quelle:",
        "add_game": "Spiel hinzufügen",
        "steam_path": "Steam-Pfad",
        "steam_path_hint": "Steam-Installationspfad auswählen, leer lassen für automatische Erkennung",
        "github_token": "GitHub Persönliches Token",
        "github_token_hint": "Optional, für erhöhte API-Anfrage-Limits",
        "basic_settings": "Grundeinstellungen",
        "appearance": "Erscheinungsbild",
        "theme_mode": "Themen-Modus",
        "theme_color": "Themen-Farbe",
        "language": "Sprache",
        "save_settings": "Einstellungen speichern",
        "about": "Über",
        "thanks": "Danksagungen",
        "restart_required": "Neustart erforderlich",
        "language_changed": "Sprache geändert zu {0}\n\nJetzt Anwendung neu starten um Änderungen anzuwenden?",
        "theme_mode_changed": "Themen-Modus geändert zu {0}\n\nJetzt Anwendung neu starten um Änderungen anzuwenden?",
        "theme_color_changed": "Themen-Farbe geändert zu {0}\n\nJetzt Anwendung neu starten um Änderungen anzuwenden?",
        "restart_steam_confirm": "Steam neu starten",
        "restart_steam_message": "Sind Sie sicher, dass Sie Steam neu starten möchten?\n\nDies wird das aktuelle Steam schließen und neu starten.",
        "total_games": "Gesamt: {0} Spiele | SteamTools: {1} | GreenLuma: {2}",
        "load_failed": "Laden fehlgeschlagen: {0}",
        "reset_settings": "Einstellungen zurücksetzen",
        "reset_settings_message": "Sind Sie sicher, dass Sie alle Einstellungen auf Standard zurücksetzen möchten?\n\nDiese Aktion kann nicht rückgängig gemacht werden.",
        "reset_success": "Zurücksetzen erfolgreich",
        "reset_success_message": "Einstellungen wurden auf Standard zurückgesetzt, bitte Seite neu laden",
        "reset_failed": "Zurücksetzen fehlgeschlagen",
        "restarting": "Neustart",
        "restarting_message": "Steam wird neu gestartet, bitte warten...",
        "restart_success": "Neustart erfolgreich",
        "restart_success_message": "Steam wurde neu gestartet",
        "restart_failed": "Neustart fehlgeschlagen",
        "restart_failed_message": "Steam-Neustart fehlgeschlagen, bitte manuell neu starten",
        "restart_error_message": "Fehler beim Neustart von Steam: {0}",
        "application_config": "Anwendungs-Konfiguration",
        "debug_mode": "Debug-Modus",
        "debug_mode_hint": "Detaillierte Debug-Log-Ausgabe aktivieren",
        "enable_debug_log": "Detaillierte Debug-Log-Ausgabe aktivieren",
        "save_log_files": "Log-Dateien speichern",
        "save_logs_to_file": "Logs in Datei speichern",
        "save_log_files_hint": "Logs in Datei speichern",
        "unlocker_mode": "Unlocker-Modus",
        "auto_detect": "Automatische Erkennung",
        "force_steamtools": "SteamTools erzwingen",
        "force_greenluma": "GreenLuma erzwingen",
        "force_unlocker_hint": "Verwendung des angegebenen Unlockers erzwingen",
        "download_timeout": "Download-Timeout",
        "download_timeout_hint": "Timeout in Sekunden für Manifest-Downloads, erhöhen Sie bei langsamem Netzwerk",
        "theme_mode_hint": "Wählen Sie den Anwendungs-Themen-Modus",
        "theme_color_hint": "Wählen Sie die Themen-Farbe",
        "language_hint": "Wählen Sie die Anwendungs-Sprache",
        "window_effect": "Fenster-Effekt",
        "window_effect_hint": "Wählen Sie den Fenster-Hintergrund-Effekt",
        "effect_none": "Kein Effekt",
        "effect_mica": "Mica (Win11)",
        "effect_acrylic": "Acrylic (Win10+)",
        "effect_aero": "Aero Blur",
        "light_theme": "Hell",
        "dark_theme": "Dunkel",
        "follow_system": "System folgen",
        "default_blue": "Standard-Blau (#0078d4)",
        "purple": "Violett (#9b4dca)",
        "green": "Grün (#10893e)",
        "orange": "Orange (#ff8c00)",
        "red": "Rot (#e81123)",
        "pink": "Pink (#e3008c)",
        "tip_source_fail": "Tipp: Wenn eine Quelle fehlschlägt, versuchen Sie eine andere",
        "auto_select": "Automatisch auswählen",
        "auto_search_github": "Automatische GitHub-Suche",
        "swa_v2": "SWA V2",
        "walftech": "Walftech",
        "steamautocracks_v2": "SteamAutoCracks V2 (Nur Schlüssel)",
        "sudama": "Sudama-Bibliothek (Nur Schlüssel)",
        "buqiuren": "Manifest-Hilfsbibliothek (Nur Manifest)",
        "github_auiowu": "GitHub (Auiowu)",
        "check_update": "Nach Updates suchen",
        "checking": "Suche...",
        "update_available": "Neue Version verfügbar",
        "current_version": "Aktuelle Version",
        "latest_version": "Neueste Version",
        "no_release_notes": "Keine Versionshinweise",
        "go_to_download": "Herunterladen",
        "already_latest": "Bereits aktuell",
        "already_latest_content": "Sie verwenden die neueste Version.",
        "check_update_failed": "Prüfung fehlgeschlagen",
        "restart_steam_title": "Steam neu starten",
        "restart_steam_confirm_message": "Sind Sie sicher, dass Sie Steam neu starten möchten?\n\nDies wird das aktuelle Steam schließen und neu starten.",
        "tip": "Tipp",
        "recognition_success": "Erkennung erfolgreich",
        "game_not_found": "Spiel nicht gefunden",
        "check_game_name": "Bitte überprüfen Sie den Spielnamen oder versuchen Sie die AppID",
        "search_failed": "Suche fehlgeschlagen",
        "game_selected": "Spiel ausgewählt",
        "add_success": "Hinzufügen erfolgreich",
        "add_success_content": "AppID {0} wurde erfolgreich hinzugefügt, starten Sie Steam neu um es zu aktivieren",
        "adding_game": "Spiel wird zur Bibliothek hinzugefügt...",
        "please_wait_adding": "Bitte warten Sie, Hinzufügen wird verarbeitet",
        "process_failed": "Verarbeitung fehlgeschlagen",
        "check_logs": "Bitte überprüfen Sie die Logs",
        "check_details": "Verarbeitung fehlgeschlagen, bitte überprüfen Sie die Details oder versuchen Sie andere Quellen",
        "auto_detect_placeholder": "Leer lassen für automatische Erkennung",
        "token_placeholder": "Optional, für erhöhte API-Anfrage-Limits",
        "load_config_failed": "Konfiguration laden fehlgeschlagen",
        "save_success": "Speichern erfolgreich",
        "save_success_content": "Konfiguration gespeichert",
        "save_failed": "Speichern fehlgeschlagen",
        "unknown_error": "Unbekannter Fehler",
        "data_process_failed": "Datenverarbeitung fehlgeschlagen",
        "please_wait": "Bitte warten Sie",
        "unknown_game": "Unbekanntes Spiel",
        "reset_to_default": "Auf Standard zurücksetzen",
        "about_title": "Über",
        "thanks_title": "Danksagungen",
        "about_text": "Cai Install - Fluent Design Version\n\nVersion: \n1.7\nDies ist ein modernes Steam-Spiel-Unlocking-Tool basierend auf PyQt6-Fluent-Widgets.\n\nFunktionen:\n• Fluent Design Stil\n• Unterstützung für mehrere Manifest-Quellen\n• Spielsuche und -hinzufügen\n• Verwaltung installierter Spiele\n• Themen-Anpassung\n\nProjekt-URL: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Besondere Danksagung\n\nEntwickler:\n• zhouchentao666 - Entwickler\n\nOpen-Source-Projekte:\n• PyQt6 - Qt6 Python Bindings\n• PyQt-Fluent-Widgets - Fluent Design Komponentenbibliothek\n• Cai-install-Web-GUI - Originalprojekt-Autor\n• httpx - Asynchroner HTTP-Client\n\nManifest-Quellen:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Manifest-Hilfsbibliothek\n\nVielen Dank an alle Entwickler und Benutzer, die zu diesem Projekt beigetragen haben!",
        "donate": "Spenden",
        "donate_title": "Entwickler unterstützen",
        "donate_desc": "Wenn dieses Projekt hilfreich war, spendieren Sie dem Autor einen Kaffee ☕",
        "donate_wechat": "WeChat Pay",
        "donate_alipay": "Alipay",
        "donate_loading": "Laden...",
        "donate_load_failed": "Bild konnte nicht geladen werden",
        "fixed_version": "Feste Version",
        "auto_update": "Auto-Update",
        "toggle_version_mode": "Versionsmodus wechseln",
        "st_settings": "SteamTools-Einstellungen",
        "st_settings_hint": "Versionsverwaltungsmodus für SteamTools-Dateien steuern",
        "st_fixed_enable": "SteamTools Feste Version aktivieren",
        "st_fixed_tooltip": "Neue SteamTools-Dateien verwenden standardmäßig den festen Versionsmodus",
        "st_fixed_manifest_mode": "Manifest-Reparatur feste Version",
        "st_fixed_manifest_mode_hint": "Manifest automatisch reparieren beim Wechsel zur festen Version",
        "st_fixed_manifest_always": "Immer",
        "st_fixed_manifest_never": "Nie",
        "st_fixed_manifest_ask": "Fragen",
        "dlc_timeout": "DLC-Netzwerk-Timeout",
        "dlc_timeout_hint": "Timeout für DLC-Liste, bei langsamen Netzwerk erhöhen (Sekunden)",
        "show_progress_bar": "Fortschrittsbalken anzeigen",
        "show_progress_bar_hint": "Fortschrittsbalken während Suche und Hinzufügen für bessere Benutzererfahrung anzeigen",

        "hide_search": "Suche ausblenden",
        "hide_search_hint": "Suchoption in der Seitenleiste ausblenden",

        "name_not_found": "Name nicht gefunden",
        "fetch_failed": "Abruf fehlgeschlagen",
    },
    "ja_JP": {
        "app_title": "FluentInstall",
        "home": "ホーム",
        "search": "検索",
        "settings": "設定",
        "default_page": "デフォルトページ",
        "default_page_hint": "アプリケーション起動時に表示するデフォルトページを選択",
        "default_page_home": "ホーム",
        "default_page_search": "ライブラリ検索",
        "restart_steam": "Steamを再起動",
        "installed_games": "インストール済みゲーム",
        "search_placeholder": "ゲーム名またはAppIDを検索",
        "loading": "読み込み中...",
        "no_games": "ゲームなし",
        "delete": "削除",
        "confirm_delete": "削除の確認",
        "delete_message": "AppID {0} を削除してもよろしいですか？\n\nこの操作は元に戻せません。",
        "deleting": "削除中",
        "delete_success": "削除成功",
        "delete_failed": "削除失敗",
        "search_and_add": "ゲームを検索して追加",
        "game_name_or_appid": "ゲーム名またはAppID/Steamリンクを入力",
        "search_button": "検索",
        "add_options": "追加オプション",
        "add_all_dlc": "すべてのDLCを追加",
        "patch_manifest": "マニフェストをパッチ",
        "patch_depot_key": "デポットキーをパッチ",
        "manifest_source": "マニフェストソース:",
        "add_game": "ゲームを追加",
        "steam_path": "Steamパス",
        "steam_path_hint": "Steamインストールパスを選択、空の場合は自動検出",
        "github_token": "GitHubパーソナルトークン",
        "github_token_hint": "オプション、APIリクエスト制限を向上",
        "basic_settings": "基本設定",
        "appearance": "外観",
        "theme_mode": "テーマモード",
        "theme_color": "テーマカラー",
        "language": "言語",
        "save_settings": "設定を保存",
        "about": "について",
        "thanks": "謝辞",
        "restart_required": "再起動が必要",
        "language_changed": "言語が {0} に変更されました\n\n変更を適用するために今すぐアプリケーションを再起動しますか？",
        "theme_mode_changed": "テーマモードが {0} に変更されました\n\n変更を適用するために今すぐアプリケーションを再起動しますか？",
        "theme_color_changed": "テーマカラーが {0} に変更されました\n\n変更を適用するために今すぐアプリケーションを再起動しますか？",
        "restart_steam_confirm": "Steamを再起動",
        "restart_steam_message": "Steamを再起動してもよろしいですか？\n\n現在実行中のSteamを終了して再起動します。",
        "total_games": "合計: {0} ゲーム | SteamTools: {1} | GreenLuma: {2}",
        "load_failed": "読み込み失敗: {0}",
        "reset_settings": "設定をリセット",
        "reset_settings_message": "すべての設定をデフォルトにリセットしてもよろしいですか？\n\nこの操作は元に戻せません。",
        "reset_success": "リセット成功",
        "reset_success_message": "設定がデフォルトにリセットされました、ページを再読み込みしてください",
        "reset_failed": "リセット失敗",
        "restarting": "再起動中",
        "restarting_message": "Steamを再起動中、しばらくお待ちください...",
        "restart_success": "再起動成功",
        "restart_success_message": "Steamが再起動されました",
        "restart_failed": "再起動失敗",
        "restart_failed_message": "Steamの再起動に失敗しました、手動で再起動してください",
        "restart_error_message": "Steamの再起動エラー: {0}",
        "application_config": "アプリケーション設定",
        "debug_mode": "デバッグモード",
        "debug_mode_hint": "詳細なデバッグログ出力を有効にする",
        "enable_debug_log": "詳細なデバッグログ出力を有効にする",
        "save_log_files": "ログファイルを保存",
        "save_logs_to_file": "ログをファイルに保存",
        "save_log_files_hint": "ログをファイルに保存",
        "unlocker_mode": "アンロッカーモード",
        "auto_detect": "自動検出",
        "force_steamtools": "SteamToolsを強制",
        "force_greenluma": "GreenLumaを強制",
        "force_unlocker_hint": "指定されたアンロッカーを強制的に使用",
        "download_timeout": "ダウンロードタイムアウト",
        "download_timeout_hint": "マニフェストダウンロードのタイムアウト（秒）、ネットワークが遅い場合は増やしてください",
        "theme_mode_hint": "アプリケーションテーマモードを選択",
        "theme_color_hint": "テーマカラーを選択",
        "language_hint": "アプリケーション言語を選択",
        "window_effect": "ウィンドウエフェクト",
        "window_effect_hint": "ウィンドウ背景エフェクトを選択",
        "effect_none": "エフェクトなし",
        "effect_mica": "マイカ (Win11)",
        "effect_acrylic": "アクリル (Win10+)",
        "effect_aero": "Aero ブラー",
        "light_theme": "ライト",
        "dark_theme": "ダーク",
        "follow_system": "システムに従う",
        "default_blue": "デフォルトブルー (#0078d4)",
        "purple": "パープル (#9b4dca)",
        "green": "グリーン (#10893e)",
        "orange": "オレンジ (#ff8c00)",
        "red": "レッド (#e81123)",
        "pink": "ピンク (#e3008c)",
        "tip_source_fail": "ヒント: ソースが失敗した場合は別のソースを試してください",
        "auto_search_github": "GitHubを自動検索",
        "auto_select": "自動選択",
        "swa_v2": "SWA V2",
        "walftech": "Walftech",
        "steamautocracks_v2": "SteamAutoCracks V2 (キーのみ)",
        "sudama": "Sudamaライブラリ (キーのみ)",
        "buqiuren": "マニフェストヘルパーライブラリ (マニフェストのみ)",
        "github_auiowu": "GitHub (Auiowu)",
        "check_update": "アップデートを確認",
        "checking": "確認中...",
        "update_available": "新しいバージョンが利用可能",
        "current_version": "現在のバージョン",
        "latest_version": "最新バージョン",
        "no_release_notes": "リリースノートなし",
        "go_to_download": "ダウンロード",
        "already_latest": "最新版です",
        "already_latest_content": "最新バージョンを使用しています。",
        "check_update_failed": "確認に失敗しました",
        "restart_steam_title": "Steamを再起動",
        "restart_steam_confirm_message": "Steamを再起動してもよろしいですか？\n\n現在実行中のSteamを終了して再起動します。",
        "tip": "ヒント",
        "recognition_success": "認識成功",
        "game_not_found": "ゲームが見つかりません",
        "check_game_name": "ゲーム名を確認するか、AppIDをお試しください",
        "search_failed": "検索失敗",
        "game_selected": "ゲームが選択されました",
        "add_success": "追加成功",
        "add_success_content": "AppID {0} が正常に追加されました、Steamを再起動して有効にしてください",
        "adding_game": "ゲームをライブラリに追加中...",
        "please_wait_adding": "しばらくお待ちください、追加処理中です",
        "process_failed": "処理失敗",
        "check_logs": "ログを確認してください",
        "check_details": "処理に失敗しました、詳細を確認するか別のソースをお試しください",
        "auto_detect_placeholder": "自動検出の場合は空のままにしてください",
        "token_placeholder": "オプション、APIリクエスト制限を向上",
        "load_config_failed": "設定の読み込みに失敗しました",
        "save_success": "保存成功",
        "save_success_content": "設定が保存されました",
        "save_failed": "保存失敗",
        "unknown_error": "不明なエラー",
        "data_process_failed": "データ処理に失敗しました",
        "please_wait": "しばらくお待ちください",
        "unknown_game": "不明なゲーム",
        "reset_to_default": "デフォルトにリセット",
        "about_title": "について",
        "thanks_title": "謝辞",
        "about_text": "Cai Install - Fluent Design バージョン\n\nバージョン: 1.7\n\nこれはPyQt6-Fluent-WidgetsをベースにしたモダンなSteamゲームアンロックツールです。\n\n機能:\n• Fluent Designスタイル\n• 複数のマニフェストソースをサポート\n• ゲーム検索と追加\n• インストール済みゲームの管理\n• テーマカスタマイズ\n\nプロジェクトURL: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "特別な感謝\n\n開発者:\n• zhouchentao666 - 開発者\n\nオープンソースプロジェクト:\n• PyQt6 - Qt6 Pythonバインディング\n• PyQt-Fluent-Widgets - Fluent Designコンポーネントライブラリ\n• Cai-install-Web-GUI - オリジナルプロジェクト作成者\n• httpx - 非同期HTTPクライアント\n\nマニフェストソース:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• マニフェストヘルパーライブラリ\n\nこのプロジェクトに貢献してくれたすべての開発者とユーザーの皆様に感謝します！",
        "donate": "寄付",
        "donate_title": "開発者を支援",
        "donate_desc": "このプロジェクトが役に立った場合は、作者にコーヒーをご馳走ください ☕",
        "donate_wechat": "WeChat Pay",
        "donate_alipay": "Alipay",
        "donate_loading": "読み込み中...",
        "donate_load_failed": "画像の読み込みに失敗しました",
        "fixed_version": "固定バージョン",
        "auto_update": "自動更新",
        "toggle_version_mode": "バージョンモード切替",
        "st_settings": "SteamTools設定",
        "st_settings_hint": "SteamToolsファイルのバージョン管理モードを制御",
        "st_fixed_enable": "SteamTools固定バージョンモードを有効にする",
        "st_fixed_tooltip": "新しいSteamToolsファイルはデフォルトで固定バージョンモードを使用します",
        "st_fixed_manifest_mode": "固定バージョンマニフェスト修復",
        "st_fixed_manifest_mode_hint": "ホームページで固定バージョンに切り替える際にマニフェストを自動修復",
        "st_fixed_manifest_always": "常に",
        "st_fixed_manifest_never": "从不",
        "st_fixed_manifest_ask": "確認",
        "dlc_timeout": "DLC ネットワークタイムアウト",
        "dlc_timeout_hint": "DLCリスト取得のタイムアウト、ネットワークが遅い場合は増やしてください（秒）",
        "show_progress_bar": "進捗バーを表示",
        "show_progress_bar_hint": "検索と追加中に進捗バーを表示して、より良いユーザー体験を提供",


        "hide_search_hint": "サイドバーの検索オプションを非表示",
        "hide_launcher": "オンラインゲームを非表示",
        "hide_launcher_hint": "サイドバーのオンラインゲームオプションを非表示",
        "hide_trainer": "トレーナーを非表示",
        "hide_trainer_hint": "サイドバーのトレーナーオプションを非表示",
        "name_not_found": "名前が見つかりません",
        "fetch_failed": "取得失敗",
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
        "steamautocracks_v2": "SteamAutoCracks V2 (僅金鑰)",
        "sudama": "Sudama 資料庫 (僅金鑰)",
        "buqiuren": "清單不求人資料庫 (僅清單)",
        "github_auiowu": "GitHub (Auiowu)",
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
        "name_not_found": "名稱未找到",
        "fetch_failed": "獲取失敗",
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
        # 两种联机模式
        "launcher_mode_label": "联机方式",
        "launcher_mode_dll": "DLL 注入联机 (推荐)",
        "launcher_mode_bat": "BAT 脚本注入联机",
        "launcher_mode_dll_desc": "扫描 Steam 库中的 steam_api.dll，加载后初始化 Steam API，再启动游戏。兼容性最佳。",
        "launcher_mode_bat_desc": "在游戏目录生成 BAT 脚本，通过环境变量注入 AppID 启动游戏。简单快速。",
        "launcher_bat_start": "生成脚本并启动",
        "launcher_mode_select": "选择联机方式",
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
        "launcher_mode_dll_desc": "Scans Steam library for steam_api.dll, loads it to initialize Steam API, then launches the game. Best compatibility.",
        "launcher_mode_bat_desc": "Generates a BAT script in the game directory to inject AppID via environment variables. Simple and fast.",
        "launcher_bat_start": "Generate Script & Launch",
        "launcher_mode_select": "Select Launch Mode",
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
        "launcher_app_id": "協議ID (AppID)",
        "launcher_app_id_hint": "預設為480 (太空戰)，可更改为實際遊戲AppID",
        "launcher_start": "啟動服務並啟動遊戲",
        "launcher_stop": "停止服務",
        "launcher_log": "運行時日誌",
        "launcher_clear_log": "清除日誌",
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
}
for _lang, _keys in _EXTRA_TEXTS.items():
    if _lang in TEXTS:
        TEXTS[_lang].update(_keys)
for _lang in TEXTS:
    if _lang not in _EXTRA_TEXTS:
        TEXTS[_lang].update(_EXTRA_TEXTS["zh_CN"])

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
    "ja_JP": {
        "trainer_nav": "トレーナー",
        "trainer_title": "ゲームトレーナー",
        "trainer_search_placeholder": "トレーナーを検索（ゲーム名）...",
        "trainer_search_btn": "検索",
        "trainer_installed_title": "インストール済みトレーナー",
        "trainer_search_results": "検索結果",
        "trainer_download_btn": "ダウンロード",
        "trainer_launch_btn": "起動",
        "trainer_delete_btn": "削除",
        "trainer_refresh_btn": "更新",
        "trainer_open_folder": "フォルダを開く",
        "trainer_no_installed": "インストール済みトレーナーはありません",
        "trainer_no_results": "トレーナーが見つかりません",
        "trainer_searching": "検索中...",
        "trainer_downloading": "ダウンロード中...",
        "trainer_download_success": "ダウンロード成功",
        "trainer_download_failed": "ダウンロード失敗",
        "trainer_launch_failed": "起動失敗",
        "trainer_delete_confirm": "削除の確認",
        "trainer_delete_confirm_msg": "{0} を削除してもよろしいですか？",
        "trainer_deleted": "削除しました",
        "trainer_db_missing": "GCMデータベースが見つかりません",
        "trainer_db_missing_hint": "トレーナーデータベースをダウンロードするには、Game Cheats Managerをインストールして実行するか、直接検索してください（インターネット接続が必要です）",
        "trainer_version": "バージョン",
        "trainer_source": "ソース",
        "trainer_log": "操作ログ",
        "trainer_clear_log": "ログをクリア",
        "trainer_already_exists": "トレーナーは既に存在します",
        "trainer_open_gcm": "GCMを開く",
        "trainer_progress": "ダウンロード進捗",
    },
    "fr_FR": {
        "trainer_nav": "Trainers",
        "trainer_title": "Trainers de Jeu",
        "trainer_search_placeholder": "Rechercher des trainers (nom du jeu)...",
        "trainer_search_btn": "Rechercher",
        "trainer_installed_title": "Trainers Installés",
        "trainer_search_results": "Résultats de Recherche",
        "trainer_download_btn": "Télécharger",
        "trainer_launch_btn": "Lancer",
        "trainer_delete_btn": "Supprimer",
        "trainer_refresh_btn": "Actualiser",
        "trainer_open_folder": "Ouvrir le Dossier",
        "trainer_no_installed": "Aucun trainer installé",
        "trainer_no_results": "Aucun trainer trouvé",
        "trainer_searching": "Recherche en cours...",
        "trainer_downloading": "Téléchargement en cours...",
        "trainer_download_success": "Téléchargement réussi",
        "trainer_download_failed": "Échec du téléchargement",
        "trainer_launch_failed": "Échec du lancement",
        "trainer_delete_confirm": "Confirmer la Suppression",
        "trainer_delete_confirm_msg": "Êtes-vous sûr de vouloir supprimer {0} ?",
        "trainer_deleted": "Supprimé",
        "trainer_db_missing": "Base de Données GCM Introuvable",
        "trainer_db_missing_hint": "Veuillez installer et exécuter Game Cheats Manager pour télécharger la base de données des trainers, ou recherchez directement (nécessite Internet)",
        "trainer_version": "Version",
        "trainer_source": "Source",
        "trainer_log": "Journal des Opérations",
        "trainer_clear_log": "Effacer le Journal",
        "trainer_already_exists": "Le trainer existe déjà",
        "trainer_open_gcm": "Ouvrir GCM",
        "trainer_progress": "Progression du Téléchargement",
    },
    "ru_RU": {
        "trainer_nav": "Трейнеры",
        "trainer_title": "Игровые Трейнеры",
        "trainer_search_placeholder": "Поиск трейнеров (название игры)...",
        "trainer_search_btn": "Поиск",
        "trainer_installed_title": "Установленные Трейнеры",
        "trainer_search_results": "Результаты Поиска",
        "trainer_download_btn": "Скачать",
        "trainer_launch_btn": "Запустить",
        "trainer_delete_btn": "Удалить",
        "trainer_refresh_btn": "Обновить",
        "trainer_open_folder": "Открыть Папку",
        "trainer_no_installed": "Нет установленных трейнеров",
        "trainer_no_results": "Трейнеры не найдены",
        "trainer_searching": "Поиск...",
        "trainer_downloading": "Загрузка...",
        "trainer_download_success": "Загрузка успешна",
        "trainer_download_failed": "Ошибка загрузки",
        "trainer_launch_failed": "Ошибка запуска",
        "trainer_delete_confirm": "Подтвердить Удаление",
        "trainer_delete_confirm_msg": "Вы уверены, что хотите удалить {0}?",
        "trainer_deleted": "Удалено",
        "trainer_db_missing": "База Данных GCM Не Найдена",
        "trainer_db_missing_hint": "Пожалуйста, установите и запустите Game Cheats Manager для загрузки базы данных трейнеров, или выполните прямой поиск (требуется интернет)",
        "trainer_version": "Версия",
        "trainer_source": "Источник",
        "trainer_log": "Журнал Операций",
        "trainer_clear_log": "Очистить Журнал",
        "trainer_already_exists": "Трейнер уже существует",
        "trainer_open_gcm": "Открыть GCM",
        "trainer_progress": "Прогресс Загрузки",
    },
    "de_DE": {
        "trainer_nav": "Trainer",
        "trainer_title": "Spiel-Trainer",
        "trainer_search_placeholder": "Trainer suchen (Spielname)...",
        "trainer_search_btn": "Suchen",
        "trainer_installed_title": "Installierte Trainer",
        "trainer_search_results": "Suchergebnisse",
        "trainer_download_btn": "Herunterladen",
        "trainer_launch_btn": "Starten",
        "trainer_delete_btn": "Löschen",
        "trainer_refresh_btn": "Aktualisieren",
        "trainer_open_folder": "Ordner Öffnen",
        "trainer_no_installed": "Keine Trainer installiert",
        "trainer_no_results": "Keine Trainer gefunden",
        "trainer_searching": "Suche läuft...",
        "trainer_downloading": "Wird heruntergeladen...",
        "trainer_download_success": "Download erfolgreich",
        "trainer_download_failed": "Download fehlgeschlagen",
        "trainer_launch_failed": "Start fehlgeschlagen",
        "trainer_delete_confirm": "Löschen Bestätigen",
        "trainer_delete_confirm_msg": "Sind Sie sicher, dass Sie {0} löschen möchten?",
        "trainer_deleted": "Gelöscht",
        "trainer_db_missing": "GCM-Datenbank Nicht Gefunden",
        "trainer_db_missing_hint": "Bitte installieren und starten Sie Game Cheats Manager, um die Trainer-Datenbank herunterzuladen, oder suchen Sie direkt (Internet erforderlich)",
        "trainer_version": "Version",
        "trainer_source": "Quelle",
        "trainer_log": "Betriebsprotokoll",
        "trainer_clear_log": "Protokoll Löschen",
        "trainer_already_exists": "Trainer existiert bereits",
        "trainer_open_gcm": "GCM Öffnen",
        "trainer_progress": "Download-Fortschritt",
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
        "trainer_no_results": "未找到相關修改器",
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
    "es_ES": {
        "trainer_nav": "Trainers",
        "trainer_title": "Trainers de Juegos",
        "trainer_search_placeholder": "Buscar trainers (nombre del juego)...",
        "trainer_search_btn": "Buscar",
        "trainer_installed_title": "Trainers Instalados",
        "trainer_search_results": "Resultados de Búsqueda",
        "trainer_download_btn": "Descargar",
        "trainer_launch_btn": "Iniciar",
        "trainer_delete_btn": "Eliminar",
        "trainer_refresh_btn": "Actualizar",
        "trainer_open_folder": "Abrir Carpeta",
        "trainer_no_installed": "No hay trainers instalados",
        "trainer_no_results": "No se encontraron trainers",
        "trainer_searching": "Buscando...",
        "trainer_downloading": "Descargando...",
        "trainer_download_success": "Descarga exitosa",
        "trainer_download_failed": "Descarga fallida",
        "trainer_launch_failed": "Inicio fallido",
        "trainer_delete_confirm": "Confirmar Eliminación",
        "trainer_delete_confirm_msg": "¿Estás seguro de que deseas eliminar {0}?",
        "trainer_deleted": "Eliminado",
        "trainer_db_missing": "Base de Datos GCM No Encontrada",
        "trainer_db_missing_hint": "Por favor instala y ejecuta Game Cheats Manager para descargar la base de datos de trainers, o busca directamente (requiere internet)",
        "trainer_version": "Versión",
        "trainer_source": "Fuente",
        "trainer_log": "Registro de Operaciones",
        "trainer_clear_log": "Borrar Registro",
        "trainer_already_exists": "El trainer ya existe",
        "trainer_open_gcm": "Abrir GCM",
        "trainer_progress": "Progreso de Descarga",
    },
    "ko_KR": {
        "trainer_nav": "트레이너",
        "trainer_title": "게임 트레이너",
        "trainer_search_placeholder": "트레이너 검색 (게임 이름)...",
        "trainer_search_btn": "검색",
        "trainer_installed_title": "설치된 트레이너",
        "trainer_search_results": "검색 결과",
        "trainer_download_btn": "다운로드",
        "trainer_launch_btn": "실행",
        "trainer_delete_btn": "삭제",
        "trainer_refresh_btn": "새로고침",
        "trainer_open_folder": "폴더 열기",
        "trainer_no_installed": "설치된 트레이너가 없습니다",
        "trainer_no_results": "트레이너를 찾을 수 없습니다",
        "trainer_searching": "검색 중...",
        "trainer_downloading": "다운로드 중...",
        "trainer_download_success": "다운로드 성공",
        "trainer_download_failed": "다운로드 실패",
        "trainer_launch_failed": "실행 실패",
        "trainer_delete_confirm": "삭제 확인",
        "trainer_delete_confirm_msg": "{0}을(를) 삭제하시겠습니까?",
        "trainer_deleted": "삭제됨",
        "trainer_db_missing": "GCM 데이터베이스를 찾을 수 없음",
        "trainer_db_missing_hint": "트레이너 데이터베이스를 다운로드하려면 Game Cheats Manager를 설치하고 실행하거나, 직접 검색하세요 (인터넷 필요)",
        "trainer_version": "버전",
        "trainer_source": "출처",
        "trainer_log": "작업 로그",
        "trainer_clear_log": "로그 지우기",
        "trainer_already_exists": "트레이너가 이미 존재합니다",
        "trainer_open_gcm": "GCM 열기",
        "trainer_progress": "다운로드 진행률",
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
        
        # 网络管理器（先初始化）
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self.on_cover_loaded)
        
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
        
        # 游戏标题
        # 如果游戏名称为空或显示为"名称未找到"等，显示AppID
        display_name = game_name
        if not game_name or game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed'), tr('unknown_game')):
            display_name = f"AppID: {appid}"
        self.titleLabel = BodyLabel(display_name, self)
        self.titleLabel.setWordWrap(False)
        
        # AppID 和来源
        source_text = "SteamTools" if source_type == "st" else "GreenLuma"
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
        self.moreButton.clicked.connect(self._show_more_menu)
        
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
        
        # 加载封面（最后执行）
        self.load_cover()
    
    def theme_changed(self):
        """主题变化时更新样式"""
        if isDarkTheme():
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        else:
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #f0f0f0;")
        
        # 强制刷新卡片
        self.update()
        self.repaint()
    
    def load_cover(self):
        """加载游戏封面"""
        # Steam 封面 URL
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
    
    def on_delete_clicked(self):
        """删除按钮点击"""
        # 发送信号给父页面
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, HomePage):
                parent = parent.parent()
            if parent:
                parent.delete_game(self.appid, self.source_type)
    
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

    def _show_more_menu(self):
        menu = RoundMenu(parent=self)
        
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
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, tr("delete"), triggered=self.on_delete_clicked))
        menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))


class GameCardGrid(CardWidget):
    """游戏卡片组件 - 网格视图模式"""
    
    def __init__(self, appid, game_name, source_type, parent=None, mode="auto"):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name
        self.source_type = source_type  # 'st' 或 'gl'
        self.mode = mode  # 'auto' 或 'fixed'
        
        # 网络管理器（先初始化）
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
        # 根据主题模式动态设置背景颜色
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        # 监听主题变化
        self.theme_changed()
        
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
        source_text = "SteamTools" if source_type == "st" else "GreenLuma"
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
        self.moreButton.clicked.connect(self._show_more_menu)
        
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
        
        # 加载封面（最后执行）
        self.load_cover()
    
    def theme_changed(self):
        """主题变化时更新样式"""
        if isDarkTheme():
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        else:
            self.coverLabel.setStyleSheet("border-radius: 4px; background: #f0f0f0;")
    
    def load_cover(self):
        """加载游戏封面"""
        # Steam 封面 URL
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
    
    def on_delete_clicked(self):
        """删除按钮点击"""
        # 发送信号给父页面
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, HomePage):
                parent = parent.parent()
            if parent:
                parent.delete_game(self.appid, self.source_type)

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

    def _show_more_menu(self):
        menu = RoundMenu(parent=self)
        
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
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, tr("delete"), triggered=self.on_delete_clicked))
        menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))


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
                        if any(x in lower_root for x in ["crack", "fix", "emu", "goldberg", "smartsteam"]):
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


class AsyncWorker(QThread):
    """异步工作线程"""
    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, coro):
        super().__init__()
        self.coro = coro
        self._loop = None
        self._cancelled = False
    
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


def _replace_worker(old_worker):
    """安全停止旧 worker，等待线程真正结束后返回。"""
    if old_worker is not None:
        try:
            if old_worker.isRunning():
                old_worker.cancel()
                old_worker.wait()
            old_worker.deleteLater()
        except RuntimeError:
            pass

class HomePage(ScrollArea):
    """已入库的游戏页面（主页）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        self.setWidgetResizable(True)
        
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
        
        # 加载视图和排序设置（仅同步 combo UI，布局已在上方设置）
        self.load_view_mode_preference()
        self.load_sort_mode_preference()

        # 启动时立即加载游戏列表
        self.load_games()
    
    def showEvent(self, event):
        """页面显示时不再重复加载"""
        super().showEvent(event)
    
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
            
            # 更新名称
            if appid in name_map:
                name = name_map[appid]
                if hasattr(card, 'titleLabel'):
                    card.titleLabel.setText(name)

    
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
            self.all_games_data.sort(key=lambda x: int(x[1].get('appid', '0')) if x[1].get('appid', '0').isdigit() else 0, reverse=True)
            
            # 显示所有游戏
            self.display_games(self.all_games_data)

            # 后台加载缺失的游戏名称
            self._load_missing_names(files_data)
                
        except Exception as e:
            self.stats_label.setText(f"{tr('data_process_failed')}: {str(e)}")
    
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
            
            # 如果游戏名称为空或显示为"名称未找到"，显示更友好的提示
            if not game_name or game_name in ('名称未找到', '获取失败', tr('name_not_found'), tr('fetch_failed')):
                game_name = f"AppID {appid}"
            
            # 根据视图模式创建不同类型的卡片
            if self.current_view_mode == "grid":
                card = GameCardGrid(appid, game_name, source_type, self, mode)
            else:
                card = GameCard(appid, game_name, source_type, self, mode)
            
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
        
        if sort_mode == tr("sort_az"):
            return sorted(games_data, key=lambda x: x[1].get('game_name', f"AppID {x[1].get('appid', '0')}"))
        elif sort_mode == tr("sort_za"):
            return sorted(games_data, key=lambda x: x[1].get('game_name', f"AppID {x[1].get('appid', '0')}"), reverse=True)
        else:  # 默认 - 按AppID降序
            return sorted(games_data, key=lambda x: int(x[1].get('appid', '0')) if x[1].get('appid', '0').isdigit() else 0, reverse=True)
    
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
    
    def delete_game(self, appid, source_type):
        """删除游戏"""
        # 显示确认对话框
        dialog = MessageBox(
            tr("confirm_delete"),
            tr("delete_message", appid),
            self
        )
        
        if dialog.exec():
            # 用户确认删除
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
            self.delete_worker.result_ready.connect(lambda result: self.on_delete_complete(result, appid))
            self.delete_worker.error.connect(self.on_delete_error)
            self.delete_worker.finished.connect(self.delete_worker.deleteLater)
            self.delete_worker.start()
            
            InfoBar.info(
                title=tr("deleting"),
                content=f"{tr('deleting')} AppID {appid}...",
                parent=self.window(),
                position=InfoBarPosition.TOP
            )
    
    @pyqtSlot(object)
    def on_delete_complete(self, result, appid):
        """删除完成"""
        if result.get('success'):
            InfoBar.success(
                title=tr("delete_success"),
                content=f"AppID {appid} {tr('delete_success')}",
                parent=self,
                position=InfoBarPosition.TOP
            )
            # 重新加载游戏列表
            self._games_loaded = False
            self.load_games()
        else:
            InfoBar.error(
                title=tr("delete_failed"),
                content=result.get('message', tr('unknown_error')),
                parent=self,
                position=InfoBarPosition.TOP
            )
    
    @pyqtSlot(str)
    def on_delete_error(self, error):
        """删除失败"""
        InfoBar.error(
            title=tr("delete_failed"),
            content=error,
            parent=self,
            position=InfoBarPosition.TOP
        )

    def toggle_st_version(self, filename, appid):
        """切换ST文件版本模式（自动更新/固定版本）"""
        async def _toggle():
            async with CaiBackend() as backend:
                await backend.initialize()
                result = await backend.toggle_st_version(filename)
                return result
        
        _replace_worker(getattr(self, 'toggle_worker', None))
        self.toggle_worker = AsyncWorker(_toggle())
        self.toggle_worker.result_ready.connect(lambda result: self.on_toggle_st_version_complete(result, appid))
        self.toggle_worker.error.connect(self.on_toggle_st_version_error)
        self.toggle_worker.finished.connect(self.toggle_worker.deleteLater)
        self.toggle_worker.start()
        
        InfoBar.info(
            title="版本切换",
            content=f"正在切换 AppID {appid} 的版本模式...",
            parent=self,
            position=InfoBarPosition.TOP
        )
    
    @pyqtSlot(object)
    def on_toggle_st_version_complete(self, result, appid):
        """ST文件版本切换完成"""
        if result.get('success'):
            InfoBar.success(
                title="切换成功",
                content=result.get('message', '版本模式已切换'),
                parent=self,
                position=InfoBarPosition.TOP
            )
            # 更新对应卡片的版本模式标签
            for card in self.game_cards:
                if hasattr(card, 'appid') and card.appid == appid and hasattr(card, 'source_type') and card.source_type == 'st':
                    # 从消息中判断新的模式
                    message = result.get('message', '')
                    is_fixed = '固定版本' in message
                    card.update_mode_label(is_fixed)
                    break
            
            # 如果切换到了固定版本，检查是否需要补全清单文件
            message = result.get('message', '')
            if '固定版本' in message:
                # 延迟一点执行，让切换完成的提示先显示
                QTimer.singleShot(500, lambda: self._check_and_complete_manifest_after_toggle(appid))
        else:
            InfoBar.error(
                title="切换失败",
                content=result.get('message', '未知错误'),
                parent=self,
                position=InfoBarPosition.TOP
            )
    
    def _check_and_complete_manifest_after_toggle(self, appid):
        """切换固定版本后，检查并补全清单文件"""
        # 读取配置，判断修复模式
        config_path = APP_ROOT / 'config' / 'config.json'
        manifest_mode = "ask"  # 默认询问
        try:
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                manifest_mode = config.get("ST_Fixed_Manifest_Mode", "ask")
        except Exception:
            pass
        
        # 如果设置为从不修复，直接返回
        if manifest_mode == "never":
            return
        
        # 如果设置为询问，显示确认对话框
        if manifest_mode == "ask":
            dialog = MessageBox(
                "修复Manifest",
                f"AppID {appid} 切换到固定版本后可能需要修复manifest文件。\n\n是否现在修复？",
                self
            )
            if not dialog.exec():
                return  # 用户取消
        
        # 执行修复（始终模式或询问模式且用户确认）
        async def _check_and_complete():
            async with CaiBackend() as backend:
                await backend.initialize()
                
                # 检查本地是否已有 manifest 文件
                search_paths = [
                    backend.steam_path / 'config' / 'depotcache',
                    backend.steam_path / 'depotcache'
                ]
                
                # 获取该 AppID 的所有 depot IDs
                depots_info = await backend.get_depots_safe(str(appid))
                if not depots_info:
                    backend.log.info(f"[切换固定版本] 无法获取 AppID {appid} 的 depot 信息，跳过补全")
                    return None
                
                depot_ids = [str(d[0]) for d in depots_info if d[0]]
                
                # 检查是否已存在 manifest 文件
                existing_count = 0
                for depot_id in depot_ids:
                    for search_dir in search_paths:
                        if not search_dir.exists():
                            continue
                        candidates = list(search_dir.glob(f"{depot_id}_*.manifest"))
                        if candidates:
                            existing_count += 1
                            break
                
                # 如果已存在部分 manifest，认为不需要补全
                if existing_count >= len(depot_ids):
                    backend.log.info(f"[切换固定版本] AppID {appid} 已有全部 manifest 文件，无需补全")
                    return None
                
                # 需要补全清单文件
                backend.log.info(f"[切换固定版本] AppID {appid} 缺少 manifest 文件 ({existing_count}/{len(depot_ids)})，开始补全...")
                
                # 调用补全清单文件
                post_result = await backend.complete_manifest_files(str(appid))
                return post_result
        
        def on_complete_result(result):
            if result is None:
                return  # 不需要补全或获取失败
            
            if result.get('success'):
                downloaded = result.get('downloaded', 0)
                total = result.get('total', 0)
                InfoBar.success(
                    title="补全完成",
                    content=f"AppID {appid} 补全完成：{downloaded}/{total}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=3000
                )
            else:
                msg = result.get('message', '补全失败')
                InfoBar.warning(
                    title="补全清单",
                    content=f"AppID {appid} {msg}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=4000
                )
        
        def on_complete_error(error):
            InfoBar.error(
                title="补全失败",
                content=f"AppID {appid} 补全清单时出错: {error}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000
            )
        
        # 启动补全任务
        _replace_worker(getattr(self, '_manifest_complete_worker', None))
        worker = AsyncWorker(_check_and_complete())
        self._manifest_complete_worker = worker
        worker.result_ready.connect(on_complete_result)
        worker.error.connect(on_complete_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()
    
    @pyqtSlot(str)
    def on_toggle_st_version_error(self, error):
        """ST文件版本切换失败"""
        InfoBar.error(
            title="切换失败",
            content=error,
            parent=self,
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
                config["home_sort_mode"] = "az"
            elif sort_mode_text == tr("sort_za"):
                config["home_sort_mode"] = "za"
            else:
                config["home_sort_mode"] = "default"
            
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
        self.moreButton.clicked.connect(self._show_more_menu)
        
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

    def _show_more_menu(self):
        menu = RoundMenu(parent=self)
        
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
        menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))


class SearchResultCardGrid(CardWidget):
    """搜索结果卡片组件 - 网格视图模式"""
    
    def __init__(self, appid, game_name, parent=None):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name
        
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
        self.moreButton.clicked.connect(self._show_more_menu)
        
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

    def _show_more_menu(self):
        menu = RoundMenu(parent=self)
        
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
        menu.exec(self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))


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
            "GMRC",
            "Walftech",
            "Sudama",
            "清单不求人",
            tr("MHub"),
            tr("github_auiowu"),
            "SteamAutoCracks V2",
            "SteamAutoCracks V1",
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
        
        # 修补Manifest选项
        self.patch_manifest_check = CheckBox(tr("patch_manifest"), self)
        self.patch_manifest_check.setChecked(False)
        self.patch_manifest_check.stateChanged.connect(self.on_patch_manifest_changed)
        options_layout.addWidget(self.patch_manifest_check)
        
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
        
        # 加载保存的清单源选择
        self.load_manifest_source_preference()
        
        # 加载视图和排序设置
        self.load_view_mode_preference()
        self.load_sort_mode_preference()
        
        # 加载DLC和修补选项状态
        self.load_add_dlc_preference()
        self.load_patch_key_preference()
        self.load_patch_manifest_preference()
    
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
    
    def on_patch_manifest_changed(self):
        """修补Manifest选项改变时保存状态"""
        self.save_patch_manifest_preference()
    
    def save_patch_manifest_preference(self):
        """保存修补Manifest选项状态"""
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
            
            # 保存修补Manifest选项状态
            config["patch_manifest_default"] = self.patch_manifest_check.isChecked()
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存修补Manifest选项失败: {e}")
    
    def load_patch_manifest_preference(self):
        """加载修补Manifest选项状态"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的修补Manifest选项状态
                patch_manifest_default = config.get("patch_manifest_default", False)
                self.patch_manifest_check.setChecked(patch_manifest_default)
                
        except Exception as e:
            print(f"加载修补Manifest选项失败: {e}")
    
    def __del__(self):
        """析构函数，确保清理所有worker"""
        self.cleanup_workers()
    
    def cleanup_workers(self):
        """清理所有worker线程"""
        for attr in ('search_worker', 'unlock_worker', '_manifest_worker'):
            worker = getattr(self, attr, None)
            if worker:
                if worker.isRunning():
                    worker.cancel()
                    worker.wait(3000)
                worker.deleteLater()
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
            
            # 保存清单源选择
            source_mapping = {
                0: "auto",
                1: "cysaw",
                2: "gmrc",
                3: "walftech",
                4: "sudama",
                5: "buqiuren",
                6: "MHub",
                7: "github_auiowu",
                8: "steamautocracks_v2",
                9: "steamautocracks_v1",
                10: "sac-other",
            }
            config["default_manifest_source"] = source_mapping.get(self.manifest_source_combo.currentIndex(), "auto")
            
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
    
    def load_manifest_source_preference(self):
        """加载清单源选择偏好"""
        try:
            config_path = APP_ROOT / 'config' / 'config.json'
            import json
            
            # 读取配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的清单源
                saved_source = config.get("default_manifest_source", "auto")
                
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
                    "steamautocracks_v2": 8,
                    "steamautocracks_v1": 9,
                    "sac-other": 10,
                }
                
                index = source_mapping.get(saved_source, 0)
                # 断开信号，避免触发保存
                self.manifest_source_combo.currentIndexChanged.disconnect(self.on_manifest_source_changed)
                self.manifest_source_combo.setCurrentIndex(index)
                self.manifest_source_combo.currentIndexChanged.connect(self.on_manifest_source_changed)
                
        except Exception as e:
            print(f"加载清单源偏好失败: {e}")
    
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
                    r = await backend.client.get(
                        "https://store.steampowered.com/api/featuredcategories",
                        params={"cc": "cn", "l": "schinese"},
                        timeout=15
                    )
                    data = r.json()
                    games = []
                    for section in ["top_sellers", "new_releases", "specials"]:
                        items = data.get(section, {}).get("items", [])
                        for item in items:
                            appid = str(item.get("id", ""))
                            name = item.get("name", "")
                            if appid and name and not any(g["appid"] == appid for g in games):
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
        
        if sort_mode == tr("sort_az"):
            return sorted(results, key=lambda x: x['name'])
        elif sort_mode == tr("sort_za"):
            return sorted(results, key=lambda x: x['name'], reverse=True)
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
        patch_manifest = self.patch_manifest_check.isChecked()
        
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
            8: "steamautocracks_v2",
            9: "steamautocracks_v1",
            10: "sac-other",
        }
        tool_type = index_to_source.get(self.manifest_source_combo.currentIndex(), "auto")
        
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
                    # 优化文件下载进度的文字显示
                    if "补全清单文件" in text and value >= 85:
                        # 只有在阶段6（值>=85）时才优化补全清单文件的进度显示
                        if "/" in text:
                            # 格式如 "补全清单文件 3/15：方法1（镜像源）123456_789012.manifest"
                            parts = text.split("：")
                            if len(parts) >= 2:
                                file_info = parts[0]  # "补全清单文件 3/15"
                                method_info = parts[1]  # "方法1（镜像源）123456_789012.manifest"
                                # 提取当前文件和总文件数
                                file_progress = file_info.split(" ")[-1]  # "3/15"
                                # 提取方法信息
                                method_parts = method_info.split("）")
                                method_name = method_parts[0] + "）" if "）" in method_info else method_info
                                # 详细显示文件下载进度
                                detailed_text = f"阶段 6/6：下载清单文件 {file_progress} - {method_name}"
                                self._update_download_progress_state(value, detailed_text)
                                return
                        elif "识别镜像源" in text:
                            # 格式如 "补全清单文件：识别镜像源（共 15 个文件）"
                            # 提取文件总数
                            import re
                            match = re.search(r'共 (\d+) 个文件', text)
                            if match:
                                total_files = match.group(1)
                                self._update_download_progress_state(value, f"阶段 6/6：准备下载 {total_files} 个清单文件")
                            else:
                                self._update_download_progress_state(value, "阶段 6/6：准备下载清单文件")
                            return
                        elif "准备阶段" in text:
                            # 格式如 "补全清单文件：准备阶段（读取 Depot 列表）"
                            self._update_download_progress_state(value, "阶段 6/6：准备下载清单文件")
                            return
                    
                    # 其他进度信息保持原样
                    self._update_download_progress_state(value, text)
                
                # 自动选择模式：依次尝试所有ZIP源
                if tool_type_actual == "auto":
                    auto_sources = [
                        "sudama",
                        "cysaw",
                        "walftech",
                        "MHub",
                        "steamautocracks_v1",
                        "sac-other",
                    ]
                    
                    # 更新进度条状态
                    self._update_download_progress_state(20, f"阶段 3/6：自动选择模式（{len(auto_sources)}个源）")
                    
                    for i, src in enumerate(auto_sources):
                        backend.log.info(f"[自动选择] 正在尝试源: {src}")
                        
                        # 更新进度条显示当前尝试的源，并启用动画进度
                        progress_value = 20 + (i * 60 // len(auto_sources))
                        self._update_download_progress_state(progress_value, f"阶段 3/6：尝试源 {i+1}/{len(auto_sources)} - {src}")
                        # 启用动画进度模式
                        self._progress_animating = True
                        self._progress_animation_value = float(progress_value)
                        
                        ok = False
                        try:
                            ok = await backend.process_zip_source(
                                appid, src, unlocker_type,
                                use_st_auto_update, add_all_dlc, patch_depot_key
                            )
                        except Exception as e:
                            backend.log.warning(f"[自动选择] 源 {src} 失败: {e}")
                        finally:
                            # 禁用动画进度模式
                            self._progress_animating = False
                        
                        if ok:
                            # 主入库成功后，根据选项决定是否补全清单文件
                            if patch_manifest:
                                backend.log.info(f"[自动选择] 源 {src} 成功，开始补全清单文件...")
                                self._update_download_progress_state(85, "阶段 4/6：主入库完成，开始补全清单文件...")
                                post_result = await backend.complete_manifest_files(str(appid))
                                return bool(post_result.get("success", True))
                            else:
                                backend.log.info(f"[自动选择] 源 {src} 成功，跳过补全清单文件（未勾选修补Manifest）")
                                self._update_download_progress_state(90, "阶段 4/6：主入库完成，跳过补全清单文件")
                                return True
                    
                    # 所有源都失败
                    self._update_download_progress_state(80, "阶段 3/6：所有源尝试失败")
                    return False
                
                # 指定源模式
                github_repo_map = {
                    "github_auiowu": "Auiowu/ManifestAutoUpdate",
                }
                zip_sources = ["cysaw", "gmrc", "sac-other", "walftech", "steamautocracks_v2", "steamautocracks_v1", "sudama", "buqiuren", "MHub"]
                
                # 更新进度条状态，并启用动画进度模式
                if tool_type_actual in zip_sources:
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
                    if patch_manifest:
                        backend.log.info(f"主入库成功，开始补全清单文件...")
                        self._update_download_progress_state(58, "阶段 4/6：主入库完成，开始补全清单文件...")
                        post_result = await backend.complete_manifest_files(str(appid))
                        return bool(post_result.get("success", True))
                    else:
                        backend.log.info(f"主入库成功，跳过补全清单文件（未勾选修补Manifest）")
                        self._update_download_progress_state(58, "阶段 4/6：主入库完成，跳过补全清单文件")
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
        else:
            InfoBar.error(
                title=tr("delete_failed"),
                content=tr("process_failed") + "，" + tr("check_logs"),
                parent=bar_parent,
                position=InfoBarPosition.TOP
            )
    
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
    """联机游戏页面 - 支持 DLL 注入 / BAT 脚本两种方式"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("launcherPage")
        self.setWidgetResizable(True)

        self._service: Optional[SystemCoreService] = None
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
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(20, 16, 20, 16)
        mode_layout.setSpacing(10)
        mode_layout.addWidget(BodyLabel(tr("launcher_mode_select"), mode_card))

        self.mode_dll_btn = PushButton(tr("launcher_mode_dll"), mode_card)
        self.mode_bat_btn = PushButton(tr("launcher_mode_bat"), mode_card)
        self.mode_dll_btn.setCheckable(True)
        self.mode_bat_btn.setCheckable(True)
        self.mode_dll_btn.setChecked(True)  # 默认 DLL 模式
        self.mode_dll_btn.clicked.connect(lambda: self._select_mode("dll"))
        self.mode_bat_btn.clicked.connect(lambda: self._select_mode("bat"))

        mode_btn_row = QHBoxLayout()
        mode_btn_row.addWidget(self.mode_dll_btn)
        mode_btn_row.addWidget(self.mode_bat_btn)
        mode_layout.addLayout(mode_btn_row)

        self.mode_desc_label = CaptionLabel(tr("launcher_mode_dll_desc"), mode_card)
        self.mode_desc_label.setWordWrap(True)
        self.mode_desc_label.setTextColor("#606060", "#a0a0a0")
        mode_layout.addWidget(self.mode_desc_label)
        self.mainLayout.addWidget(mode_card)

        # ── 游戏路径卡片 ──
        path_card = CardWidget(self)
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
        if mode == "dll":
            self.mode_desc_label.setText(tr("launcher_mode_dll_desc"))
            self.action_btn.setText(tr("launcher_start"))
            self.action_btn.setIcon(FluentIcon.PLAY)
        else:
            self.mode_desc_label.setText(tr("launcher_mode_bat_desc"))
            self.action_btn.setText(tr("launcher_bat_start"))
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
        if running:
            self.action_btn.setText(tr("launcher_stop"))
            self.action_btn.setIcon(FluentIcon.CLOSE)
            self.status_label.setText(tr("launcher_status_running"))
            self.status_label.setTextColor("#f59e0b", "#f59e0b")
        else:
            if self._current_mode == "dll":
                self.action_btn.setText(tr("launcher_start"))
            else:
                self.action_btn.setText(tr("launcher_bat_start"))
            self.action_btn.setIcon(FluentIcon.PLAY)
            self.status_label.setText(tr("launcher_status_ready"))
            self.status_label.setTextColor("#10b981", "#10b981")

    def _on_action(self):
        if self._running:
            self._stop_service()
        elif self._current_mode == "dll":
            self._start_dll_service()
        else:
            self._start_bat_service()

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



class SettingsPage(ScrollArea):
    """设置页面"""
    
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
        self.sidebar_group = None

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
        
        # 根据主题模式设置颜色映射
        if isDarkTheme():
            color_map = {
                "DEBUG": "#888888",
                "INFO": "#cccccc",
                "WARNING": "#f59e0b",
                "ERROR": "#ef4444",
                "CRITICAL": "#dc2626",
            }
        else:
            color_map = {
                "DEBUG": "#666666",
                "INFO": "#333333",
                "WARNING": "#d97706",
                "ERROR": "#dc2626",
                "CRITICAL": "#991b1b",
            }
        
        color = color_map.get(level, "#cccccc" if isDarkTheme() else "#333333")
        self.log_view.append(f"<span style='color:{color}'>{msg}</span>")
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

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

        self.debug_check = SwitchButton()
        self.debug_check.setChecked(False)
        app_config_card.addGroup(FluentIcon.DEVELOPER_TOOLS, tr("debug_mode"), tr("debug_mode_hint"), self.debug_check)

        self.logging_check = SwitchButton()
        self.logging_check.setChecked(True)
        app_config_card.addGroup(FluentIcon.SAVE, tr("save_log_files"), tr("save_log_files_hint"), self.logging_check)

        self.unlocker_combo = ComboBox()
        self.unlocker_combo.addItems([tr("auto_detect"), tr("force_steamtools"), tr("force_greenluma")])
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
        self.lang_combo.addItems(["系统默认", "简体中文", "English", "Français", "Русский", "Deutsch", "日本語", "繁體中文"])
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
        lang_map = {0: "system", 1: "zh_CN", 2: "en_US", 3: "fr_FR", 4: "ru_RU", 5: "de_DE", 6: "ja_JP", 7: "zh_TW"}
        lang_name_map = {0: "系统默认", 1: "简体中文", 2: "English", 3: "Français", 4: "Русский", 5: "Deutsch", 6: "日本語", 7: "繁體中文"}
        selected_lang = lang_map.get(index, "system")
        lang_name = lang_name_map.get(index, "系统默认")
        
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
            # 用户取消，恢复原来的选择
            current_lang = self.load_language_setting()
            reverse_map = {"system": 0, "zh_CN": 1, "en_US": 2, "fr_FR": 3, "ru_RU": 4, "de_DE": 5, "ja_JP": 6, "zh_TW": 7}
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
                # 生成具体的下载链接格式：https://github.com/zhouchentao666/Fluent-Install/releases/download/{version}/FluentInstall.exe
                download_url = f"https://github.com/{GITHUB_REPO}/releases/download/{latest_version}/FluentInstall.exe"
                
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
            self.on_config_loaded(config)
        except Exception as e:
            self.on_load_error(str(e))
    
    @pyqtSlot(object)
    def on_config_loaded(self, config):
        """配置加载完成"""
        if config:
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
                is_fixed = config.get("ST_Fixed_Version", True)  # 默认固定版本（与后端 DEFAULT_CONFIG 保持一致）
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
                        self.lang_combo.setCurrentIndex(0)  # 系统默认，实际为英文
                elif lang == "zh_CN":
                    self.lang_combo.setCurrentIndex(1)
                elif lang == "en_US":
                    self.lang_combo.setCurrentIndex(2)
                elif lang == "fr_FR":
                    self.lang_combo.setCurrentIndex(3)
                elif lang == "ru_RU":
                    self.lang_combo.setCurrentIndex(4)
                elif lang == "de_DE":
                    self.lang_combo.setCurrentIndex(5)
                elif lang == "ja_JP":
                    self.lang_combo.setCurrentIndex(6)
                elif lang == "zh_TW":
                    self.lang_combo.setCurrentIndex(7)
                else:
                    self.lang_combo.setCurrentIndex(2)  # 默认英文
                
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
                
                # 应用窗口特效
                if hasattr(self.window(), 'apply_window_effect'):
                    self.window().apply_window_effect(window_effect)
    
    @pyqtSlot(str)
    def on_load_error(self, error):
        """加载失败"""
        InfoBar.error(
                title=tr("load_config_failed"),
                content=error,
            parent=self,
            position=InfoBarPosition.TOP
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
                unlocker_map = {0: "auto", 1: "steamtools", 2: "greenluma"}
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
            lang_map = {0: "system", 1: "zh_CN", 2: "en_US", 3: "fr_FR", 4: "ru_RU", 5: "de_DE", 6: "ja_JP", 7: "zh_TW"}
            config["language"] = lang_map.get(self.lang_combo.currentIndex(), "system")
            
            # 保存窗口特效
            if self.effect_combo:
                effect_map = {0: "none", 1: "mica"}
                config["window_effect"] = effect_map.get(self.effect_combo.currentIndex(), "none")
            
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
        self.settings_page = SettingsPage(self)

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

        # 根据配置切换到默认界面
        self.switch_to_default_page()

        # 启动后台预构建设置页 UI，避免首次点击卡顿
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, self._prebuild_settings)
    
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

    def _prebuild_settings(self):
        """应用启动后预构建设置页 UI 并预加载配置，消除首次点击卡顿"""
        if not self.settings_page._ui_built:
            self.settings_page._ui_built = True
            self.settings_page._build_ui()
        if not self.settings_page._config_loaded:
            self.settings_page._config_loaded = True
            self.settings_page.load_config()
            self.settings_page._setup_auto_save_listeners()
    
    def on_restart_steam(self):
        """重启 Steam"""
        dialog = MessageBox(
            tr("restart_steam_confirm"),
            tr("restart_steam_message"),
            self
        )
        
        if dialog.exec():
            async def _restart():
                async with CaiBackend() as backend:
                    await backend.initialize()
                    success = backend.restart_steam()
                    return success

            _replace_worker(getattr(self, 'restart_steam_worker', None))
            self.restart_steam_worker = AsyncWorker(_restart())
            self.restart_steam_worker.result_ready.connect(self.on_restart_complete)
            self.restart_steam_worker.error.connect(self.on_restart_error)
            self.restart_steam_worker.finished.connect(self.restart_steam_worker.deleteLater)
            self.restart_steam_worker.start()
            
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
        if platform.system() != 'Windows':
            return

        if effect_type == "mica":
            # 启用云母特效（仅Windows 11）
            self.setMicaEffectEnabled(True)
            # 不设置全局透明背景，避免标题栏出现问题
        elif effect_type == "none":
            # 禁用特效
            self.setMicaEffectEnabled(False)
        
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

