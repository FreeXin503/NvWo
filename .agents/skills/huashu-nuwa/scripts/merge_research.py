#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
女娲 Skill 调研质量统计脚本 — Phase 1.5 强制检查点
支持12个Agent，区分 已验证 / 访问失败 URL。

用法:
    python3 merge_research.py <skill目录路径>

示例:
    python3 merge_research.py .agents/skills/charlie-munger-perspective

输出:
    打印 markdown 格式摘要表格到 stdout
    如果总已验证 URL < 200，脚本以非零退出码退出（用于 CI 检查）

验证格式（md文件中）:
    已验证  → 计入已验证
    访问失败 → 计入失败
    普通 https://... URL    → 计入未标记（不计入200目标）
"""

import sys
import io
import re
from pathlib import Path
from urllib.parse import urldefrag

# 强制 stdout 为 utf-8，解决 Windows gbk 环境下的编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')



# 12个Agent的完整映射
AGENTS = {
    '01-writings':       '1 著作',
    '02-conversations':  '2 对话',
    '03-expression-dna': '3 表达',
    '04-external-views': '4 他者',
    '05-decisions':      '5 决策',
    '06-timeline':       '6 时间线',
    '07-thought-system': '7 思想体系',
    '08-improvisation':  '8 即兴反应',
    '09-latest-updates': '9 最新动态',
    '10-work-methods':   '10 工作方法',
    '11-controversies':  '11 争议事件',
    '12-cross-domain':   '12 跨域影响',
}

# Phase 1.5 门槛
MIN_VERIFIED_TOTAL = 200
MIN_VERIFIED_PER_AGENT = 20
MIN_PRIMARY_RATIO = 0.40
MIN_FOREIGN_RATIO_FOR_FOREIGNER = 0.80
MIN_FOREIGN_RATIO_FOR_DOMESTIC = 0.25


def is_chinese_source(url: str) -> bool:
    """
    判断一个 URL 是否为中文/国内特色数据源。
    """
    url_lower = url.lower()
    # 1. 匹配国内典型域名后缀
    if re.search(r'\.(?:cn|com\.cn|net\.cn|org\.cn|gov\.cn)(?:/|$|\?|#)', url_lower):
        return True
    # 2. 匹配国内特定平台域名
    cn_domains = [
        "zhihu.com", "bilibili.com", "douban.com", "weibo.com", "weibo.cn", 
        "xiaoyuzhoufm.com", "baidu.com", "baidu.cn", "qq.com", "163.com", 
        "sohu.com", "sina.com", "sina.com.cn", "36kr.com", "huxiu.com", 
        "sspai.com", "geekpark.net", "latepost.com", "jianshu.com", 
        "csdn.net", "oschina.net", "cnblogs.com", "gitee.com", "toutiao.com",
        "wechat.com", "weixin.qq.com"
    ]
    for domain in cn_domains:
        if re.search(r'(?:^|/|\.)' + re.escape(domain) + r'(?:/|$|\?|#)', url_lower):
            return True
    return False


def normalize_url(url: str) -> str:
    """去除 URL 片段（#anchor）用于去重"""
    url = url.rstrip(')')  # 去除 markdown 残流括号
    url, _ = urldefrag(url)
    return url.rstrip('/')


def count_sources(content: str) -> dict:
    """
    统计来源数量，区分已验证/失败/未标记。
    
    识别格式：
      ✅已验证 或 ✅ 已验证 附近的 URL
      ❌访问失败 或 ❌ 访问失败 附近的 URL
      其余 URL 为"未标记"
    """
    # 逐行分析
    verified_urls = set()
    failed_urls = set()
    unlabeled_urls = set()
    primary_count = 0
    secondary_count = 0

    lines = content.split('\n')
    for line in lines:
        urls_in_line = re.findall(r'https?://[^\s\)\]"]+', line)
        urls_in_line = [normalize_url(u) for u in urls_in_line if len(u) > 10]

        is_verified = bool(re.search(r'✅\s*已验证', line))
        is_failed = bool(re.search(r'❌\s*(?:访问失败|失败)', line))

        for url in urls_in_line:
            if is_failed:
                failed_urls.add(url)
            elif is_verified:
                verified_urls.add(url)
            else:
                unlabeled_urls.add(url)

        # 一手/二手标记统计
        if re.search(r'来源类型[：:]\s*一手|一手[来源]|primary', line, re.IGNORECASE):
            primary_count += 1
        if re.search(r'来源类型[：:]\s*二手|二手[来源]|secondary', line, re.IGNORECASE):
            secondary_count += 1

    # 从 unlabeled 中移除已被分类的
    unlabeled_urls -= verified_urls
    unlabeled_urls -= failed_urls

    return {
        'verified': verified_urls,
        'failed': failed_urls,
        'unlabeled': unlabeled_urls,
        'verified_count': len(verified_urls),
        'failed_count': len(failed_urls),
        'unlabeled_count': len(unlabeled_urls),
        'primary_count': primary_count,
        'secondary_count': secondary_count,
    }


def extract_key_findings(content: str, max_items: int = 2) -> str:
    """提取关键发现（取前几个二级标题）"""
    headings = re.findall(r'^#{2,3}\s+(.+)$', content, re.MULTILINE)
    if headings:
        items = headings[:max_items]
    else:
        bolds = re.findall(r'\*\*(.+?)\*\*', content)
        items = bolds[:max_items]

    result = '、'.join(items) if items else '—'
    return result[:28] + '…' if len(result) > 28 else result


def find_contradictions(files: dict) -> list:
    """检测跨文件矛盾标记"""
    contradictions = []
    for name, content in files.items():
        matches = re.findall(r'(?:矛盾|相反|但实际上|然而.*?不同|争议|内在张力).{0,80}', content)
        label = AGENTS.get(name, name)
        for m in matches[:2]:
            contradictions.append(f"{label}: {m[:60]}")
    return contradictions[:5]


def check_file_exists_and_nonempty(path: Path) -> str:
    """检查文件是否存在且有内容"""
    if not path.exists():
        return 'missing'
    if path.stat().st_size < 100:
        return 'empty'
    return 'ok'


def main():
    if len(sys.argv) < 2:
        print("用法: python3 merge_research.py <skill目录路径>")
        sys.exit(1)

    skill_dir = Path(sys.argv[1])
    research_dir = skill_dir / 'references' / 'research'

    if not research_dir.exists():
        print(f"❌ 目录不存在: {research_dir}")
        sys.exit(1)

    # 读取人物属性
    metadata_path = research_dir / 'metadata.json'
    is_foreign = False
    person_name = skill_dir.name.replace('-perspective', '')

    if metadata_path.exists():
        import json
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                is_foreign = metadata.get('is_foreign', False)
                person_name = metadata.get('chinese_name', metadata.get('name', person_name))
        except Exception as e:
            print(f"⚠️  警告：读取 metadata.json 失败：{e}，默认按国内人物处理")
    else:
        print(f"⚠️  警告：未在 {metadata_path} 找到 metadata.json 配置文件！")

    files_content = {}
    rows = []
    all_verified = set()
    all_failed = set()
    total_primary = 0
    total_secondary = 0
    missing_agents = []
    per_agent_pass = {}

    for key, label in AGENTS.items():
        md_file = research_dir / f"{key}.md"
        file_status = check_file_exists_and_nonempty(md_file)

        if file_status != 'ok':
            reason = '缺失' if file_status == 'missing' else '空文件'
            missing_agents.append(label)
            per_agent_pass[label] = False
            rows.append({
                'label': label,
                'verified': 0,
                'failed': 0,
                'findings': f'❌ {reason}',
                'pass': False,
            })
            continue

        content = md_file.read_text(encoding='utf-8', errors='replace')
        files_content[key] = content
        stats = count_sources(content)
        findings = extract_key_findings(content)

        all_verified.update(stats['verified'])
        all_failed.update(stats['failed'])
        total_primary += stats['primary_count']
        total_secondary += stats['secondary_count']

        agent_pass = stats['verified_count'] >= MIN_VERIFIED_PER_AGENT
        per_agent_pass[label] = agent_pass
        pass_mark = '✅' if agent_pass else '⚠️'

        rows.append({
            'label': label,
            'verified': stats['verified_count'],
            'failed': stats['failed_count'],
            'findings': findings,
            'pass': agent_pass,
            'pass_mark': pass_mark,
        })

    # 全局统计
    contradictions = find_contradictions(files_content)
    total_verified = len(all_verified)
    total_failed = len(all_failed)

    total_labeled = total_primary + total_secondary
    primary_ratio = total_primary / total_labeled if total_labeled > 0 else 0
    primary_ratio_str = f"{primary_ratio:.0%}" if total_labeled > 0 else "未标记"

    # 计算外网源比例
    foreign_verified = {url for url in all_verified if not is_chinese_source(url)}
    foreign_ratio = len(foreign_verified) / total_verified if total_verified > 0 else 0
    foreign_ratio_str = f"{foreign_ratio:.0%}" if total_verified > 0 else "未标记"
    
    target_foreign_ratio = MIN_FOREIGN_RATIO_FOR_FOREIGNER if is_foreign else MIN_FOREIGN_RATIO_FOR_DOMESTIC
    foreign_pass = foreign_ratio >= target_foreign_ratio
    # 如果是国外人物，不达标则是硬性 ❌，国内人物则是建议 ⚠️
    foreign_mark = '✅' if foreign_pass else '❌' if is_foreign else '⚠️'

    # ── 输出表格 ──
    sep_top = "┌────────────────┬────────────┬──────────┬────────────────────────────────┐"
    sep_header = "│ Agent          │ ✅已验证URL │ ❌失败URL │ 关键发现                         │"
    sep_mid = "├────────────────┼────────────┼──────────┼────────────────────────────────┤"
    sep_bot = "└────────────────┴────────────┴──────────┴────────────────────────────────┘"

    print(sep_top)
    print(sep_header)
    print(sep_mid)

    for r in rows:
        label = r['label']
        v = str(r['verified'])
        f = str(r['failed'])
        findings = r['findings']
        pm = r.get('pass_mark', '⚠️')
        print(f"│ {label:<14} │ {pm} {v:<8} │ {f:<8} │ {findings:<30} │")

    print(sep_mid)

    # 汇总行
    total_pass = total_verified >= MIN_VERIFIED_TOTAL
    total_mark = '✅' if total_pass else '❌'
    ratio_pass = primary_ratio >= MIN_PRIMARY_RATIO
    ratio_mark = '✅' if ratio_pass else '⚠️'

    print(f"│ {'总计（去重后）':<14} │ {total_mark} {total_verified:<8} │ {total_failed:<8} │ {'— ':<30} │")
    print(f"│ {'一手来源占比':<14} │ {ratio_mark} {primary_ratio_str:<9} │ {'—':<8} │ {'（目标≥40%）':<30} │")
    print(f"│ {'外网来源占比':<14} │ {foreign_mark} {foreign_ratio_str:<9} │ {'—':<8} │ {'（目标≥80%）' if is_foreign else '（目标≥25%）':<30} │")

    if contradictions:
        print(f"│ {'矛盾点':<14} │ {'  ' + str(len(contradictions)) + '处':<10} │ {'—':<8} │ {contradictions[0][:30]:<30} │")
    else:
        print(f"│ {'矛盾点':<14} │ {'  0处':<10} │ {'—':<8} │ {'—':<30} │")

    if missing_agents:
        missing_str = ', '.join(missing_agents[:3])
        print(f"│ {'信息不足维度':<14} │ {'  ' + str(len(missing_agents)) + '个':<10} │ {'—':<8} │ {missing_str[:30]:<30} │")
    else:
        print(f"│ {'信息不足维度':<14} │ {'  无':<10} │ {'—':<8} │ {'—':<30} │")

    print(sep_bot)

    # ── Phase 1.5 门槛判断 ──
    print()
    print("=" * 64)
    print("⚠️  以上数字来自 merge_research.py 脚本输出，非模型自报")
    print("=" * 64)
    print()

    passed = True

    check1 = total_verified >= MIN_VERIFIED_TOTAL
    print(f"{'✅' if check1 else '❌'} 总已验证URL（去重）≥ {MIN_VERIFIED_TOTAL}：{total_verified} 条 → {'PASS' if check1 else 'FAIL — 必须返回Phase 1继续采集'}")
    if not check1:
        passed = False

    check2 = all(r['pass'] for r in rows)
    failing_agents = [r['label'] for r in rows if not r['pass']]
    if check2:
        print(f"✅ 每个Agent已验证URL ≥ {MIN_VERIFIED_PER_AGENT}：全部通过 → PASS")
    else:
        print(f"⚠️  每个Agent已验证URL ≥ {MIN_VERIFIED_PER_AGENT}：以下Agent不足 → {', '.join(failing_agents)}")
        passed = False

    check3 = primary_ratio >= MIN_PRIMARY_RATIO
    print(f"{'✅' if check3 else '⚠️ '} 一手来源占比 ≥ {MIN_PRIMARY_RATIO:.0%}：当前 {primary_ratio_str} → {'PASS' if check3 else 'WARN — 建议补充一手来源'}")
    if not check3:
        passed = False

    check_foreign = foreign_ratio >= target_foreign_ratio
    foreign_desc = f"国外名人强制要求外网源比率 ≥ 80%" if is_foreign else f"中国名人外网源比率建议 ≥ 25%"
    print(f"{'✅' if check_foreign else '❌' if is_foreign else '⚠️ '} 外网来源占比 ({foreign_desc})：当前 {foreign_ratio_str} (外网源: {len(foreign_verified)}/{total_verified}) → {'PASS' if check_foreign else 'FAIL — 必须开启VPN到国外渠道检索' if is_foreign else 'WARN — 建议补充国外视角来源'}")
    
    # 只有对于国外人物，外网来源不达标才强制拦截退出
    if is_foreign and not check_foreign:
        passed = False

    check4 = len(missing_agents) == 0
    print(f"{'✅' if check4 else '❌'} 所有md文件存在且有内容：{'PASS' if check4 else 'FAIL — 缺失: ' + ', '.join(missing_agents)}")
    if not check4:
        passed = False

    print()
    if passed:
        print("🎉 Phase 1.5 门槛全部通过，可以进入 Phase 2 框架提炼。")
        sys.exit(0)
    else:
        print("🚫 Phase 1.5 门槛未通过，禁止进入 Phase 2，请返回 Phase 1 继续补充资料。")
        sys.exit(1)


if __name__ == '__main__':
    main()
