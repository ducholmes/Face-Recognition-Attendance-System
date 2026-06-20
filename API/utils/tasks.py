import time
from celery import Celery
from API.db.database_module import FaceAttendanceDB

# 1. Khởi tạo Celery và trỏ địa chỉ tới Redis
celery_app = Celery(
    'background_tasks',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0'
)

# Khởi tạo DB instance để sử dụng trong worker
db = FaceAttendanceDB()

# 2. Định nghĩa task đăng ký sinh viên bất đồng bộ
@celery_app.task(bind=True)
def process_registration_background(self, student_id: str, name: str, email: str, birthday: str, phone: str, gender: str, face_vector: list):
    print(f"==================================================")
    print(f"[WORKER] Bắt đầu nhận xử lý đăng ký cho sinh viên ID: {student_id}")
    print(f"==================================================")
    
    try:
        # Gọi hàm đăng ký thực tế từ lớp FaceAttendanceDB
        success = db.register_student(
            student_id=student_id,
            name=name,
            email=email,
            birthday=birthday,
            phone=phone,
            gender=gender,
            face_vector=face_vector
        )
        
        if success:
            print(f"[WORKER - {student_id}] Đăng ký thành công và đồng bộ lên Supabase & Pinecone!")
            return {"status": "SUCCESS", "student_id": student_id, "name": name}
        else:
            raise Exception("Hàm register_student của FaceAttendanceDB trả về False")
            
    except Exception as e:
        print(f"[WORKER - ERROR] Lỗi khi xử lý đăng ký sinh viên {student_id}: {str(e)}")
        # Trả về lỗi để ghi nhận trạng thái thất bại
        return {"status": "FAILED", "student_id": student_id, "error": str(e)}


@celery_app.task(bind=True)
def confirm_attendance_background(self, student_id: str, snapshot_url: str):
    print(f"==================================================")
    print(f"[WORKER] Bắt đầu nhận xử lý xác nhận điểm danh cho sinh viên ID: {student_id}")
    print(f"==================================================")

    try:
        # Ghi trực tiếp log điểm danh vào bảng attendance_logs trên Supabase
        response = db.supabase.table("attendance_logs").insert({
            "student_id": student_id,
            "action": "IN",
            "image_path": snapshot_url
        }).execute()

        print(f"[WORKER - {student_id}] Ghi nhận điểm danh thành công vào Supabase!")
        return {"status": "SUCCESS", "student_id": student_id, "data": response.data}
    except Exception as e:
        print(f"[WORKER - ERROR] Lỗi ghi nhận điểm danh cho sinh viên {student_id}: {str(e)}")
        return {"status": "FAILED", "student_id": student_id, "error": str(e)}