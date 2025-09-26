#!/usr/bin/env python3
"""
Simple HTTP server for EnvEval website development
Serves files with CORS headers to allow local file access
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def main():
    # Change to the parent directory (EnvEval root) to serve both website and dataset
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    PORT = 8000
    
    print(f"🚀 Starting EnvEval development server...")
    print(f"📁 Serving from: {project_root}")
    print(f"🌐 Website URL: http://localhost:{PORT}/website/")
    print(f"📊 Dataset URL: http://localhost:{PORT}/dataset/")
    print(f"⚠️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            sys.exit(0)

if __name__ == "__main__":
    main()
