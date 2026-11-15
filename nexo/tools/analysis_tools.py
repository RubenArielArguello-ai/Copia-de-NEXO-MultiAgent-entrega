"""Read-only log/code inspection and bounded HTTP health checks."""
from __future__ import annotations

import ast
import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

from nexo.tools.base_tool import BaseTool, ToolParameter
from nexo.tools.basic_tools import _project_path


MAX_ANALYSIS_BYTES = 2 * 1024 * 1024
SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+")


class LogAnalysisTool(BaseTool):
    """Read a bounded workspace log and return redacted counts/pattern evidence."""
    timeout_seconds = 5
    @property
    def name(self): return "log_analysis"

    @property
    def description(self): return "Analiza errores y patrones en un log de texto del workspace"

    @property
    def parameters(self):
        return {"path": ToolParameter("path", str, required=True, description="Ruta de log dentro del workspace")}

    def execute(self, context):
        path = _project_path(str(context.get("path", "")))
        data = path.read_bytes()
        if len(data) > MAX_ANALYSIS_BYTES:
            return {"success": False, "error": "El log excede el límite de 2 MiB", "output": {}}
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        patterns = {"error": re.compile(r"\b(error|err|fatal|exception|traceback)\b", re.I),
                    "warning": re.compile(r"\b(warn|warning)\b", re.I),
                    "timeout": re.compile(r"\b(timeout|timed out)\b", re.I),
                    "denied": re.compile(r"\b(denied|unauthorized|forbidden)\b", re.I)}
        counts = {name: sum(bool(pattern.search(line)) for line in lines) for name, pattern in patterns.items()}
        matches = []
        for number, line in enumerate(lines, 1):
            if any(pattern.search(line) for pattern in patterns.values()):
                matches.append({"line": number, "text": SECRET_PATTERN.sub(r"\1=[REDACTED]", line[:500])})
        return {"success": True, "output": {"path": str(path.relative_to(Path.cwd().resolve())),
                "line_count": len(lines), "sha256": hashlib.sha256(data).hexdigest(),
                "pattern_counts": counts, "matches": matches[:100], "truncated_matches": max(0, len(matches)-100)}}


class CodeEngineeringTool(BaseTool):
    """Static Python inspection. Never imports or executes inspected code."""
    timeout_seconds = 5
    @property
    def name(self): return "code_engineering"

    @property
    def description(self): return "Comprueba sintaxis Python y patrones peligrosos sin ejecutar el archivo"

    @property
    def parameters(self):
        return {"path": ToolParameter("path", str, required=True, description="Archivo Python dentro del workspace")}

    def execute(self, context):
        path = _project_path(str(context.get("path", "")))
        if path.suffix.casefold() != ".py":
            return {"success": False, "error": "El analizador de código solo procesa archivos Python", "output": {}}
        data = path.read_bytes()
        if len(data) > MAX_ANALYSIS_BYTES:
            return {"success": False, "error": "El archivo excede el límite de 2 MiB", "output": {}}
        text = data.decode("utf-8", errors="replace")
        findings = []
        try:
            tree = ast.parse(text, filename=path.name)
            compile(tree, path.name, "exec")
            syntax_valid = True
        except (SyntaxError, ValueError) as exc:
            syntax_valid = False
            findings.append({"type": "syntax_error", "line": exc.lineno, "message": exc.msg})
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = node.func.id if isinstance(node.func, ast.Name) else ""
                    attr = node.func.attr if isinstance(node.func, ast.Attribute) else ""
                    if name in {"eval", "exec"}:
                        findings.append({"type": "dynamic_execution", "line": node.lineno, "severity": "high"})
                    if name == "Popen" or attr == "Popen":
                        findings.append({"type": "subprocess", "line": node.lineno, "severity": "review"})
        return {"success": True, "output": {"path": str(path.relative_to(Path.cwd().resolve())),
                "sha256": hashlib.sha256(data).hexdigest(), "syntax_valid": syntax_valid,
                "findings": findings, "executed": False, "automated_changes": False}}


class HTTPHealthCheckTool(BaseTool):
    """Fetch public HTTP(S) endpoints while rejecting private/local destinations."""
    timeout_seconds = 7
    @property
    def name(self): return "http_health_check"

    @property
    def description(self): return "Verifica estado y latencia HTTP de un endpoint público sin seguir redirecciones"

    @property
    def parameters(self):
        return {"url": ToolParameter("url", str, required=True, description="Endpoint HTTP(S) con destino público"),
                "timeout": ToolParameter("timeout", int, required=False, default=4, description="Tiempo máximo de conexión en segundos")}

    def execute(self, context):
        url = str(context.get("url", "")).strip()
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return {"success": False, "error": "URL inválida; se requiere HTTP(S) sin credenciales", "output": {}}
        try:
            explicit_port = parsed.port
        except ValueError:
            return {"success": False, "error": "Puerto HTTP inválido", "output": {}}
        display_host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        display_port = f":{explicit_port}" if explicit_port else ""
        display_url = f"{parsed.scheme}://{display_host}{display_port}{parsed.path or '/'}"
        conn = None
        try:
            port = explicit_port or (443 if parsed.scheme == "https" else 80)
            addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
            ips = sorted({item[4][0] for item in addresses})
            if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
                return {"success": False, "error": "Destino bloqueado por política SSRF", "output": {"host": parsed.hostname}}
            target = ips[0]
            timeout = min(5.0, max(1.0, float(context.get("timeout", 4))))
            started = time.monotonic()
            if parsed.scheme == "https":
                raw_socket = socket.create_connection((target, port), timeout=timeout)
                pinned_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=parsed.hostname)
                conn = http.client.HTTPConnection(target, port, timeout=timeout)
                conn.sock = pinned_socket
            else:
                conn = http.client.HTTPConnection(target, port, timeout=timeout)
                conn.sock = socket.create_connection((target, port), timeout=timeout)
            path = parsed.path or "/"
            if parsed.query: path += "?" + parsed.query
            default_port = 443 if parsed.scheme == "https" else 80
            host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
            host_header = host if port == default_port else f"{host}:{port}"
            conn.request("GET", path, headers={"Host": host_header, "User-Agent": "NEXO-health-check/1.0", "Connection": "close"})
            response = conn.getresponse()
            response.read(2048)
            elapsed = round((time.monotonic() - started) * 1000, 2)
            status = response.status
            safe_url = f"{parsed.scheme}://{host_header}{parsed.path or '/'}"
            return {"success": True, "output": {"url": safe_url, "status_code": status,
                    "healthy": 200 <= status < 400, "latency_ms": elapsed,
                    "redirect_followed": False, "resolved_addresses": ips}}
        except (ValueError, OSError, socket.error, http.client.HTTPException, ssl.SSLError) as exc:
            return {"success": False, "error": f"HTTP health check failed: {type(exc).__name__}", "output": {"url": display_url}}
        finally:
            if conn is not None:
                conn.close()


class ReportGenerationTool(BaseTool):
    """Produce a report strictly from observed prior tool outputs."""
    timeout_seconds = 5
    @property
    def name(self): return "report_generation"

    @property
    def description(self): return "Consolida resultados observados con referencias a sus herramientas y evidencias"

    @property
    def parameters(self):
        return {"request": ToolParameter("request", str, required=False, default=""),
                "prior_results": ToolParameter("prior_results", list, required=False, default=[])}

    def execute(self, context):
        results = context.get("prior_results", [])
        evidence = []
        observations = []
        for item in results if isinstance(results, list) else []:
            result = item.get("result", {}) if isinstance(item, dict) else {}
            payload = result.get("raw_results", {}) if isinstance(result, dict) else {}
            evidence.append({"task_id": item.get("task_id"), "tool": result.get("tool_used"),
                             "success": result.get("tool_success"), "observed": payload})
            if result.get("tool_success"):
                if result.get("tool_used") == "system_diagnostic":
                    disk = payload.get("disk", {})
                    memory = payload.get("memory", {})
                    system = payload.get("system", {})
                    observations.append(f"Sistema: {system.get('os', 'desconocido')}; CPU lógicas: {system.get('cpu_count', 'sin dato')}; RAM: {memory.get('total_gb', 'sin dato')} GiB total, {memory.get('available_gb', 'sin dato')} GiB disponible; disco usado: {disk.get('percent_used', 'sin dato')}%.")
                elif result.get("tool_used") == "network_diagnostic":
                    diagnosis = payload.get("diagnosis", {})
                    observations.append(f"Conectividad observada: {diagnosis.get('overall_status', 'estado no disponible')}.")
        report_text = "Informe técnico NEXO\n\n" + ("\n".join(f"- {line}" for line in observations) if observations else "No hay observaciones suficientes.")
        report_text += "\n\nEvidencias adjuntas por tarea, herramienta y hash/valores observados. No se incorporaron conclusiones sin datos registrados."
        successful_count = sum(item.get("success") is True for item in evidence)
        return {"success": successful_count > 0, "output": {"title": "Informe técnico NEXO", "report_text": report_text,
                "mission": str(context.get("request", "")), "evidence_count": successful_count,
                "evidence": evidence, "limitations": [] if evidence else ["No se recibieron resultados observados"],
                "conclusion": "Hallazgos derivados únicamente de las evidencias listadas." if evidence else "Sin evidencia suficiente."}}
