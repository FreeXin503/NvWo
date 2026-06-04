"""批量搜索资料并升级所有蒸馏人"""
import urllib.request
import json
import time

# 设置标准输出为UTF-8
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 先确保服务器启动
print("=== 批量升级所有蒸馏人 ===")
print("等待服务器就绪...")
time.sleep(2)

# 获取所有技能列表
resp = urllib.request.urlopen('http://localhost:8866/api/skills')
skills = json.loads(resp.read().decode())['skills']

# 过滤出蒸馏人技能
perspective_skills = [s for s in skills if '-perspective' in s['name']]
print("找到 {} 个蒸馏人技能".format(len(perspective_skills)))

# 为每个蒸馏人执行一键自动升级（带搜索）
success_count = 0
failed_count = 0

for skill in perspective_skills:
    name = skill['name']
    display_name = skill['display_name']
    
    print("\n--- 正在升级: {} ---".format(display_name))
    
    try:
        # 调用一键自动升级API（开启搜索）
        data = json.dumps({
            'search': True,
            'useUploaded': True
        }).encode('utf-8')
        
        req = urllib.request.Request(
            'http://localhost:8866/api/skills/{}/auto-upgrade'.format(name),
            data=data,
            method='POST',
            headers={'Content-Type': 'application/json'}
        )
        
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode())
        
        if result.get('ok'):
            print("[OK] 升级成功")
            for step in result.get('steps', []):
                # 清理emoji
                step_clean = ''.join(c for c in step if ord(c) < 128)
                print("   {}".format(step_clean))
            success_count += 1
        else:
            print("[FAIL] 升级失败")
            if result.get('errors'):
                for err in result['errors']:
                    err_clean = ''.join(c for c in err if ord(c) < 128)
                    print("   {}".format(err_clean))
            failed_count += 1
            
    except Exception as e:
        print("[FAIL] 升级失败: {}".format(e))
        failed_count += 1

print("\n=== 批量升级完成 ===")
print("成功: {}".format(success_count))
print("失败: {}".format(failed_count))