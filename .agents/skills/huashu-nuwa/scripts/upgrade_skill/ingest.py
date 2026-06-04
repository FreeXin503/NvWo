"""
素材摄入模块 — 解析、分类、存储新素材到暂存区

输入: 文件路径列表、URL列表
输出: 暂存区中按Agent分类的素材摘要
"""

import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .config import AGENT_KEYWORDS, SKILLS_ROOT


def hash_content(text: str) -> str:
    """生成内容指纹，用于去重"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def extract_text_from_file(filepath: str) -> str:
    """从文件提取文本内容"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    ext = path.suffix.lower()

    if ext in (".txt", ".md", ".markdown"):
        return path.read_text(encoding="utf-8")

    if ext == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2)

    # 尝试作为纯文本读取
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"无法解析文件格式: {filepath}")


def extract_title(text: str, source: str = "") -> str:
    """从文本中提取标题"""
    # 优先取第一行markdown标题
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # 取前80个字符作为标题
    first_line = text.split("\n")[0].strip()
    if len(first_line) > 80:
        first_line = first_line[:77] + "..."
    return first_line or f"无标题素材 ({source})"


def categorize_by_agent(text: str) -> dict[str, float]:
    """
    按Agent关键词匹配度给素材打分，返回每个Agent的匹配分数。
    分数越高说明素材越适合该Agent分析。
    """
    text_lower = text.lower()
    scores = {}

    for agent_key, keywords in AGENT_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 1
        # 归一化：分数 / 关键词总数
        scores[agent_key] = score / len(keywords) if keywords else 0

    return scores


def classify_material(text: str, threshold: float = 0.05) -> list[str]:
    """
    将素材分类到最相关的Agent。
    返回Agent key列表（如 ["01-writings", "05-decisions"]）。
    """
    scores = categorize_by_agent(text)
    # 超过阈值的都算相关
    relevant = [k for k, v in scores.items() if v >= threshold]
    # 按分数降序排列
    relevant.sort(key=lambda k: scores[k], reverse=True)

    if not relevant:
        # 默认归入timeline
        return ["06-timeline"]

    return relevant[:3]  # 最多3个分类


def extract_key_points(text: str, max_points: int = 5) -> list[str]:
    """从素材中提取关键要点"""
    points = []

    # 提取markdown列表项
    list_items = re.findall(r"^[-*]\s+(.+)$", text, re.MULTILINE)
    if list_items:
        points.extend(list_items[:max_points])

    # 提取加粗文本
    if len(points) < max_points:
        bolds = re.findall(r"\*\*(.+?)\*\*", text)
        for b in bolds:
            if len(b) > 10 and b not in points:
                points.append(b)
            if len(points) >= max_points:
                break

    # 补充：提取带引号的句子
    if len(points) < max_points:
        quotes = re.findall(r"[「『""]([^」』""]{8,80})[」』""]", text)
        for q in quotes:
            if q not in points:
                points.append(q)
            if len(points) >= max_points:
                break

    return points[:max_points]


def extract_date_hints(text: str) -> Optional[str]:
    """尝试从文本中提取日期信息"""
    date_patterns = [
        r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
        r"(\d{4}年\d{1,2}月)",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def ingest_material(text: str, source: str, source_type: str = "file") -> dict:
    """
    摄入单条素材，返回结构化摘要。

    返回:
        {
            "id": "abc123",
            "source": "文件路径或URL",
            "source_type": "file|url|paste",
            "title": "素材标题",
            "date_hint": "2024-01-15" or None,
            "agents": ["01-writings", "05-decisions"],
            "agent_scores": {"01-writings": 0.3, ...},
            "key_points": ["要点1", "要点2"],
            "content_hash": "abc123def456",
            "content_preview": "前200字...",
            "ingested_at": "2024-06-04T12:00:00",
        }
    """
    content_hash = hash_content(text)
    date_hint = extract_date_hints(text)
    title = extract_title(text, source)
    agents = classify_material(text)
    agent_scores = categorize_by_agent(text)
    key_points = extract_key_points(text)

    return {
        "id": content_hash,
        "source": source,
        "source_type": source_type,
        "title": title,
        "date_hint": date_hint,
        "agents": agents,
        "agent_scores": agent_scores,
        "key_points": key_points,
        "content_hash": content_hash,
        "content_preview": text[:300].replace("\n", " "),
        "ingested_at": datetime.now().isoformat(),
    }


def save_staging(skill_name: str, material: dict, raw_text: str) -> str:
    """
    保存素材到暂存区。

    暂存区结构:
        .agents/skills/<skill_name>/references/staging/
        ├── index.json          # 素材索引
        └── raw/
            ├── {content_hash}.md   # 原始素材
    """
    skill_dir = Path(SKILLS_ROOT) / skill_name
    staging_dir = skill_dir / "references" / "staging"
    raw_dir = staging_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 保存原始文本
    raw_file = raw_dir / f"{material['content_hash']}.md"
    if not raw_file.exists():
        raw_file.write_text(raw_text, encoding="utf-8")

    # 更新索引
    index_file = staging_dir / "index.json"
    index = []
    if index_file.exists():
        index = json.loads(index_file.read_text(encoding="utf-8"))

    # 去重：相同hash的素材不重复添加
    existing_ids = {m["content_hash"] for m in index}
    if material["content_hash"] not in existing_ids:
        index.append(material)
        index_file.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return str(raw_file)


def ingest_files(skill_name: str, filepaths: list[str]) -> list[dict]:
    """批量摄入文件"""
    results = []
    for fp in filepaths:
        text = extract_text_from_file(fp)
        material = ingest_material(text, source=fp, source_type="file")
        save_staging(skill_name, material, text)
        results.append(material)
    return results


def ingest_urls(skill_name: str, urls: list[str]) -> list[dict]:
    """
    批量摄入URL。
    注意：此函数只记录URL元数据，实际网页抓取需要后续步骤。
    返回占位material，标记为待抓取。
    """
    results = []
    for url in urls:
        text = f"URL: {url}\n待抓取内容"
        material = ingest_material(text, source=url, source_type="url")
        material["status"] = "pending_fetch"
        save_staging(skill_name, material, text)
        results.append(material)
    return results


def get_staging_index(skill_name: str) -> list[dict]:
    """获取暂存区索引"""
    index_file = Path(SKILLS_ROOT) / skill_name / "references" / "staging" / "index.json"
    if not index_file.exists():
        return []
    return json.loads(index_file.read_text(encoding="utf-8"))


def load_raw_material(skill_name: str, content_hash: str) -> str:
    """加载暂存区中的原始素材"""
    raw_file = (
        Path(SKILLS_ROOT)
        / skill_name
        / "references"
        / "staging"
        / "raw"
        / f"{content_hash}.md"
    )
    if raw_file.exists():
        return raw_file.read_text(encoding="utf-8")
    return ""


def clear_staging(skill_name: str) -> None:
    """清空暂存区"""
    import shutil
    staging_dir = Path(SKILLS_ROOT) / skill_name / "references" / "staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)