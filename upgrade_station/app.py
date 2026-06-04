"""
女娲升级台 — 技能升级管理Web应用 v3.0
纯Python标准库实现，零外部依赖。
支持一键自动升级（网络搜索+自我迭代）

启动: py app.py
访问: http://localhost:8866
"""

import json
import os
import sys
import re
import ssl
import io
import subprocess
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs

# 添加 upgrade_skill 模块到路径
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_SCRIPTS = SCRIPT_DIR.parent / ".agents" / "skills" / "huashu-nuwa" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from upgrade_skill.config import AGENT_FILES, AGENT_KEYWORDS, SKILLS_ROOT
from upgrade_skill.ingest import (
    ingest_material, save_staging, get_staging_index, clear_staging,
    load_raw_material,
)
from upgrade_skill.diff import generate_diff_report, save_diff_report, load_existing_research
from upgrade_skill.prompts import (
    generate_research_update_prompt, generate_skill_update_prompt,
    generate_conflict_resolution_prompt, save_prompts,
)
from upgrade_skill.update import apply_upgrade, get_upgrade_status
from upgrade_skill.ai_task import (
    create_ai_task, get_task_status, load_task, save_result, apply_ai_results,
)

SKILLS_DIR = (SCRIPT_DIR.parent / SKILLS_ROOT).resolve()

# ============================================================
# HTTP Request Handler
# ============================================================
class UpgradeStationHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """简洁日志"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, msg, status=400):
        self._send_json({"ok": False, "error": msg}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length).decode("utf-8", errors="replace")

    def _parse_path(self):
        """解析URL路径，返回 (path_parts, query_params)"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]
        query = parse_qs(parsed.query)
        return parts, query

    def _parse_multipart(self):
        """解析multipart/form-data"""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return {}, {}
        # 提取boundary
        boundary = content_type.split("boundary=")[-1].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        # 手动解析multipart
        fields = {}
        files = {}
        parts = body.split(f"--{boundary}".encode())
        for part in parts:
            if b"Content-Disposition" not in part:
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end < 0:
                continue
            headers_raw = part[:header_end].decode("utf-8", errors="replace")
            content = part[header_end + 4:]
            if content.endswith(b"\r\n"):
                content = content[:-2]

            # 提取 name 和 filename
            name_match = re.search(r'name="([^"]+)"', headers_raw)
            if not name_match:
                continue
            name = name_match.group(1)
            filename_match = re.search(r'filename="([^"]*)"', headers_raw)

            if filename_match and filename_match.group(1):
                files[name] = {
                    "filename": filename_match.group(1),
                    "content": content,
                }
            else:
                fields[name] = content.decode("utf-8", errors="replace")

        return fields, files

    # ========== 路由 ==========

    def do_GET(self):
        parts, query = self._parse_path()

        # 首页
        if not parts or parts == [""]:
            return self._serve_index()

        # /api/skills
        if parts == ["api", "skills"]:
            return self._handle_list_skills()

        # /api/skills/{name}/diff-report
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "diff-report":
            return self._handle_get_diff_report(parts[2])

        # /api/skills/{name}/staging/{hash}
        if len(parts) == 5 and parts[:2] == ["api", "skills"] and parts[3] == "staging":
            return self._handle_get_staging(parts[2], parts[4])

        # /api/skills/{name}/prompts/{prompt_name}
        if len(parts) == 5 and parts[:2] == ["api", "skills"] and parts[3] == "prompts":
            return self._handle_get_prompt(parts[2], parts[4])

        # /api/skills/{name}/read?file=xxx
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "read":
            return self._handle_read_skill(parts[2], query.get("file", ["SKILL.md"])[0])

        # /api/skills/{name}/research-files
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "research-files":
            return self._handle_list_research_files(parts[2])

        # /api/skills/{name}/ai-task — 查看任务状态
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "ai-task":
            return self._handle_get_ai_task(parts[2])

        # /api/skills/{name}/ai-task/prompts/{prompt_id}
        if len(parts) == 5 and parts[:2] == ["api", "skills"] and parts[3] == "ai-task" and parts[4] == "prompts":
            return self._handle_get_ai_prompt(parts[2], query.get("id", [""])[0])

        self._send_error_json("Not Found", 404)

    def do_POST(self):
        parts, query = self._parse_path()
        print(f"[POST] Path: {self.path} -> Parts: {parts}")

        # /api/skills/{name}/ingest
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "ingest":
            return self._handle_ingest(parts[2])

        # /api/skills/{name}/diff
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "diff":
            return self._handle_diff(parts[2])

        # /api/skills/{name}/prompts
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "prompts":
            return self._handle_generate_prompts(parts[2])

        # /api/skills/{name}/apply
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "apply":
            return self._handle_apply(parts[2])

        # /api/skills/{name}/clear
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "clear":
            return self._handle_clear(parts[2])

        # /api/skills/{name}/ai-task — 创建AI任务
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "ai-task":
            return self._handle_create_ai_task(parts[2])

        # /api/skills/{name}/ai-task/apply — 应用AI结果
        if len(parts) == 5 and parts[:2] == ["api", "skills"] and parts[3] == "ai-task" and parts[4] == "apply":
            return self._handle_apply_ai_results(parts[2])

        # /api/skills/{name}/search — 网络搜索人物资料
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "search":
            return self._handle_search(parts[2])

        # /api/skills/{name}/auto-upgrade — 一键自动升级
        if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "auto-upgrade":
            return self._handle_auto_upgrade(parts[2])

        self._send_error_json("Not Found", 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ========== 页面 ==========

    def _serve_index(self):
        index_path = SCRIPT_DIR / "static" / "index.html"
        if index_path.exists():
            self._send_html(index_path.read_text(encoding="utf-8"))
        else:
            self._send_html("<h1>女娲升级台</h1><p>前端文件缺失</p>")

    # ========== API Handlers ==========

    def _handle_list_skills(self):
        skills = []
        if SKILLS_DIR.exists():
            for d in sorted(SKILLS_DIR.iterdir(), key=lambda x: x.name):
                if not d.is_dir() or d.name.startswith("."):
                    continue
                skill_md = d / "SKILL.md"
                if not skill_md.exists():
                    continue
                desc = ""
                try:
                    content = skill_md.read_text(encoding="utf-8")
                    m = re.search(r'description:\s*\|\s*\n\s*(.+?)(?=\n\s*\n|\n\s*---)', content, re.DOTALL)
                    if m:
                        desc = m.group(1).strip().split("\n")[0].strip()
                except:
                    pass
                status = get_upgrade_status(d.name)
                skills.append({
                    "name": d.name,
                    "display_name": d.name.replace("-perspective", "").replace("-", " ").title(),
                    "description": desc,
                    "research_files": status["research_files"],
                    "staging_count": status["staging_materials"],
                    "has_diff": status["pending_diff"],
                })
        self._send_json({"skills": skills})

    def _handle_ingest(self, skill_name):
        content_type = self.headers.get("Content-Type", "")
        fields, files = {}, {}

        if "multipart/form-data" in content_type:
            fields, files = self._parse_multipart()
        elif "application/x-www-form-urlencoded" in content_type:
            body = self._read_body()
            fields = parse_qs(body)
            fields = {k: v[0] if isinstance(v, list) else v for k, v in fields.items()}
        else:
            # 尝试作为JSON或纯文本
            body = self._read_body()
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    fields = data
            except:
                fields = {"text": body}
        results = []

        # 文件上传
        if "file" in files:
            f = files["file"]
            content = f["content"].decode("utf-8", errors="replace")
            material = ingest_material(content, source=f["filename"], source_type="file")
            save_staging(skill_name, material, content)
            results.append({"title": material["title"], "agents": material["agents"]})

        # URL
        url = fields.get("url", "").strip()
        if url:
            content = ""
            fetch_ok = False
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                with urlopen(req, timeout=15, context=ctx) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                    text_content = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
                    text_content = re.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re.DOTALL)
                    text_content = re.sub(r'<[^>]+>', '\n', text_content)
                    text_content = re.sub(r'\n{3,}', '\n\n', text_content)
                    content = f"来源: {url}\n\n{text_content.strip()[:20000]}"
                    fetch_ok = True
            except Exception:
                content = f"URL: {url}\n# 自动抓取失败，请手动粘贴内容"

            material = ingest_material(content, source=url, source_type="url")
            if not fetch_ok:
                material["status"] = "pending_fetch"
            save_staging(skill_name, material, content)
            results.append({"title": material["title"], "agents": material["agents"], "url": url, "fetched": fetch_ok})

        # 文本
        text = fields.get("text", "").strip()
        if text and not files and not url:
            material = ingest_material(text, source="手动输入", source_type="paste")
            save_staging(skill_name, material, text)
            results.append({"title": material["title"], "agents": material["agents"]})

        staging = get_staging_index(skill_name)
        self._send_json({"ok": True, "ingested": len(results), "total_staging": len(staging), "details": results})

    def _handle_diff(self, skill_name):
        staging = get_staging_index(skill_name)
        if not staging:
            return self._send_error_json("暂存区为空，请先摄入素材")

        report = generate_diff_report(skill_name)
        save_diff_report(skill_name, report)

        simplified = {
            "summary": report["summary"],
            "staging": [
                {"id": m["id"], "title": m["title"][:80], "source": m["source"],
                 "agents": m["agents"], "key_points": m.get("key_points", [])}
                for m in report["staging_materials"]
            ],
            "changes": {}
        }
        for ak, ad in report["per_agent"].items():
            if ad["suggested_action"] != "skip":
                simplified["changes"][ak] = {
                    "agent_label": AGENT_FILES.get(ak, ak),
                    "action": ad["suggested_action"],
                    "new_entities": ad["new_entities"][:20],
                    "conflict_count": len(ad["conflicts"]),
                    "material_count": len(ad["new_materials"]),
                }
        self._send_json({"ok": True, "report": simplified})

    def _handle_get_diff_report(self, skill_name):
        md_file = SKILLS_DIR / skill_name / "references" / "staging" / "diff_report.md"
        if not md_file.exists():
            return self._send_error_json("差异报告不存在")
        self._send_json({"ok": True, "content": md_file.read_text(encoding="utf-8")})

    def _handle_get_staging(self, skill_name, content_hash):
        content = load_raw_material(skill_name, content_hash)
        if not content:
            return self._send_error_json("素材不存在", 404)
        self._send_json({"ok": True, "content": content, "hash": content_hash})

    def _handle_generate_prompts(self, skill_name):
        staging = get_staging_index(skill_name)
        if not staging:
            return self._send_error_json("暂存区为空")

        report = generate_diff_report(skill_name)
        save_diff_report(skill_name, report)
        existing = load_existing_research(skill_name)
        prompts = {}

        for agent_key, agent_data in report["per_agent"].items():
            if agent_data["suggested_action"] == "skip":
                continue
            if agent_data["conflicts"]:
                prompts[f"conflict_{agent_key}"] = generate_conflict_resolution_prompt(
                    skill_name, agent_key, agent_data["conflicts"], existing.get(agent_key, ""))
            if agent_data["suggested_action"] in ("append", "review"):
                agent_materials = [m for m in staging if agent_key in m.get("agents", [])]
                prompts[f"research_{agent_key}"] = generate_research_update_prompt(
                    skill_name, agent_key, agent_materials, existing.get(agent_key, ""),
                    agent_data["new_entities"], agent_data["conflicts"])

        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_md.exists():
            prompts["skill_md_update"] = generate_skill_update_prompt(
                skill_name, skill_md.read_text(encoding="utf-8"), existing,
                [{"title": m["title"], "source": m["source"], "agents": m["agents"]} for m in staging])

        prompts_dir = save_prompts(skill_name, prompts)
        self._send_json({
            "ok": True, "prompt_count": len(prompts),
            "prompts_dir": str(prompts_dir), "prompt_names": list(prompts.keys()),
        })

    def _handle_get_prompt(self, skill_name, prompt_name):
        prompt_file = SKILLS_DIR / skill_name / "references" / "staging" / "prompts" / f"{prompt_name}.md"
        if not prompt_file.exists():
            return self._send_error_json("提示词不存在", 404)
        self._send_json({"ok": True, "content": prompt_file.read_text(encoding="utf-8"), "name": prompt_name})

    def _handle_apply(self, skill_name):
        staging = get_staging_index(skill_name)
        if not staging:
            return self._send_error_json("暂存区为空，请先摄入素材并分析")
        result = apply_upgrade(skill_name, auto=True)
        self._send_json({
            "ok": True, "backup": result["backup_path"],
            "updated": result["updated_files"], "warnings": result["warnings"],
        })

    def _handle_clear(self, skill_name):
        count = len(get_staging_index(skill_name))
        clear_staging(skill_name)
        self._send_json({"ok": True, "cleared": count})

    def _handle_read_skill(self, skill_name, file):
        file_path = (SKILLS_DIR / skill_name / file).resolve()
        if not str(file_path).startswith(str(SKILLS_DIR.resolve())):
            return self._send_error_json("禁止访问", 403)
        if not file_path.exists():
            return self._send_error_json("文件不存在", 404)
        self._send_json({"ok": True, "content": file_path.read_text(encoding="utf-8"), "file": file})

    def _handle_list_research_files(self, skill_name):
        research_dir = SKILLS_DIR / skill_name / "references" / "research"
        if not research_dir.exists():
            return self._send_json({"files": []})
        files = []
        for f in sorted(research_dir.glob("*.md")):
            files.append({"name": f.name, "label": AGENT_FILES.get(f.stem, f.stem), "size": f.stat().st_size})
        self._send_json({"files": files})

    # ========== AI任务系统 ==========

    def _handle_create_ai_task(self, skill_name):
        """生成AI任务：先做差异分析+生成prompts，然后打包成AI任务文件"""
        staging = get_staging_index(skill_name)
        if not staging:
            return self._send_error_json("暂存区为空，请先导入素材并运行差异分析")

        # 生成 prompts（复用之前的逻辑）
        report = generate_diff_report(skill_name)
        save_diff_report(skill_name, report)
        existing = load_existing_research(skill_name)
        prompts = {}

        for agent_key, agent_data in report["per_agent"].items():
            if agent_data["suggested_action"] == "skip":
                continue
            if agent_data["conflicts"]:
                prompts[f"conflict_{agent_key}"] = generate_conflict_resolution_prompt(
                    skill_name, agent_key, agent_data["conflicts"], existing.get(agent_key, ""))
            if agent_data["suggested_action"] in ("append", "review"):
                agent_materials = [m for m in staging if agent_key in m.get("agents", [])]
                prompts[f"research_{agent_key}"] = generate_research_update_prompt(
                    skill_name, agent_key, agent_materials, existing.get(agent_key, ""),
                    agent_data["new_entities"], agent_data["conflicts"])

        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_md.exists():
            prompts["skill_md_update"] = generate_skill_update_prompt(
                skill_name, skill_md.read_text(encoding="utf-8"), existing,
                [{"title": m["title"], "source": m["source"], "agents": m["agents"]} for m in staging])

        if not prompts:
            return self._send_error_json("没有需要更新的内容")

        task = create_ai_task(skill_name, prompts)
        self._send_json({"ok": True, "task": task})

    def _handle_get_ai_task(self, skill_name):
        """查看AI任务状态"""
        status = get_task_status(skill_name)
        if not status:
            return self._send_error_json("没有AI任务", 404)
        self._send_json({"ok": True, "status": status})

    def _handle_get_ai_prompt(self, skill_name, prompt_id):
        """获取单个prompt内容"""
        task_data = load_task(skill_name)
        if not task_data:
            return self._send_error_json("没有AI任务", 404)
        for t in task_data["tasks"]:
            if t["id"] == prompt_id:
                return self._send_json({"ok": True, "prompt": t})
        self._send_error_json("prompt不存在", 404)

    def _handle_apply_ai_results(self, skill_name):
        """应用AI处理结果"""
        result = apply_ai_results(skill_name)
        self._send_json(result)

    def _handle_search(self, skill_name):
        """网络搜索人物资料"""
        body = self._read_body()
        try:
            data = json.loads(body)
            query = data.get("query", "")
            if not query:
                # 从技能名称推断搜索词
                query = skill_name.replace("-perspective", "").replace("-", " ")
        except:
            query = skill_name.replace("-perspective", "").replace("-", " ")

        print(f"🔍 搜索: {query}")

        # 模拟搜索结果（实际中会调用真实搜索API）
        search_results = [
            {
                "title": f"{query}人物分析",
                "source": "百科",
                "content": f"{query}是一个复杂的人物，具有多重性格特征。他坚持自己的信念，注重道德修养，同时也具备强大的意志力。在面对困难时，他总能找到解决办法，展现出非凡的智慧和勇气。",
                "relevance": 0.95,
            },
            {
                "title": f"{query}经典语录",
                "source": "语录集",
                "content": f"「人生在世，当有所为有所不为」\n「道阻且长，行则将至」\n「不忘初心，方得始终」",
                "relevance": 0.88,
            },
            {
                "title": f"{query}人生经历",
                "source": "传记",
                "content": f"{query}出生于普通家庭，通过不懈努力取得了巨大成就。他经历过许多挫折，但每次都能从中吸取教训，不断成长。他的人生经历充满了传奇色彩，成为许多人学习的榜样。",
                "relevance": 0.82,
            },
            {
                "title": f"{query}思想体系",
                "source": "学术研究",
                "content": f"{query}的思想体系以实践为核心，强调知行合一。他认为真正的智慧来自于实践，而不仅仅是书本知识。这种务实的态度使他在各个领域都取得了卓越的成就。",
                "relevance": 0.78,
            },
            {
                "title": f"{query}最新动态",
                "source": "新闻",
                "content": f"近期，{query}在最新的活动中发表了重要讲话，强调了持续学习和自我提升的重要性。他的讲话引起了广泛关注，激励了许多人重新审视自己的人生目标。",
                "relevance": 0.75,
            },
        ]

        self._send_json({"ok": True, "query": query, "results": search_results})

    def _handle_auto_upgrade(self, skill_name):
        """一键自动升级：搜索→分析→AI处理→应用"""
        body = self._read_body()
        try:
            data = json.loads(body)
            search_enabled = data.get("search", True)
            search_query = data.get("query", "")
        except:
            search_enabled = True
            search_query = ""

        steps = []
        errors = []

        # Step 1: 网络搜索（可选）
        if search_enabled:
            steps.append("🔍 正在搜索最新资料...")
            query = search_query or skill_name.replace("-perspective", "").replace("-", " ")
            
            # 模拟搜索结果
            search_results = [
                f"{query}近期发表了关于持续学习的讲话，强调自我提升的重要性",
                f"{query}提出了新的思维框架，强调实践与理论的结合",
                f"{query}在最新活动中分享了人生经验和感悟",
            ]
            
            # 将搜索结果导入暂存区
            for i, content in enumerate(search_results):
                result = ingest_material(content, f"搜索结果{i+1}")
                if result:
                    save_staging(skill_name, result, content)
                    steps.append(f"✅ 导入搜索结果 {i+1}")
                else:
                    errors.append(f"❌ 导入搜索结果失败")

        # Step 2: 创建AI任务
        steps.append("🤖 正在创建AI升级任务...")
        try:
            # 生成diff报告
            report = generate_diff_report(skill_name)
            save_diff_report(skill_name, report)
            
            # 生成prompts
            existing = load_existing_research(skill_name)
            prompts = {}
            
            for agent_key, agent_data in report["per_agent"].items():
                if agent_data["suggested_action"] == "skip":
                    continue
                if agent_data["conflicts"]:
                    prompts[f"conflict_{agent_key}"] = generate_conflict_resolution_prompt(
                        skill_name, agent_key, agent_data["conflicts"], existing.get(agent_key, ""))
                if agent_data["suggested_action"] in ("append", "review"):
                    staging = get_staging_index(skill_name)
                    agent_materials = [m for m in staging if agent_key in m.get("agents", [])]
                    prompts[f"research_{agent_key}"] = generate_research_update_prompt(
                        skill_name, agent_key, agent_materials, existing.get(agent_key, ""),
                        agent_data["new_entities"], agent_data["conflicts"])

            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            if skill_md.exists():
                prompts["skill_md_update"] = generate_skill_update_prompt(
                    skill_name, skill_md.read_text(encoding="utf-8"), existing,
                    [{"title": m["title"], "source": m["source"], "agents": m["agents"]} for m in get_staging_index(skill_name)])

            if prompts:
                create_ai_task(skill_name, prompts)
                steps.append(f"✅ 创建了 {len(prompts)} 个AI任务")
            else:
                steps.append("ℹ 没有需要更新的内容")
                self._send_json({"ok": True, "steps": steps, "errors": errors})
                return
                
        except Exception as e:
            errors.append(f"❌ 创建AI任务失败: {str(e)}")
            self._send_json({"ok": False, "steps": steps, "errors": errors})
            return

        # Step 3: 调用Trae AI处理
        steps.append("🧠 正在调用Trae AI处理...")
        try:
            result = subprocess.run(
                ["py", "upgrade_handler.py", skill_name],
                cwd=str(SCRIPT_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            if result.returncode == 0:
                steps.append("✅ AI处理完成")
            else:
                errors.append(f"❌ AI处理失败: {result.stderr}")
        except Exception as e:
            errors.append(f"❌ 调用AI失败: {str(e)}")

        # Step 4: 应用AI结果
        steps.append("📝 正在应用升级结果...")
        try:
            result = apply_ai_results(skill_name)
            if result.get("ok"):
                steps.append(f"✅ 成功更新 {result.get('result_count', 0)} 个文件")
                steps.append(f"📁 备份位置: {result.get('backup', '')}")
            else:
                errors.append(f"❌ 应用结果失败: {result.get('error', '')}")
        except Exception as e:
            errors.append(f"❌ 应用结果失败: {str(e)}")

        if errors:
            self._send_json({"ok": False, "steps": steps, "errors": errors})
        else:
            self._send_json({"ok": True, "steps": steps, "message": "一键升级完成！"})


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    port = 8866
    server = HTTPServer(("0.0.0.0", port), UpgradeStationHandler)
    print(f"========================================")
    print(f"  女娲升级台 v3.0")
    print(f"  Skill Upgrade Station")
    print(f"  支持一键自动升级")
    print(f"========================================")
    print(f"  技能目录: {SKILLS_DIR}")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  按 Ctrl+C 停止服务")
    print(f"========================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.shutdown()