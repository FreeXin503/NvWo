"""测试批量升级流程"""
import urllib.request
import json
import subprocess

# 测试1: 为陈平安添加素材
print("=== 测试1: 导入素材 ===")
data = {
    "text": "陈平安在2024年新章节中，领悟了新的剑道境界。他说：「我陈平安，剑在手中，道在心中。」"
}
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/ingest",
    json.dumps(data).encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
print("陈平安素材导入:", json.loads(resp.read().decode()))

# 测试2: 创建AI任务
print("\n=== 测试2: 创建AI任务 ===")
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/ai-task",
    method="POST"
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read().decode())
print(json.dumps(result, ensure_ascii=False, indent=2))

# 测试3: 运行升级处理脚本（模拟"升级全部"命令）
print("\n=== 测试3: 运行升级处理 ===")
result = subprocess.run(
    ["py", "upgrade_handler.py", "chen-pingan-perspective"],
    cwd="e:\\GzrjxyGzrjxyGzrjxyGzrjxy\\opencode\\nvwo\\upgrade_station",
    capture_output=True,
    text=True,
    encoding="utf-8"
)
print("stdout:", result.stdout)
if result.stderr:
    print("stderr:", result.stderr)

# 测试4: 检查任务状态
print("\n=== 测试4: 检查任务状态 ===")
resp = urllib.request.urlopen("http://localhost:8866/api/skills/chen-pingan-perspective/ai-task")
print(json.loads(resp.read().decode()))

print("\n🎉 批量升级测试完成!")