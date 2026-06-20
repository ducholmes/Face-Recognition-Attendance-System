import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime

mock_supabase = MagicMock()
mock_pinecone_index = MagicMock()


def _load_real_class():
    """Load FaceAttendanceDB trực tiếp từ source file, bỏ qua sys.modules.

    test_api_endpoints.py dùng patch().start() không stop(),
    thay FaceAttendanceDB = MagicMock vĩnh viễn trong sys.modules.
    Cách duy nhất lấy class thật: load lại từ file gốc.
    """
    import importlib.util
    import os

    src = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "API", "db", "database_module.py",
    )

    with patch("supabase.create_client", return_value=mock_supabase), \
         patch("pinecone.Pinecone") as mock_pc:
        mock_pc.return_value.Index.return_value = mock_pinecone_index

        spec = importlib.util.spec_from_file_location("_db_fresh", src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    return mod.FaceAttendanceDB, mod


_RealFaceAttendanceDB, _fresh_mod = _load_real_class()


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset tất cả mock trước mỗi test."""
    mock_supabase.reset_mock()
    mock_pinecone_index.reset_mock()
    yield


@pytest.fixture
def db():
    """Tạo instance FaceAttendanceDB với mock DB."""
    with patch.object(_fresh_mod, "create_client", return_value=mock_supabase), \
         patch.object(_fresh_mod, "Pinecone") as mock_pc:
        mock_pc.return_value.Index.return_value = mock_pinecone_index
        instance = _RealFaceAttendanceDB()

    instance.supabase = mock_supabase
    instance.index = mock_pinecone_index
    instance.namespace = "test-namespace"
    return instance


class TestRegisterStudent:
    """
    register_student() phải:
    1. Insert vào Supabase table 'students'
    2. Upsert vector vào Pinecone
    3. Trả về True nếu thành công
    """

    def test_register_success(self, db):
        """Đăng ký thành công → True."""
        mock_supabase.table.return_value \
            .insert.return_value \
            .execute.return_value.data = [{"student_id": "SV001"}]

        result = db.register_student(
            student_id="SV001",
            name="Nguyễn Văn A",
            email="sv001@student.edu",
            birthday="2003-05-15",
            phone="0901234567",
            gender="Nam",
            face_vector=np.random.rand(512).astype("float32"),
        )

        assert result is True

    def test_register_inserts_to_supabase(self, db):
        """Kiểm tra có gọi Supabase insert đúng table."""
        mock_supabase.table.return_value \
            .insert.return_value \
            .execute.return_value.data = [{}]

        db.register_student(
            student_id="SV001",
            name="Test",
            email="test@test.com",
            birthday="2003-01-01",
            phone="0900000000",
            gender="Nam",
            face_vector=[0.1] * 512,
        )

        # Kiểm tra gọi supabase.table("students")
        mock_supabase.table.assert_called_with("students")

    def test_register_upserts_to_pinecone(self, db):
        """Kiểm tra có gọi Pinecone upsert."""
        mock_supabase.table.return_value \
            .insert.return_value \
            .execute.return_value.data = [{}]

        db.register_student(
            student_id="SV001",
            name="Test",
            email="test@test.com",
            birthday="2003-01-01",
            phone="0900000000",
            gender="Nam",
            face_vector=[0.1] * 512,
        )

        # Kiểm tra Pinecone upsert được gọi
        mock_pinecone_index.upsert.assert_called_once()

        # Kiểm tra upsert đúng namespace
        call_kwargs = mock_pinecone_index.upsert.call_args
        assert call_kwargs.kwargs.get("namespace") == "test-namespace" or \
               call_kwargs[1].get("namespace") == "test-namespace"

    def test_register_with_numpy_vector(self, db):
        """Truyền numpy array → tự convert sang list."""
        mock_supabase.table.return_value \
            .insert.return_value \
            .execute.return_value.data = [{}]

        vector = np.random.rand(512).astype("float32")
        result = db.register_student(
            student_id="SV001",
            name="Test",
            email="test@test.com",
            birthday="2003-01-01",
            phone="0900000000",
            gender="Nam",
            face_vector=vector,  # numpy array, không phải list
        )

        assert result is True

    def test_register_failure_returns_false(self, db):
        """Supabase lỗi → trả về False."""
        mock_supabase.table.return_value \
            .insert.return_value \
            .execute.side_effect = Exception("Duplicate key")

        result = db.register_student(
            student_id="SV001",
            name="Test",
            email="test@test.com",
            birthday="2003-01-01",
            phone="0900000000",
            gender="Nam",
            face_vector=[0.1] * 512,
        )

        assert result is False

class TestDeleteStudent:
    """
    delete_student() phải:
    1. Xóa vector khỏi Pinecone
    2. Xóa row khỏi Supabase table 'students'
    3. Trả về True nếu thành công
    """

    def test_delete_success(self, db):
        """Xóa thành công → True."""
        mock_supabase.table.return_value \
            .delete.return_value \
            .eq.return_value \
            .execute.return_value.data = [{"student_id": "SV001"}]

        result = db.delete_student("SV001")

        assert result is True

    def test_delete_calls_pinecone(self, db):
        """Kiểm tra gọi Pinecone delete đúng ID."""
        mock_supabase.table.return_value \
            .delete.return_value \
            .eq.return_value \
            .execute.return_value.data = []

        db.delete_student("SV001")

        mock_pinecone_index.delete.assert_called_once_with(
            ids=["SV001"],
            namespace="test-namespace"
        )

    def test_delete_calls_supabase(self, db):
        """Kiểm tra gọi Supabase delete đúng table và student_id."""
        mock_supabase.table.return_value \
            .delete.return_value \
            .eq.return_value \
            .execute.return_value.data = []

        db.delete_student("SV001")

        mock_supabase.table.assert_called_with("students")

    def test_delete_converts_id_to_string(self, db):
        """student_id truyền vào int → tự convert thành str."""
        mock_supabase.table.return_value \
            .delete.return_value \
            .eq.return_value \
            .execute.return_value.data = []

        db.delete_student(12345)

        # Pinecone phải nhận string, không phải int
        mock_pinecone_index.delete.assert_called_once_with(
            ids=["12345"],
            namespace="test-namespace"
        )

    def test_delete_failure_returns_false(self, db):
        """Lỗi → trả về False."""
        mock_pinecone_index.delete.side_effect = Exception("Network error")

        result = db.delete_student("SV001")

        assert result is False

class TestUpdateStudent:
    """
    update_student() có thể cập nhật:
    - Chỉ tên (Supabase only)
    - Chỉ vector (Pinecone only)
    - Cả hai
    """

    def test_update_name_only(self, db):
        """Chỉ cập nhật tên → gọi Supabase, KHÔNG gọi Pinecone."""
        mock_supabase.table.return_value \
            .update.return_value \
            .eq.return_value \
            .execute.return_value.data = [{"student_id": "SV001", "name": "Tên Mới"}]

        result = db.update_student("SV001", name="Tên Mới")

        assert result is True
        mock_supabase.table.assert_called_with("students")
        # Pinecone KHÔNG được gọi upsert khi chỉ update tên
        mock_pinecone_index.upsert.assert_not_called()

    def test_update_vector_only(self, db):
        """Chỉ cập nhật vector → gọi Pinecone upsert."""
        new_vector = [0.5] * 512

        result = db.update_student("SV001", new_face_vector=new_vector)

        assert result is True
        mock_pinecone_index.upsert.assert_called_once()

    def test_update_vector_is_normalized(self, db):
        """Vector được normalize trước khi upsert vào Pinecone."""
        new_vector = [3.0, 4.0] + [0.0] * 126  # norm = 5

        db.update_student("SV001", new_face_vector=new_vector)

        # Lấy vector đã upsert
        call_args = mock_pinecone_index.upsert.call_args
        upserted_vectors = call_args.kwargs.get("vectors") or call_args[1].get("vectors") or call_args[0][0]

        if isinstance(upserted_vectors, list):
            values = upserted_vectors[0]["values"]
        else:
            values = upserted_vectors

        # Kiểm tra norm ≈ 1
        norm = np.linalg.norm(values)
        assert abs(norm - 1.0) < 1e-4

    def test_update_both_name_and_vector(self, db):
        """Cập nhật cả tên và vector → gọi cả Supabase và Pinecone."""
        mock_supabase.table.return_value \
            .update.return_value \
            .eq.return_value \
            .execute.return_value.data = [{}]

        result = db.update_student(
            "SV001",
            name="Tên Mới",
            new_face_vector=[0.1] * 512
        )

        assert result is True
        mock_supabase.table.assert_called()
        mock_pinecone_index.upsert.assert_called_once()

    def test_update_failure_returns_false(self, db):
        """Lỗi → trả về False."""
        mock_supabase.table.return_value \
            .update.return_value \
            .eq.return_value \
            .execute.side_effect = Exception("DB error")

        result = db.update_student("SV001", name="Fail")

        assert result is False

class TestGetSummaryStats:
    """
    get_summary_stats() trả về dict với 3 key:
    - Tổng số sinh viên
    - Tổng số lượt quét
    - Lượt quét hôm nay
    """

    def test_stats_returns_correct_keys(self, db):
        """Trả về đúng 3 key thống kê."""
        # Mock 3 queries
        mock_studs = MagicMock()
        mock_studs.count = 10

        mock_logs = MagicMock()
        mock_logs.count = 100

        mock_today = MagicMock()
        mock_today.count = 5

        mock_supabase.table.return_value \
            .select.return_value \
            .execute.return_value = mock_studs

        mock_supabase.table.return_value \
            .select.return_value \
            .gte.return_value \
            .lte.return_value \
            .execute.return_value = mock_today

        result = db.get_summary_stats()

        assert "Tổng số sinh viên" in result
        assert "Tổng số lượt quét" in result
        assert "Lượt quét hôm nay" in result

    def test_stats_error_returns_zeros(self, db):
        """Nếu DB lỗi → trả về dict toàn 0."""
        mock_supabase.table.side_effect = Exception("Connection error")

        result = db.get_summary_stats()

        assert result["Tổng số sinh viên"] == 0
        assert result["Tổng số lượt quét"] == 0
        assert result["Lượt quét hôm nay"] == 0
