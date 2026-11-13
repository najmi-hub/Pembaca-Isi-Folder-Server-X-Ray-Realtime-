import http.server
import socketserver
import os

PORT = 8080
DIRECTORY = r"D:\Image" if os.path.exists("D:\\") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "Image")

os.makedirs(DIRECTORY, exist_ok=True)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

socketserver.TCPServer.allow_reuse_address = True

if __name__ == "__main__":
    print(f"Menjalankan Image Server di: {DIRECTORY}")
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Server aktif melayani gambar pada http://localhost:{PORT}")
            httpd.serve_forever()
    except OSError:
        print(f"\nPort {PORT} sedang digunakan oleh proses lain (pythonw di background).")
        print(f"Cek di browser: http://localhost:{PORT}")