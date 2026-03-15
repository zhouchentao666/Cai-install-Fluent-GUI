"""
Cai Install - Fluent Design 版本
使用 PyQt-Fluent-Widgets 框架
"""
import sys
import asyncio
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QUrl, QLocale, QTranslator
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QIcon, QPixmap, QFont
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
    SpinBox, HyperlinkButton
)

# 导入后端
from backend import CaiBackend



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
    }
}

def load_theme_config():
    """加载主题配置"""
    try:
        config_path = Path.cwd() / 'config.json'
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
        config_path = Path.cwd() / 'config.json'
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
        "theme_mode": "主题模式",
        "theme_color": "主题色",
        "language": "语言",
        "save_settings": "保存设置",
        "about": "关于",
        "thanks": "鸣谢",
        "restart_required": "需要重启",
        "language_changed": "语言已更改为 {0}\n\n是否立即重启应用以应用更改？",
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
        "effect_mica": "云母",
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
        "auto_search_github": "自动搜索GitHub",
        "swa_v2": "SWA V2",
        "cysaw": "Cysaw",
        "furcate": "Furcate",
        "walftech": "Walftech",
        "steamdatabase": "steamdatabase",
        "steamautocracks_v2": "SteamAutoCracks V2 (仅密钥)",
        "sudama": "Sudama库 (仅密钥)",
        "buqiuren": "清单不求人库 (仅清单)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_sac": "GitHub (SAC)",
        "restart_steam_title": "重启 Steam",
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
        "about_text": "Cai Install - Fluent Design 版本\n\n版本: 1.3\n\n这是一个基于 PyQt6-Fluent-Widgets 的现代化 Steam 游戏解锁工具。\n\n功能特性:\n• Fluent Design 设计风格\n• 支持多种清单源\n• 游戏搜索和入库\n• 已入库游戏管理\n• 主题自定义\n\n项目地址: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "特别鸣谢\n\n开发者:\n• zhouchentao666 - 制作人员\n\n开源项目:\n• PyQt6 - Qt6 Python 绑定\n• PyQt-Fluent-Widgets - Fluent Design 组件库\n• Cai-install-Web-GUI - 原始项目作者\n• httpx - 异步 HTTP 客户端\n\n清单源提供:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• 清单不求人\n\n社区与联系:\n• GitHub: https://github.com/zhouchentao666/Fluent-Install\n• 加入 Q 群: https://qm.qq.com/q/gtTLap5Jw4\n• TG 群组: https://t.me/+vTrqXKpRJE9kNmVl\n• TG 频道: https://t.me/FluentInstall\n• Discord: https://discord.gg/2qh68QRMuA\n\n感谢所有为本项目做出贡献的开发者和用户！",
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
        "effect_mica": "Mica",
        "default_blue": "Default Blue (#0078d4)",
        "purple": "Purple (#9b4dca)",
        "green": "Green (#10893e)",
        "orange": "Orange (#ff8c00)",
        "red": "Red (#e81123)",
        "pink": "Pink (#e3008c)",
        "tip_source_fail": "Tip: If one source fails, try another",
        "auto_search_github": "Auto Search GitHub",
        "swa_v2": "SWA V2",
        "cysaw": "Cysaw",
        "furcate": "Furcate",
        "walftech": "Walftech",
        "steamdatabase": "steamdatabase",
        "steamautocracks_v2": "SteamAutoCracks V2 (Keys Only)",
        "sudama": "Sudama Library (Keys Only)",
        "buqiuren": "Manifest Helper Library (Manifest Only)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_sac": "GitHub (SAC)",
        "restart_steam_title": "Restart Steam",
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
        "about_text": "Cai Install - Fluent Design Version\n\nVersion: 1.3\n\nThis is a modern Steam game unlocking tool based on PyQt6-Fluent-Widgets.\n\nFeatures:\n• Fluent Design style\n• Support for multiple manifest sources\n• Game search and adding\n• Installed games management\n• Theme customization\n\nProject URL: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Special Thanks\n\nDevelopers:\n• zhouchentao666 - Developer\n\nOpen Source Projects:\n• PyQt6 - Qt6 Python Bindings\n• PyQt-Fluent-Widgets - Fluent Design Component Library\n• Cai-install-Web-GUI - Original Project Author\n• httpx - Async HTTP Client\n\nManifest Sources:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Manifest Helper Library\n\nThanks to all developers and users who contributed to this project!",
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
        "effect_mica": "Mica",
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
        "auto_search_github": "Recherche automatique GitHub",
        "swa_v2": "SWA V2",
        "cysaw": "Cysaw",
        "furcate": "Furcate",
        "walftech": "Walftech",
        "steamdatabase": "steamdatabase",
        "steamautocracks_v2": "SteamAutoCracks V2 (Clés seulement)",
        "sudama": "Bibliothèque Sudama (Clés seulement)",
        "buqiuren": "Bibliothèque d'aide de manifeste (Manifeste seulement)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_sac": "GitHub (SAC)",
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
        "about_text": "Cai Install - Version Fluent Design\n\nVersion: 1.3\n\nCeci est un outil de déverrouillage de jeu Steam moderne basé sur PyQt6-Fluent-Widgets.\n\nFonctionnalités:\n• Style Fluent Design\n• Support de plusieurs sources de manifestes\n• Recherche et ajout de jeux\n• Gestion des jeux installés\n• Personnalisation du thème\n\nURL du projet: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Remerciements spéciaux\n\nDéveloppeurs:\n• zhouchentao666 - Développeur\n\nProjets open source:\n• PyQt6 - Bindings Python Qt6\n• PyQt-Fluent-Widgets - Bibliothèque de composants Fluent Design\n• Cai-install-Web-GUI - Auteur du projet original\n• httpx - Client HTTP asynchrone\n\nSources de manifestes:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Bibliothèque d'aide de manifeste\n\nMerci à tous les développeurs et utilisateurs qui ont contribué à ce projet!",
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
        "effect_mica": "Мика",
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
        "auto_search_github": "Автопоиск GitHub",
        "swa_v2": "SWA V2",
        "cysaw": "Cysaw",
        "furcate": "Furcate",
        "walftech": "Walftech",
        "steamdatabase": "steamdatabase",
        "steamautocracks_v2": "SteamAutoCracks V2 (Только ключи)",
        "sudama": "Библиотека Sudama (Только ключи)",
        "buqiuren": "Библиотека помощи манифеста (Только манифест)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_sac": "GitHub (SAC)",
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
        "about_text": "Cai Install - Версия Fluent Design\n\nВерсия: 1.3\n\nЭто современный инструмент разблокировки игр Steam на основе PyQt6-Fluent-Widgets.\n\nФункции:\n• Стиль Fluent Design\n• Поддержка нескольких источников манифестов\n• Поиск и добавление игр\n• Управление установленными играми\n• Настройка темы\n\nURL проекта: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Особая благодарность\n\nРазработчики:\n• zhouchentao666 - Разработчик\n\nПроекты с открытым исходным кодом:\n• PyQt6 - Привязки Python Qt6\n• PyQt-Fluent-Widgets - Библиотека компонентов Fluent Design\n• Cai-install-Web-GUI - Автор оригинального проекта\n• httpx - Асинхронный HTTP клиент\n\nИсточники манифестов:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Библиотека помощи манифеста\n\nСпасибо всем разработчикам и пользователям, внесшим вклад в этот проект!",
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
        "effect_mica": "Mica",
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
        "auto_search_github": "Automatische GitHub-Suche",
        "swa_v2": "SWA V2",
        "cysaw": "Cysaw",
        "furcate": "Furcate",
        "walftech": "Walftech",
        "steamdatabase": "steamdatabase",
        "steamautocracks_v2": "SteamAutoCracks V2 (Nur Schlüssel)",
        "sudama": "Sudama-Bibliothek (Nur Schlüssel)",
        "buqiuren": "Manifest-Hilfsbibliothek (Nur Manifest)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_sac": "GitHub (SAC)",
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
        "about_text": "Cai Install - Fluent Design Version\n\nVersion: \n1.3\nDies ist ein modernes Steam-Spiel-Unlocking-Tool basierend auf PyQt6-Fluent-Widgets.\n\nFunktionen:\n• Fluent Design Stil\n• Unterstützung für mehrere Manifest-Quellen\n• Spielsuche und -hinzufügen\n• Verwaltung installierter Spiele\n• Themen-Anpassung\n\nProjekt-URL: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "Besondere Danksagung\n\nEntwickler:\n• zhouchentao666 - Entwickler\n\nOpen-Source-Projekte:\n• PyQt6 - Qt6 Python Bindings\n• PyQt-Fluent-Widgets - Fluent Design Komponentenbibliothek\n• Cai-install-Web-GUI - Originalprojekt-Autor\n• httpx - Asynchroner HTTP-Client\n\nManifest-Quellen:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• Manifest-Hilfsbibliothek\n\nVielen Dank an alle Entwickler und Benutzer, die zu diesem Projekt beigetragen haben!",
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
        "effect_mica": "マイカ",
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
        "swa_v2": "SWA V2",
        "cysaw": "Cysaw",
        "furcate": "Furcate",
        "walftech": "Walftech",
        "steamdatabase": "steamdatabase",
        "steamautocracks_v2": "SteamAutoCracks V2 (キーのみ)",
        "sudama": "Sudamaライブラリ (キーのみ)",
        "buqiuren": "マニフェストヘルパーライブラリ (マニフェストのみ)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_sac": "GitHub (SAC)",
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
        "about_text": "Cai Install - Fluent Design バージョン\n\nバージョン: 1.3\n\nこれはPyQt6-Fluent-WidgetsをベースにしたモダンなSteamゲームアンロックツールです。\n\n機能:\n• Fluent Designスタイル\n• 複数のマニフェストソースをサポート\n• ゲーム検索と追加\n• インストール済みゲームの管理\n• テーマカスタマイズ\n\nプロジェクトURL: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "特別な感謝\n\n開発者:\n• zhouchentao666 - 開発者\n\nオープンソースプロジェクト:\n• PyQt6 - Qt6 Pythonバインディング\n• PyQt-Fluent-Widgets - Fluent Designコンポーネントライブラリ\n• Cai-install-Web-GUI - オリジナルプロジェクト作成者\n• httpx - 非同期HTTPクライアント\n\nマニフェストソース:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• マニフェストヘルパーライブラリ\n\nこのプロジェクトに貢献してくれたすべての開発者とユーザーの皆様に感謝します！",
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
        "effect_mica": "雲母",
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
        "auto_search_github": "自動搜尋GitHub",
        "swa_v2": "SWA V2",
        "cysaw": "Cysaw",
        "furcate": "Furcate",
        "walftech": "Walftech",
        "steamdatabase": "steamdatabase",
        "steamautocracks_v2": "SteamAutoCracks V2 (僅金鑰)",
        "sudama": "Sudama 資料庫 (僅金鑰)",
        "buqiuren": "清單不求人資料庫 (僅清單)",
        "github_auiowu": "GitHub (Auiowu)",
        "github_sac": "GitHub (SAC)",
        "restart_steam_title": "重新啟動 Steam",
        "restart_steam_confirm_message": "確定要重新啟動 Steam 嗎？\n\n這將關閉目前執行中的 Steam 並重新啟動。",
        
        # 缺失的翻譯鍵
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
        "about_text": "Cai Install - Fluent Design 版本\n\n版本: 1.3\n\n這是一套基於 PyQt6-Fluent-Widgets 的現代化 Steam 遊戲解鎖工具。\n\n功能特色:\n• Fluent Design 設計風格\n• 支援多種清單來源\n• 遊戲搜尋與入库\n• 已入库遊戲管理\n• 佈景主題自訂\n\n專案位址: https://github.com/zhouchentao666/Cai-install-Fluent-GUI",
        "thanks_text": "特別感謝\n\n開發者:\n• zhouchentao666 - 製作人員\n\n開源專案:\n• PyQt6 - Qt6 Python 綁定\n• PyQt-Fluent-Widgets - Fluent Design 元件庫\n• Cai-install-Web-GUI - 原始專案作者\n• httpx - 非同步 HTTP 用戶端\n\n清單來源提供:\n• SWA V2\n• Cysaw\n• Furcate\n• Walftech\n• steamdatabase\n• SteamAutoCracks\n• Sudama\n• 清單不求人\n\n感謝所有為本專案貢獻的開發者與使用者！",
    },
}

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
    
    def __init__(self, appid, game_name, source_type, parent=None):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name
        self.source_type = source_type  # 'st' 或 'gl'
        
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
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        
        # 游戏标题
        # 如果游戏名称为空或显示为"名称未找到"等，显示AppID
        display_name = game_name
        if not game_name or game_name == '名称未找到' or game_name == '获取失败' or game_name == tr('unknown_game'):
            display_name = f"AppID: {appid}"
        self.titleLabel = BodyLabel(display_name, self)
        self.titleLabel.setWordWrap(False)
        
        # AppID 和来源
        source_text = "SteamTools" if source_type == "st" else "GreenLuma"
        self.infoLabel = CaptionLabel(f"AppID: {appid} | {source_text}", self)
        self.infoLabel.setTextColor("#606060", "#d2d2d2")
        
        # 删除按钮
        self.deleteButton = TransparentToolButton(FluentIcon.DELETE, self)
        self.deleteButton.setFixedSize(32, 32)
        self.deleteButton.setToolTip(tr("delete"))
        self.deleteButton.clicked.connect(self.on_delete_clicked)
        
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
        self.hBoxLayout.addWidget(self.deleteButton, 0, Qt.AlignmentFlag.AlignRight)
        
        # 加载封面（最后执行）
        self.load_cover()
    
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


class GameCardGrid(CardWidget):
    """游戏卡片组件 - 网格视图模式"""
    
    def __init__(self, appid, game_name, source_type, parent=None):
        super().__init__(parent)
        self.appid = appid
        self.game_name = game_name
        self.source_type = source_type  # 'st' 或 'gl'
        
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
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        
        # 游戏标题
        display_name = game_name
        if not game_name or game_name == '名称未找到' or game_name == '获取失败' or game_name == tr('unknown_game'):
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
        
        # 删除按钮
        self.deleteButton = TransparentToolButton(FluentIcon.DELETE, self)
        self.deleteButton.setFixedSize(32, 32)
        self.deleteButton.setToolTip(tr("delete"))
        self.deleteButton.clicked.connect(self.on_delete_clicked)
        
        # 设置布局
        self.setFixedSize(200, 250)  # 稍微减小高度
        
        # 添加组件到布局 - 优化间距
        self.vBoxLayout.addWidget(self.coverLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(5)  # 封面和标题之间的小间距
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(3)  # 标题和信息之间的小间距
        self.vBoxLayout.addWidget(self.infoLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(8)  # 信息和按钮之间的适中间距
        self.vBoxLayout.addWidget(self.deleteButton, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(5)  # 底部小间距
        
        # 加载封面（最后执行）
        self.load_cover()
    
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


class AsyncWorker(QThread):
    """异步工作线程"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, coro):
        super().__init__()
        self.coro = coro
        self._loop = None
    
    def run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            result = self._loop.run_until_complete(self.coro)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # 确保正确清理事件循环
            if self._loop:
                try:
                    # 取消所有pending任务
                    pending = asyncio.all_tasks(self._loop) if hasattr(asyncio, 'all_tasks') else []
                    if pending:
                        for task in pending:
                            task.cancel()
                        self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    # 关闭事件循环
                    if not self._loop.is_closed():
                        self._loop.close()
                except Exception:
                    pass
                finally:
                    self._loop = None

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
            self.current_view_mode = "list"
            self.card_layout = self.list_layout
            self.card_container.setLayout(self.list_layout)
        
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
    
    def showEvent(self, event):
        """页面显示时加载游戏列表"""
        super().showEvent(event)
        if not self._games_loaded:
            self._games_loaded = True
            self.load_games()
    
    def load_games(self):
        """加载游戏列表"""
        async def _load():
            async with CaiBackend() as backend:
                await backend.initialize()
                files_data = await backend.get_managed_files()
                return files_data
        
        self.worker = AsyncWorker(_load())
        self.worker.finished.connect(self.on_games_loaded)
        self.worker.error.connect(self.on_load_error)
        self.worker.start()
    
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
            self.worker.finished.connect(lambda: self.on_refresh_complete())
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
            
            # 如果游戏名称为空或显示为"名称未找到"，显示更友好的提示
            if not game_name or game_name == '名称未找到' or game_name == '获取失败':
                game_name = f"AppID {appid}"
            
            # 根据视图模式创建不同类型的卡片
            if self.current_view_mode == "grid":
                card = GameCardGrid(appid, game_name, source_type, self)
            else:
                card = GameCard(appid, game_name, source_type, self)
            
            self.card_layout.addWidget(card)
            self.game_cards.append(card)
        
        if not sorted_games:
            empty_label = BodyLabel(tr("no_games"), self)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(empty_label)
            self.game_cards.append(empty_label)
    

    
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
            
            self.delete_worker = AsyncWorker(_delete())
            self.delete_worker.finished.connect(lambda result: self.on_delete_complete(result, appid))
            self.delete_worker.error.connect(self.on_delete_error)
            self.delete_worker.start()
            
            InfoBar.info(
                title=tr("deleting"),
                content=f"{tr('deleting')} AppID {appid}...",
                parent=self,
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
    
    def save_view_mode_preference(self):
        """保存视图模式设置"""
        try:
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
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
            config_path = Path.cwd() / 'config.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get(key, "list")
        except Exception:
            pass
        return "list"

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
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
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
            config_path = Path.cwd() / 'config.json'
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
            config_path = Path.cwd() / 'config.json'
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
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        
        # 游戏标题
        self.titleLabel = BodyLabel(game_name, self)
        self.titleLabel.setWordWrap(False)
        
        # AppID
        self.infoLabel = CaptionLabel(f"AppID: {appid}", self)
        self.infoLabel.setTextColor("#606060", "#d2d2d2")
        
        # 入库按钮
        self.selectButton = PrimaryPushButton("入库", self)
        self.selectButton.setFixedSize(80, 32)
        self.selectButton.clicked.connect(self.on_select_clicked)
        
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
        
        # 加载封面
        self.load_cover()
    
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
                # 直接调用入库，传入当前游戏信息
                parent.unlock_game_direct(self.appid, self.game_name)


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
        self.coverLabel.setStyleSheet("border-radius: 4px; background: #2a2a2a;")
        
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
        
        # 入库按钮
        self.selectButton = PrimaryPushButton("入库", self)
        self.selectButton.setFixedSize(80, 32)
        self.selectButton.clicked.connect(self.on_select_clicked)
        
        # 设置布局
        self.setFixedSize(200, 250)  # 稍微减小高度
        
        # 添加组件到布局 - 优化间距
        self.vBoxLayout.addWidget(self.coverLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(5)  # 封面和标题之间的小间距
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(3)  # 标题和信息之间的小间距
        self.vBoxLayout.addWidget(self.infoLabel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(8)  # 信息和按钮之间的适中间距
        self.vBoxLayout.addWidget(self.selectButton, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addSpacing(5)  # 底部小间距
        
        # 加载封面
        self.load_cover()
    
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
        # 发送信号给父页面
        if self.parent():
            parent = self.parent()
            while parent and not isinstance(parent, SearchPage):
                parent = parent.parent()
            if parent:
                parent.unlock_game_direct(self.appid, self.game_name)


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
        self.search_input.textChanged.connect(self.on_search_text_changed)
        search_row_layout.addWidget(self.search_input)
        
        # 视图模式选择
        self.view_mode_label = QLabel(tr("view_mode") + ":", self)
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
        self.manifest_source_combo = ComboBox(self)
        self.manifest_source_combo.addItems([
            "DLCSteamAutoCracks V2",
            "SWA V2 (printedwaste)", 
            "Cysaw",
            "Furcate", 
            "Walftech",
            "SteamDatabase",
            "Sudama",
            "清单不求人"
        ])
        self.manifest_source_combo.setCurrentIndex(0)  # 默认选择 SteamAutoCracks V2
        self.manifest_source_combo.setFixedWidth(200)
        self.manifest_source_combo.currentIndexChanged.connect(self.on_manifest_source_changed)
        options_layout.addWidget(self.manifest_source_label)
        options_layout.addWidget(self.manifest_source_combo)
        options_layout.addSpacing(20)
        
        # 选项
        self.add_dlc_check = CheckBox(tr("add_all_dlc"), self)
        self.add_dlc_check.setChecked(False)
        self.add_dlc_check.stateChanged.connect(self.on_add_dlc_changed)
        options_layout.addWidget(self.add_dlc_check)
        
        self.patch_key_check = CheckBox(tr("patch_depot_key"), self)
        self.patch_key_check.setChecked(False)
        self.patch_key_check.stateChanged.connect(self.on_patch_key_changed)
        options_layout.addWidget(self.patch_key_check)
        
        options_layout.addStretch(1)
        layout.addLayout(options_layout)
        
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
            self.current_view_mode = "list"
            self.results_layout = self.list_results_layout
            self.results_container.setLayout(self.list_results_layout)
        
        layout.addWidget(self.results_container)
        layout.addStretch(1)
        
        # 设置透明背景
        self.setStyleSheet("SearchPage { background: transparent; }")
        container.setStyleSheet("QWidget#searchContainer { background: transparent; }")
        
        # 状态变量
        self.search_worker = None
        self.unlock_worker = None
        self.result_cards = []
        self.search_timer = None
        self.search_results = []  # 存储搜索结果用于排序
        
        # 加载保存的清单源选择
        self.load_manifest_source_preference()
        
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
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
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
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的DLC选项状态
                add_dlc_default = config.get("add_all_dlc_default", False)
                self.add_dlc_check.setChecked(add_dlc_default)
                
        except Exception as e:
            print(f"加载DLC选项失败: {e}")
    
    def save_patch_key_preference(self):
        """保存修补Key选项状态"""
        try:
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
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
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的修补Key选项状态
                patch_key_default = config.get("patch_depot_key_default", False)
                self.patch_key_check.setChecked(patch_key_default)
                
        except Exception as e:
            print(f"加载修补Key选项失败: {e}")
    
    def __del__(self):
        """析构函数，确保清理所有worker"""
        self.cleanup_workers()
    
    def cleanup_workers(self):
        """清理所有worker线程"""
        # 清理搜索worker
        if hasattr(self, 'search_worker') and self.search_worker:
            if self.search_worker.isRunning():
                self.search_worker.quit()
                self.search_worker.wait(1000)  # 最多等待1秒
            self.search_worker.deleteLater()
            self.search_worker = None
        
        # 清理解锁worker
        if hasattr(self, 'unlock_worker') and self.unlock_worker:
            if self.unlock_worker.isRunning():
                self.unlock_worker.quit()
                self.unlock_worker.wait(1000)  # 最多等待1秒
            self.unlock_worker.deleteLater()
            self.unlock_worker = None
        
        # 清理清单源保存worker
        if hasattr(self, '_manifest_worker') and self._manifest_worker:
            if self._manifest_worker.isRunning():
                self._manifest_worker.quit()
                self._manifest_worker.wait(1000)  # 最多等待1秒
            self._manifest_worker.deleteLater()
            self._manifest_worker = None
        
        # 清理定时器
        if hasattr(self, 'search_timer') and self.search_timer:
            self.search_timer.stop()
            self.search_timer.deleteLater()
            self.search_timer = None
    
    def on_search_text_changed(self):
        """搜索文本变化时自动搜索"""
        # 延迟搜索，避免频繁搜索
        if self.search_timer:
            self.search_timer.stop()
        else:
            from PyQt6.QtCore import QTimer
            self.search_timer = QTimer()
            self.search_timer.timeout.connect(self.on_search)
            self.search_timer.setSingleShot(True)
        
        # 延迟500ms搜索
        self.search_timer.start(500)
    
    def on_manifest_source_changed(self):
        """清单源选择改变时保存偏好"""
        self.save_manifest_source_preference()
    
    def save_manifest_source_preference(self):
        """保存清单源选择偏好"""
        async def _save():
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 保存清单源选择
            source_mapping = {
                0: "steamautocracks_v2",
                1: "printedwaste", 
                2: "cysaw",
                3: "furcate",
                4: "walftech",
                5: "steamdatabase",
                6: "sudama",
                7: "buqiuren"
            }
            config["default_manifest_source"] = source_mapping.get(self.manifest_source_combo.currentIndex(), "steamautocracks_v2")
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        
        # 使用异步worker保存，并确保正确清理
        if hasattr(self, '_manifest_worker') and self._manifest_worker and self._manifest_worker.isRunning():
            self._manifest_worker.quit()
            self._manifest_worker.wait()
        
        self._manifest_worker = AsyncWorker(_save())
        self._manifest_worker.finished.connect(self._on_manifest_save_complete)
        self._manifest_worker.error.connect(self._on_manifest_save_error)
        self._manifest_worker.start()
    
    def _on_manifest_save_complete(self, result):
        """清单源保存完成"""
        # 清理worker引用
        if hasattr(self, '_manifest_worker'):
            self._manifest_worker.deleteLater()
            self._manifest_worker = None
    
    def _on_manifest_save_error(self, error):
        """清单源保存失败"""
        print(f"保存清单源偏好失败: {error}")
        # 清理worker引用
        if hasattr(self, '_manifest_worker'):
            self._manifest_worker.deleteLater()
            self._manifest_worker = None
    
    def load_manifest_source_preference(self):
        """加载清单源选择偏好"""
        try:
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取保存的清单源
                saved_source = config.get("default_manifest_source", "steamautocracks_v2")
                
                # 映射到combo索引
                source_mapping = {
                    "steamautocracks_v2": 0,
                    "printedwaste": 1, 
                    "cysaw": 2,
                    "furcate": 3,
                    "walftech": 4,
                    "steamdatabase": 5,
                    "sudama": 6,
                    "buqiuren": 7
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
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
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
            config_path = Path.cwd() / 'config.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get(key, "list")
        except Exception:
            pass
        return "list"

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
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
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
            config_path = Path.cwd() / 'config.json'
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
    
    def on_search(self):
        """搜索游戏"""
        query = self.search_input.text().strip()
        if not query:
            # 清空结果
            for card in self.result_cards:
                card.deleteLater()
            self.result_cards.clear()
            return
        
        # 清空之前的结果卡片
        for card in self.result_cards:
            card.deleteLater()
        self.result_cards.clear()
        
        # 显示进度（简化版本，无进度环）
        # 这里可以添加简单的加载提示
        
        async def _search():
            async with CaiBackend() as backend:
                await backend.initialize()
                
                # 尝试提取 AppID
                appid = backend.extract_app_id(query)
                if appid:
                    # 直接是 AppID
                    return {'type': 'appid', 'appid': appid}
                else:
                    # 搜索游戏名称
                    results = await backend.find_appid_by_name(query)
                    return {'type': 'search', 'results': results}
        
        # 确保之前的搜索worker已清理
        if hasattr(self, 'search_worker') and self.search_worker and self.search_worker.isRunning():
            self.search_worker.quit()
            self.search_worker.wait()
        
        self.search_worker = AsyncWorker(_search())
        self.search_worker.finished.connect(self.on_search_complete)
        self.search_worker.error.connect(self.on_search_error)
        self.search_worker.start()
    

    
    @pyqtSlot(object)
    def on_search_complete(self, result):
        """搜索完成"""
        # 清理搜索worker引用
        if hasattr(self, 'search_worker') and self.search_worker:
            self.search_worker.deleteLater()
            self.search_worker = None
        
        # 无进度环，直接处理结果
        
        if result['type'] == 'appid':
            # 直接是 AppID，自动开始入库
            self.unlock_game_direct(result['appid'], None)
        else:
            # 搜索结果
            results = result['results']
            if not results:
                InfoBar.warning(
                    title=tr("game_not_found"),
                    content=tr("game_not_found"),
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                return
            
            # 存储搜索结果
            self.search_results = results
            
            # 显示搜索结果
            self.display_search_results(results)
    
    def display_search_results(self, results):
        """显示搜索结果"""
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
        
        # 重新添加到布局（title=0, search_row=1, options=2, results=3）
        self.main_layout.insertWidget(3, self.results_container)
        
        # 保存视图模式偏好
        self.save_view_mode_preference()
        
        # 重新显示搜索结果
        if current_results:
            self.display_search_results(current_results)
    
    def on_sort_changed(self):
        """排序方式改变"""
        # 保存排序模式偏好
        self.save_sort_mode_preference()
        
        # 重新显示搜索结果
        if self.search_results:
            self.display_search_results(self.search_results)
    
    def save_sort_mode_preference(self):
        """保存排序模式设置"""
        try:
            config_path = Path.cwd() / 'config.json'
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
        # 清理搜索worker引用
        if hasattr(self, 'search_worker') and self.search_worker:
            self.search_worker.deleteLater()
            self.search_worker = None
        
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
        
        # 获取用户选择的清单源
        source_mapping = {
            "SteamAutoCracks V2": "steamautocracks_v2",
            "SWA V2 (printedwaste)": "printedwaste",
            "Cysaw": "cysaw", 
            "Furcate": "furcate",
            "Walftech": "walftech",
            "SteamDatabase": "steamdatabase",
            "Sudama": "sudama",
            "清单不求人": "buqiuren"
        }
        selected_source = self.manifest_source_combo.currentText()
        tool_type = source_mapping.get(selected_source, "steamautocracks_v2")
        
        # 显示入库提示
        display_name = game_name or f"AppID {appid}"
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
                
                # 使用用户选择的清单源
                tool_type_actual = tool_type
                
                # 判断是 ZIP 源还是 GitHub 源
                zip_sources = ["printedwaste", "cysaw", "furcate", "walftech", "steamdatabase", "steamautocracks_v2", "sudama", "buqiuren"]
                if tool_type_actual in zip_sources:
                    success = await backend.process_zip_source(
                        appid, tool_type_actual, unlocker_type,
                        False, add_all_dlc, patch_depot_key
                    )
                else:
                    success = await backend.process_github_manifest(
                        appid, tool_type_actual, unlocker_type,
                        False, add_all_dlc, patch_depot_key
                    )
                
                return success
        
        # 确保之前的解锁worker已清理
        if hasattr(self, 'unlock_worker') and self.unlock_worker and self.unlock_worker.isRunning():
            self.unlock_worker.quit()
            self.unlock_worker.wait()
        
        self.unlock_worker = AsyncWorker(_unlock())
        self.unlock_worker.finished.connect(self.on_unlock_complete)
        self.unlock_worker.error.connect(self.on_unlock_error)
        self.unlock_worker.start()
    
    @pyqtSlot(object)
    def on_unlock_complete(self, success):
        """入库完成"""
        # 清理解锁worker引用
        if hasattr(self, 'unlock_worker') and self.unlock_worker:
            self.unlock_worker.deleteLater()
            self.unlock_worker = None
        
        if success:
            InfoBar.success(
                title=tr("add_success"),
                content=tr("add_success_content").format(self.current_appid if hasattr(self, 'current_appid') else '游戏'),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            # 通知主页刷新游戏列表
            self.notify_home_refresh()
        else:
            InfoBar.error(
                title=tr("delete_failed"),
                content=tr("process_failed") + "，" + tr("check_logs"),
                parent=self,
                position=InfoBarPosition.TOP
            )
    
    @pyqtSlot(str)
    def on_unlock_error(self, error):
        """入库失败"""
        # 清理解锁worker引用
        if hasattr(self, 'unlock_worker') and self.unlock_worker:
            self.unlock_worker.deleteLater()
            self.unlock_worker = None
        
        # 友好的错误提示
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
            parent=self,
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
        self.steam_path_edit.setFixedWidth(320)
        
        # GitHub Token设置
        self.token_edit = LineEdit()
        self.token_edit.setPlaceholderText(tr("token_placeholder"))
        self.token_edit.setFixedWidth(320)

        # 添加组件到分组中
        self.addGroup(FluentIcon.FOLDER, tr("steam_path"), tr("steam_path_hint"), self.steam_path_edit)
        self.addGroup(FluentIcon.GITHUB, tr("github_token"), tr("github_token_hint"), self.token_edit)


class SettingsPage(ScrollArea):
    """设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.setWidgetResizable(True)
        
        # 主容器
        container = QWidget()
        container.setObjectName("settingsContainer")
        self.setWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题
        title = SubtitleLabel(tr("settings"), self)
        layout.addWidget(title)
        
        # 使用新的分组卡片布局
        settings_card = SettinsCard(self)
        layout.addWidget(settings_card)
        
        # 保存对控件的引用以便后续使用
        self.steam_path_edit = settings_card.steam_path_edit
        self.token_edit = settings_card.token_edit
        self.debug_check = None
        self.logging_check = None
        self.unlocker_combo = None
        self.timeout_spinbox = None
        self.theme_combo = None
        self.color_combo = None
        self.lang_combo = None
        self.effect_combo = None
        
        # 添加其他设置卡片（应用程序配置、外观设置等）
        self._setup_additional_settings(layout)
        
        layout.addStretch(1)
        
        # 设置透明背景
        self.setStyleSheet("SettingsPage { background: transparent; }")
        container.setStyleSheet("QWidget#settingsContainer { background: transparent; }")
        
        # 标记需要加载配置
        self._config_loaded = False
        self.worker = None
        self._save_timer = None
    
    def _setup_additional_settings(self, layout):
        """设置其他设置卡片"""
        # 应用程序配置卡片
        app_config_card = GroupHeaderCardWidget(self)
        app_config_card.setTitle(tr("application_config"))
        app_config_card.setBorderRadius(8)
        
        # 调试模式
        self.debug_check = CheckBox(tr("enable_debug_log"))
        app_config_card.addGroup(FluentIcon.DEVELOPER_TOOLS, tr("debug_mode"), tr("debug_mode_hint"), self.debug_check)
        
        # 保存日志文件
        self.logging_check = CheckBox(tr("save_logs_to_file"))
        app_config_card.addGroup(FluentIcon.SAVE, tr("save_log_files"), tr("save_log_files_hint"), self.logging_check)
        
        # 强制解锁工具模式
        self.unlocker_combo = ComboBox()
        self.unlocker_combo.addItems([tr("auto_detect"), tr("force_steamtools"), tr("force_greenluma")])
        self.unlocker_combo.setCurrentIndex(0)
        self.unlocker_combo.setFixedWidth(180)
        app_config_card.addGroup(FluentIcon.SETTING, tr("unlocker_mode"), tr("force_unlocker_hint"), self.unlocker_combo)
        
        # 入库超时时间
        self.timeout_spinbox = SpinBox()
        self.timeout_spinbox.setRange(10, 300)
        self.timeout_spinbox.setValue(30)
        self.timeout_spinbox.setSuffix(" s")
        self.timeout_spinbox.setFixedWidth(120)
        app_config_card.addGroup(FluentIcon.SPEED_HIGH, tr("download_timeout"), tr("download_timeout_hint"), self.timeout_spinbox)
        
        layout.addWidget(app_config_card)
        
        # 外观设置卡片
        appearance_card = GroupHeaderCardWidget(self)
        appearance_card.setTitle(tr("appearance"))
        appearance_card.setBorderRadius(8)
        
        # 主题模式
        self.theme_combo = ComboBox()
        self.theme_combo.addItems([tr("light_theme"), tr("dark_theme"), tr("follow_system")])
        self.theme_combo.setCurrentIndex(2 if not isDarkTheme() else 1)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_mode_changed)
        self.theme_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.PALETTE, tr("theme_mode"), tr("theme_mode_hint"), self.theme_combo)
        
        # 主题色
        self.color_combo = ComboBox()
        self.color_combo.addItems([
            tr("default_blue"),
            tr("purple"),
            tr("green"),
            tr("orange"),
            tr("red"),
            tr("pink")
        ])
        self.color_combo.currentIndexChanged.connect(self.on_theme_color_changed)
        self.color_combo.setFixedWidth(200)
        appearance_card.addGroup(FluentIcon.BRUSH, tr("theme_color"), tr("theme_color_hint"), self.color_combo)
        
        # 默认界面
        self.default_page_combo = ComboBox()
        self.default_page_combo.addItems([
            tr("default_page_home"),
            tr("default_page_search")
        ])
        self.default_page_combo.currentIndexChanged.connect(self.on_default_page_changed)
        self.default_page_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.HOME, tr("default_page"), tr("default_page_hint"), self.default_page_combo)
        
        # 语言
        self.lang_combo = ComboBox()
        self.lang_combo.addItems(["系统默认", "简体中文", "English", "Français", "Русский", "Deutsch", "日本語", "繁體中文"])
        self.lang_combo.setCurrentIndex(0)  # 默认为系统默认
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self.lang_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.LANGUAGE, tr("language"), tr("language_hint"), self.lang_combo)
        
        # 窗口特效
        self.effect_combo = ComboBox()
        self.effect_combo.addItems([
            tr("effect_none"),
            tr("effect_mica")
        ])
        self.effect_combo.currentIndexChanged.connect(self.on_window_effect_changed)
        self.effect_combo.setFixedWidth(150)
        appearance_card.addGroup(FluentIcon.PALETTE, tr("window_effect"), tr("window_effect_hint"), self.effect_combo)
        
        layout.addWidget(appearance_card)
        
        # 按钮行
        button_layout = QHBoxLayout()
        
        self.reset_btn = PushButton(tr("reset_to_default"))
        self.reset_btn.clicked.connect(self.reset_settings)
        self.reset_btn.setFixedWidth(120)
        button_layout.addWidget(self.reset_btn)
        
        self.about_btn = PushButton(tr("about"))
        self.about_btn.clicked.connect(self.show_about)
        self.about_btn.setFixedWidth(100)
        button_layout.addWidget(self.about_btn)
        
        self.thanks_btn = PushButton(tr("thanks"))
        self.thanks_btn.clicked.connect(self.show_thanks)
        self.thanks_btn.setFixedWidth(100)
        button_layout.addWidget(self.thanks_btn)
        
        self.github_btn = HyperlinkButton("https://github.com/zhouchentao666/Fluent-Install", "GitHub")
        self.github_btn.setFixedWidth(80)
        button_layout.addWidget(self.github_btn)
        
        self.qq_btn = HyperlinkButton("https://qm.qq.com/q/gtTLap5Jw4", "Q群")
        self.qq_btn.setFixedWidth(60)
        button_layout.addWidget(self.qq_btn)
        
        self.tg_group_btn = HyperlinkButton("https://t.me/+vTrqXKpRJE9kNmVl", "TG群组")
        self.tg_group_btn.setFixedWidth(75)
        button_layout.addWidget(self.tg_group_btn)
        
        self.tg_channel_btn = HyperlinkButton("https://t.me/FluentInstall", "TG频道")
        self.tg_channel_btn.setFixedWidth(75)
        button_layout.addWidget(self.tg_channel_btn)
        
        self.discord_btn = HyperlinkButton("https://discord.gg/2qh68QRMuA", "Discord")
        self.discord_btn.setFixedWidth(80)
        button_layout.addWidget(self.discord_btn)
        
        button_layout.addStretch(1)
        layout.addLayout(button_layout)
    
    def showEvent(self, event):
        """页面显示时加载配置"""
        super().showEvent(event)
        if not self._config_loaded:
            self._config_loaded = True
            self.load_config()
            # 设置自动保存监听器
            self._setup_auto_save_listeners()
    
    def _setup_auto_save_listeners(self):
        """设置自动保存监听器"""
        # Steam路径和Token输入框
        if self.steam_path_edit:
            self.steam_path_edit.textChanged.connect(self._on_setting_changed_delayed)
        if self.token_edit:
            self.token_edit.textChanged.connect(self._on_setting_changed_delayed)
        
        # 复选框
        if self.debug_check:
            self.debug_check.stateChanged.connect(self._on_setting_changed)
        if self.logging_check:
            self.logging_check.stateChanged.connect(self._on_setting_changed)
        
        # 下拉框
        if self.unlocker_combo:
            self.unlocker_combo.currentIndexChanged.connect(self._on_setting_changed)
        
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
        if index == 0:  # 浅色
            setTheme(Theme.LIGHT)
        elif index == 1:  # 深色
            setTheme(Theme.DARK)
        else:  # 跟随系统
            setTheme(Theme.AUTO)
        
        # 立即保存设置
        self.save_theme_setting("theme_mode", ["light", "dark", "auto"][index])
    
    def on_theme_color_changed(self, index):
        """主题色切换"""
        colors = ["#0078d4", "#9b4dca", "#10893e", "#ff8c00", "#e81123", "#e3008c"]
        if 0 <= index < len(colors):
            setThemeColor(colors[index])
            # 立即保存设置
            self.save_theme_setting("theme_color", colors[index])
    
    def save_theme_setting(self, key, value):
        """保存单个主题设置"""
        try:
            config_path = Path.cwd() / 'config.json'
            import json
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            config[key] = value
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存主题设置失败: {e}")
    
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
            config_path = Path.cwd() / 'config.json'
            import json
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            config["language"] = lang
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存语言设置失败: {e}")
    
    def load_language_setting(self):
        """加载语言设置"""
        try:
            config_path = Path.cwd() / 'config.json'
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get("language", "zh_CN")
        except:
            pass
        return "zh_CN"
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """Cai Install - Fluent Design 版本

版本: 1.3

这是一个基于 PyQt6-Fluent-Widgets 的现代化 Steam 游戏解锁工具。

功能特性:
• Fluent Design 设计风格
• 支持多种清单源
• 游戏搜索和入库
• 已入库游戏管理
• 主题自定义

项目地址: https://github.com/zhouchentao666/Cai-install-Fluent-GUI"""
        
        dialog = MessageBox(tr("about_title"), about_text, self.window())
        dialog.exec()
    
    def show_thanks(self):
        """显示鸣谢对话框"""
        thanks_text = """特别鸣谢

开发者:
• zhouchentao666 - 制作人员

开源项目:
• PyQt6 - Qt6 Python 绑定
• PyQt-Fluent-Widgets - Fluent Design 组件库
• Cai-install-Web-GUI - 原始项目作者
• httpx - 异步 HTTP 客户端

清单源提供:
• SWA V2
• Cysaw
• Furcate
• Walftech
• steamdatabase
• SteamAutoCracks
• Sudama
• 清单不求人

社区与联系:
• GitHub: https://github.com/zhouchentao666/Fluent-Install
• 加入 Q 群: https://qm.qq.com/q/gtTLap5Jw4
• TG 群组: https://t.me/+vTrqXKpRJE9kNmVl
• TG 频道: https://t.me/FluentInstall
• Discord: https://discord.gg/2qh68QRMuA

感谢所有为本项目做出贡献的开发者和用户！"""
        
        dialog = MessageBox(tr("thanks_title"), thanks_text, self.window())
        dialog.exec()
    
    def load_config(self):
        """加载配置"""
        async def _load():
            async with CaiBackend() as backend:
                config = await backend.load_config()
                return config
        
        self.worker = AsyncWorker(_load())
        self.worker.finished.connect(self.on_config_loaded)
        self.worker.error.connect(self.on_load_error)
        self.worker.start()
    
    @pyqtSlot(object)
    def on_config_loaded(self, config):
        """配置加载完成"""
        if config:
            # 获取主设置卡片
            settings_card = self.findChild(SettinsCard)
            if settings_card:
                settings_card.steam_path_edit.setText(config.get("Custom_Steam_Path", ""))
                settings_card.token_edit.setText(config.get("Github_Personal_Token", ""))
            
            # 加载应用程序配置
            if self.debug_check:
                self.debug_check.setChecked(config.get("debug_mode", False))
            if self.logging_check:
                self.logging_check.setChecked(config.get("logging_files", True))
            
            # 加载解锁工具模式
            if self.unlocker_combo:
                force_unlocker = config.get("force_unlocker_type", "auto")
                if force_unlocker == "steamtools":
                    self.unlocker_combo.setCurrentIndex(1)
                elif force_unlocker == "greenluma":
                    self.unlocker_combo.setCurrentIndex(2)
                else:
                    self.unlocker_combo.setCurrentIndex(0)
            
            # 加载入库超时时间
            if self.timeout_spinbox:
                self.timeout_spinbox.setValue(config.get("download_timeout", 30))
            
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
            config_path = Path.cwd() / 'config.json'
            import json
            
            # 读取现有配置
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                from backend import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            
            # 更新配置
            settings_card = self.findChild(SettinsCard)
            if settings_card:
                config["Custom_Steam_Path"] = settings_card.steam_path_edit.text().strip()
                config["Github_Personal_Token"] = settings_card.token_edit.text().strip()
            
            # 保存应用程序配置
            if self.debug_check:
                config["debug_mode"] = self.debug_check.isChecked()
            if self.logging_check:
                config["logging_files"] = self.logging_check.isChecked()
            
            # 保存解锁工具模式
            if self.unlocker_combo:
                unlocker_map = {0: "auto", 1: "steamtools", 2: "greenluma"}
                config["force_unlocker_type"] = unlocker_map.get(self.unlocker_combo.currentIndex(), "auto")
            
            # 保存入库超时时间
            if self.timeout_spinbox:
                config["download_timeout"] = self.timeout_spinbox.value()
            
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
        
        self.worker = AsyncWorker(_save())
        self.worker.finished.connect(self.on_save_success)
        self.worker.error.connect(self.on_save_error)
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
                config_path = Path.cwd() / 'config.json'
                from backend import DEFAULT_CONFIG
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
            
            self.worker = AsyncWorker(_reset())
            self.worker.finished.connect(self.on_reset_success)
            self.worker.error.connect(self.on_reset_error)
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
        self.setWindowTitle(tr("app_title"))
        self.resize(1000, 700)
        
        # 设置窗口图标为Fluent内置的下载图标
        self.setWindowIcon(FluentIcon.CLOUD_DOWNLOAD.icon())
        
        # 设置标题栏（避免按钮重叠）
        self.titleBar.raise_()
        
        # 创建页面
        self.home_page = HomePage(self)
        self.search_page = SearchPage(self)
        self.settings_page = SettingsPage(self)
        
        # 添加导航项
        self.addSubInterface(
            self.home_page,
            FluentIcon.HOME,
            tr("home")
        )
        
        self.addSubInterface(
            self.search_page,
            FluentIcon.SEARCH,
            tr("search")
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
    
    def switch_to_default_page(self):
        """切换到默认界面"""
        try:
            config_path = Path.cwd() / 'config.json'
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
    
    def on_restart_steam(self):
        """重启 Steam"""
        dialog = MessageBox(
            tr("restart_steam_confirm"),
            tr("restart_steam_message"),
            self
        )
        
        if dialog.exec():
            # 用户点击确认
            self.restart_steam_worker = None
            
            async def _restart():
                async with CaiBackend() as backend:
                    await backend.initialize()
                    success = backend.restart_steam()
                    return success
            
            self.restart_steam_worker = AsyncWorker(_restart())
            self.restart_steam_worker.finished.connect(self.on_restart_complete)
            self.restart_steam_worker.error.connect(self.on_restart_error)
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
            self.setStyleSheet("background-color: transparent")
        elif effect_type == "none":
            # 禁用特效
            self.setMicaEffectEnabled(False)
            self.setStyleSheet("")
        
        # 保存设置
        try:
            config_path = Path.cwd() / 'config.json'
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
        config_path = Path.cwd() / 'config.json'
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