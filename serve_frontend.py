import http.server
import socketserver
import os

PORT = 8000
DIRECTORY = r"D:\Projects\Gradious\Frontend"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print("Serving at port", PORT)
    httpd.serve_forever()
