import pytest
import json
import re
from playwright.sync_api import Page, expect

def setup_admin_auth(page: Page):
    """Inject local storage fake JWT token để bypass script auto-redirect"""
    page.goto("http://127.0.0.1:5001/welcome")
    page.evaluate("""() => {
        localStorage.setItem('access_token', 'fake-admin-token');
        localStorage.setItem('user', JSON.stringify({
            id: 1, role: 'admin', name: 'Admin User'
        }));
    }""")

def test_admin_dashboard(page: Page):
    """Test Admin vào Dashboard và xem thống kê"""
    setup_admin_auth(page)
    
    # Mock API thống kê
    page.route("**/api/attendance/today", lambda route: route.fulfill(
        status=200,
        json={"history": [], "total": 0}
    ))
    # Mock students API for dashboard count
    page.route("**/api/students", lambda route: route.fulfill(
        status=200,
        json=[{"student_id": "SV01", "name": "Nguyen Van A"}]
    ))
    
    page.goto("http://127.0.0.1:5001/dashboard")
    expect(page).to_have_url("http://127.0.0.1:5001/dashboard")
    expect(page.locator("text=Tổng quan hệ thống")).to_be_visible()

def test_admin_student_management(page: Page):
    """Test quản lý sinh viên (Xem, Sửa, Xóa)"""
    setup_admin_auth(page)
    
    # 1. Mock API trả về danh sách sinh viên
    mock_students = [
        {
            "student_id": "SV001",
            "name": "Nguyễn Văn Test",
            "birthday": "2000-01-01",
            "gender": "Nam",
            "phone": "0123456789"
        }
    ]
    
    page.route("**/api/students", lambda route: route.fulfill(
        status=200,
        json=mock_students
    ))
    
    page.goto("http://127.0.0.1:5001/students")
    
    # Chờ bảng load xong
    table = page.locator("#studentsTable")
    expect(table).to_be_visible()
    
    # Kiểm tra hiển thị thông tin
    expect(page.locator("text=Nguyễn Văn Test")).to_be_visible()
    expect(page.locator("text=SV001")).to_be_visible()
    
    # 2. Test luồng Xóa (Delete)
    # Mock API Delete
    page.route(re.compile(r".*/students/SV001"), lambda route: route.fulfill(
        status=200,
        json={"message": "deleted"}
    ) if route.request.method == "DELETE" else route.continue_())
    
    # Bấm nút xóa của SV001
    page.click("tr[data-id='sv001'] button.btn-outline-danger")
    
    # Xác nhận popup hiện lên
    expect(page.locator("#deleteModal")).to_be_visible()
    
    # Đóng popup (không bấm xác nhận để đi tiếp test sửa)
    page.click("#deleteModal button.btn-secondary")
    expect(page.locator("#deleteModal")).not_to_be_visible()
    
    # 3. Test luồng Sửa (Edit)
    page.route(re.compile(r".*/students/SV001"), lambda route: route.fulfill(
        status=200,
        json={"message": "updated", "data": []}
    ) if route.request.method == "PUT" else route.continue_())
    
    page.click("tr[data-id='sv001'] button.btn-outline-primary")
    expect(page.locator("#editModal")).to_be_visible()
    
    # Điền form sửa
    page.fill("#editName", "Nguyễn Văn Đã Sửa")
    page.click("#confirmEditBtn")
    
    # Kiểm tra Toast thông báo thành công
    expect(page.locator("text=Cập nhật thông tin thành công")).to_be_visible()
