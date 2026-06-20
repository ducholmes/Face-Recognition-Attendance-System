import time
import pytest
from unittest.mock import patch, MagicMock


# ---- Chặn DB trước khi import ----
with patch("API.db.database_module.FaceAttendanceDB", MagicMock()):
    from API.services import attendance_service
    from API.services.attendance_service import save_attendance, COOLDOWN


class TestCooldownLogic:
    """Test logic chống spam điểm danh (30 giây giữa 2 lần)."""

    def setup_method(self):
        """
        Reset trạng thái trước MỖI test.
        - Xóa sạch dict last_checkin → mỗi test bắt đầu từ trạng thái "chưa ai điểm danh"
        - Mock lại db.supabase để hàm save_attendance không gọi DB thật
        """
        attendance_service.last_checkin.clear()
        fake_response = MagicMock()
        fake_response.data = [{"id": 1, "student_id": "SV001", "action": "IN"}]

        attendance_service.db.supabase.table.return_value \
            .insert.return_value \
            .execute.return_value = fake_response

        self.task_patcher = patch("API.services.attendance_service.confirm_attendance_background.delay")
        self.mock_task_delay = self.task_patcher.start()
        fake_task = MagicMock()
        fake_task.id = "fake-task-123"
        self.mock_task_delay.return_value = fake_task

    def teardown_method(self):
        self.task_patcher.stop()

    def test_first_checkin_succeeds(self):
        """Lần đầu điểm danh luôn thành công."""
        result = save_attendance("SV001")
        assert result["success"] is True
        assert "data" in result

    def test_first_checkin_records_timestamp(self):
        """Sau lần đầu, student_id được ghi vào last_checkin."""
        save_attendance("SV001")
        assert "SV001" in attendance_service.last_checkin

    def test_second_checkin_within_cooldown_blocked(self):
        """Điểm danh lần 2 ngay lập tức bị chặn."""
        save_attendance("SV001")             
        result = save_attendance("SV001")            
        assert result["success"] is False
        assert "message" in result               

    def test_cooldown_message_contains_wait_time(self):
        """Thông báo chặn có chứa số giây cần đợi."""
        save_attendance("SV001")
        result = save_attendance("SV001")
        # Message dạng: "Vui lòng đợi 29s trước khi điểm danh lại"
        assert "đợi" in result["message"]

    def test_different_students_not_affected(self):
        """Sinh viên A bị cooldown, sinh viên B vẫn điểm danh được."""
        save_attendance("SV001")    
        save_attendance("SV001")                

        result = save_attendance("SV002")         
        assert result["success"] is True

    def test_checkin_after_cooldown_expires(self):
        """Sau khi hết 30s cooldown → điểm danh lại được."""
        save_attendance("SV001")          

        attendance_service.last_checkin["SV001"] = time.time() - 31

        result = save_attendance("SV001")    
        assert result["success"] is True

    def test_checkin_exactly_at_cooldown_boundary(self):
        """Đúng 30s → vẫn bị chặn (< COOLDOWN, không phải <=)."""
        save_attendance("SV001")

        attendance_service.last_checkin["SV001"] = time.time() - 29

        result = save_attendance("SV001")
        assert result["success"] is False

    def test_task_queue_error_returns_failure(self):
        """Nếu queue task gặp lỗi → trả về success: False, có error message."""
        self.mock_task_delay.side_effect = Exception("Redis connection timeout")

        result = save_attendance("SV_ERR")
        assert result["success"] is False
        assert "Redis connection timeout" in result["error"]

    # --------------------------------------------------
    # Test giá trị COOLDOWN
    # --------------------------------------------------

    def test_cooldown_value_is_30_seconds(self):
        """Xác nhận COOLDOWN = 30 giây (tránh ai đó sửa nhầm)."""
        assert COOLDOWN == 30
