import os
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from config import MIN_FACE_SIZE, IOU_THRESHOLD, RECOGNITION_THRESHOLD

class SystemConfigManager:
    _instance = None
    _cache = {}
    
    # Sử dụng fallback trong trường hợp kết nối tới supabase thất bại
    _fallback = {
        'MIN_FACE_SIZE': MIN_FACE_SIZE,
        'IOU_THRESHOLD': IOU_THRESHOLD,
        'RECOGNITION_THRESHOLD': RECOGNITION_THRESHOLD
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemConfigManager, cls).__new__(cls)
            cls._instance.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            cls._instance._cache = {}
            cls._instance.load_all_configs()
        return cls._instance

    def load_all_configs(self):
        """Kéo toàn bộ cấu hình từ Database lên RAM"""
        try:
            response = self.supabase.table('system_configs').select('*').execute()
            if response.data:
                for row in response.data:
                    self._cache[row['key']] = self._parse_value(row['value'], row['data_type'])
                print(" Đã tải thành công Cấu hình hệ thống từ Supabase.")
            else:
                print(" Bảng system_configs trống. Sử dụng cấu hình mặc định (Fallback).")
        except Exception as e:
            print(f" Lỗi khi tải cấu hình từ Supabase: {e}. Đang dùng cấu hình mặc định (Fallback).")

    def _parse_value(self, value, data_type):
        """Ép kiểu dữ liệu an toàn"""
        try:
            if data_type == 'int':
                return int(value)
            elif data_type == 'float':
                return float(value)
            elif data_type == 'boolean':
                return str(value).lower() in ('true', '1', 't', 'y', 'yes')
            return str(value)
        except ValueError:
            return value

    def get(self, key):
        """Lấy giá trị cấu hình (Ưu tiên Cache)"""
        if key in self._cache:
            return self._cache[key]
        elif key in self._fallback:
            return self._fallback[key]
        return None
        
    def get_all(self):
        """Trả về toàn bộ cấu hình hiện tại"""
        # Trả về kết hợp giữa cache và fallback (cache đè fallback)
        result = self._fallback.copy()
        result.update(self._cache)
        return result

    def update_config(self, key, value, data_type=None):
        """Lưu cấu hình mới vào Database và Cập nhật Cache"""
        # Nếu data_type không được cung cấp, cố gắng suy luận từ giá trị hiện tại
        if not data_type:
            try:
                # Kiểm tra type trong Database trước
                res = self.supabase.table('system_configs').select('data_type').eq('key', key).execute()
                if res.data:
                    data_type = res.data[0]['data_type']
                else:
                    data_type = 'string'
            except:
                data_type = 'string'

        str_value = str(value)
        
        try:
            self.supabase.table('system_configs').upsert({
                'key': key,
                'value': str_value,
                'data_type': data_type
            }).execute()
            
            # Cập nhật cache
            self._cache[key] = self._parse_value(str_value, data_type)
            return True, f"Cập nhật thành công {key}"
        except Exception as e:
            return False, f"Lỗi lưu DB: {str(e)}"

config_manager = SystemConfigManager()
