"""测试auto-upgrade API"""
import urllib.request
import json
import sys

url = 'http://localhost:8866/api/skills/charles-munger-perspective/auto-upgrade'
data = json.dumps({'search': True}).encode('utf-8')

req = urllib.request.Request(url, data=data, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('Content-Length', len(data))

resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read().decode('utf-8'))

# 使用ASCII输出
print("Status:", result.get('ok'))
print("Message:", result.get('message'))
print("\nSteps:")
for step in result.get('steps', []):
    # 移除emoji
    step_clean = ''.join(c for c in step if ord(c) < 128)
    print(f"  {step_clean}")