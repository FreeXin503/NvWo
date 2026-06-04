"""测试脚本 - 完整升级流程"""
import urllib.request
import json

# 1. 导入素材
print("=== 1. 导入素材 ===")
data = {
    "text": "陈平安在2024年新章节中，第十五次破碎后重建，领悟了新的剑道境界。他说：「我陈平安，剑在手中，道在心中。不为天下，只求心安。」标志着他的思想从护天下转变为求心安。"
}
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/ingest",
    json.dumps(data).encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
print(json.loads(resp.read().decode()))

# 2. 创建AI任务
print("\n=== 2. 创建AI任务 ===")
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/ai-task",
    method="POST"
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read().decode())
print(result)

# 3. 运行AI升级处理
print("\n=== 3. 运行AI处理 ===")
import subprocess
result = subprocess.run(
    ["py", "upgrade_handler.py", "chen-pingan-perspective"],
    cwd="e:\\GzrjxyGzrjxyGzrjxyGzrjxy\\opencode\\nvwo\\upgrade_station",
    capture_output=True,
    text=True
)
print(result.stdout)
if result.stderr:
    print("stderr:", result.stderr)

# 4. 检查任务状态
print("\n=== 4. 检查任务状态 ===")
resp = urllib.request.urlopen("http://localhost:8866/api/skills/chen-pingan-perspective/ai-task")
print(json.loads(resp.read().decode()))

# 5. 应用AI结果
print("\n=== 5. 应用AI结果 ===")
req = urllib.request.Request(
    "http://localhost:8866/api/skills/chen-pingan-perspective/ai-task/apply",
    method="POST"
)
resp = urllib.request.urlopen(req)
print(json.loads(resp.read().decode()))

print("\n🎉 完整流程测试完成!")