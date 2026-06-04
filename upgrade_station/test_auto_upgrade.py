"""测试一键自动升级功能"""
import urllib.request
import json
import time

print("=== 测试一键自动升级 ===")
print("等待服务器启动...")
time.sleep(2)

# 测试1: 一键自动升级
print("\n1. 调用一键自动升级API")
data = {
    "search": True,
    "useUploaded": True,
}
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/auto-upgrade",
    json.dumps(data).encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/json"}
)

try:
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read().decode())
    print("✅ 请求成功")
    print("\n升级步骤:")
    for step in result.get("steps", []):
        print(f"  {step}")
    if result.get("message"):
        print(f"\n{result['message']}")
except Exception as e:
    print(f"❌ 请求失败: {e}")

# 测试2: 搜索功能
print("\n\n=== 测试搜索功能 ===")
data = {"query": "陈平安 剑来"}
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/search",
    json.dumps(data).encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/json"}
)

try:
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode())
    print(f"✅ 搜索成功，查询: {result['query']}")
    print(f"找到 {len(result['results'])} 条结果")
    for r in result['results'][:3]:
        print(f"\n📄 {r['title']} ({r['source']})")
        print(f"   相关性: {r['relevance']}")
        print(f"   摘要: {r['content'][:100]}...")
except Exception as e:
    print(f"❌ 搜索失败: {e}")

print("\n🎉 测试完成!")