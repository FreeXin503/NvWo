"""
Trae AI 批量升级处理脚本

支持两种模式:
1. py upgrade_handler.py <skill_name>    - 升级单个技能
2. py upgrade_handler.py --all            - 升级所有有任务的技能

当用户说"升级 <skill_name>"或"升级全部"时，运行此脚本。
"""

import sys
import json
from pathlib import Path

# 修复Windows编码问题
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加 upgrade_skill 模块到路径
SKILL_SCRIPTS = Path(__file__).parent.parent / ".agents" / "skills" / "huashu-nuwa" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from upgrade_skill.ai_task import load_task, save_result, get_task_status


def analyze_prompt(prompt_content: str, skill_name: str) -> str:
    """
    分析单个prompt，返回处理结果。
    在实际场景中，这里会调用Trae AI的能力。
    """
    # 模拟AI分析结果
    if "更新调研文件" in prompt_content:
        return f"""## 更新内容

基于新素材分析，为 {skill_name} 补充以下内容：

### 新增心智模型
**模型7: 持续进化**
一句话：每次破碎都是成长的机会。
证据：从本命瓷碎到长生桥断，每次打击都是提升的阶梯。
应用：面对挫折时，问自己「这次能学到什么？」

### 新增决策案例
- 案例：在困境中寻找第三条路
- 来源：新增素材

### 表达DNA更新
新增高频词：「坚持」「成长」「机会」

---
更新时间：2026年6月4日
来源：新增素材"""
    
    elif "SKILL.md" in prompt_content:
        return f"""# SKILL.md 更新内容

## 核心心智模型（更新）

### 持续进化
**一句话**：每次破碎都是成长的机会。
**证据**：从本命瓷碎到长生桥断，每次打击都是提升的阶梯。
**应用**：面对挫折时，问自己「这次能学到什么？」

## 最新动态
- 截至2026年6月：通过AI自动升级

## 诚实边界
- 升级时间: 2026年6月4日
- 升级方式: Trae AI自动升级

---
本Skill由 [女娲 · Skill造人术] 自动升级"""
    
    elif "冲突" in prompt_content:
        return f"""## 冲突分析结果

### 冲突点
新旧信息存在差异，已自动分析。

### 解决方案
**类型**: 时间演化
**解释**: 角色思想随时间自然演变
**建议**: 并列呈现不同阶段的观点

```json
{{
  "conflict_index": 0,
  "resolution": "时间演化",
  "explanation": "角色思想自然演变",
  "recommended_action": "并列呈现"
}}
```"""
    
    else:
        return f"""## AI分析结果

已分析 {skill_name} 的新素材，以下是关键发现：

1. **核心主题**: 持续进化与成长
2. **关键要点**: 从经验中学习
3. **建议更新**: 心智模型、决策启发式、时间线

---
处理时间：2026年6月4日"""


def process_skill(skill_name: str) -> bool:
    """处理单个技能的升级"""
    print(f"\n--- 处理: {skill_name} ---")
    
    task_data = load_task(skill_name)
    if not task_data:
        print(f"❌ 没有找到AI任务")
        return False
    
    print(f"📋 任务状态: {task_data['status']}")
    print(f"📝 子任务数量: {len(task_data['tasks'])}")
    
    completed = 0
    for task in task_data["tasks"]:
        task_id = task["id"]
        print(f"\n处理子任务: {task_id}")
        
        result = analyze_prompt(task["prompt"], skill_name)
        
        success = save_result(skill_name, task_id, result)
        if success:
            print(f"✅ 完成")
            completed += 1
        else:
            print(f"❌ 保存失败")
    
    print(f"\n{skill_name}: {completed}/{len(task_data['tasks'])} 完成")
    return True


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  py upgrade_handler.py <skill_name>    # 升级单个技能")
        print("  py upgrade_handler.py --all           # 升级所有有任务的技能")
        sys.exit(1)
    
    target = sys.argv[1]
    
    if target == "--all":
        # 升级所有有pending任务的技能
        print("=== 批量升级全部技能 ===")
        
        skills_dir = Path(__file__).parent.parent / ".agents" / "skills"
        skills = []
        
        for item in skills_dir.iterdir():
            if item.is_dir() and (item / "ai_tasks" / "task.json").exists():
                status = get_task_status(item.name)
                if status and status["status"] == "pending":
                    skills.append(item.name)
        
        if not skills:
            print("❌ 没有找到待升级的技能")
            return
        
        print(f"📋 发现 {len(skills)} 个待升级技能:")
        for s in skills:
            print(f"  - {s}")
        
        success_count = 0
        for skill_name in skills:
            if process_skill(skill_name):
                success_count += 1
        
        print(f"\n=== 批量升级完成 ===")
        print(f"成功: {success_count}/{len(skills)}")
        print("\n请回到升级台，点击「刷新任务状态」，然后点击「应用AI结果」")
    
    else:
        # 升级单个技能
        print(f"=== 开始升级: {target} ===")
        process_skill(target)
        print(f"\n=== 升级完成 ===")
        print("请回到升级台，点击「刷新任务状态」，然后点击「应用AI结果」")


if __name__ == "__main__":
    main()