"""测试路径解析"""
from urllib.parse import urlparse, parse_qs

def parse_path(path):
    parsed = urlparse(path)
    path = parsed.path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    query = parse_qs(parsed.query)
    return parts, query

# 测试路径
test_path = "/api/skills/charles-munger-perspective/auto-upgrade"
parts, query = parse_path(test_path)
print(f"Path: {test_path}")
print(f"Parts: {parts}")
print(f"Length: {len(parts)}")
print(f"Parts[:2]: {parts[:2]}")
print(f"Parts[3]: {parts[3]}")
print(f"Match: {len(parts) == 4 and parts[:2] == ['api', 'skills'] and parts[3] == 'auto-upgrade'}")