#!/usr/bin/env python3
# server.py — 给 lin-home 后端用的 HTTP 薄壳（纯标准库，零依赖）
#
# 跑法（VPS）：
#   FISHING_KEY=<密钥> python3 server.py        # 端口默认 8040，可用 PORT 覆盖
#   pm2 start server.py --name fishing --interpreter python3
#
# 接口：
#   GET  /health                → {"ok": true}
#   POST /cmd  {"cmd": "cast 10"}          → {"result": "……游戏文字……"}
#   POST /cmd  {"new_game": 2024}          → {"result": "……新的一局……"}（会清进度，慎用）
#   鉴权：请求头 X-Api-Key 必须等于环境变量 FISHING_KEY（没设 FISHING_KEY 则不鉴权，仅本机测试）
#
# 存档由 fishing.py 自己管（本目录 fishing_save.json），git pull 不会碰它。

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import fishing  # 盲玩版引擎

KEY = os.environ.get("FISHING_KEY", "")
PORT = int(os.environ.get("PORT", "8040"))
# 引擎是全局状态 + 写存档文件，不是线程安全的，所有指令串行执行
_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/cmd":
            return self._send(404, {"error": "not found"})
        if KEY and self.headers.get("X-Api-Key") != KEY:
            return self._send(401, {"error": "bad api key"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except Exception:
            return self._send(400, {"error": "bad json"})
        try:
            with _LOCK:
                if "new_game" in payload:
                    result = fishing.new_game(payload["new_game"])
                else:
                    cmd = str(payload.get("cmd") or "").strip()
                    if not cmd:
                        return self._send(400, {"error": "empty cmd"})
                    result = fishing.cmd(cmd)
        except Exception as e:  # cmd() 本身不该抛，这层是最后兜底
            return self._send(500, {"error": str(e)})
        return self._send(200, {"result": result})

    def log_message(self, fmt, *args):
        pass  # 不刷访问日志，pm2 日志保持干净


if __name__ == "__main__":
    if not KEY:
        print("⚠️ 没设 FISHING_KEY，接口无鉴权（仅本机测试用）")
    print(f"🎣 fishing server listening on :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
