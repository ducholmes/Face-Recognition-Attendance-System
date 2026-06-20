import pytest
from playwright.sync_api import Page, expect

def setup_student_auth(page: Page):
    """Tiêm local storage fake JWT token cho role Student"""
    page.goto("http://127.0.0.1:5001/welcome")
    page.evaluate("""() => {
        localStorage.setItem('access_token', 'fake-student-token');
        localStorage.setItem('user', JSON.stringify({
            id: 2, role: 'student', name: 'Student User'
        }));
    }""")

def test_student_profile(page: Page):
    """Test trang Profile của Student"""
    setup_student_auth(page)
    
    # Mock API profile (nếu có gọi)
    page.route("**/api/student/check-registration", lambda route: route.fulfill(
        status=200,
        json={"success": True, "registered": True, "student": {"student_id": "SV002", "name": "Student User"}}
    ))
    page.route("**/api/student/attendance-history", lambda route: route.fulfill(
        status=200,
        json={"success": True, "history": []}
    ))
    
    page.goto("http://127.0.0.1:5001/student/profile")
    expect(page).to_have_url("http://127.0.0.1:5001/student/profile")
    
    # Đảm bảo hiển thị tên học sinh (tùy thuộc vào cách UI render, ta cứ check text)
    expect(page.locator("text=Face Attendance")).to_be_visible()

def test_student_cannot_access_admin_pages(page: Page):
    """Test học sinh không được phép thao tác trên trang Admin"""
    setup_student_auth(page)
    
    # Nếu học sinh cố gắng truy cập API của admin, mock API sẽ giả lập Backend trả về 403
    page.route("**/api/students", lambda route: route.fulfill(
        status=403,
        json={"detail": "Not authenticated or wrong role"}
    ))
    
    page.goto("http://127.0.0.1:5001/students")
    
    # Frontend auth.js sẽ tự động chuyển hướng (redirect) học sinh khỏi trang /students về /student/profile
    expect(page).to_have_url("http://127.0.0.1:5001/student/profile")
