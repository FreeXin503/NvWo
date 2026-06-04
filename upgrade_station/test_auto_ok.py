"""测试auto-upgrade API"""
import urllib.request
import json

url = 'http://localhost:8866/api/skills/charles-munger-perspective/auto-upgrade'
data = json.dumps({'search': True}).encode('utf-8')

req = urllib.request.Request(url, data=data, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('Content-Length', len(data))

resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read().decode('utf-8'))
print(json.dumps(result, ensure_ascii=False, indent=2))