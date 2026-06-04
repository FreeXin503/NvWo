"""
AI任务管理 — 将升级提示词转化为可被Trae AI处理的任务文件

流程:
1. 升级台生成prompts → 写入 task.json（状态: pending）
2. 用户对Trae AI说"升级 <skill_name>"
3. Trae AI读取 task.json，处理每个prompt → 写入结果（状态: completed）
4. 升级台检测到结果 → 用户点击"应用AI结果" → 自动写入调研文件和SKILL.md
"""

import json
from datetime import datetime
from pathlib import Path

from .config import SKILLS_ROOT, AGENT_FILES

TASK_DIR_NAME = "ai_tasks"


def get_task_dir(skill_name: str) -> Path:
    return Path(SKILLS_ROOT) / skill_name / TASK_DIR_NAME


def create_ai_task(skill_name: str, prompts: dict[str, str]) -> dict:
    """
    创建AI任务文件。
    
    参数:
        skill_name: 技能名称
        prompts: {prompt_id: prompt_content} 的字典
    
    返回: 任务摘要
    """
    task_dir = get_task_dir(skill_name)
    task_dir.mkdir(parents=True, exist_ok=True)
    
    tasks = []
    for pid, prompt_content in prompts.items():
        # 推断任务类型
        if pid.startswith("conflict_"):
            task_type = "conflict_resolution"
            agent_key = pid.replace("conflict_", "")
        elif pid.startswith("research_"):
            task_type = "research_update"
            agent_key = pid.replace("research_", "")
        elif pid == "skill_md_update":
            task_type = "skill_update"
            agent_key = None
        else:
            task_type = "unknown"
            agent_key = None
        
        tasks.append({
            "id": pid,
            "type": task_type,
            "agent_key": agent_key,
            "agent_label": AGENT_FILES.get(agent_key, "") if agent_key else "",
            "prompt": prompt_content,
        })
    
    task_data = {
        "skill_name": skill_name,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "tasks": tasks,
        "results": {},
    }
    
    task_file = task_dir / "task.json"
    task_file.write_text(
        json.dumps(task_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    return {
        "skill_name": skill_name,
        "task_count": len(tasks),
        "task_ids": [t["id"] for t in tasks],
        "task_dir": str(task_dir),
        "status": "pending",
        "instruction": f"请对Trae AI说: 升级 {skill_name}",
    }


def get_task_status(skill_name: str) -> dict | None:
    """获取AI任务状态"""
    task_file = get_task_dir(skill_name) / "task.json"
    if not task_file.exists():
        return None
    
    data = json.loads(task_file.read_text(encoding="utf-8"))
    return {
        "skill_name": data["skill_name"],
        "status": data["status"],
        "created_at": data["created_at"],
        "completed_at": data.get("completed_at"),
        "task_count": len(data["tasks"]),
        "completed_count": len(data.get("results", {})),
        "task_ids": [t["id"] for t in data["tasks"]],
        "result_ids": list(data.get("results", {}).keys()),
    }


def load_task(skill_name: str) -> dict | None:
    """加载完整任务数据（供AI处理）"""
    task_file = get_task_dir(skill_name) / "task.json"
    if not task_file.exists():
        return None
    return json.loads(task_file.read_text(encoding="utf-8"))


def save_result(skill_name: str, task_id: str, result_content: str) -> bool:
    """
    保存单个任务的处理结果。
    由Trae AI调用，将处理结果写入task.json。
    """
    task_file = get_task_dir(skill_name) / "task.json"
    if not task_file.exists():
        return False
    
    data = json.loads(task_file.read_text(encoding="utf-8"))
    data.setdefault("results", {})
    data["results"][task_id] = result_content
    
    # 检查是否所有任务都完成了
    all_ids = {t["id"] for t in data["tasks"]}
    done_ids = set(data["results"].keys())
    if all_ids == done_ids:
        data["status"] = "completed"
        data["completed_at"] = datetime.now().isoformat()
    else:
        data["status"] = "partial"
    
    task_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return True


def apply_ai_results(skill_name: str) -> dict:
    """
    将AI处理结果应用到调研文件和SKILL.md。
    由升级台调用。
    """
    task_data = load_task(skill_name)
    if not task_data:
        return {"ok": False, "error": "没有AI任务"}
    
    if task_data["status"] not in ("completed", "partial"):
        return {"ok": False, "error": f"任务状态: {task_data['status']}，请等待AI处理完成"}
    
    results = task_data.get("results", {})
    if not results:
        return {"ok": False, "error": "AI尚未返回任何结果"}
    
    from .update import apply_ai_generated_content, apply_skill_md_update, backup_skill
    
    backup_path = backup_skill(skill_name)
    updated = [backup_path]
    
    for task_id, content in results.items():
        if task_id.startswith("research_") or task_id.startswith("conflict_"):
            # 调研文件更新
            agent_key = task_id.replace("research_", "").replace("conflict_", "")
            path = apply_ai_generated_content(skill_name, agent_key, content)
            updated.append(path)
        elif task_id == "skill_md_update":
            # SKILL.md 更新
            path = apply_skill_md_update(skill_name, content)
            updated.append(path)
    
    # 标记任务为已应用
    task_data["status"] = "applied"
    task_file = get_task_dir(skill_name) / "task.json"
    task_file.write_text(
        json.dumps(task_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    return {
        "ok": True,
        "backup": backup_path,
        "updated": updated,
        "result_count": len(results),
    }