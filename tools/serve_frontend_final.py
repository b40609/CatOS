# -*- coding: utf-8 -*-
"""
Serve C:\\Users\\user\\Desktop\\catOS-Frontend-Final at 127.0.0.1:8899
"""
import http.server
import socketserver
import os
import sys

DIRECTORY = r"C:\Users\user\Desktop\catOS-Frontend-Final"
PORT = 8899

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

def main():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving {DIRECTORY} at http://127.0.0.1:{PORT}")
        sys.stdout.flush()
        httpd.serve_forever()

if __name__ == '__main__':
    main()
