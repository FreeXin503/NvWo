#!/usr/bin/env python3
"""
女娲技能升级工具 — CLI入口

用法:
    # 1. 摄入新素材
    python -m upgrade_skill ingest <skill_name> --files a.md b.txt --urls https://...

    # 2. 生成差异报告
    python -m upgrade_skill diff <skill_name>

    # 3. 生成AI提示词
    python -m upgrade_skill prompts <skill_name>

    # 4. 应用升级（自动模式，无冲突时）
    python -m upgrade_skill apply <skill_name> --auto

    # 5. 一键全套（ingest + diff + apply --auto）
    python -m upgrade_skill auto <skill_name> --files a.md --urls https://...

    # 6. 查看状态
    python -m upgrade_skill status <skill_name>

    # 7. 清理暂存区
    python -m upgrade_skill clear <skill_name>

示例:
    python -m upgrade_skill auto chen-pingan-perspective --files ./new_interview.txt
    python -m upgrade_skill ingest chen-pingan-perspective --urls https://example.com/article
    python -m upgrade_skill diff chen-pingan-perspective
"""

import argparse
import os
import sys
from pathlib import Path

# 修复Windows GBK编码问题: 使用ASCII安全输出
def _safe_print(*args, **kwargs):
    """安全打印，自动替换emoji为ASCII"""
    text = " ".join(str(a) for a in args)
    replacements = {
        "\u2705": "[OK]", "\u274c": "[FAIL]", "\u274e": "[FAIL]",
        "\U0001f4c4": "[FILE]", "\U0001f4dd": "[PROMPT]",
        "\u26a0\ufe0f": "[WARN]", "\u26a0": "[WARN]",
        "\U0001f389": "[DONE]", "\U0001f4e3": "[INFO]",
        "\u2709\ufe0f": "[MAIL]",
    }
    for emoji, ascii_val in replacements.items():
        text = text.replace(emoji, ascii_val)
    print(text, **kwargs)

from . import __version__
from .config import SKILLS_ROOT, AGENT_FILES
from .ingest import ingest_files, ingest_urls, get_staging_index, clear_staging
from .diff import generate_diff_report, save_diff_report
from .prompts import (
    generate_research_update_prompt,
    generate_skill_update_prompt,
    generate_conflict_resolution_prompt,
    save_prompts,
)
from .update import apply_upgrade, get_upgrade_status, load_existing_research


def cmd_ingest(args):
    """摄入新素材"""
    skill_name = args.skill_name
    results = []

    if args.files:
        filepaths = [str(Path(f).resolve()) for f in args.files]
        results.extend(ingest_files(skill_name, filepaths))

    if args.urls:
        results.extend(ingest_urls(skill_name, args.urls))

    if args.text:
        from .ingest import ingest_material, save_staging
        material = ingest_material(args.text, source="命令行输入", source_type="paste")
        save_staging(skill_name, material, args.text)
        results.append(material)

    _safe_print(f"[OK] 已摄入 {len(results)} 条素材到 {skill_name}")
    for r in results:
        agents_str = ", ".join(r.get("agents", []))
        _safe_print(f"   [FILE] {r['title'][:60]}")
        _safe_print(f"      分类: {agents_str}")
        if r.get("key_points"):
            for kp in r["key_points"][:2]:
                _safe_print(f"      要点: {kp}")
    _safe_print()
    _safe_print(f"下一步: python -m upgrade_skill diff {skill_name}")


def cmd_diff(args):
    """生成差异报告"""
    skill_name = args.skill_name
    staging = get_staging_index(skill_name)

    if not staging:
        _safe_print(f"[FAIL] {skill_name} 暂存区为空，请先摄入素材")
        _safe_print(f"   python -m upgrade_skill ingest {skill_name} --files <paths>")
        return

    _safe_print(f"正在分析 {len(staging)} 条素材...")
    report = generate_diff_report(skill_name)
    md_path = save_diff_report(skill_name, report)

    _safe_print(f"[OK] 差异报告已生成")
    _safe_print(f"   JSON: references/staging/diff_report.json")
    _safe_print(f"   MD:   {md_path}")
    _safe_print()
    _safe_print(f"概览:")
    _safe_print(f"   新素材: {report['summary']['total_new_materials']} 条")
    _safe_print(f"   新实体: {report['summary']['total_new_entities']} 个")
    _safe_print(f"   潜在冲突: {report['summary']['total_conflicts']} 处")
    _safe_print(f"   建议操作: {report['summary']['recommended_action']}")
    _safe_print()

    if report["summary"]["recommended_action"] == "auto_append":
        _safe_print(f"下一步: python -m upgrade_skill apply {skill_name} --auto")
    elif report["summary"]["recommended_action"] == "review_and_apply":
        _safe_print(f"[WARN] 检测到潜在冲突，请先审核差异报告")
        _safe_print(f"   1. 查看: references/staging/diff_report.md")
        _safe_print(f"   2. 生成AI提示词: python -m upgrade_skill prompts {skill_name}")
    else:
        _safe_print(f"未检测到需要更新的内容")


def cmd_prompts(args):
    """生成AI提示词"""
    skill_name = args.skill_name

    # 先确保有差异报告
    staging_dir = Path(SKILLS_ROOT) / skill_name / "references" / "staging"
    diff_file = staging_dir / "diff_report.json"
    if not diff_file.exists():
        _safe_print("正在生成差异报告...")
        report = generate_diff_report(skill_name)
        save_diff_report(skill_name, report)
    else:
        import json
        report = json.loads(diff_file.read_text(encoding="utf-8"))

    existing = load_existing_research(skill_name)
    staging = get_staging_index(skill_name)
    prompts = {}

    # 为每个有变更的Agent生成提示词
    for agent_key, agent_data in report["per_agent"].items():
        if agent_data["suggested_action"] == "skip":
            continue

        if agent_data["conflicts"]:
            prompt = generate_conflict_resolution_prompt(
                skill_name,
                agent_key,
                agent_data["conflicts"],
                existing.get(agent_key, ""),
            )
            prompts[f"conflict_{agent_key}"] = prompt

        if agent_data["suggested_action"] in ("append", "review"):
            agent_materials = [
                m for m in staging if agent_key in m.get("agents", [])
            ]
            prompt = generate_research_update_prompt(
                skill_name,
                agent_key,
                agent_materials,
                existing.get(agent_key, ""),
                agent_data["new_entities"],
                agent_data["conflicts"],
            )
            prompts[f"research_{agent_key}"] = prompt

    # 生成SKILL.md更新提示词
    skill_md = Path(SKILLS_ROOT) / skill_name / "SKILL.md"
    if skill_md.exists():
        prompt = generate_skill_update_prompt(
            skill_name,
            skill_md.read_text(encoding="utf-8"),
            existing,
            [
                {"title": m["title"], "source": m["source"], "agents": m["agents"]}
                for m in staging
            ],
        )
        prompts["skill_md"] = prompt

    prompts_dir = save_prompts(skill_name, prompts)

    _safe_print(f"[OK] 已生成 {len(prompts)} 个AI提示词")
    _safe_print(f"   保存位置: {prompts_dir}")
    _safe_print()
    for name in prompts:
        _safe_print(f"   [PROMPT] {name}.md")


def cmd_apply(args):
    """应用升级"""
    skill_name = args.skill_name

    if args.auto:
        _safe_print(f"自动模式: 正在升级 {skill_name}...")
        result = apply_upgrade(skill_name, auto=True)

        _safe_print(f"[OK] 备份: {result['backup_path']}")
        for f in result["updated_files"]:
            _safe_print(f"   已更新: {f}")
        for w in result["warnings"]:
            _safe_print(f"   [WARN] {w}")

        if not result["warnings"]:
            _safe_print(f"\n[DONE] 升级完成! 请运行质量检查:")
            _safe_print(f"   python quality_check.py {skill_name}/SKILL.md")
    else:
        _safe_print("手动模式: 请先处理提示词，然后将AI输出传入")
        _safe_print("用法: python -m upgrade_skill apply <skill_name> --research <json_file> --skill <md_file>")


def cmd_auto(args):
    """一键全套: ingest + diff + apply --auto"""
    skill_name = args.skill_name

    # Step 1: Ingest
    if args.files or args.urls or args.text:
        _safe_print("=" * 50)
        _safe_print("Step 1/3: 摄入素材")
        _safe_print("=" * 50)
        cmd_ingest(args)
        _safe_print()

    # Step 2: Diff
    _safe_print("=" * 50)
    _safe_print("Step 2/3: 差异分析")
    _safe_print("=" * 50)
    cmd_diff(args)
    _safe_print()

    # Step 3: Prompt generation
    _safe_print("=" * 50)
    _safe_print("Step 3/3: 生成AI提示词")
    _safe_print("=" * 50)
    cmd_prompts(args)
    _safe_print()

    _safe_print("=" * 50)
    _safe_print("[OK] 提示词已就绪。请将 prompts/ 目录下的提示词喂给AI，")
    _safe_print("   然后将AI输出传回: python -m upgrade_skill apply <skill_name>")
    _safe_print("=" * 50)


def cmd_status(args):
    """查看升级状态"""
    skill_name = args.skill_name
    status = get_upgrade_status(skill_name)

    _safe_print(f"技能: {status['skill_name']}")
    _safe_print(f"暂存素材: {status['staging_materials']} 条")
    _safe_print(f"调研文件: {status['research_files']} 个")
    _safe_print(f"差异报告: {'[OK] 已生成' if status['pending_diff'] else '[FAIL] 未生成'}")
    _safe_print(f"AI提示词: {'[OK] 已生成' if status['pending_prompts'] else '[FAIL] 未生成'}")
    _safe_print(f"可升级: {'[OK] 是' if status['ready_to_apply'] else '[FAIL] 否'}")


def cmd_clear(args):
    """清理暂存区"""
    skill_name = args.skill_name
    staging = get_staging_index(skill_name)
    clear_staging(skill_name)
    _safe_print(f"[OK] 已清理 {skill_name} 暂存区 ({len(staging)} 条素材)")


def main():
    parser = argparse.ArgumentParser(
        description=f"女娲技能升级工具 v{__version__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m upgrade_skill auto chen-pingan-perspective --files ./new.txt
  python -m upgrade_skill ingest chen-pingan-perspective --files a.md b.txt
  python -m upgrade_skill diff chen-pingan-perspective
  python -m upgrade_skill prompts chen-pingan-perspective
  python -m upgrade_skill status chen-pingan-perspective
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="摄入新素材")
    p_ingest.add_argument("skill_name", help="技能名称 (如 chen-pingan-perspective)")
    p_ingest.add_argument("--files", nargs="+", help="素材文件路径")
    p_ingest.add_argument("--urls", nargs="+", help="素材URL")
    p_ingest.add_argument("--text", help="直接粘贴文本")

    # diff
    p_diff = subparsers.add_parser("diff", help="生成差异报告")
    p_diff.add_argument("skill_name", help="技能名称")

    # prompts
    p_prompts = subparsers.add_parser("prompts", help="生成AI提示词")
    p_prompts.add_argument("skill_name", help="技能名称")

    # apply
    p_apply = subparsers.add_parser("apply", help="应用升级")
    p_apply.add_argument("skill_name", help="技能名称")
    p_apply.add_argument("--auto", action="store_true", help="自动模式")

    # auto
    p_auto = subparsers.add_parser("auto", help="一键全套")
    p_auto.add_argument("skill_name", help="技能名称")
    p_auto.add_argument("--files", nargs="+", help="素材文件路径")
    p_auto.add_argument("--urls", nargs="+", help="素材URL")
    p_auto.add_argument("--text", help="直接粘贴文本")

    # status
    p_status = subparsers.add_parser("status", help="查看升级状态")
    p_status.add_argument("skill_name", help="技能名称")

    # clear
    p_clear = subparsers.add_parser("clear", help="清理暂存区")
    p_clear.add_argument("skill_name", help="技能名称")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "ingest": cmd_ingest,
        "diff": cmd_diff,
        "prompts": cmd_prompts,
        "apply": cmd_apply,
        "auto": cmd_auto,
        "status": cmd_status,
        "clear": cmd_clear,
    }

    cmd_fn = commands.get(args.command)
    if cmd_fn:
        cmd_fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()