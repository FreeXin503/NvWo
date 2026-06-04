"""
AI提示词生成模块 — 为新素材生成合适的AI处理提示词

输出: 结构化提示词，供AI（LLM）分析新素材并更新调研文件/SKILL.md
"""

import json
from pathlib import Path
from datetime import datetime

from .config import AGENT_FILES, SKILLS_ROOT
from .ingest import get_staging_index


def generate_research_update_prompt(
    skill_name: str,
    agent_key: str,
    new_materials: list[dict],
    existing_content: str,
    new_entities: list[str],
    conflicts: list[dict],
) -> str:
    """
    生成更新调研文件的AI提示词。
    返回完整的prompt字符串，可直接喂给LLM。
    """
    agent_label = AGENT_FILES.get(agent_key, agent_key)

    materials_text = ""
    for m in new_materials:
        raw_file = (
            Path(SKILLS_ROOT)
            / skill_name
            / "references"
            / "staging"
            / "raw"
            / f"{m['content_hash']}.md"
        )
        if raw_file.exists():
            content = raw_file.read_text(encoding="utf-8")
            materials_text += f"\n### 素材: {m['title']}\n来源: {m['source']}\n\n{content}\n\n---\n"

    prompt = f"""# 任务: 更新调研文件

你是女娲技能升级系统的分析引擎。请分析以下新素材，更新 `{agent_label}` ({agent_key}) 的调研文件。

## 现有调研内容

{existing_content[:3000]}

## 新素材

{materials_text[:5000]}

## 新发现的实体

{', '.join(new_entities[:20]) if new_entities else '无'}

## 潜在冲突

{json.dumps(conflicts[:3], ensure_ascii=False, indent=2) if conflicts else '无'}

## 要求

请输出更新后的完整调研文件内容（Markdown格式）。更新规则：

1. **追加新信息**：在现有内容中合理位置插入新发现，保持原有结构
2. **保留原有内容**：除非新信息明确修正了旧信息，否则不要删除现有内容
3. **标注来源**：新增内容需标注来源（新素材的文件名或URL）
4. **处理冲突**：如果新旧信息矛盾，同时保留并标注「[待确认] [新素材]」和「[原调研]」
5. **更新时间戳**：在文件末尾更新调研时间

仅输出更新后的markdown内容，不要输出解释性文字。
"""
    return prompt


def generate_skill_update_prompt(
    skill_name: str,
    existing_skill: str,
    updated_research: dict[str, str],
    staging_summary: list[dict],
) -> str:
    """
    生成更新SKILL.md的AI提示词。
    传入更新后的调研文件内容，生成新的SKILL.md。
    """
    N = len(staging_summary)
    research_summary = ""
    for agent_key, content in updated_research.items():
        agent_label = AGENT_FILES.get(agent_key, agent_key)
        # 只取每个Agent的关键段落
        research_summary += f"\n## {agent_label} 关键更新\n\n{content[-2000:]}\n\n"

    staging_text = json.dumps(staging_summary, ensure_ascii=False, indent=2)

    prompt = f"""# 任务: 更新 SKILL.md

你是女娲技能升级系统的合成引擎。请基于更新后的调研文件，重新生成完整的SKILL.md。

## 当前SKILL.md

{existing_skill[:2000]}

## 更新后的调研摘要

{research_summary[:5000]}

## 新素材列表

{staging_text[:2000]}

## 要求

在现有SKILL.md基础上进行增量更新（不是完全重写）：

1. **心智模型**：如果有新的行为模式或持续验证，可新增或调整心智模型。保留原有模型结构。
2. **决策启发式**：如果有新的决策案例，追加到对应启发式的「案例」中。
3. **表达DNA**：如果新素材揭示了新的表达特征，补充细节。
4. **时间线**：如果有新事件，追加到时间线表格中。
5. **最新动态**：更新为最新时间。
6. **诚实边界**：如果可以填补之前的诚实边界条目，更新之。
7. **调研来源**：在附录中追加新素材来源。
8. **版本标记**：在诚实边界中追加「升级时间: {datetime.now().strftime('%Y年%m月%d日')}，新增{N}条素材」

仅输出更新后的完整SKILL.md内容，不要输出解释性文字。
"""
    return prompt


def generate_conflict_resolution_prompt(
    skill_name: str,
    agent_key: str,
    conflicts: list[dict],
    existing_content: str,
) -> str:
    """生成冲突解决提示词"""
    agent_label = AGENT_FILES.get(agent_key, agent_key)

    return f"""# 任务: 解决调研冲突

## 背景
在更新 `{skill_name}` 的 `{agent_label}` 调研文件时，发现了以下潜在冲突：

{json.dumps(conflicts, ensure_ascii=False, indent=2)}

## 现有调研内容（相关部分）

{existing_content[:2000]}

## 要求

请分析每个冲突，判断：
1. 是新信息修正了旧认知？→ 标注「修正」
2. 是不同时间阶段的观点变化？→ 标注「时间演化」，保留两个版本
3. 是不同场景下的不同表现？→ 标注「场景差异」，分场景记录
4. 是真正的矛盾？→ 标注「待确认」，并列呈现

输出格式:
```json
[
  {{
    "conflict_index": 0,
    "resolution": "修正|时间演化|场景差异|待确认",
    "explanation": "解释",
    "recommended_action": "替换旧内容|追加新内容|并列呈现|保留原内容"
  }}
]
```
"""


def save_prompts(skill_name: str, prompts: dict) -> str:
    """保存提示词到暂存区"""
    staging_dir = Path(SKILLS_ROOT) / skill_name / "references" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    prompts_dir = staging_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    for name, content in prompts.items():
        file_path = prompts_dir / f"{name}.md"
        file_path.write_text(content, encoding="utf-8")

    return str(prompts_dir)