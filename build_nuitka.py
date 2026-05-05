#!/usr/bin/env python3
"""
Nuitka 打包脚本
用于将 fluent_app.py 打包成独立的 exe 可执行文件
"""

import os
import sys
import subprocess
from pathlib import Path


def build_exe():
    """使用 Nuitka 构建 exe 文件"""
    
    # 获取脚本所在目录（避免在某些环境下 Path.cwd() 返回错误路径）
    current_dir = Path(__file__).resolve().parent
    
    # 检查 Python 版本
    print(f"Python 版本: {sys.version}")
    
    # 检查必要文件和目录是否存在，动态构建参数
    data_dir_args = []
    data_file_args = []
    
    # 检查并添加数据目录
    # 注意: GBE_Patch 实际路径是 backend/DRM/免steam补丁, 打包后映射为 GBE_Patch
    #       GreenLuma 实际路径是 backend/DRM/GreenLuma, 打包后映射为 GreenLuma
    data_dirs = [
        ('config', 'config'),
        ('assets', 'assets'),
        ('backend/DRM/免steam补丁', 'GBE_Patch'),
        ('backend/DRM/GreenLuma', 'GreenLuma'),
    ]
    
    for src_dir, dest_dir in data_dirs:
        full_path = current_dir / src_dir
        if full_path.exists():
            # Nuitka 格式: --include-data-dir=源目录路径=目标目录名
            data_dir_args.append(f'--include-data-dir={src_dir}={dest_dir}')
        else:
            print(f"警告: 数据目录不存在，跳过: {src_dir}")
    
    # 检查并添加数据文件
    data_files = [
        ('backend/steam_api64.dll', 'backend/steam_api64.dll'),
    ]
    
    for src_file, dest_file in data_files:
        full_path = current_dir / src_file
        if full_path.exists():
            # Nuitka 格式: --include-data-files=源文件路径=目标文件路径
            data_file_args.append(f'--include-data-files={src_file}={dest_file}')
        else:
            print(f"警告: 数据文件不存在，跳过: {src_file}")
    
    # 检测 MinGW 路径
    mingw_path = r'D:\zhouchentao\ruanjian\RedPanda\mingw64'
    if not os.path.exists(mingw_path):
        # 尝试从环境变量查找
        for path in os.environ.get('PATH', '').split(';'):
            if 'mingw' in path.lower() and 'bin' in path.lower():
                mingw_path = os.path.dirname(path)
                break
    
    if os.path.exists(mingw_path):
        print(f"✓ 找到 MinGW: {mingw_path}")
        os.environ['CC'] = os.path.join(mingw_path, 'bin', 'gcc.exe')
    else:
        print("警告: 未找到 MinGW，将使用 Nuitka 自动下载")
        # 设置下载缓存目录，支持断点续传
        nuitka_cache_dir = Path(os.environ.get('LOCALAPPDATA', '')) / 'Nuitka' / 'Nuitka' / 'Cache'
        if nuitka_cache_dir.exists():
            print(f"Nuitka 缓存目录: {nuitka_cache_dir}")
            # 检查是否有部分下载的文件
            download_dir = nuitka_cache_dir / 'DOWNLO~1' / 'gcc' / 'x86_64'
            if download_dir.exists():
                print(f"检查下载缓存: {download_dir}")
                for item in download_dir.rglob('*.zip'):
                    print(f"  发现: {item.name} ({item.stat().st_size / 1024 / 1024:.2f} MB)")
    
    # Nuitka 基础参数
    args = [
        sys.executable,  # Python 解释器
        '-m', 'nuitka',
        'main.py',  # 主程序文件
        
        # 单文件模式
        '--onefile',
        
        # 启用 PyQt6 插件
        '--enable-plugin=pyqt6',
        
        # 无控制台窗口（GUI程序）
        '--windows-console-mode=disable',
        
        # 图标文件
        '--windows-icon-from-ico=assets/icon.ico',
        
        # 输出设置
        '--output-dir=dist',
        '--output-filename=FluentInstall',
        
        # 清理和下载选项
        '--remove-output',
        '--assume-yes-for-downloads',
        '--quiet',  # 静默模式，自动回答警告提示
        
        # 单文件模式防闪退选项
        '--onefile-tempdir-spec={TEMP}/FluentInstall_{PID}_{TIME}',  # 指定临时目录
        '--windows-force-stdout-spec={TEMP}/FluentInstall_output.txt',  # 捕获输出用于调试
        '--windows-force-stderr-spec={TEMP}/FluentInstall_error.txt',
    ]
    
    # 如果找到 MinGW，添加编译器选项
    if os.path.exists(mingw_path):
        args.extend([
            f'--mingw64',  # 使用 MinGW64
        ])
    
    # 添加数据目录参数
    args.extend(data_dir_args)
    
    # 添加数据文件参数
    args.extend(data_file_args)
    
    # 添加其他参数
    args.extend([
        # 隐式导入的模块
        '--include-package=backend',  # 包含整个 backend 包
        '--include-package=Crypto',  # pycryptodome
        '--include-package=qfluentwidgets',  # Fluent Widgets
        '--include-package=psutil',  # psutil（D加密模块需要）
        '--include-package=PyQt6.sip',  # PyQt6.sip（用于对象删除检查）
        
        # 隐式导入的单个模块
        '--include-module=backend.cai_backend',
        '--include-module=backend.drm_backend',
        '--include-module=backend.cw_extractor_core',  # CW 提取核心模块
        '--include-module=backend.steam_account_manager',
        '--include-module=backend.trainer_backend',
        '--include-module=httpx',
        '--include-module=socksio',
        '--include-module=aiofiles',
        '--include-module=aiohttp',
        '--include-module=ujson',
        '--include-module=colorlog',
        '--include-module=vdf',
        '--include-package=PIL',  # Pillow 图像处理库
        '--include-package=steam',  # steam 模块（获取App信息需要）
        '--include-package=gevent',  # steam 模块依赖
        '--include-module=eventemitter',  # steam 模块依赖
        '--include-package=google.protobuf',  # steam 模块依赖
        '--include-package=cloudscraper',  # cloudscraper 用于绕过 Cloudflare 人机验证
        
        # 性能优化选项
        '--lto=yes',  # 启用链接时优化（提高编译速度，增加内存占用）
        '--jobs=16',  # 减少并行任务数（避免内存不足）
        '--show-progress',  # 显示编译进度
        '--show-memory',  # 显示内存使用情况
        
        # 其他选项
        '--windows-company-name=FluentInstall',
        '--windows-product-name=FluentInstall',
        '--windows-file-version=1.7.0.0',
        '--windows-product-version=1.7.0.0',
    ])
    
    # 检查必要文件和目录
    checks = [
        ('assets/icon.ico', '图标文件', True),
        ('config', '配置目录', False),
        ('assets', '资源目录', False),
        ('backend/DRM/免steam补丁', 'GBE_Patch 目录', False),
        ('backend/DRM/GreenLuma', 'GreenLuma 目录', False),
        ('backend/steam_api64.dll', 'steam_api64.dll', True),
    ]
    
    for path, name, is_file in checks:
        full_path = current_dir / path
        exists = full_path.exists() if is_file else full_path.exists()
        if not exists:
            print(f"警告: {name} ({full_path}) 不存在")
        else:
            print(f"✓ 找到 {name}: {full_path}")
    
    print("\n开始 Nuitka 打包...")
    print(f"命令: {' '.join(str(arg) for arg in args)}")
    print("-" * 60)
    
    try:
        # 运行 Nuitka
        result = subprocess.run(args, check=True)
        
        print("-" * 60)
        print("\n✓ Nuitka 打包完成！")
        
        # 文件夹模式下，输出路径为 dist/FluentInstall.exe
        exe_path = current_dir / 'dist' / 'FluentInstall.exe'
        
        if exe_path.exists():
            print(f"✓ 生成的 exe 文件: {exe_path}")
            print(f"  文件大小: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
            
            # 添加D加密
            print("\n正在添加 D 加密...")
            drm_script = current_dir / 'backend' / '_insert_drm.py'
            
            if drm_script.exists():
                try:
                    subprocess.run([sys.executable, str(drm_script), str(exe_path)], check=True)
                    print("✓ D 加密添加成功！")
                except Exception as e:
                    print(f"✗ 添加 D 加密失败: {e}")
            else:
                print(f"警告: DRM 脚本不存在: {drm_script}")
        else:
            print(f"✗ 未找到生成的 exe 文件: {exe_path}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ 打包失败: {e}")
        return False
    except FileNotFoundError:
        print("\n✗ 错误: 找不到 Nuitka")
        print("请先安装 Nuitka: pip install nuitka")
        return False
    except Exception as e:
        print(f"\n✗ 打包时出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def clean_build():
    """清理构建文件"""
    current_dir = Path(__file__).resolve().parent
    
    dirs_to_remove = [
        'build',
        'main.build',
        'main.dist',
        'main.onefile-build',
        '__pycache__',
    ]
    
    print("清理构建文件...")
    for dir_name in dirs_to_remove:
        dir_path = current_dir / dir_name
        if dir_path.exists():
            import shutil
            try:
                shutil.rmtree(dir_path)
                print(f"  已删除: {dir_path}")
            except Exception as e:
                print(f"  无法删除 {dir_path}: {e}")
    
    print("清理完成！")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Nuitka 打包脚本')
    parser.add_argument('--clean', action='store_true', help='清理构建文件')
    parser.add_argument('--no-drm', action='store_true', help='不添加 D 加密')
    
    args = parser.parse_args()
    
    if args.clean:
        clean_build()
    else:
        success = build_exe()
        sys.exit(0 if success else 1)
