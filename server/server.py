#!/usr/bin/env python3
"""Backend for the glasses app: receives a photo and a question, answers with Codex.

Codex runs with the user's own ChatGPT login (no API key). One request at a time,
so a burst of taps cannot drain the plan's limits.

    python3 server.py                 # listens on 0.0.0.0:8787
    curl -H "Authorization: Bearer $(cat ~/.config/glasses-chat/token)" localhost:8787/health
"""
import base64
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("GLASSES_PORT", "8787"))
MODEL = os.environ.get("GLASSES_MODEL", "")  # empty = Codex default from ~/.codex/config.toml
EFFORT = os.environ.get("GLASSES_EFFORT", "low")
TIMEOUT = int(os.environ.get("GLASSES_TIMEOUT", "60"))
TOKEN_FILE = Path.home() / ".config/glasses-chat/token"
MAX_BODY = 8 * 1024 * 1024

PROMPT = """Sei l'assistente vocale dentro un paio di occhiali smart. La foto, se c'e', \
e' quello che l'utente sta guardando in questo momento.
Rispondi in italiano, in una o due frasi brevi e naturali da dire ad alta voce: \
niente markdown, niente elenchi, niente emoji. Se la domanda non riguarda la foto, \
rispondi alla domanda e basta. Non usare strumenti e non leggere file.

Domanda: {question}"""

LOCK = threading.Lock()


def load_token():
    if not TOKEN_FILE.exists():
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(secrets.token_urlsafe(24))
        TOKEN_FILE.chmod(0o600)
    return TOKEN_FILE.read_text().strip()


def ask_codex(question, image_bytes):
    with tempfile.TemporaryDirectory(prefix="glasses-") as tmp:
        out = Path(tmp) / "answer.txt"
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
               "-C", tmp, "-o", str(out), "-c", f'model_reasoning_effort="{EFFORT}"']
        if MODEL:
            cmd += ["-m", MODEL]
        # the prompt goes before -i, which takes several files
        cmd.append(PROMPT.format(question=question or "Cosa sto guardando?"))
        if image_bytes:
            img = Path(tmp) / "view.jpg"
            img.write_bytes(image_bytes)
            cmd += ["-i", str(img)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        answer = out.read_text().strip() if out.exists() else ""
        if r.returncode != 0 or not answer:
            raise RuntimeError((r.stderr or r.stdout).strip()[-400:] or f"codex exit {r.returncode}")
        return answer


class Handler(BaseHTTPRequestHandler):
    server_version = "glasses-chat/1"

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        return secrets.compare_digest(self.headers.get("Authorization", ""), f"Bearer {TOKEN}")

    def do_GET(self):
        if self.path != "/health":
            return self._send(404, {"error": "not found"})
        if not self._authorized():
            return self._send(401, {"error": "token"})
        self._send(200, {"ok": True, "backend": "codex", "model": MODEL or "default", "busy": LOCK.locked()})

    def do_POST(self):
        if self.path != "/ask":
            return self._send(404, {"error": "not found"})
        if not self._authorized():
            return self._send(401, {"error": "token"})
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_BODY:
            return self._send(413, {"error": "body"})
        try:
            req = json.loads(self.rfile.read(length))
            image = base64.b64decode(req["image"]) if req.get("image") else None
        except (ValueError, KeyError) as e:
            return self._send(400, {"error": f"json: {e}"})
        if not LOCK.acquire(blocking=False):
            return self._send(429, {"error": "busy", "answer": "Sto ancora rispondendo alla domanda di prima."})
        t0 = time.monotonic()
        try:
            answer = ask_codex(req.get("question", "").strip(), image)
            secs = round(time.monotonic() - t0, 1)
            self.log_message("ok %.1fs q=%r", secs, req.get("question", "")[:60])
            self._send(200, {"answer": answer, "seconds": secs})
        except subprocess.TimeoutExpired:
            self._send(504, {"error": "timeout", "answer": "Non sono riuscito a rispondere in tempo."})
        except Exception as e:  # surface the reason to the app, it reads it aloud only in debug
            self.log_message("error %s", e)
            self._send(502, {"error": str(e), "answer": "C'e' stato un problema con ChatGPT."})
        finally:
            LOCK.release()


if __name__ == "__main__":
    TOKEN = load_token()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"glasses-chat on :{PORT}, token in {TOKEN_FILE}", file=sys.stderr, flush=True)
    srv.serve_forever()
