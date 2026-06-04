"""
女娲技能升级工具 — 自动升级蒸馏人物Skill

当有新的素材（文章、访谈、新闻等）时，自动分析差异、
更新调研文件、重新生成SKILL.md。

用法:
    python -m upgrade_skill ingest <skill_name> --files <paths> [--urls <urls>]
    python -m upgrade_skill diff <skill_name>
    python -m upgrade_skill apply <skill_name> [--auto]
    python -m upgrade_skill auto <skill_name> --files <paths> [--urls <urls>]
"""

__version__ = "1.0.0"