import urllib.request
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import time

class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503)
        self.end_headers()

server = HTTPServer(('127.0.0.1', 8080), MyHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()

import subprocess
p = subprocess.run(["yt-dlp", "http://127.0.0.1:8080/test", "--retries", "2", "--retry-sleep", "linear=1::1"], capture_output=True, text=True)
print(p.stdout)
print("----")
print(p.stderr)
