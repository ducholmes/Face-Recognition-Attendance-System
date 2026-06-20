import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from API.services.recognition import recognize_face, to_vector
from API.db.config_manager import config_manager
import API.services.recognition as recognition_module

mock_db_instance = MagicMock()

@pytest.fixture(autouse=True)
def patch_db():
    """Ghi đè trực tiếp biến db trong module recognition bằng mock_db_instance."""
    original_db = recognition_module.db
    recognition_module.db = mock_db_instance
    mock_db_instance.reset_mock()
    yield
    recognition_module.db = original_db


class TestRecognizeFaceThreshold:
    """Test ngưỡng nhận diện (RECOGNITION_THRESHOLD = 0.80)."""

    def test_threshold_value(self):
        """Xác nhận RECOGNITION_THRESHOLD = 0.80."""
        assert config_manager.get('RECOGNITION_THRESHOLD') == 0.80

    def test_score_below_threshold_recognized(self):
        """
        Score = 0.15 (< 0.5) → nhận diện THÀNH CÔNG.
        Score thấp = vector rất giống nhau = đúng người.
        """
        # Mock Pinecone trả về 1 match với score thấp
        fake_match = MagicMock()
        fake_match.score = 0.15
        fake_match.metadata = {"student_id": "SV001"}

        fake_query_result = MagicMock()
        fake_query_result.matches = [fake_match]

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        # Mock Supabase trả về thông tin sinh viên
        fake_student_response = MagicMock()
        fake_student_response.data = [{"student_id": "SV001", "name": "Nguyễn Văn A"}]

        mock_db_instance.supabase.table.return_value \
            .select.return_value \
            .eq.return_value \
            .execute.return_value = fake_student_response

        # Gọi hàm
        result = recognize_face([0.1] * 512)

        assert result["recognized"] is True
        assert result["student_id"] == "SV001"
        assert result["name"] == "Nguyễn Văn A"
        assert result["similarity"] == 0.15

    def test_score_above_threshold_not_recognized(self):
        """
        Score = 0.85 (> 0.80) → KHÔNG nhận diện được.
        Score cao = vector khác nhau = không phải người đã đăng ký.
        """
        fake_match = MagicMock()
        fake_match.score = 0.85
        fake_match.metadata = {"student_id": "SV001"}

        fake_query_result = MagicMock()
        fake_query_result.matches = [fake_match]

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        result = recognize_face([0.1] * 512)

        assert result["recognized"] is False
        assert result["similarity"] == 0.85

    def test_score_exactly_at_threshold(self):
        """
        Score = 0.80 (= RECOGNITION_THRESHOLD) → KHÔNG nhận diện (vì điều kiện là >).
        Code: if score > RECOGNITION_THRESHOLD → False. Vậy score = 0.80 thì KHÔNG vào if.
        → Tức score = 0.80 vẫn được nhận diện!
        """
        fake_match = MagicMock()
        fake_match.score = 0.80
        fake_match.metadata = {"student_id": "SV001"}

        fake_query_result = MagicMock()
        fake_query_result.matches = [fake_match]

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        # Mock Supabase
        fake_student_response = MagicMock()
        fake_student_response.data = [{"student_id": "SV001", "name": "Test"}]

        mock_db_instance.supabase.table.return_value \
            .select.return_value \
            .eq.return_value \
            .execute.return_value = fake_student_response

        result = recognize_face([0.1] * 512)

        # score = 0.5, điều kiện > 0.5 là False → đi tiếp → recognized = True
        assert result["recognized"] is True


class TestRecognizeFaceNoMatches:
    """Test khi Pinecone không tìm thấy match nào."""

    def test_empty_matches_not_recognized(self):
        """Không có match → recognized = False."""
        fake_query_result = MagicMock()
        fake_query_result.matches = []

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        result = recognize_face([0.1] * 512)

        assert result["recognized"] is False


class TestRecognizeFaceMultipleMatches:
    """Test khi Pinecone trả về nhiều matches (top_k=3)."""

    def test_picks_best_match_lowest_score(self):
        """
        Có 3 matches với score khác nhau → chọn match có score THẤP NHẤT.
        Code dùng: best = min(matches, key=lambda x: x.score)
        """
        match1 = MagicMock()
        match1.score = 0.3
        match1.metadata = {"student_id": "SV001"}

        match2 = MagicMock()
        match2.score = 0.1  # ← Thấp nhất = giống nhất
        match2.metadata = {"student_id": "SV002"}

        match3 = MagicMock()
        match3.score = 0.4
        match3.metadata = {"student_id": "SV003"}

        fake_query_result = MagicMock()
        fake_query_result.matches = [match1, match2, match3]

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        # Mock Supabase trả về SV002
        fake_student_response = MagicMock()
        fake_student_response.data = [{"student_id": "SV002", "name": "Trần Thị B"}]

        mock_db_instance.supabase.table.return_value \
            .select.return_value \
            .eq.return_value \
            .execute.return_value = fake_student_response

        result = recognize_face([0.1] * 512)

        assert result["recognized"] is True
        assert result["student_id"] == "SV002"
        assert result["name"] == "Trần Thị B"
        assert result["similarity"] == 0.1


class TestRecognizeFaceEdgeCases:
    """Test các trường hợp đặc biệt."""

    def test_missing_student_id_in_metadata(self):
        """
        Pinecone trả về match nhưng metadata KHÔNG CÓ student_id.
        → recognized = False, có error message.
        """
        fake_match = MagicMock()
        fake_match.score = 0.1
        fake_match.metadata = {}  # ← Thiếu student_id!

        fake_query_result = MagicMock()
        fake_query_result.matches = [fake_match]

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        result = recognize_face([0.1] * 512)

        assert result["recognized"] is False
        assert "missing student_id" in result.get("error", "")

    def test_student_not_found_in_supabase(self):
        """
        Pinecone nhận diện được, nhưng Supabase KHÔNG TÌM THẤY sinh viên.
        → recognized = True, name = None.
        """
        fake_match = MagicMock()
        fake_match.score = 0.1
        fake_match.metadata = {"student_id": "SV_DELETED"}

        fake_query_result = MagicMock()
        fake_query_result.matches = [fake_match]

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        # Supabase trả về rỗng — sinh viên đã bị xóa khỏi DB
        fake_student_response = MagicMock()
        fake_student_response.data = []

        mock_db_instance.supabase.table.return_value \
            .select.return_value \
            .eq.return_value \
            .execute.return_value = fake_student_response

        result = recognize_face([0.1] * 512)

        assert result["recognized"] is True
        assert result["student_id"] == "SV_DELETED"
        assert result["name"] is None  # ← student not found

    def test_pinecone_query_uses_correct_params(self):
        """Kiểm tra query gọi đúng tham số: top_k=3, include_metadata=True."""
        fake_query_result = MagicMock()
        fake_query_result.matches = []

        mock_db_instance.index.query.return_value = fake_query_result
        mock_db_instance.namespace = "test-namespace"

        recognize_face([0.1] * 512)

        # Kiểm tra Pinecone được gọi đúng
        call_kwargs = mock_db_instance.index.query.call_args
        assert call_kwargs.kwargs.get("top_k") == 3 or call_kwargs[1].get("top_k") == 3
        assert call_kwargs.kwargs.get("include_metadata") is True or call_kwargs[1].get("include_metadata") is True
