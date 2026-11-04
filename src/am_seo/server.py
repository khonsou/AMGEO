"""A loopback-only browser console over the project's existing local workflows."""
from __future__ import annotations

import hmac
import io
import json
import secrets
import subprocess
import threading
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .measurement import measure
from .workflow import WorkflowEngine
from .geo_workspace import GeoWorkspace
from .question_lab import QuestionLab

MAX_BODY = 32 * 1024
MARKETS = {"both", "zh-CN", "en-US"}
CHANNELS = {"search", "ai", "reviews", "community", "catalog", "owned"}
ARTIFACTS = {
    "strategy": ("SEO / GEO 品牌策略", "markdown", "outputs/angrymiao-seo-geo-strategy.md"),
    "agent-plan": ("Agent 执行计划", "markdown", "outputs/agent-nextsteps.md"),
    "facts": ("产品事实与冲突", "json", "outputs/agent-kit/product-facts.json"),
    "queries": ("中英问题种子", "json", "outputs/agent-kit/query-seeds.json"),
    "validation": ("资料验收结果", "json", "outputs/agent-kit/qa-results.json"),
    "report": ("项目运行报告", "json", "outputs/project-status.json"),
    "battery-zh": ("电池机制中文草稿", "markdown", "outputs/agent-kit/battery-mechanism.zh-CN.md"),
    "battery-en": ("Battery mechanism English draft", "markdown", "outputs/agent-kit/battery-mechanism.en.md"),
    "operations": ("可回滚的快照修改", "json", "outputs/agent-kit/am-infinity-97.operations.json"),
    "readme": ("项目使命与方法", "markdown", "README.md"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, root: Path, host: str, port: int):
        self.root = root.resolve()
        self.runtime = self.root / "outputs/runtime/console"
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.records = {}
        for name in ("requests", "jobs", "feedback"):
            value = _read(self.runtime / f"{name}.json", [])
            self.records[name] = value if isinstance(value, list) else []
        # Bind first: a failed second start must not alter a running console's records.
        super().__init__((host, port), ConsoleHandler)
        self.workflow = WorkflowEngine(self.root, evaluator=measure)
        self.geo_workspace = GeoWorkspace(self.root)
        self.question_lab = QuestionLab(self.root, self.geo_workspace)
        # A restarted server cannot resume an old subprocess or claim it succeeded.
        changed = False
        for job in self.records["jobs"]:
            if isinstance(job, dict) and job.get("status") in {"queued", "running"}:
                job.update(status="failed", finished_at=_now(), error="服务重启，旧任务未确认完成。请重新运行检查。")
                changed = True
        if changed:
            self.save("jobs")

    def save(self, name: str):
        self.runtime.mkdir(parents=True, exist_ok=True)
        target = self.runtime / f"{name}.json"
        temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(self.records[name], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)

    def state(self):
        tasks_doc = _read(self.root / "outputs/agent-kit/tasks.json", {})
        tasks = tasks_doc.get("tasks", []) if isinstance(tasks_doc, dict) else tasks_doc
        tasks = tasks if isinstance(tasks, list) else []
        upstreams = _read(self.root / "config/upstreams.lock.json", {})
        with self.lock:
            return {
                "project": _read(self.root / "config/project.json", {}),
                "tasks": tasks,
                "task_counts": dict(Counter(t.get("status", "unknown") for t in tasks if isinstance(t, dict))),
                "capabilities": _read(self.root / "outputs/agent-kit/capabilities.json", {}),
                "validation": _read(self.root / "outputs/agent-kit/qa-results.json"),
                "run_report": _read(self.root / "outputs/project-status.json"),
                "upstreams": upstreams.get("upstreams", []) if isinstance(upstreams, dict) else [],
                "requests": json.loads(json.dumps(self.records["requests"])),
                "jobs": json.loads(json.dumps(self.records["jobs"])),
                "feedback": json.loads(json.dumps(self.records["feedback"])),
                "artifacts": [{"id": key, "title": entry[0], "kind": entry[1]} for key, entry in ARTIFACTS.items() if (self.root / entry[2]).is_file()],
                "csrf_token": self.token,
                "workflow": self.workflow.state(),
                "geo_workspace": self.geo_workspace.state(),
                "question_lab": self.question_lab.state(),
            }

    def run_job(self, job: dict):
        commands = {
            "offline-validation": [str(self.root / "am-seo"), "run", "--offline"],
            "upstream-verification": [str(self.root / "am-seo"), "deps", "verify"],
        }
        with self.lock:
            job.update(status="running", started_at=_now())
            self.save("jobs")
        try:
            result = subprocess.run(commands[job["kind"]], cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=300, check=False)
            with self.lock:
                job.update(status="succeeded" if result.returncode == 0 else "failed", exit_code=result.returncode, output=result.stdout[-30000:])
                if result.returncode:
                    job["error"] = f"检查命令退出码：{result.returncode}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            with self.lock:
                job.update(status="failed", error="检查超时。" if isinstance(exc, subprocess.TimeoutExpired) else f"无法运行检查：{exc}", output="")
        finally:
            with self.lock:
                job["finished_at"] = _now()
                self.save("jobs")


class ConsoleHandler(BaseHTTPRequestHandler):
    server: ConsoleServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # Bodies and goal/feedback text are never included in access logs.
        return

    def _headers(self, status: int, content_type: str, length: int):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()

    def _json(self, status: int, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _error(self, status: int, message: str):
        self._json(status, {"error": message})

    def _valid_host(self) -> bool:
        raw = self.headers.get("Host", "")
        try:
            host = urlsplit("//" + raw)
            return host.hostname in {"localhost", "127.0.0.1"} and host.port == self.server.server_port and not host.username and not host.password and not host.path and not host.query and not host.fragment
        except ValueError:
            return False

    def _path(self):
        return unquote(urlsplit(self.path).path)

    def do_GET(self):
        if not self._valid_host():
            self._error(403, "只接受当前本机地址的请求。")
            return
        path = self._path()
        if path == "/api/health":
            self._json(200, {"status": "ok", "project": "AM SEO"})
        elif path == "/api/state":
            self._json(200, self.server.state())
        elif path == "/api/geo/download":
            stream = io.BytesIO()
            try:
                with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                    for task in self.server.geo_workspace.state()["tasks"]:
                        for artifact in task.get("artifacts", []):
                            archive.writestr(task["id"] + "/" + artifact["filename"], self.server.geo_workspace.artifact(task["id"], artifact["filename"]))
                raw = stream.getvalue()
                self._headers(200, "application/zip", len(raw))
                self.wfile.write(raw)
            except (ValueError, OSError):
                self._error(409, "产物变化，请重新准备后下载。")
        elif path.startswith("/api/geo/files/"):
            parts = path[len("/api/geo/files/"):].split("/")
            try:
                if len(parts) != 2: raise ValueError()
                raw = self.server.geo_workspace.artifact(*parts)
                suffix = Path(parts[1]).suffix
                mime = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json"}.get(suffix, "text/plain")
                self._headers(200, mime + "; charset=utf-8", len(raw)); self.wfile.write(raw)
            except (ValueError, OSError):
                self._error(404, "产物不存在或哈希已变化。")
        elif path.startswith("/api/workflow/artifacts/"):
            parts = path[len("/api/workflow/artifacts/"):].split("/")
            try:
                if len(parts) != 3 or not parts[2].isdigit():
                    raise ValueError("交付物标识无效。")
                artifact = self.server.workflow.get_artifact(parts[0], parts[1], int(parts[2]))
                self._json(200, artifact)
            except (ValueError, OSError):
                self._error(404, "任务交付物不存在或尚未生成。")
        elif path.startswith("/api/artifacts/"):
            artifact_id = path[len("/api/artifacts/"):]
            item = ARTIFACTS.get(artifact_id)
            if not item:
                self._error(404, "交付物不存在。")
                return
            try:
                content = (self.server.root / item[2]).read_text(encoding="utf-8")
            except OSError:
                self._error(404, "交付物尚未生成。")
                return
            self._json(200, {"id": artifact_id, "title": item[0], "kind": item[1], "content": content})
        else:
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/focus.js": ("focus.js", "text/javascript; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8")}
            asset = assets.get(path)
            if not asset:
                self._error(404, "页面不存在。")
                return
            try:
                body = (Path(__file__).parent / "web" / asset[0]).read_bytes()
            except OSError:
                self._error(503, "控制台页面尚未安装。")
                return
            self._headers(200, asset[1], len(body))
            self.wfile.write(body)

    def do_POST(self):
        if not self._valid_host():
            self.close_connection = True
            self._error(403, "只接受当前本机地址的请求。")
            return
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://" + self.headers.get("Host", ""):
            self.close_connection = True
            self._error(403, "请求来源不匹配。")
            return
        token = self.headers.get("X-AMSEO-Token", "")
        if not hmac.compare_digest(token.encode("utf-8"), self.server.token.encode("ascii")):
            self.close_connection = True
            self._error(403, "请刷新工作台后重试。")
            return
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            self._error(400, "不支持该请求编码。")
            return
        if self.headers.get_content_type() != "application/json":
            self.close_connection = True
            self._error(415, "请求需要 JSON 数据。")
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            self._error(413 if length > MAX_BODY else 400, "请求大小不符合要求。")
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            self._error(400, "请求数据格式错误。")
            return
        path = self._path()
        if path == "/api/geo":
            workspace = self.server.geo_workspace
            try:
                action = payload.get("action")
                if action == "generate": result = workspace.generate(payload.get("question_ids"))
                elif action == "prepare": result = workspace.prepare(payload.get("task_id"))
                elif action == "prepare-all":
                    result = [workspace.prepare(task["id"]) for task in workspace.state()["tasks"] if task.get("status") == "ready"]
                elif action == "check": result = workspace.check(payload.get("task_id"))
                elif action == "toggle": result = workspace.toggle(payload.get("task_id"), payload.get("done"))
                elif action == "import-traffic": result = workspace.import_traffic(payload)
                else: raise ValueError("优化操作不存在。")
                self._json(200, {"result": result})
            except (ValueError, OSError) as error:
                self._error(400, str(error)[:300])
        elif path == "/api/question-lab":
            try:
                action = payload.get("action")
                if action == "configure": result = self.server.question_lab.configure(payload)
                elif action == "verify-connection": result = self.server.question_lab.verify_connection()
                else: result = self.server.question_lab.start(action, payload)
                self._json(200, {"result": result})
            except (ValueError, OSError) as error:
                # Provider errors are sanitized before reaching this boundary.
                self._error(400, str(error)[:400])
        elif path == "/api/workflow":
            try:
                result = self.server.workflow.start(
                    payload.get("action"), cycle_id=payload.get("cycle_id"),
                    task_id=payload.get("task_id"), payload=payload,
                )
            except ValueError as error:
                self._error(409 if self.server.workflow.state()["active"] else 400, str(error))
                return
            self._json(202, result)
        elif path == "/api/jobs":
            kind = payload.get("kind")
            if not isinstance(kind, str) or kind not in {"offline-validation", "upstream-verification"}:
                self._error(400, "不支持的检查类型。")
                return
            with self.server.lock:
                active = next((j for j in self.server.records["jobs"] if j.get("status") in {"queued", "running"}), None)
                if active:
                    self._json(409, {"error": "已有检查正在运行。", "job": active})
                    return
                job = {"id": uuid.uuid4().hex, "kind": kind, "status": "queued", "created_at": _now(), "output": ""}
                self.server.records["jobs"].append(job)
                self.server.save("jobs")
                snapshot = dict(job)
                threading.Thread(target=self.server.run_job, args=(job,), daemon=True).start()
            self._json(202, {"job": snapshot})
        elif path == "/api/requests":
            goal, market, channels = payload.get("goal"), payload.get("market"), payload.get("channels")
            if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 4000 or not isinstance(market, str) or market not in MARKETS or not isinstance(channels, list) or not 1 <= len(channels) <= len(CHANNELS) or any(not isinstance(c, str) or c not in CHANNELS for c in channels):
                self._error(400, "请填写目标、市场和至少一个有效渠道。")
                return
            request = {"id": uuid.uuid4().hex, "goal": goal.strip(), "market": market, "channels": list(dict.fromkeys(channels)), "status": "waiting_executor", "created_at": _now()}
            with self.server.lock:
                self.server.records["requests"].append(request)
                self.server.save("requests")
            self._json(201, {"request": request})
        elif path == "/api/feedback":
            task_id, feedback = payload.get("task_id"), payload.get("text")
            task_ids = {t.get("id") for t in self.server.state()["tasks"] if isinstance(t, dict)}
            if not isinstance(task_id, str) or task_id not in task_ids or not isinstance(feedback, str) or not 1 <= len(feedback.strip()) <= 4000:
                self._error(400, "请选择任务并填写反馈。")
                return
            item = {"id": uuid.uuid4().hex, "task_id": task_id, "text": feedback.strip(), "status": "recorded", "created_at": _now()}
            with self.server.lock:
                self.server.records["feedback"].append(item)
                self.server.save("feedback")
            self._json(201, {"feedback": item})
        else:
            self._error(404, "操作不存在。")


def make_server(root: Path, host: str = "127.0.0.1", port: int = 0) -> ConsoleServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The local console must bind to 127.0.0.1 or localhost.")
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    return ConsoleServer(Path(root), host, port)


def serve(root: Path, host: str = "127.0.0.1", port: int = 8787):
    server = make_server(root, host=host, port=port)
    print(f"AM SEO 工作台：http://{host}:{server.server_port}/", flush=True)
    print("仅本机可访问；按 Ctrl+C 停止。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
