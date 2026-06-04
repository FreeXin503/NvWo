"""
更新模块 — 应用差异分析结果，更新调研文件和SKILL.md

支持两种模式:
- auto: 自动追加新素材内容到调研文件（无冲突时）
- manual: 输出提示词，等待AI/人工处理后应用
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from .config import AGENT_FILES, SKILLS_ROOT
from .diff import generate_diff_report, load_existing_research
from .ingest import get_staging_index, load_raw_material, clear_staging


def backup_skill(skill_name: str) -> str:
    """备份当前Skill到.backup目录"""
    skill_dir = Path(SKILLS_ROOT) / skill_name
    backup_dir = skill_dir / ".backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 备份调研文件
    research_dir = skill_dir / "references" / "research"
    if research_dir.exists():
        for f in research_dir.glob("*.md"):
            shutil.copy2(f, backup_dir / f.name)

    # 备份SKILL.md
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        shutil.copy2(skill_md, backup_dir / "SKILL.md")

    return str(backup_dir)


def auto_append_research(
    skill_name: str,
    agent_key: str,
    new_materials: list[dict],
) -> str:
    """
    自动追加新素材到调研文件。
    无冲突时使用，将新素材关键要点追加到调研文件末尾。
    """
    research_dir = Path(SKILLS_ROOT) / skill_name / "references" / "research"
    research_file = research_dir / f"{agent_key}.md"

    existing_content = ""
    if research_file.exists():
        existing_content = research_file.read_text(encoding="utf-8")

    # 构建追加内容
    append_lines = [
        "",
        "---",
        f"## 更新 ({datetime.now().strftime('%Y-%m-%d')})",
        "",
    ]

    for m in new_materials:
        raw = load_raw_material(skill_name, m["content_hash"])
        if not raw:
            continue

        append_lines.append(f"### 素材: {m['title']}")
        append_lines.append(f"来源: {m['source']}")
        if m.get("date_hint"):
            append_lines.append(f"日期: {m['date_hint']}")
        append_lines.append("")

        # 提取关键信息（非URL部分）
        for line in raw.split("\n"):
            line = line.strip()
            if line and not line.startswith("URL:") and not line.startswith("待抓取"):
                append_lines.append(line)
        append_lines.append("")

    updated_content = existing_content + "\n".join(append_lines)
    research_file.write_text(updated_content, encoding="utf-8")

    return str(research_file)


def apply_ai_generated_content(
    skill_name: str,
    agent_key: str,
    new_content: str,
) -> str:
    """
    应用AI生成的新调研文件内容。
    直接替换原有调研文件。
    """
    research_dir = Path(SKILLS_ROOT) / skill_name / "references" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    research_file = research_dir / f"{agent_key}.md"
    research_file.write_text(new_content, encoding="utf-8")
    return str(research_file)


def apply_skill_md_update(skill_name: str, new_skill_content: str) -> str:
    """应用AI生成的SKILL.md更新"""
    skill_dir = Path(SKILLS_ROOT) / skill_name
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(new_skill_content, encoding="utf-8")
    return str(skill_file)


def apply_upgrade(
    skill_name: str,
    auto: bool = False,
    ai_research_updates: dict[str, str] | None = None,
    ai_skill_update: str | None = None,
) -> dict:
    """
    执行升级操作。

    参数:
        skill_name: 技能名称
        auto: 是否自动模式（无冲突时自动追加）
        ai_research_updates: {agent_key: new_content} AI生成的调研文件更新
        ai_skill_update: AI生成的新SKILL.md内容

    返回:
        {"backup_path": str, "updated_files": [str], "warnings": [str]}
    """
    warnings = []
    updated_files = []

    # 备份
    backup_path = backup_skill(skill_name)
    updated_files.append(backup_path)

    # 生成差异报告
    report = generate_diff_report(skill_name)

    if report["summary"]["recommended_action"] == "no_changes":
        warnings.append("没有检测到需要更新的内容")
        return {
            "backup_path": backup_path,
            "updated_files": updated_files,
            "warnings": warnings,
        }

    if ai_research_updates:
        # 使用AI生成的内容
        for agent_key, new_content in ai_research_updates.items():
            path = apply_ai_generated_content(skill_name, agent_key, new_content)
            updated_files.append(path)
    elif auto:
        # 自动模式：追加无冲突的内容
        for agent_key, agent_data in report["per_agent"].items():
            if agent_data["suggested_action"] == "append":
                staging = get_staging_index(skill_name)
                agent_materials = [
                    m for m in staging if agent_key in m.get("agents", [])
                ]
                if agent_materials:
                    path = auto_append_research(
                        skill_name, agent_key, agent_materials
                    )
                    updated_files.append(path)
    else:
        warnings.append(
            "手动模式: 请先处理差异报告，然后提供AI生成的内容再调用apply"
        )

    # 更新SKILL.md
    if ai_skill_update:
        path = apply_skill_md_update(skill_name, ai_skill_update)
        updated_files.append(path)
    elif auto:
        # 自动模式：标记需要更新SKILL.md
        warnings.append(
            "SKILL.md需要AI重新生成。请运行: python -m upgrade_skill regenerate-skill <skill_name>"
        )

    # 清理暂存区
    if auto and not warnings:
        clear_staging(skill_name)

    return {
        "backup_path": backup_path,
        "updated_files": updated_files,
        "warnings": warnings,
    }


def get_upgrade_status(skill_name: str) -> dict:
    """获取技能升级状态"""
    staging = get_staging_index(skill_name)
    existing = load_existing_research(skill_name)

    staging_dir = Path(SKILLS_ROOT) / skill_name / "references" / "staging"
    has_diff = (staging_dir / "diff_report.json").exists()
    has_prompts = (staging_dir / "prompts").exists()

    return {
        "skill_name": skill_name,
        "staging_materials": len(staging),
        "research_files": len(existing),
        "pending_diff": has_diff,
        "pending_prompts": has_prompts,
        "ready_to_apply": has_diff and not staging,
    }