#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
เปิด dashboard.html ให้มือถือ/แท็บเล็ตในวง Wi-Fi เดียวกันดูได้

    python scripts/serve.py            # พอร์ต 8765
    python scripts/serve.py --port 8080
"""

import argparse
import http.server
import socket
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/dashboard.html"
        return super().do_GET()

    def log_message(self, fmt, *args):  # noqa: A003
        print(f"{self.address_string()} - {fmt % args}")


def lan_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    with socketserver.TCPServer(("0.0.0.0", args.port), Handler) as httpd:
        print(f"เปิดแดชบอร์ดที่  http://{lan_ip()}:{args.port}/")
        print("ในเครื่องนี้:   http://localhost:{}/".format(args.port))
        print("กด Ctrl+C เพื่อหยุด")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nหยุดแล้ว")


if __name__ == "__main__":
    main()
