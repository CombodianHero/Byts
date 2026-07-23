"""
Health check endpoint for Koyeb
"""
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server.serve_forever()
