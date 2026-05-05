#!/usr/bin/env python3
"""
Cai Install - Fluent Design 版本入口
"""
import sys
import os
import json
import traceback
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def main():
    """主入口函数"""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt, QLocale
        from app.fluent_app import MainWindow, load_theme_config, load_language_config, set_language
        from qfluentwidgets import setTheme, Theme, setThemeColor

        # 启用高 DPI 缩放
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        # 启用 Desktop OpenGL（与2.9版本一致，避免Qt6Core.dll崩溃）
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL)

        app = QApplication(sys.argv)
        
        # 加载语言设置
        try:
            lang = load_language_config()
            # 如果是系统默认，检测系统语言
            if lang == "system":
                system_locale = QLocale.system()
                if system_locale.language() == QLocale.Language.Chinese:
                    if system_locale.country() in (QLocale.Country.Taiwan, QLocale.Country.HongKong):
                        lang = "zh_TW"
                    else:
                        lang = "zh_CN"
                else:
                    lang = "zh_CN"
            set_language(lang)
        except Exception as e:
            print(f"加载语言配置失败: {e}")
        
        # 加载主题配置
        try:
            theme_config = load_theme_config()
        except Exception as e:
            print(f"加载主题配置失败: {e}")
            theme_config = {"theme_mode": "auto", "theme_color": "#0078d4"}
        
        # 应用主题设置
        theme_mode = theme_config.get("theme_mode", "auto")
        if theme_mode == "light":
            setTheme(Theme.LIGHT)
        elif theme_mode == "dark":
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.AUTO)
        
        # 应用主题色
        setThemeColor(theme_config.get("theme_color", "#0078d4"))

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
        
    except Exception as e:
        error_msg = f"程序启动失败: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        # 写入错误日志
        try:
            log_path = Path.home() / "FluentInstall_error.log"
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(error_msg)
            print(f"错误日志已保存到: {log_path}")
        except:
            pass
        sys.exit(1)

if __name__ == '__main__':
    main()
