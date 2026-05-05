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
    
    # 获取脚本所在目录（避免在某些环境下 Path.cwd() 返回错误路径）
    current_dir = Path(__file__).resolve().parent
    
    # PyInstaller 参数
    args = [
        'main.py',  # 主程序文件
        '--name=FluentInstall',  # 生成的 exe 名称
        '--onefile',  # 打包成单个文件
        '--windowed',  # 无控制台窗口（GUI程序）
        '--icon=assets/icon.ico',  # 图标文件（如果存在）
        '--add-data=config;config',  # 添加 config 目录
        '--add-data=assets;assets',  # 添加 assets 目录（如果存在）
        '--add-data=backend/DRM/免steam补丁;GBE_Patch',  # 添加 GBE_Patch 目录 (D加密GBE模式需要)
        '--add-data=backend/DRM/GreenLuma;GreenLuma',  # 添加 GreenLuma 目录 (D加密GreenLuma模式需要)
        '--add-data=backend/steam_api64.dll;backend',  # 添加 steam_api64.dll (CW提取工具需要)
        '--hidden-import=backend.cai_backend',  # 显式导入 cai_backend 模块
        '--hidden-import=backend.drm_backend',  # 显式导入 backend D加密模块
        '--hidden-import=backend.cw_extractor_core',  # 显式导入 CW 提取核心模块
        '--hidden-import=backend.steam_account_manager',  # 显式导入 backend 账号切换模块
        '--hidden-import=backend.trainer_backend',  # 显式导入 backend 修改器模块
        '--hidden-import=PyQt6',  # 显式导入 PyQt6
        '--hidden-import=qfluentwidgets',  # 显式导入 qfluentwidgets
        '--hidden-import=httpx',  # 显式导入 httpx
        '--hidden-import=socksio',  # 显式导入 socksio（SOCKS代理依赖）
        '--hidden-import=aiofiles',  # 显式导入 aiofiles
        '--hidden-import=aiohttp',  # 显式导入 aiohttp（封面下载需要）
        '--hidden-import=ujson',  # 显式导入 ujson
        '--hidden-import=colorlog',  # 显式导入 colorlog
        '--hidden-import=vdf',  # 显式导入 vdf
        '--hidden-import=steam',  # steam 模块（获取App信息需要）
        '--hidden-import=gevent',  # steam 模块依赖
        '--hidden-import=eventemitter',  # steam 模块依赖
        '--hidden-import=google.protobuf',  # steam 模块依赖
        '--hidden-import=cloudscraper',  # cloudscraper 用于绕过 Cloudflare 人机验证
        '--hidden-import=Crypto',  # 显式导入 pycryptodome
        '--hidden-import=Crypto.Cipher',  # 显式导入 pycryptodome AES
        '--hidden-import=Crypto.Util.Padding',  # 显式导入 pycryptodome Padding
        '--hidden-import=psutil',  # 显式导入 psutil（D加密模块需要）
        '--hidden-import=PyQt6.sip',  # 显式导入 PyQt6.sip
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
    
    # 检查 steam_api64.dll 是否存在
    steam_api_dll = current_dir / 'backend' / 'steam_api64.dll'
    if not steam_api_dll.exists():
        print(f"警告: steam_api64.dll {steam_api_dll} 不存在，CW提取工具可能无法正常工作")
    else:
        print(f"找到 steam_api64.dll: {steam_api_dll}")
    
    # 检查 GBE_Patch 目录是否存在 (实际路径是 backend/DRM/免steam补丁)
    gbe_dir = current_dir / 'backend' / 'DRM' / '免steam补丁'
    if not gbe_dir.exists():
        print(f"警告: GBE_Patch 目录 {gbe_dir} 不存在")
        args = [arg for arg in args if '免steam补丁' in arg]

    # 检查 GreenLuma 目录是否存在 (实际路径是 backend/DRM/GreenLuma)
    greenluma_dir = current_dir / 'backend' / 'DRM' / 'GreenLuma'
    if not greenluma_dir.exists():
        print(f"警告: GreenLuma 目录 {greenluma_dir} 不存在")
        args = [arg for arg in args if 'DRM/GreenLuma' in arg]

    print("开始打包...")
    print(f"PyInstaller 参数: {' '.join(args)}")
    
    try:
        # 运行 PyInstaller
        PyInstaller.__main__.run(args)
        
        print("\n打包完成！")
        exe_file = current_dir / 'dist' / 'FluentInstall.exe'
        print(f"生成的 exe 文件在: {exe_file}")
        
        if exe_file.exists():
            print(f"  文件大小: {exe_file.stat().st_size / 1024 / 1024:.2f} MB")
            
            # UPX 加壳
            print("\n正在 UPX 加壳...")
            try:
                import subprocess
                upx_result = subprocess.run(['upx', '--best', str(exe_file)], capture_output=True, text=True)
                if upx_result.returncode == 0:
                    print("✓ UPX 加壳成功！")
                    print(f"  加壳后大小: {exe_file.stat().st_size / 1024 / 1024:.2f} MB")
                else:
                    print(f"⚠ UPX 加壳可能已执行或有警告")
            except FileNotFoundError:
                print("⚠ 未找到 UPX，跳过加壳（请安装 UPX 并添加到 PATH）")
            except Exception as e:
                print(f"⚠ UPX 加壳失败: {e}")
            
            # 添加D加密
            print("\n正在添加D加密...")
            drm_script = current_dir / 'backend' / '_insert_drm.py'
            
            if drm_script.exists():
                try:
                    subprocess.run([sys.executable, str(drm_script), str(exe_file)], check=True)
                    print("D加密添加成功！")
                except Exception as e:
                    print(f"添加D加密失败: {e}")
            else:
                print("警告: 无法添加D加密，脚本不存在")
        else:
            print("警告: 未找到生成的 exe 文件")
        
    except Exception as e:
        print(f"打包失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)