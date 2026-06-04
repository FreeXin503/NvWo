#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
女娲 Skill VPN 连通性测试脚本
尝试请求外网核心节点（如 wikipedia.org 或 google.com）来验证外网访问状态。
"""

import sys
import io
import urllib.request
import urllib.error

# 解决 Windows 下的控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

TEST_URLS = [
    "https://www.wikipedia.org",
    "https://www.google.com"
]

def check_connection(url: str, timeout: int = 5) -> bool:
    """测试单个 URL 连通性"""
    try:
        # 使用自定义的 User-Agent 避免有些站屏蔽 Python-urllib
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return True
    except Exception as e:
        # 捕获所有连接超时、网络不可达、SSL 握手失败等错误
        pass
    return False

def main():
    print("🌐 正在检测 VPN 连通性，尝试连接国外核心节点...")
    
    success = False
    for url in TEST_URLS:
        print(f"  --> 正在尝试连接: {url} ...")
        if check_connection(url):
            print(f"  ✅ 连接成功: {url}")
            success = True
            break
        else:
            print(f"  ❌ 连接超时或被拒绝: {url}")
            
    if success:
        print("\n🎉 VPN 连通性测试通过！外网访问正常。")
        sys.exit(0)
    else:
        print("\n" + "!" * 64)
        print("❌ 错误：未检测到可用的 VPN 连接！")
        print("原因：直连国外核心节点（Wikipedia/Google）超时或被拦截。")
        print("警告：此状态下将无法访问国外核心信息源，严禁强行进行国外人物蒸馏。")
        print("请在系统或终端中开启 VPN 代理后重试。")
        print("!" * 64 + "\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
