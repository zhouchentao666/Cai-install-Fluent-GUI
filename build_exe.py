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
        '--add-data=config;config',  # 添加 config 目录
        '--add-data=assets;assets',  # 添加 assets 目录（如果存在）
        '--add-data=GBE_Patch;GBE_Patch',  # 添加 GBE_Patch 目录 (D加密GBE模式需要)
        '--add-data=GreenLuma_2026_1.7.4-Steam006;GreenLuma',  # 添加 GreenLuma 目录 (D加密GreenLuma模式需要)
        '--hidden-import=cai_backend',  # 显式导入 cai_backend 模块
        '--hidden-import=backend.authorizer_backend',  # 显式导入 backend 授权模块
        '--hidden-import=backend.cw_extractor_core',  # 显式导入 backend CW提取模块
        '--hidden-import=backend.trainer_backend',  # 显式导入 backend 修改器模块
        '--hidden-import=PyQt6',  # 显式导入 PyQt6
        '--hidden-import=qfluentwidgets',  # 显式导入 qfluentwidgets
        '--hidden-import=httpx',  # 显式导入 httpx
        '--hidden-import=socksio',  # 显式导入 socksio（SOCKS代理依赖）
        '--hidden-import=aiofiles',  # 显式导入 aiofiles
        '--hidden-import=ujson',  # 显式导入 ujson
        '--hidden-import=colorlog',  # 显式导入 colorlog
        '--hidden-import=vdf',  # 显式导入 vdf
        '--hidden-import=Crypto',  # 显式导入 pycryptodome
        '--hidden-import=Crypto.Cipher',  # 显式导入 pycryptodome AES
        '--hidden-import=Crypto.Util.Padding',  # 显式导入 pycryptodome Padding
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
        args = [arg for arg in args if not arg.startswith('--icon=')]
    
    # 检查 assets 目录是否存在
    assets_dir = current_dir / 'assets'
    if not assets_dir.exists():
        print(f"警告: assets 目录 {assets_dir} 不存在")
        args = [arg for arg in args if not arg.startswith('--add-data=assets')]
    
    # 检查 config 目录是否存在
    config_dir = current_dir / 'config'
    if not config_dir.exists():
        print(f"警告: config 目录 {config_dir} 不存在")
        args = [arg for arg in args if not arg.startswith('--add-data=config')]
    
    # 检查 backend 目录是否存在
    backend_dir = current_dir / 'backend'
    if not backend_dir.exists():
        print(f"警告: backend 目录 {backend_dir} 不存在")
    
    # 检查 GBE_Patch 目录是否存在
    gbe_dir = current_dir / 'GBE_Patch'
    if not gbe_dir.exists():
        print(f"警告: GBE_Patch 目录 {gbe_dir} 不存在")
        args = [arg for arg in args if not arg.startswith('--add-data=GBE_Patch')]

    # 检查 GreenLuma 目录是否存在
    greenluma_dir = current_dir / 'GreenLuma_2026_1.7.4-Steam006'
    if not greenluma_dir.exists():
        print(f"警告: GreenLuma 目录 {greenluma_dir} 不存在")
        args = [arg for arg in args if not arg.startswith('--add-data=GreenLuma')]

    # 检查 backup 目录是否存在
    backup_dir = current_dir / 'backup'
    if not backup_dir.exists():
        print(f"警告: backup 目录 {backup_dir} 不存在")
        args = [arg for arg in args if not arg.startswith('--add-data=backup')]
    
    print("开始打包...")
    print(f"PyInstaller 参数: {' '.join(args)}")
    
    try:
        # 运行 PyInstaller
        PyInstaller.__main__.run(args)
        
        print("\n打包完成！")
        print(f"生成的 exe 文件在: {current_dir / 'dist' / 'FluentInstall.exe'}")
        
        # 添加D加密
        print("\n正在添加D加密...")
        drm_script = current_dir / 'backend' / '_insert_drm.py'
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