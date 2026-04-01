#!/usr/bin/env python3
"""
PyInstaller 打包脚本
用于将 fluent_app.py 打包成独立的 exe 可执行文件
"""

import PyInstaller.__main__
import os
import sys
from pathlib import Path

def build_exe():
    """构建 exe 文件"""
    
    # 获取当前目录
    current_dir = Path.cwd()
    
    # PyInstaller 参数
    args = [
        'fluent_app.py',  # 主程序文件
        '--name=FluentInstall',  # 生成的 exe 名称
        '--onefile',  # 打包成单个文件
        '--windowed',  # 无控制台窗口（GUI程序）
        '--icon=assets/icon.ico',  # 图标文件（如果存在）
        '--add-data=config.json;.',  # 添加配置文件
        '--add-data=assets;assets',  # 添加 assets 目录（如果存在）
        '--hidden-import=backend',  # 显式导入 backend 模块
        '--hidden-import=PyQt6',  # 显式导入 PyQt6
        '--hidden-import=qfluentwidgets',  # 显式导入 qfluentwidgets
        '--hidden-import=httpx',  # 显式导入 httpx
        '--hidden-import=socksio',  # 显式导入 socksio（SOCKS代理依赖）
        '--hidden-import=aiofiles',  # 显式导入 aiofiles
        '--hidden-import=ujson',  # 显式导入 ujson
        '--hidden-import=colorlog',  # 显式导入 colorlog
        '--hidden-import=vdf',  # 显式导入 vdf
        '--clean',  # 清理临时文件
        '--noconfirm',  # 覆盖已存在的文件
        '--distpath=dist',  # 输出目录
        '--workpath=build',  # 工作目录
        '--specpath=.',  # spec 文件目录
    ]
    
    # 检查图标文件是否存在
    icon_path = current_dir / 'assets' / 'icon.ico'
    if not icon_path.exists():
        print(f"警告: 图标文件 {icon_path} 不存在，将使用默认图标")
        # 移除图标参数
        args = [arg for arg in args if not arg.startswith('--icon=')]
    
    # 检查 assets 目录是否存在
    assets_dir = current_dir / 'assets'
    if not assets_dir.exists():
        print(f"警告: assets 目录 {assets_dir} 不存在")
        # 移除 assets 参数
        args = [arg for arg in args if not arg.startswith('--add-data=assets')]
    
    # 检查 config.json 是否存在
    config_path = current_dir / 'config.json'
    if not config_path.exists():
        print(f"警告: 配置文件 {config_path} 不存在")
        # 移除 config 参数
        args = [arg for arg in args if not arg.startswith('--add-data=config.json')]
    
    print("开始打包...")
    print(f"PyInstaller 参数: {' '.join(args)}")
    
    try:
        # 运行 PyInstaller
        PyInstaller.__main__.run(args)
        
        print("\n打包完成！")
        print(f"生成的 exe 文件在: {current_dir / 'dist' / 'FluentInstall.exe'}")
        
        # 添加D加密
        print("\n正在添加D加密...")
        drm_script = current_dir / '_insert_drm.py'
        exe_file = current_dir / 'dist' / 'FluentInstall.exe'
        
        if drm_script.exists() and exe_file.exists():
            try:
                import subprocess
                subprocess.run([sys.executable, str(drm_script), str(exe_file)], check=True)
                print("D加密添加成功！")
            except Exception as e:
                print(f"添加D加密失败: {e}")
        else:
            print("警告: 无法添加D加密，脚本或可执行文件不存在")
        
    except Exception as e:
        print(f"打包失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)