import pytest
import numpy as np
import json
from unittest.mock import patch, MagicMock

with patch("API.services.recognition.FaceAttendanceDB", MagicMock()):
    from API.services.recognition import to_vector


class TestToVectorWithNone:
    """Test khi input là None."""

    def test_none_returns_zero_vector(self):
        """None → vector 512 chiều toàn số 0."""
        result = to_vector(None)
        assert isinstance(result, np.ndarray)
        assert result.shape == (512,)
        assert np.all(result == 0)

    def test_none_returns_float32(self):
        """Kiểu dữ liệu phải là float32."""
        result = to_vector(None)
        assert result.dtype == np.float32


class TestToVectorWithJsonString:
    """Test khi input là JSON string (chuỗi ký tự chứa mảng số)."""

    def test_json_string_parsed_correctly(self):
        """Chuỗi JSON '[0.1, 0.2, 0.3]' → numpy array."""
        input_str = json.dumps([0.1, 0.2, 0.3])
        result = to_vector(input_str)

        assert isinstance(result, np.ndarray)
        assert len(result) == 3

    def test_json_string_is_normalized(self):
        """Vector sau khi parse JSON phải được normalize (norm ≈ 1)."""
        input_str = json.dumps([3.0, 4.0]) 
        result = to_vector(input_str)

        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5


class TestToVectorWithList:
    """Test khi input là list Python."""

    def test_list_converted_to_numpy(self):
        """List thường → numpy array."""
        result = to_vector([1.0, 2.0, 3.0])
        assert isinstance(result, np.ndarray)
        assert len(result) == 3

    def test_list_is_normalized(self):
        """Vector phải được normalize."""
        result = to_vector([3.0, 4.0]) 
        # Sau normalize: [3/5, 4/5] = [0.6, 0.8]
        expected = np.array([0.6, 0.8], dtype=np.float32)
        np.testing.assert_allclose(result, expected, atol=1e-5)

    def test_512_dim_embedding(self):
        """Test với vector 512 chiều (kích thước thật của ArcFace embedding)."""
        input_vec = [float(i) for i in range(512)]
        result = to_vector(input_vec)

        assert result.shape == (512,)
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5


class TestToVectorNormalization:
    """Test chi tiết logic normalize."""

    def test_already_normalized_vector(self):
        """Vector đã có norm = 1 → giữ nguyên hướng."""
        result = to_vector([1.0, 0.0, 0.0])
        expected = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        np.testing.assert_allclose(result, expected, atol=1e-5)

    def test_zero_vector_not_divided(self):
        """Vector toàn 0, không chia (tránh chia cho 0)."""
        result = to_vector([0.0, 0.0, 0.0])
        expected = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        np.testing.assert_array_equal(result, expected)

    def test_negative_values_preserved_direction(self):
        """Vector có giá trị âm → normalize giữ đúng hướng."""
        result = to_vector([-3.0, 4.0])
        # norm = 5, kết quả = [-0.6, 0.8]
        assert result[0] < 0
        assert result[1] > 0
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5

    def test_very_small_values(self):
        """Giá trị rất nhỏ → vẫn normalize được."""
        result = to_vector([1e-10, 1e-10])
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5


class TestToVectorOutputShape:
    """Test output luôn là 1-D array (reshape(-1))."""

    def test_1d_input_stays_1d(self):
        """Input 1D → output 1D."""
        result = to_vector([1.0, 2.0])
        assert result.ndim == 1

    def test_output_is_flat(self):
        """Output luôn phẳng (1 chiều), dù input có shape khác."""
        input_2d = np.array([[1.0, 2.0, 3.0]])  # shape (1, 3)
        result = to_vector(input_2d)
        assert result.ndim == 1
        assert result.shape == (3,)
