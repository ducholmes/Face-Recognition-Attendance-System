from fastapi import APIRouter, Depends
from API.db.database_module import FaceAttendanceDB
from API.models.update_student_model import UpdateStudentRequest
from API.utils.auth import require_role
from datetime import datetime
import pytz

router = APIRouter()

db = FaceAttendanceDB()


# CHECK IF STUDENT HAS REGISTERED
@router.get("/student/check-registration")
async def check_student_registration(
    user=Depends(require_role(["student"]))
):
    """Kiểm tra xem học sinh đã đăng ký khuôn mặt chưa"""
    try:
        user_id = getattr(user, "id", None)
        user_email = getattr(user, "email", None)
        
        if not user_id:
            return {
                "success": False,
                "registered": False,
                "message": "User ID not found"
            }
        
        # Check if student exists in students table by email
        student_res = db.supabase.table("students") \
            .select("student_id, name") \
            .eq("email", user_email) \
            .execute()
        
        if student_res.data and len(student_res.data) > 0:
            return {
                "success": True,
                "registered": True,
                "student": student_res.data[0]
            }
        
        return {
            "success": True,
            "registered": False,
            "message": "Student not registered yet"
        }
        
    except Exception as e:
        print(f"Error checking student registration: {e}")
        return {
            "success": False,
            "registered": False,
            "message": str(e)
        }

@router.get("/student/attendance-history")
async def get_student_attendance_history(
    user=Depends(require_role(["student"]))
):
    """Lấy lịch sử điểm danh của học sinh đang đăng nhập"""
    try:
        # Get user email from auth
        user_email = getattr(user, "email", None)
        
        if not user_email:
            return {
                "success": False,
                "message": "User email not found",
                "history": []
            }
        
        # Find student by email
        student_res = db.supabase.table("students") \
            .select("student_id, name") \
            .eq("email", user_email) \
            .execute()
        
        # If not found by phone, try to get from user profile
        if not student_res.data:
            # Get student_id from profiles or another linking table
            # For now, return empty if no student found
            return {
                "success": True,
                "message": "No student record found",
                "history": []
            }
        
        student_id = student_res.data[0]["student_id"]
        
        # Get attendance logs for this student
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        
        logs_res = db.supabase.table("attendance_logs") \
            .select("*, students(name, student_id)") \
            .eq("student_id", student_id) \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()
        
        # Format history
        history = []
        for log in logs_res.data:
            created_at = datetime.fromisoformat(log["created_at"].replace('Z', '+00:00'))
            vn_time = created_at.astimezone(vn_tz)
            
            history.append({
                "date": vn_time.strftime("%Y-%m-%d"),
                "time": vn_time.strftime("%H:%M:%S"),
                "status": "present" if log["action"] == "IN" else "absent",
                "action": log["action"]
            })
        
        return {
            "success": True,
            "history": history,
            "total": len(history)
        }
        
    except Exception as e:
        print(f"Error getting student attendance history: {e}")
        return {
            "success": False,
            "message": str(e),
            "history": []
        }


# DELETE STUDENT
@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    user=Depends(require_role(["admin"]))
):

    result = db.delete_student(student_id)

    if not result:
        return {"error": "not found"}

    return {"message": "deleted"}


# UPDATE STUDENT
@router.put("/students/{student_id}")
async def update_student(
    student_id: str,
    data: UpdateStudentRequest,
    user=Depends(require_role(["admin"]))
):

    updated = db.supabase.table("students") \
        .update(data.model_dump(exclude_none=True)) \
        .eq("student_id", student_id) \
        .execute()

    if not updated.data:
        return {"error": "not found"}

    return {
        "message": "updated",
        "data": updated.data
    }