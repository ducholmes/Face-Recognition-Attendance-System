from client.app import application
from config import upload_dir
import os

if __name__ == '__main__':
    print("🚀 Starting Face Detection Stream Server...")
    print(f"📁 Saving detected faces to: {upload_dir}/")
    print("🌐 Open browser at: http://localhost:5000")
    print("=" * 50)
    application.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
