"""只监听本机的标准库 HTTP GUI，无第三方依赖，不记录输入。"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .core import bits, decrypt_ascii, encrypt_ascii, parse_bits, trace_block
from .exchange import make_exchange, verify_exchange
from .experiments import brute_force, collision_analysis
from .visualization import simulate_peers, visual_trace

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
MAX_REQUEST_BYTES = 65_536


def parse_pairs(value: str) -> list[tuple[int, int]]:
    if not isinstance(value, str):
        raise ValueError("请每行输入一对 8 位明文和密文，以空格分隔")
    pairs = []
    for line_number, line in enumerate(value.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"第 {line_number} 行需要两列：明文 密文")
        pairs.append((parse_bits(parts[0], 8, "明文"), parse_bits(parts[1], 8, "密文")))
    return pairs


def dispatch(path: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("请求必须是 JSON 对象")
    if path == "/api/visual":
        return visual_trace(parse_bits(payload.get("block"), 8, "分组"),
                            parse_bits(payload.get("key"), 10, "密钥"), payload.get("operation"))
    if path == "/api/simulate":
        key = parse_bits(payload.get("key"), 10, "密钥")
        value = payload.get("plaintexts")
        if not isinstance(value, str):
            raise ValueError("请每行输入一个 8 位明文")
        plaintexts = [parse_bits(line.strip(), 8, "明文") for line in value.splitlines() if line.strip()]
        return simulate_peers(key, plaintexts)
    if path == "/api/block":
        operation = payload.get("operation")
        if operation not in ("encrypt", "decrypt"):
            raise ValueError("请选择加密或解密")
        return trace_block(parse_bits(payload.get("block"), 8, "分组"),
                           parse_bits(payload.get("key"), 10, "密钥"), operation == "decrypt")
    if path == "/api/ascii":
        key = parse_bits(payload.get("key"), 10, "密钥")
        value = payload.get("text")
        if not isinstance(value, str) or len(value) > 8192:
            raise ValueError("文本长度不能超过 8192 个字符")
        if payload.get("operation") == "encrypt":
            ciphertext = encrypt_ascii(value, key)
            return {"hex": ciphertext.hex(" "), "binary": " ".join(bits(byte) for byte in ciphertext),
                    "plaintext_binary": " ".join(bits(byte) for byte in value.encode("ascii")),
                    "bytes": len(ciphertext)}
        if payload.get("operation") == "decrypt":
            try:
                ciphertext = bytes.fromhex(value)
            except ValueError as error:
                raise ValueError("密文必须是十六进制字节，例如 a8 12；每字节两位") from error
            return {"text": decrypt_ascii(ciphertext, key), "bytes": len(ciphertext)}
        raise ValueError("请选择加密或解密")
    if path == "/api/brute":
        return brute_force(parse_pairs(payload.get("pairs")))
    if path == "/api/collision":
        return collision_analysis(parse_bits(payload.get("plaintext"), 8, "明文"))
    if path == "/api/export":
        key = parse_bits(payload.get("key"), 10, "密钥")
        value = payload.get("plaintexts")
        if not isinstance(value, str):
            raise ValueError("请每行输入一个 8 位明文")
        plaintexts = [parse_bits(line.strip(), 8, "明文") for line in value.splitlines() if line.strip()]
        return make_exchange(key, plaintexts)
    if path == "/api/verify":
        return verify_exchange(payload.get("document"))
    raise ValueError("未知功能")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format_string: str, *args) -> None:
        # 默认不输出请求日志，避免演示输入及个人信息进入终端录屏。
        pass

    def send_content(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status: int, result: dict) -> None:
        self.send_content(status, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def valid_host(self) -> bool:
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def do_GET(self) -> None:
        if not self.valid_host():
            self.send_json(403, {"error": "仅允许本机访问"})
            return
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/visuals.js": ("visuals.js", "text/javascript; charset=utf-8"),
                 "/visuals.css": ("visuals.css", "text/css; charset=utf-8")}
        resource = files.get(urlsplit(self.path).path)
        if resource is None:
            self.send_json(404, {"error": "页面不存在"})
            return
        filename, mime = resource
        self.send_content(200, (WEB_ROOT / filename).read_bytes(), mime)

    def do_POST(self) -> None:
        origin = self.headers.get("Origin")
        allowed_origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if not self.valid_host() or (origin is not None and origin not in allowed_origins):
            self.send_json(403, {"error": "仅允许本机同源请求"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("请求大小应在 1–65536 字节之间")
            payload = json.loads(self.rfile.read(length))
            result = dispatch(urlsplit(self.path).path, payload)
            self.send_json(200, result)
        except (ValueError, UnicodeError) as error:
            self.send_json(400, {"error": str(error)})


def main() -> None:
    parser = argparse.ArgumentParser(description="S-DES 本地实验台（仅监听 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as error:
        parser.exit(1, f"启动失败：{error}；可用 --port 8766 更换端口。\n")
    print(f"S-DES 实验台：http://127.0.0.1:{args.port} （Ctrl+C 退出）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
