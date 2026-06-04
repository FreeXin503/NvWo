"""测试AI任务创建"""
import urllib.request
import json

print("=== 创建AI任务 ===")
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/ai-task",
    method="POST"
)
resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read().decode())
print(json.dumps(result, ensure_ascii=False, indent=2))