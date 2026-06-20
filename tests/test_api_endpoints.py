import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import date

# Mock FaceAttendanceDB — được dùng trong hầu hết route files
mock_db_class = MagicMock()
mock_db_instance = MagicMock()
mock_db_class.return_value = mock_db_instance

# Mock supabase create_client — được dùng trong auth.py
mock_supabase_client = MagicMock()

# Áp dụng mock TRƯỚC khi import
patches = [
    patch("API.db.database_module.create_client", return_value=mock_supabase_client),
    patch("API.db.database_module.Pinecone", MagicMock()),
    patch("API.db.database_module.FaceAttendanceDB", mock_db_class),
    patch("API.routes.recognize.recognize_face", MagicMock(return_value={"recognized": False})),
    patch("API.websocket_handler.recognize_face", MagicMock(return_value={"recognized": False})),
    patch("API.utils.auth.create_client", return_value=mock_supabase_client),
]

for p in patches:
    p.start()

from fastapi.testclient import TestClient
from API.main import app
from API.utils.auth import require_role

def make_fake_auth(role="admin"):
    """
    Tạo dependency giả thay thế require_role().
    Thay vì check token thật với Supabase, trả về fake user ngay.
    """
    fake_user = MagicMock()
    fake_user.id = "test-user-id"
    fake_user.email = "test@example.com"
    fake_user.get = lambda key, default=None: {
        "id": "test-user-id",
        "email": "test@example.com",
        "role": role,
    }.get(key, default)

    async def fake_role_checker():
        return fake_user

    return fake_role_checker

original_require_role = require_role


def mock_require_role(allowed_roles):
    """Trả về fake checker thay vì checker thật."""
    return make_fake_auth(allowed_roles[0])

@pytest.fixture
def client():
    """Tạo TestClient với tất cả auth dependencies được bypass."""
    with patch("API.routes.attendance.require_role", mock_require_role), \
         patch("API.routes.auth.require_role", mock_require_role), \
         patch("API.routes.register.require_role", mock_require_role), \
         patch("API.routes.students.require_role", mock_require_role), \
         patch("API.routes.student_detail.require_role", mock_require_role), \
         patch("API.routes.snapshots.require_role", mock_require_role), \
         patch("API.routes.recognize.require_role", mock_require_role):

        # Cần re-import và re-build routes để patch có hiệu lực
        # Nhưng vì app đã build, ta override dependency trực tiếp
        # Override tất cả dependency bằng cách dùng dependency_overrides
        for route in app.routes:
            if hasattr(route, "dependant"):
                for dep in route.dependant.dependencies:
                    if hasattr(dep, "call") and "role_checker" in str(dep.call):
                        app.dependency_overrides[dep.call] = make_fake_auth()

        with TestClient(app) as c:
            yield c

        # Cleanup
        app.dependency_overrides.clear()


@pytest.fixture
def mock_db():
    """Trả về mock DB instance để test có thể config response."""
    return mock_db_instance

class TestHealthEndpoint:
    """Test GET /health — endpoint đơn giản nhất, không cần auth."""

    def test_health_returns_200(self, client):
        """Health check trả về status 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client):
        """Response body có status = 'ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

class TestAttendanceConfirm:
    """Test POST /attendance/confirm — điểm danh."""

    def test_confirm_with_valid_data(self, client, mock_db):
        """Gửi student_id hợp lệ → 200."""
        # Mock save_attendance trả về thành công
        with patch("API.routes.attendance.save_attendance") as mock_save:
            mock_save.return_value = {
                "success": True,
                "data": [{"id": 1, "student_id": "SV001"}]
            }

            response = client.post("/attendance/confirm", json={
                "student_id": "SV001",
                "snapshot_url": "http://example.com/photo.jpg"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_confirm_with_int_student_id(self, client, mock_db):
        """student_id là int → tự convert thành str (nhờ field_validator)."""
        with patch("API.routes.attendance.save_attendance") as mock_save:
            mock_save.return_value = {
                "success": True,
                "data": [{"id": 1, "student_id": "12345"}]
            }

            response = client.post("/attendance/confirm", json={
                "student_id": 12345
            })

            assert response.status_code == 200

    def test_confirm_missing_student_id(self, client):
        """Thiếu student_id → 422 Validation Error."""
        response = client.post("/attendance/confirm", json={})
        assert response.status_code == 422

    def test_confirm_cooldown_returns_400(self, client):
        """Khi bị cooldown → 400 Bad Request."""
        with patch("API.routes.attendance.save_attendance") as mock_save:
            mock_save.return_value = {
                "success": False,
                "message": "Vui lòng đợi 25s trước khi điểm danh lại"
            }

            response = client.post("/attendance/confirm", json={
                "student_id": "SV001"
            })

            assert response.status_code == 400


class TestAttendanceGet:
    """Test GET /attendance/ — lấy lịch sử điểm danh."""

    def test_get_attendance_success(self, client, mock_db):
        """Lấy danh sách điểm danh thành công."""
        mock_db.supabase.table.return_value \
            .select.return_value \
            .order.return_value \
            .execute.return_value.data = [
                {"student_id": "SV001", "action": "IN", "created_at": "2026-05-22T10:00:00"}
            ]

        response = client.get("/attendance/")
        assert response.status_code == 200

    def test_get_attendance_stats(self, client, mock_db):
        """Lấy thống kê điểm danh."""
        mock_db.get_summary_stats.return_value = {
            "Tổng số sinh viên": 10,
            "Tổng số lượt quét": 50,
            "Lượt quét hôm nay": 5,
        }

        response = client.get("/attendance/stats")
        assert response.status_code == 200

class TestAuthRegister:
    """Test POST /auth/register — đăng ký tài khoản."""

    def test_register_non_student_role_returns_403(self, client, mock_db):
        """Đăng ký với role teacher → 403 Forbidden."""
        response = client.post("/auth/register", json={
            "email": "teacher@example.com",
            "password": "securepass123",
            "role": "teacher"
        })

        assert response.status_code == 403

    def test_register_student_success(self, client, mock_db):
        """Đăng ký sinh viên thành công."""
        # Mock Supabase auth sign_up
        fake_user = MagicMock()
        fake_user.id = "new-user-id"
        fake_user.email = "student@example.com"

        fake_auth_response = MagicMock()
        fake_auth_response.user = fake_user

        mock_db.supabase.auth.sign_up.return_value = fake_auth_response
        mock_db.supabase.table.return_value \
            .insert.return_value \
            .execute.return_value.data = [{"id": "new-user-id", "role": "student"}]

        response = client.post("/auth/register", json={
            "email": "student@example.com",
            "password": "securepass123",
            "role": "student"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"]["role"] == "student"

    def test_register_invalid_email_returns_422(self, client):
        """Email sai format → 422 (Pydantic validation)."""
        response = client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "securepass123",
            "role": "student"
        })

        assert response.status_code == 422

    def test_register_short_password_returns_422(self, client):
        """Password < 8 ký tự → 422 (Pydantic validation)."""
        response = client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "short",
            "role": "student"
        })

        assert response.status_code == 422


class TestAuthLogin:
    """Test POST /auth/login — đăng nhập."""

    def test_login_success(self, client, mock_db):
        """Đăng nhập thành công → trả về token."""
        fake_user = MagicMock()
        fake_user.id = "user-123"
        fake_user.email = "test@example.com"

        fake_session = MagicMock()
        fake_session.access_token = "access-token-abc"
        fake_session.refresh_token = "refresh-token-xyz"

        fake_response = MagicMock()
        fake_response.user = fake_user
        fake_response.session = fake_session

        mock_db.supabase.auth.sign_in_with_password.return_value = fake_response
        mock_db.supabase.table.return_value \
            .select.return_value \
            .eq.return_value \
            .execute.return_value.data = [{"role": "student"}]

        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "securepass123"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["access_token"] == "access-token-abc"
        assert data["refresh_token"] == "refresh-token-xyz"

    def test_login_invalid_email_returns_422(self, client):
        """Email sai format → 422."""
        response = client.post("/auth/login", json={
            "email": "not-an-email",
            "password": "password123"
        })

        assert response.status_code == 422

    def test_login_wrong_credentials_returns_401(self, client, mock_db):
        """Sai email/password → 401."""
        mock_db.supabase.auth.sign_in_with_password.side_effect = \
            Exception("Invalid login credentials")

        response = client.post("/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })

        assert response.status_code == 401

class TestStudentsEndpoint:
    """Test GET /students/ — lấy danh sách sinh viên."""

    def test_get_students_returns_list(self, client, mock_db):
        """Trả về danh sách sinh viên."""
        mock_db.supabase.table.return_value \
            .select.return_value \
            .execute.return_value.data = [
                {"student_id": "SV001", "name": "Nguyễn Văn A"},
                {"student_id": "SV002", "name": "Trần Thị B"},
            ]

        response = client.get("/students/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_students_empty(self, client, mock_db):
        """Không có sinh viên → trả list rỗng."""
        mock_db.supabase.table.return_value \
            .select.return_value \
            .execute.return_value.data = []

        response = client.get("/students/")
        assert response.status_code == 200
        data = response.json()
        assert data == []

class TestStudentDelete:
    """Test DELETE /students/{student_id}."""

    def test_delete_student_success(self, client, mock_db):
        """Xóa sinh viên thành công."""
        mock_db.delete_student.return_value = True

        response = client.delete("/students/SV001")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "deleted"

    def test_delete_student_not_found(self, client, mock_db):
        """Sinh viên không tồn tại → trả error."""
        mock_db.delete_student.return_value = False

        response = client.delete("/students/INVALID")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data


class TestStudentUpdate:
    """Test PUT /students/{student_id}."""

    def test_update_student_success(self, client, mock_db):
        """Cập nhật thông tin sinh viên thành công."""
        mock_db.supabase.table.return_value \
            .update.return_value \
            .eq.return_value \
            .execute.return_value.data = [
                {"student_id": "SV001", "name": "Tên Mới"}
            ]

        response = client.put("/students/SV001", json={
            "name": "Tên Mới"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "updated"

    def test_update_student_not_found(self, client, mock_db):
        """Sinh viên không tồn tại → trả error."""
        mock_db.supabase.table.return_value \
            .update.return_value \
            .eq.return_value \
            .execute.return_value.data = []

        response = client.put("/students/INVALID", json={
            "name": "Tên Mới"
        })

        assert response.status_code == 200
        data = response.json()
        assert "error" in data

class TestRegisterStudent:
    """Test POST /register — đăng ký khuôn mặt sinh viên."""

    def test_register_missing_fields_returns_422(self, client):
        """Thiếu field bắt buộc → 422."""
        response = client.post("/register", json={
            "student_id": "SV001"
            # thiếu name, email, birthday, phone, gender, embedding
        })

        assert response.status_code == 422

    def test_register_invalid_embedding_returns_422(self, client):
        """Embedding không phải list float → 422."""
        response = client.post("/register", json={
            "student_id": "SV001",
            "name": "Test",
            "email": "test@example.com",
            "birthday": "2003-01-01",
            "phone": "0901234567",
            "gender": "Nam",
            "embedding": "not-a-list"
        })

        assert response.status_code == 422

class TestNotFound:
    """Test route không tồn tại."""

    def test_unknown_route_returns_404(self, client):
        """Truy cập route không có → 404."""
        response = client.get("/this-does-not-exist")
        assert response.status_code == 404

    def test_wrong_method_returns_405(self, client):
        """Gọi sai HTTP method → 405."""
        response = client.delete("/health")  # health chỉ có GET
        assert response.status_code == 405
