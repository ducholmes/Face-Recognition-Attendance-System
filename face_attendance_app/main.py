import os
import httpx
import io
from fastapi import FastAPI, Request, Cookie, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Face Attendance Frontend")

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

API_BASE    = os.getenv("API_BASE_URL", "http://localhost:8000")
CLIENT_BASE = os.getenv("CLIENT_BASE_URL", "http://localhost:5000")

def render(request: Request, template_name: str, context: dict = None):
    """
    Starlette 1.0+: TemplateResponse(request, name, context)
    Sử dụng positional parameters để tương thích.
    """
    ctx = context or {}
    ctx["request"] = request
    ctx["api_base"] = API_BASE
    return templates.TemplateResponse(request, template_name, ctx)


# ---------------------------------------------------------------------------
# Helper: check authentication from Authorization header
# ---------------------------------------------------------------------------

def get_user_from_token(authorization: Optional[str] = None):
    """
    Extract user info from Authorization header.
    Returns user dict or None if not authenticated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return {"authenticated": True}

async def api_get(path: str, headers: dict = None):
    """Gọi GET đến backend API, trả về JSON hoặc None."""
    try:
        request_headers = headers or {}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}{path}", headers=request_headers)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[API GET {path}] error: {e}")
        return None

@app.post("/process_frame")
async def proxy_process_frame(request: Request):
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{CLIENT_BASE}/process_frame",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "client_offline", "message": f"Flask client chưa chạy. Hãy chạy: python run.py (port 5000)"},
            status_code=503
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/continue_recognition")
async def proxy_continue_recognition():
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{CLIENT_BASE}/continue_recognition")
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "client_offline", "message": "Flask client chưa chạy. Hãy chạy: python run.py (port 5000)"},
            status_code=503
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/confirm_attendance")
async def proxy_confirm_attendance_upload():
    """Proxy → Flask client: upload snapshot khi người dùng xác nhận."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{CLIENT_BASE}/confirm_attendance")
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "client_offline", "message": "Flask client chưa chạy. Hãy chạy: python run.py (port 5000)"},
            status_code=503
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/register_face")
async def proxy_register_face(request: Request):
    """Proxy → Flask client: trích xuất embedding từ ảnh."""
    try:
        body = await request.json()
        print(f"[proxy_register_face] Received request with keys: {body.keys()}")
    except Exception as e:
        print(f"[proxy_register_face] JSON parse error: {e}")
        return JSONResponse({"error": "Dữ liệu gửi lên không phải JSON hợp lệ hoặc bị rỗng."}, status_code=400)
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{CLIENT_BASE}/register_face",
                json=body,  # Sửa từ content=body thành json=body
                headers={"Content-Type": "application/json"},
            )
            print(f"[proxy_register_face] Flask response status: {r.status_code}")
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "client_offline", "message": "Flask client chưa chạy. Hãy chạy: python client/app.py (port 5000)"},
            status_code=503
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/register")
async def proxy_register(request: Request):
    """Proxy → Backend API: đăng ký sinh viên vào Pinecone + Supabase."""
    print("=" * 80)
    print("[proxy_register] Received request from frontend")
    try:
        data = await request.json()
        print(f"[proxy_register] Data keys: {data.keys()}")
        print(f"[proxy_register] Student ID: {data.get('student_id')}")
        print(f"[proxy_register] Name: {data.get('name')}")
        print(f"[proxy_register] Embedding length: {len(data.get('embedding', []))}")
    except Exception as e:
        print(f"[proxy_register] JSON parse error: {e}")
        return JSONResponse(
            {"error": "invalid_json", "message": f"Dữ liệu gửi lên không phải JSON hợp lệ: {str(e)}"},
            status_code=400
        )
    
    # Forward Authorization header từ browser lên backend API
    auth_header = request.headers.get("Authorization")
    print(f"[proxy_register] Authorization header from browser: {'PRESENT' if auth_header else 'MISSING'}")
    print(f"[proxy_register] All request headers: {dict(request.headers)}")
    forward_headers = {"Content-Type": "application/json"}
    if auth_header:
        forward_headers["Authorization"] = auth_header

    try:
        print(f"[proxy_register] Forwarding to {API_BASE}/register...")
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{API_BASE}/register",
                json=data,
                headers=forward_headers
            )
            print(f"[proxy_register] Backend response status: {r.status_code}")
            response_data = r.json()
            print(f"[proxy_register] Backend response: {response_data}")
            return JSONResponse(content=response_data, status_code=r.status_code)
    except httpx.ConnectError:
        print("[proxy_register] ERROR: Cannot connect to Backend API")
        return JSONResponse(
            {"error": "api_offline", "message": "Backend API chưa chạy. Hãy chạy: uvicorn API.main:app --port 8000"},
            status_code=503
        )
    except Exception as e:
        print(f"[proxy_register] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/reset_detection")
async def proxy_reset():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{CLIENT_BASE}/reset_detection")
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except httpx.ConnectError:
        return JSONResponse({"success": True}, status_code=200)  # reset silently
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/students/{student_id}")
async def proxy_delete_student(student_id: str, request: Request):
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.delete(f"{API_BASE}/students/{student_id}", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.put("/students/{student_id}")
async def proxy_update_student(student_id: str, request: Request):
    """Proxy PUT /students/{student_id} to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header, "Content-Type": "application/json"} if auth_header else {"Content-Type": "application/json"}
    try:
        body = await request.json()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.put(f"{API_BASE}/students/{student_id}", json=body, headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/snapshots/{image_path:path}")
async def proxy_get_snapshot(image_path: str, request: Request):
    """Proxy GET /snapshots/{image_path} to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        # follow_redirects=True để xử lý cả trường hợp backend redirect sang public URL
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(f"{API_BASE}/snapshots/{image_path}", headers=headers)
            if r.status_code == 200:
                content_type = r.headers.get("content-type", "image/jpeg")
                return Response(
                    content=r.content,
                    media_type=content_type,
                    headers={
                        "Content-Disposition": r.headers.get("content-disposition", f"inline; filename={image_path.split('/')[-1]}"),
                        "Cache-Control": "public, max-age=3600"
                    }
                )
            else:
                try:
                    return JSONResponse(content=r.json(), status_code=r.status_code)
                except Exception:
                    return JSONResponse(content={"error": r.text}, status_code=r.status_code)
    except Exception as e:
        print(f"[proxy_snapshot] Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/students")
async def proxy_get_students(request: Request):
    """Proxy GET /students to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}/students", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/attendance")
async def proxy_get_attendance(request: Request):
    """Proxy GET /attendance to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}/attendance", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/attendance/confirm")
async def proxy_confirm_attendance(request: Request):
    """Proxy POST /attendance/confirm to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header, "Content-Type": "application/json"} if auth_header else {"Content-Type": "application/json"}
    try:
        body = await request.json()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{API_BASE}/attendance/confirm", json=body, headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/attendance/today")
async def proxy_get_attendance_today(request: Request):
    """Proxy GET /attendance/today to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}/attendance/today", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



@app.post("/api/auth/login")
async def proxy_login(request: Request):
    """Proxy login request to backend API"""
    try:
        body = await request.json()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{API_BASE}/auth/login", json=body)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/auth/register")
async def proxy_register_auth(request: Request):
    """Proxy auth registration request to backend API"""
    try:
        body = await request.json()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{API_BASE}/auth/register", json=body)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/student/check-registration")
async def proxy_check_registration(request: Request):
    """Proxy GET /student/check-registration to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}/student/check-registration", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/student/attendance-history")
async def proxy_attendance_history(request: Request):
    """Proxy GET /student/attendance-history to backend API with auth header"""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}/student/attendance-history", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/admin/configs")
async def proxy_get_configs(request: Request):
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}/admin/configs", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/admin/configs/{key}")
async def proxy_get_config(key: str, request: Request):
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_BASE}/admin/configs/{key}", headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.put("/api/admin/configs/{key}")
async def proxy_update_config(key: str, request: Request):
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header, "Content-Type": "application/json"} if auth_header else {"Content-Type": "application/json"}
    try:
        body = await request.json()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.put(f"{API_BASE}/admin/configs/{key}", json=body, headers=headers)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/welcome", response_class=HTMLResponse)
async def welcome_page(request: Request):
    """Render welcome/landing page"""
    return render(request, "welcome.html")


@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page"""
    return render(request, "auth/login.html")


@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render register page for students"""
    return render(request, "auth/register.html")


@app.post("/auth/logout")
async def logout():
    """Handle logout"""
    return JSONResponse({"success": True, "message": "Logged out successfully"})

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/welcome")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Don't fetch data server-side, let client-side JavaScript handle it with token
    return render(request, "dashboard.html", {
        "active_page": "dashboard",
    })


@app.get("/students", response_class=HTMLResponse)
async def students_page(request: Request):
    # Don't fetch data server-side, let client-side JavaScript handle it with token
    return render(request, "students.html", {
        "active_page": "students",
    })


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return render(request, "register.html", {
        "active_page": "register",
    })


@app.get("/attendance", response_class=HTMLResponse)
async def attendance_page(request: Request):
    return render(request, "attendance.html", {
        "active_page": "attendance",
        "api_base":    API_BASE,
    })


@app.get("/attendance/history", response_class=HTMLResponse)
async def attendance_history(request: Request):
    # Don't fetch data server-side, let client-side JavaScript handle it with token
    # Get Supabase URL for image display
    supabase_url = os.getenv("SUPABASE_URL", "")
    
    return render(request, "attendance_history.html", {
        "active_page": "history",
        "supabase_url": supabase_url,
    })


@app.get("/student/profile", response_class=HTMLResponse)
async def student_profile(request: Request):
    """Student profile page"""
    return render(request, "student/profile.html", {
        "active_page": "profile",
    })


@app.get("/student/register", response_class=HTMLResponse)
async def student_register(request: Request):
    """Student face registration page"""
    return render(request, "student/register.html", {
        "active_page": "register",
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Admin configuration settings page"""
    return render(request, "settings.html", {
        "active_page": "settings",
    })
