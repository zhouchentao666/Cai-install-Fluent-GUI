#!/usr/bin/env python3
"""
D加密插入工具
用于在构建过程中为生成的可执行文件添加D加密功能
"""

import os
import sys
import hashlib
import struct
from pathlib import Path

def generate_drm_key():
    """生成D加密密钥"""
    # 使用当前时间和随机数生成密钥
    import time
    import random
    key = f"{time.time()}{random.randint(1000, 9999)}".encode()
    return hashlib.sha256(key).digest()[:16]

def insert_drm(exe_path):
    """为可执行文件添加D加密"""
    if not os.path.exists(exe_path):
        print(f"错误: 可执行文件 {exe_path} 不存在")
        return False
    
    try:
        # 读取可执行文件
        with open(exe_path, 'rb') as f:
            content = f.read()
        
        # 生成D加密密钥
        drm_key = generate_drm_key()
        
        # 计算文件哈希
        file_hash = hashlib.sha256(content).digest()
        
        # 构建D加密数据
        drm_data = b'DRM' + struct.pack('I', len(drm_key)) + drm_key + file_hash
        
        # 将D加密数据添加到文件末尾
        with open(exe_path, 'ab') as f:
            f.write(drm_data)
        
        print(f"成功为 {exe_path} 添加D加密")
        return True
        
    except Exception as e:
        print(f"添加D加密失败: {e}")
        return False

def verify_drm(exe_path):
    """验证可执行文件的D加密"""
    if not os.path.exists(exe_path):
        print(f"错误: 可执行文件 {exe_path} 不存在")
        return False
    
    try:
        # 读取可执行文件
        with open(exe_path, 'rb') as f:
            content = f.read()
        
        # 检查文件末尾是否有D加密数据
        if len(content) < 4 + 4 + 16 + 32:  # DRM标记(3) + 密钥长度(4) + 密钥(16) + 哈希(32)
            print("错误: 文件没有D加密数据")
            return False
        
        # 提取D加密数据
        drm_marker = content[-75:-72]  # 最后75字节开始的3字节
        if drm_marker != b'DRM':
            print("错误: 无效的D加密标记")
            return False
        
        print(f"D加密验证成功: {exe_path}")
        return True
        
    except Exception as e:
        print(f"验证D加密失败: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python _insert_drm.py <可执行文件路径>")
        sys.exit(1)
    
    exe_path = sys.argv[1]
    insert_drm(exe_path)