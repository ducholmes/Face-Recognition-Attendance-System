import pytest
from datetime import date
from pydantic import ValidationError

from API.models.auth_models import (
    RegisterRequest as AuthRegisterRequest,
    LoginRequest,
    RefreshRequest,
    UpdateRoleRequest,
    UserInfo,
    RegisterResponse,
    ErrorResponse,
)
from API.models.register_model import RegisterRequest as StudentRegisterRequest
from API.models.recognize_model import RecognizeRequest
from API.models.update_student_model import UpdateStudentRequest

class TestAuthRegisterRequest:
    """Test model đăng ký tài khoản (email, password, role)."""

    def test_valid_register(self):
        """Dữ liệu hợp lệ → tạo thành công."""
        req = AuthRegisterRequest(
            email="student@example.com",
            password="securepass123",
            role="student"
        )
        assert req.email == "student@example.com"
        assert req.password == "securepass123"
        assert req.role == "student"

    def test_all_valid_roles(self):
        """Cả 3 role đều hợp lệ: admin, teacher, student."""
        for role in ["admin", "teacher", "student"]:
            req = AuthRegisterRequest(
                email="test@example.com",
                password="securepass123",
                role=role
            )
            assert req.role == role

    def test_invalid_role_rejected(self):
        """Role không nằm trong danh sách → bị reject."""
        with pytest.raises(ValidationError) as exc_info:
            AuthRegisterRequest(
                email="test@example.com",
                password="securepass123",
                role="hacker"
            )
        # Kiểm tra lỗi liên quan đến field 'role'
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("role",) for e in errors)

    def test_invalid_email_rejected(self):
        """Email sai format → bị reject."""
        with pytest.raises(ValidationError) as exc_info:
            AuthRegisterRequest(
                email="not-an-email",
                password="securepass123",
                role="student"
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("email",) for e in errors)

    def test_empty_email_rejected(self):
        """Email rỗng → bị reject."""
        with pytest.raises(ValidationError):
            AuthRegisterRequest(
                email="",
                password="securepass123",
                role="student"
            )

    def test_password_too_short_rejected(self):
        """Password < 8 ký tự → bị reject (min_length=8)."""
        with pytest.raises(ValidationError) as exc_info:
            AuthRegisterRequest(
                email="test@example.com",
                password="short",
                role="student"
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors)

    def test_password_exactly_8_chars(self):
        """Password đúng 8 ký tự → chấp nhận."""
        req = AuthRegisterRequest(
            email="test@example.com",
            password="12345678",
            role="student"
        )
        assert req.password == "12345678"

    def test_missing_email_rejected(self):
        """Thiếu email → bị reject."""
        with pytest.raises(ValidationError):
            AuthRegisterRequest(
                password="securepass123",
                role="student"
            )

    def test_missing_password_rejected(self):
        """Thiếu password → bị reject."""
        with pytest.raises(ValidationError):
            AuthRegisterRequest(
                email="test@example.com",
                role="student"
            )

    def test_missing_role_rejected(self):
        """Thiếu role → bị reject."""
        with pytest.raises(ValidationError):
            AuthRegisterRequest(
                email="test@example.com",
                password="securepass123"
            )

class TestLoginRequest:
    """Test model đăng nhập."""

    def test_valid_login(self):
        """Dữ liệu hợp lệ → tạo thành công."""
        req = LoginRequest(
            email="user@example.com",
            password="mypassword"
        )
        assert req.email == "user@example.com"
        assert req.password == "mypassword"

    def test_invalid_email_rejected(self):
        """Email sai format → bị reject."""
        with pytest.raises(ValidationError):
            LoginRequest(
                email="invalid",
                password="mypassword"
            )

    def test_missing_password_rejected(self):
        """Thiếu password → bị reject."""
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com")

class TestRefreshRequest:
    """Test model refresh token."""

    def test_valid_refresh(self):
        req = RefreshRequest(refresh_token="some-token-string")
        assert req.refresh_token == "some-token-string"

    def test_missing_token_rejected(self):
        with pytest.raises(ValidationError):
            RefreshRequest()


class TestUpdateRoleRequest:
    """Test model cập nhật role."""

    def test_valid_update_role(self):
        req = UpdateRoleRequest(user_id="user-123", new_role="admin")
        assert req.user_id == "user-123"
        assert req.new_role == "admin"

    def test_invalid_new_role_rejected(self):
        """Role không hợp lệ → bị reject."""
        with pytest.raises(ValidationError):
            UpdateRoleRequest(user_id="user-123", new_role="superadmin")

class TestResponseModels:
    """Test các model response."""

    def test_user_info(self):
        user = UserInfo(id="u1", email="a@b.com", role="student")
        assert user.id == "u1"

    def test_register_response(self):
        resp = RegisterResponse(
            success=True,
            message="OK",
            user=UserInfo(id="u1", email="a@b.com", role="student")
        )
        assert resp.success is True
        assert resp.user.email == "a@b.com"

    def test_error_response_defaults(self):
        """ErrorResponse có success mặc định là False."""
        err = ErrorResponse(error="Something went wrong")
        assert err.success is False
        assert err.detail is None
        assert err.error_code is None

class TestStudentRegisterRequest:
    """Test model đăng ký sinh viên."""

    def test_valid_student_register(self):
        """Dữ liệu hợp lệ → tạo thành công."""
        req = StudentRegisterRequest(
            student_id="SV001",
            name="Nguyễn Văn A",
            email="sv001@student.edu",
            birthday=date(2003, 5, 15),
            phone="0901234567",
            gender="Nam",
            embedding=[0.1] * 512
        )
        assert req.student_id == "SV001"
        assert req.name == "Nguyễn Văn A"
        assert req.birthday == date(2003, 5, 15)
        assert len(req.embedding) == 512

    def test_missing_student_id_rejected(self):
        """Thiếu student_id → bị reject."""
        with pytest.raises(ValidationError):
            StudentRegisterRequest(
                name="Nguyễn Văn A",
                email="sv@student.edu",
                birthday=date(2003, 5, 15),
                phone="0901234567",
                gender="Nam",
                embedding=[0.1] * 512
            )

    def test_missing_embedding_rejected(self):
        """Thiếu embedding → bị reject."""
        with pytest.raises(ValidationError):
            StudentRegisterRequest(
                student_id="SV001",
                name="Nguyễn Văn A",
                email="sv@student.edu",
                birthday=date(2003, 5, 15),
                phone="0901234567",
                gender="Nam"
            )

    def test_invalid_birthday_format_rejected(self):
        """Birthday sai format → bị reject."""
        with pytest.raises(ValidationError):
            StudentRegisterRequest(
                student_id="SV001",
                name="Nguyễn Văn A",
                email="sv@student.edu",
                birthday="not-a-date",
                phone="0901234567",
                gender="Nam",
                embedding=[0.1] * 512
            )

    def test_embedding_must_be_list_of_float(self):
        """Embedding phải là list số thực."""
        with pytest.raises(ValidationError):
            StudentRegisterRequest(
                student_id="SV001",
                name="Test",
                email="sv@student.edu",
                birthday=date(2003, 1, 1),
                phone="0901234567",
                gender="Nam",
                embedding=["not", "a", "number"]
            )

    def test_email_not_validated_as_email(self):
        """
        email field chỉ là str, không validate format.
        """
        req = StudentRegisterRequest(
            student_id="SV001",
            name="Test",
            email="this-is-not-an-email",
            birthday=date(2003, 1, 1),
            phone="0901234567",
            gender="Nam",
            embedding=[0.1] * 512
        )
        # Vẫn chấp nhận vì email chỉ là str
        assert req.email == "this-is-not-an-email"


class TestRecognizeRequest:
    """Test model nhận diện khuôn mặt."""

    def test_valid_recognize(self):
        req = RecognizeRequest(embedding=[0.1, 0.2, 0.3])
        assert len(req.embedding) == 3

    def test_empty_embedding_accepted(self):
        """List rỗng vẫn hợp lệ về mặt Pydantic (không có min length)."""
        req = RecognizeRequest(embedding=[])
        assert req.embedding == []

    def test_missing_embedding_rejected(self):
        with pytest.raises(ValidationError):
            RecognizeRequest()

class TestUpdateStudentRequest:
    """Test model cập nhật thông tin sinh viên."""

    def test_update_all_fields(self):
        req = UpdateStudentRequest(
            name="Tên Mới",
            phone="0909999999",
            gender="Nữ",
            birthday="2003-05-15"
        )
        assert req.name == "Tên Mới"
        assert req.phone == "0909999999"

    def test_update_partial_fields(self):
        """Chỉ cập nhật 1 field, còn lại None."""
        req = UpdateStudentRequest(name="Tên Mới")
        assert req.name == "Tên Mới"
        assert req.phone is None
        assert req.gender is None
        assert req.birthday is None

    def test_update_no_fields(self):
        """Không truyền gì cũng hợp lệ (tất cả Optional)."""
        req = UpdateStudentRequest()
        assert req.name is None
        assert req.phone is None
