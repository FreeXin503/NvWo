"""
差异分析模块 — 对比新素材与现有调研文件，识别新增/冲突/补充信息

输出: 差异报告（JSON + Markdown），供AI或人工审核
"""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .config import AGENT_FILES, SKILLS_ROOT
from .ingest import get_staging_index, load_raw_material


def load_existing_research(skill_name: str) -> dict[str, str]:
    """加载现有调研文件"""
    research_dir = Path(SKILLS_ROOT) / skill_name / "references" / "research"
    existing = {}

    for agent_key in AGENT_FILES:
        md_file = research_dir / f"{agent_key}.md"
        if md_file.exists():
            existing[agent_key] = md_file.read_text(encoding="utf-8")

    return existing


def find_similar_passages(
    new_text: str, existing_text: str, threshold: float = 0.6
) -> list[dict]:
    """
    在新文本中查找与现有调研相似度高的段落。
    返回高相似度匹配列表（可能重复或冲突的内容）。
    """
    # 将文本按段落分割
    new_paras = [p.strip() for p in new_text.split("\n\n") if len(p.strip()) > 50]
    existing_paras = [
        p.strip() for p in existing_text.split("\n\n") if len(p.strip()) > 50
    ]

    matches = []
    for np in new_paras:
        for ep in existing_paras:
            ratio = SequenceMatcher(None, np[:200], ep[:200]).ratio()
            if ratio >= threshold:
                matches.append(
                    {
                        "new_paragraph": np[:300],
                        "existing_paragraph": ep[:300],
                        "similarity": round(ratio, 2),
                        "type": "similar",
                    }
                )

    return matches


def extract_new_entities(new_text: str, existing_text: str) -> list[str]:
    """
    提取新素材中出现了但现有调研中未出现的关键实体。
    实体: 人名、地名、组织名、专有名词。
    """
    # 简单实现：提取markdown加粗、中文引号、英文引号中的内容
    patterns = [
        r"\*\*(.+?)\*\*",
        r"[「『""]([^」』""]{2,30})[」』""]",
        r"`([^`]+)`",
    ]

    new_entities = set()
    existing_entities = set()

    for pattern in patterns:
        new_entities.update(re.findall(pattern, new_text))
        existing_entities.update(re.findall(pattern, existing_text))

    return sorted(new_entities - existing_entities)


def detect_conflicts(new_text: str, existing_text: str) -> list[dict]:
    """
    检测新素材与现有调研的矛盾点。
    使用关键词标记检测可能的矛盾。
    """
    conflict_markers = [
        # (冲突标记, 新文本关键词, 现有文本关键词)
        (r"(?:实际上|然而|但事实上|并非如此|相反)", "contradiction"),
        (r"(?:修正|纠正|错误|误解|misunderstand)", "correction"),
        (r"(?:新的|更新|最新|updated|latest|recent)", "update"),
    ]

    conflicts = []

    for marker_pattern, conflict_type in conflict_markers:
        new_matches = re.findall(
            marker_pattern + r".{0,100}", new_text, re.IGNORECASE
        )
        for nm in new_matches:
            # 在现有文本中找是否有关联内容
            conflicts.append(
                {
                    "type": conflict_type,
                    "new_text_snippet": nm[:150],
                    "description": f"新素材含有{conflict_type}标记，可能挑战现有认知",
                }
            )

    return conflicts[:10]  # 最多10条


def generate_diff_report(skill_name: str) -> dict:
    """
    生成完整的差异分析报告。

    返回结构:
    {
        "skill_name": "chen-pingan-perspective",
        "generated_at": "2024-06-04T12:00:00",
        "staging_materials": [...],  # 暂存素材列表
        "per_agent": {
            "01-writings": {
                "new_materials": [...],      # 该Agent相关的新素材
                "new_entities": [...],       # 新出现的实体
                "similar_passages": [...],   # 与现有调研相似的内容
                "conflicts": [...],          # 潜在矛盾
                "suggested_action": "append|review|skip",
            },
            ...
        },
        "summary": {
            "total_new_materials": 5,
            "total_new_entities": 12,
            "total_conflicts": 2,
            "agents_with_changes": ["01-writings", "05-decisions"],
            "recommended_action": "review_and_apply",
        }
    }
    """
    staging = get_staging_index(skill_name)
    existing = load_existing_research(skill_name)

    per_agent = {}
    total_new_entities = 0
    total_conflicts = 0
    agents_with_changes = []

    for agent_key in AGENT_FILES:
        # 筛选该Agent相关的暂存素材
        agent_materials = [
            m for m in staging if agent_key in m.get("agents", [])
        ]

        if not agent_materials and agent_key not in existing:
            per_agent[agent_key] = {
                "new_materials": [],
                "new_entities": [],
                "similar_passages": [],
                "conflicts": [],
                "suggested_action": "skip",
            }
            continue

        # 合并该Agent所有新素材文本
        new_text = ""
        for m in agent_materials:
            raw = load_raw_material(skill_name, m["content_hash"])
            new_text += raw + "\n\n"

        existing_text = existing.get(agent_key, "")

        # 找新实体
        new_entities = extract_new_entities(new_text, existing_text)
        total_new_entities += len(new_entities)

        # 找相似段落
        similar = find_similar_passages(new_text, existing_text)

        # 检测冲突
        conflicts = detect_conflicts(new_text, existing_text)
        total_conflicts += len(conflicts)

        # 建议操作
        if not agent_materials:
            suggested_action = "skip"
        elif conflicts:
            suggested_action = "review"
        elif new_entities or agent_materials:
            suggested_action = "append"
        else:
            suggested_action = "skip"

        if suggested_action != "skip":
            agents_with_changes.append(agent_key)

        per_agent[agent_key] = {
            "new_materials": [
                {
                    "id": m["content_hash"],
                    "title": m["title"],
                    "source": m["source"],
                    "date_hint": m.get("date_hint"),
                    "key_points": m["key_points"],
                }
                for m in agent_materials
            ],
            "new_entities": new_entities,
            "similar_passages": similar,
            "conflicts": conflicts,
            "suggested_action": suggested_action,
        }

    # 确定整体建议
    if total_conflicts > 0:
        recommended_action = "review_and_apply"
    elif agents_with_changes:
        recommended_action = "auto_append"
    else:
        recommended_action = "no_changes"

    return {
        "skill_name": skill_name,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "staging_materials": [
            {
                "id": m["content_hash"],
                "title": m["title"],
                "source": m["source"],
                "agents": m["agents"],
                "key_points": m["key_points"],
            }
            for m in staging
        ],
        "per_agent": per_agent,
        "summary": {
            "total_new_materials": len(staging),
            "total_new_entities": total_new_entities,
            "total_conflicts": total_conflicts,
            "agents_with_changes": agents_with_changes,
            "recommended_action": recommended_action,
        },
    }


def format_diff_markdown(report: dict) -> str:
    """将差异报告格式化为Markdown"""
    lines = [
        f"# 升级差异报告: {report['skill_name']}",
        f"生成时间: {report['generated_at']}",
        "",
        "## 概览",
        f"- 新素材: {report['summary']['total_new_materials']} 条",
        f"- 新实体: {report['summary']['total_new_entities']} 个",
        f"- 潜在冲突: {report['summary']['total_conflicts']} 处",
        f"- 涉及Agent: {', '.join(report['summary']['agents_with_changes']) or '无'}",
        f"- 建议操作: **{report['summary']['recommended_action']}**",
        "",
    ]

    # 暂存素材列表
    if report["staging_materials"]:
        lines.append("## 新素材列表")
        lines.append("")
        for m in report["staging_materials"]:
            lines.append(f"- **{m['title']}** ({m['source']})")
            lines.append(f"  - Agent: {', '.join(m['agents'])}")
            if m.get("key_points"):
                for kp in m["key_points"][:3]:
                    lines.append(f"  - 要点: {kp}")
            lines.append("")

    # 按Agent详细报告
    for agent_key, agent_data in report["per_agent"].items():
        if agent_data["suggested_action"] == "skip":
            continue

        agent_label = AGENT_FILES.get(agent_key, agent_key)
        lines.append(f"## {agent_label} ({agent_key})")
        lines.append(f"操作: **{agent_data['suggested_action']}**")
        lines.append("")

        if agent_data["new_entities"]:
            lines.append(
                f"### 新实体 ({len(agent_data['new_entities'])}个)"
            )
            lines.append(", ".join(agent_data["new_entities"][:20]))
            lines.append("")

        if agent_data["conflicts"]:
            lines.append(f"### 潜在冲突 ({len(agent_data['conflicts'])}处)")
            for c in agent_data["conflicts"]:
                lines.append(
                    f"- [{c['type']}] {c['description']}"
                )
                lines.append(f"  - 文本: {c['new_text_snippet'][:100]}")
            lines.append("")

        if agent_data["new_materials"]:
            lines.append(f"### 相关素材 ({len(agent_data['new_materials'])}条)")
            for m in agent_data["new_materials"]:
                lines.append(f"- {m['title']} ({m['source']})")
                if m.get("date_hint"):
                    lines.append(f"  - 日期: {m['date_hint']}")
            lines.append("")

    return "\n".join(lines)


def save_diff_report(skill_name: str, report: dict) -> str:
    """保存差异报告到暂存区"""
    staging_dir = Path(SKILLS_ROOT) / skill_name / "references" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    # JSON版
    json_path = staging_dir / "diff_report.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Markdown版
    md_path = staging_dir / "diff_report.md"
    md_content = format_diff_markdown(report)
    md_path.write_text(md_content, encoding="utf-8")

    return str(md_path)