import pytest
from playwright.sync_api import Page, expect

def test_login_admin_success(page: Page):
    """Test login thành công với role admin"""
    
    # 1. Bật tính năng chặn request và mock API
    def handle_login(route):
        route.fulfill(
            status=200,
            json={
                "success": True,
                "access_token": "fake-jwt",
                "refresh_token": "fake-refresh",
                "user": {
                    "id": 1,
                    "email": "admin@example.com",
                    "role": "admin",
                    "name": "Admin Tester"
                }
            }
        )
    
    page.route("**/api/auth/login", handle_login)
    
    # 2. Truy cập trang login
    page.goto("http://127.0.0.1:5001/auth/login")
    
    # 3. Điền thông tin
    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password123")
    
    # 4. Nhấn nút Đăng nhập
    page.click("button[id='loginBtn']")
    
    # 5. Xác nhận hiển thị thông báo thành công
    alert = page.locator(".alert-success")
    expect(alert).to_be_visible()
    expect(alert).to_contain_text("Đăng nhập thành công")
    
    # 6. Xác nhận đã được chuyển hướng sang trang dashboard
    # Playwright có thể đợi URL thay đổi
    page.wait_for_url("**/dashboard")
    expect(page).to_have_url("http://127.0.0.1:5001/dashboard")


def test_login_student_success(page: Page):
    """Test login thành công với role student và redirect đúng trang"""
    
    def handle_login(route):
        route.fulfill(
            status=200,
            json={
                "success": True,
                "access_token": "fake-jwt-student",
                "refresh_token": "fake-refresh",
                "user": {
                    "id": 2,
                    "email": "student@student.com",
                    "role": "student",
                    "name": "Student Tester"
                }
            }
        )
    
    page.route("**/api/auth/login", handle_login)
    
    page.goto("http://127.0.0.1:5001/auth/login")
    
    page.fill("input[name='email']", "student@student.com")
    page.fill("input[name='password']", "password123")
    page.click("button[id='loginBtn']")
    
    # 6. Xác nhận đã được chuyển hướng sang trang profile thay vì dashboard
    page.wait_for_url("**/student/profile")
    expect(page).to_have_url("http://127.0.0.1:5001/student/profile")


def test_login_failure(page: Page):
    """Test hiển thị lỗi khi sai mật khẩu"""
    
    def handle_login(route):
        route.fulfill(
            status=401,
            json={
                "success": False,
                "message": "Sai mật khẩu hoặc email"
            }
        )
    
    page.route("**/api/auth/login", handle_login)
    
    page.goto("http://127.0.0.1:5001/auth/login")
    
    page.fill("input[name='email']", "wrong@example.com")
    page.fill("input[name='password']", "wrongpass")
    page.click("button[id='loginBtn']")
    
    # Xác nhận có thông báo lỗi
    alert = page.locator(".alert-danger")
    expect(alert).to_be_visible()
    expect(alert).to_contain_text("Sai mật khẩu hoặc email")
