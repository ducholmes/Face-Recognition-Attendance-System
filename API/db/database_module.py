import os
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import pytz
from supabase import create_client, Client
from pinecone import Pinecone
from config import upload_dir, SUPABASE_URL, SUPABASE_KEY, PINECONE_KEY, PINECONE_INDEX, PINECONE_NAMESPACE
from API.db.config_manager import config_manager

class FaceAttendanceDB:
    def __init__(self):
        
        # 1. Kết nối Supabase
        url = SUPABASE_URL
        key = SUPABASE_KEY
        
        # DEBUG: Log connection details
        print(f"Supabase URL: {url}")
        key_prefix = key[:15] if key and len(key) > 15 else key
        print(f"Supabase Key prefix: {key_prefix}...")
        print(f"Key type: {'service_role' if key and key.startswith('eyJ') else 'anon/other' if key else 'MISSING'}")
        
        self.supabase: Client = create_client(url, key)
        
        # 2. Kết nối Pinecone
        pc = Pinecone(api_key=PINECONE_KEY)
        self.index = pc.Index(PINECONE_INDEX)
        self.namespace = PINECONE_NAMESPACE
        
        # Cấu hình phụ
        self.vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        print(f" Hệ thống sẵn sàng (Namespace: {self.namespace})")

    def register_student(self, student_id, name, email, birthday, phone, gender, face_vector):
        try:
            if isinstance(face_vector, np.ndarray):
                vector_list = face_vector.tolist()
            else:
                vector_list = face_vector
            
            # Convert birthday to string for JSON serialization
            birthday_str = str(birthday) if birthday else None

            # 1. Supabase
            self.supabase.table("students").insert({
                "student_id": str(student_id),
                "name": name,
                "email": email,
                "birthday": birthday_str,
                "phone": phone,
                "gender": gender
            }).execute()

            # 2. Pinecone
            self.index.upsert(
                vectors=[
                    {
                        "id": str(student_id),
                        "values": vector_list,
                        "metadata": {
                            "student_id": str(student_id),
                            "name": name,
                            "birthday": birthday_str,
                            "phone": phone,
                            "gender": gender
                        }
                    }
                ],
                namespace=self.namespace
            )

            print(f"Đăng ký thành công: {name}")
            return True

        except Exception as e:
            print(f"Lỗi đăng ký: {e}")
            return False

    def process_attendance(self, action, face_vector, frame):
        try:
            if isinstance(face_vector, np.ndarray):
                vector_list = face_vector.tolist()
            else:
                vector_list = face_vector

            # 1. Nhận diện trên Pinecone
            results = self.index.query(vector=vector_list, top_k=1, namespace=self.namespace)
            if not results['matches']: return " Dữ liệu trống"

            match = results['matches'][0]
            student_id = match['id']
            score = match['score']
            
            current_threshold = config_manager.get('RECOGNITION_THRESHOLD')

            if score <= current_threshold:
                # 2. Tạo tên file ảnh duy nhất
                timestamp = datetime.now(self.vn_tz).strftime("%Y%m%d_%H%M%S")
                file_name = f"{student_id}_{timestamp}.jpg"

                # 3. Ghi Nhật ký vào SQL
                self.supabase.table('attendance_logs').insert({
                    "student_id": student_id,
                    "action": action,
                    "image_path": file_name
                }).execute()

                # 4. Upload ảnh lên Object Storage
                _, img_encoded = cv2.imencode('.jpg', frame)
                self.supabase.storage.from_(upload_dir).upload(
                    path=file_name,
                    file=img_encoded.tobytes(),
                    file_options={"content-type": "image/jpeg"}
                )

                # Lấy tên SV để phản hồi
                res = self.supabase.table('students').select('name').eq('student_id', student_id).execute()
                name = res.data[0]['name'] if res.data else "Unknown"
                return f" {action}: {name} ({score:.4f})"
            else:
                return f" Tôi chưa thấy người này bao giờ ({score:.4f})"
                
        except Exception as e:
            return f" Lỗi: {e}"

    def get_report(self):
        """Xuất báo cáo có đầy đủ thông tin và link ảnh"""
        try:
            logs = self.supabase.table('attendance_logs').select('*').execute()
            studs = self.supabase.table('students').select('student_id, name').execute()
            if not logs.data: return pd.DataFrame()

            df = pd.merge(pd.DataFrame(logs.data), pd.DataFrame(studs.data), on='student_id', how='left')
            
            # Ép giờ Việt Nam
            df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Ho_Chi_Minh').dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Sắp xếp theo thời gian mới nhất
            df = df.sort_values(by='created_at', ascending=False)
            
            return df[['student_id', 'name', 'action', 'created_at', 'image_path']]
        except Exception as e:
            print(f" Lỗi báo cáo: {e}")
            return pd.DataFrame()
    
    def get_summary_stats(self):
        """Thống kê tổng quan cho màn hình Dashboard"""
        try:
            # 1. Đếm tổng số sinh viên đã đăng ký
            res_studs = self.supabase.table('students').select('student_id', count='exact').execute()
            total_students = res_studs.count if res_studs.count else 0

            # 2. Đếm tổng số lượt điểm danh (Toàn thời gian)
            res_logs = self.supabase.table('attendance_logs').select('id', count='exact').execute()
            total_logs = res_logs.count if res_logs.count else 0

            # 3. Đếm số lượt điểm danh trong ngày hôm nay
            today_str = datetime.now(self.vn_tz).strftime('%Y-%m-%d')
            # Lọc từ 00:00:00 đến 23:59:59 của ngày hôm nay
            res_today = self.supabase.table('attendance_logs').select('id', count='exact') \
                            .gte('created_at', f"{today_str}T00:00:00+07:00") \
                            .lte('created_at', f"{today_str}T23:59:59+07:00").execute()
            today_logs = res_today.count if res_today.count else 0

            return {
                "Tổng số sinh viên": total_students,
                "Tổng số lượt quét": total_logs,
                "Lượt quét hôm nay": today_logs
            }
        except Exception as e:
            print(f" Lỗi thống kê: {e}")
            return {"Tổng số sinh viên": 0, "Tổng số lượt quét": 0, "Lượt quét hôm nay": 0}

    def get_students_in_class(self):
        """
        Tìm ra những ai có trạng thái điểm danh cuối cùng là 'IN' trong ngày hôm nay.
        """
        try:
            today_str = datetime.now(self.vn_tz).strftime('%Y-%m-%d')
            
            res = self.supabase.table('attendance_logs') \
                .select('student_id, students(name), action, created_at') \
                .gte('created_at', f"{today_str}T00:00:00+07:00") \
                .lte('created_at', f"{today_str}T23:59:59+07:00") \
                .order('created_at', desc=True).execute()

            if not res.data:
                return pd.DataFrame()

            df = pd.DataFrame(res.data)
            df['Mã SV'] = df['student_id']
            df['Họ Tên'] = df['students'].apply(lambda x: x['name'] if isinstance(x, dict) else 'Unknown')
            df['Hành Động'] = df['action']
            df['Thời Gian'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Ho_Chi_Minh').dt.strftime('%H:%M:%S')

            df_latest = df.drop_duplicates(subset=['Mã SV'], keep='first')
            df_in_class = df_latest[df_latest['Hành Động'] == 'IN']

            return df_in_class[['Mã SV', 'Họ Tên', 'Thời Gian']]
            
        except Exception as e:
            print(f" Lỗi khi lọc sinh viên trong lớp: {e}")
            return pd.DataFrame()

    def delete_student(self, student_id):
        try:
            student_id = str(student_id)

            # 1. Xóa vector trên Pinecone
            self.index.delete(
                ids=[student_id],
                namespace=self.namespace
            )

            # 2. Xóa dữ liệu trên Supabase
            self.supabase.table('students') \
                .delete() \
                .eq('student_id', student_id) \
                .execute()

            print(f"Đã cho sinh viên {student_id} bay màu")
            return True

        except Exception as e:
            print(f"Lỗi delete: {e}")
            return False

    def update_student(self, student_id, name=None, new_face_vector=None):
        try:
            student_id = str(student_id)

            # 1. UPDATE TEXT (Supabase)
            updates = {}

            if name is not None:
                updates["name"] = name

            if updates:
                self.supabase.table('students') \
                    .update(updates) \
                    .eq('student_id', student_id) \
                    .execute()

            # 2. UPDATE VECTOR (Pinecone)
            if new_face_vector is not None:

                if isinstance(new_face_vector, np.ndarray):
                    vector_list = new_face_vector.tolist()
                else:
                    vector_list = new_face_vector

                # normalize nhẹ cho ổn định 
                vec = np.array(vector_list, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm

                self.index.upsert(
                    vectors=[{
                        "id": student_id,
                        "values": vec.tolist(),
                        "metadata": {
                            "student_id": student_id
                        }
                    }],
                    namespace=self.namespace
                )

            print(f"Update thành công student {student_id}")
            return True

        except Exception as e:
            print(f"Lỗi update: {e}")
            return False


# --- Chạy thử nghiệm ---
if __name__ == "__main__":
    db = FaceAttendanceDB()
    test_vec = np.random.rand(512).astype('float32')
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    print("\n Test Đăng ký")
    db.register_student("000000001", "Phạm Gia Hồ Huy", "2006-08-12", "098765432", "Nam", test_vec)

    print("\n Test Điểm danh & Liên kết ảnh")
    print(db.process_attendance("IN", test_vec, test_frame))

    print("\n Xem Báo cáo (Xem cột image_path)")
    print(db.get_report())

    print("\n Thống kê tổng quan Dashboard")
    stats = db.get_summary_stats()
    for key, value in stats.items():
        print(f" {key}: {value}")