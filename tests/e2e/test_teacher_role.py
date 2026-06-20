import pytest
from playwright.sync_api import Page, expect

def setup_teacher_auth(page: Page):
    """Tiêm local storage fake JWT token cho role Teacher"""
    page.goto("http://127.0.0.1:5001/welcome")
    page.evaluate("""() => {
        localStorage.setItem('access_token', 'fake-teacher-token');
        localStorage.setItem('user', JSON.stringify({
            id: 3, role: 'teacher', name: 'Teacher User'
        }));
    }""")

def test_teacher_dashboard(page: Page):
    """Test giáo viên có thể vào được Dashboard"""
    setup_teacher_auth(page)
    
    # Mock API thống kê
    page.route("**/api/attendance/today", lambda route: route.fulfill(
        status=200,
        json={"history": [], "total": 0}
    ))
    page.route("**/api/students", lambda route: route.fulfill(
        status=200,
        json=[{"student_id": "SV01", "name": "Nguyen Van A"}]
    ))
    
    page.goto("http://127.0.0.1:5001/dashboard")
    expect(page).to_have_url("http://127.0.0.1:5001/dashboard")
    expect(page.locator("text=Tổng quan hệ thống")).to_be_visible()

def test_teacher_cannot_edit_students(page: Page):
    """Test giáo viên chỉ có quyền xem danh sách sinh viên, không có nút Sửa/Xóa"""
    setup_teacher_auth(page)
    
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
    
    # Đảm bảo KHÔNG có nút sửa xóa
    row = page.locator("tr[data-id='sv001']")
    expect(row.locator("button.btn-outline-primary")).not_to_be_visible()
    expect(row.locator("button.btn-outline-danger")).not_to_be_visible()
    
    # Đảm bảo hiển thị text "Chỉ xem" thay vì các nút thao tác
    expect(row.locator("text=Chỉ xem")).to_be_visible()
