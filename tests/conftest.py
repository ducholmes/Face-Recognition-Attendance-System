"""
Conftest - Cấu hình chung cho toàn bộ test suite.
File này tự động được pytest load trước khi chạy bất kỳ test nào.
"""
import sys
import os

# Thêm root project vào sys.path để import được các module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
