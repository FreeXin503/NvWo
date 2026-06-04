"""详细测试POST请求"""
import urllib.request
import json
import sys

try:
    url = 'http://localhost:8866/api/skills/charles-munger-perspective/auto-upgrade'
    data = json.dumps({'search': True}).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Content-Length', len(data))
    
    print(f"URL: {url}")
    print(f"Data: {data.decode()}")
    print(f"Content-Type: application/json")
    print(f"Content-Length: {len(data)}")
    print("Sending request...")
    
    resp = urllib.request.urlopen(req, timeout=30)
    print(f"Response code: {resp.getcode()}")
    print(f"Response headers: {resp.info()}")
    print(f"Response body: {resp.read().decode()}")
    
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.reason}")
    print(f"Response body: {e.read().decode() if e.fp else 'N/A'}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {type(e).__name__} - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)