import os
import sys
import subprocess
import time
import requests
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



@pytest.fixture(scope="session", autouse=True)
def start_servers():
    """Khởi động FastAPI (port 5001) dưới nền để test."""
    env = os.environ.copy()
    env["PYTHONPATH"] = BASE_DIR
    
    # Tắt log quá nhiều từ Uvicorn/Flask trong lúc test
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    
    # Uvicorn FastAPI
    fastapi_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "face_attendance_app.main:app", "--port", "5001"],
        cwd=BASE_DIR,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    time.sleep(2)
    
    if fastapi_process.poll() is not None:
        stdout_fa, _ = fastapi_process.communicate()
        pytest.fail(f"FastAPI crashed immediately! Return code: {fastapi_process.poll()}\nLog:\n{stdout_fa}")
    
    # Hàm ping đợi server
    def wait_for_server(url, timeout=45):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Gửi GET request
                res = requests.get(url, timeout=1)
                return True
            except requests.ConnectionError:
                time.sleep(0.5)
        return False

    fastapi_ready = wait_for_server("http://127.0.0.1:5001/welcome")
    
    if not fastapi_ready:
        fastapi_process.terminate()
        pytest.fail("FastAPI server (5001) failed to start.")
        
    yield
    
    # Tắt server sau khi xong mọi test
    fastapi_process.terminate()
