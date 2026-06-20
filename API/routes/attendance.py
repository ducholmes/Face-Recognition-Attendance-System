from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional, Union
from API.db.database_module import FaceAttendanceDB
from API.services.attendance_service import save_attendance
from API.utils.auth import require_role
from datetime import datetime
import pytz

db = FaceAttendanceDB()

router = APIRouter(prefix="/attendance", tags=["Attendance"])


class ConfirmAttendanceRequest(BaseModel):
    student_id: Union[str, int]  # Chấp nhận cả str và int
    snapshot_url: Optional[str] = None
    
    @field_validator('student_id')
    @classmethod
    def convert_student_id_to_str(cls, v):
        """Chuyển student_id thành chuỗi"""
        return str(v)


@router.post("/confirm")
async def confirm_attendance(
    body: ConfirmAttendanceRequest
):
    """
    Xác nhận điểm danh — chỉ ghi vào attendance_logs khi người dùng bấm xác nhận.
    Endpoint này KHÔNG yêu cầu authentication để cho phép điểm danh tự do.
    """
    print(f"[/attendance/confirm] Received request: student_id={body.student_id}, snapshot_url={body.snapshot_url}")
    
    result = save_attendance(body.student_id, body.snapshot_url)
    
    print(f"[/attendance/confirm] save_attendance result: {result}")

    if not result.get("success"):
        # Cooldown hoặc lỗi DB
        error_detail = result.get("message") or result.get("error")
        print(f"[/attendance/confirm] ❌ Failed: {error_detail}")
        raise HTTPException(status_code=400, detail=error_detail)

    print(f"[/attendance/confirm] ✅ Success!")
    return {
        "success": True,
        "data": result.get("data")
    }


@router.get("")
async def get_attendance(
    user=Depends(require_role(["admin", "teacher"]))
):
    """Lấy tất cả lịch sử điểm danh"""
    try:
        response = (
            db.supabase
            .table("attendance_logs")
            .select("*, students(name, student_id)")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "success": True,
            "attendance": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "attendance": []
        }


@router.get("/today")
async def get_attendance_today(
    user=Depends(require_role(["admin", "teacher"]))
):
    """Lấy danh sách học sinh đã điểm danh trong ngày hôm nay"""
    try:
        # Get today's date in VN timezone
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        now_vn = datetime.now(vn_tz)
        today_str = now_vn.strftime('%Y-%m-%d')
        
        # Query using VN timezone format (same as database_module.py)
        response = (
            db.supabase
            .table("attendance_logs")
            .select("*, students(name, student_id, phone, gender)")
            .gte("created_at", f"{today_str}T00:00:00+07:00")
            .lte("created_at", f"{today_str}T23:59:59+07:00")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "success": True,
            "date": today_str,
            "total": len(response.data),
            "attendance": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "attendance": []
        }


@router.get("/present")
async def get_students_present(
    user=Depends(require_role(["admin", "teacher"]))
):
    """Lấy danh sách học sinh đang có mặt trong lớp (status IN)"""
    try:
        # Get today's date in VN timezone
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        now_vn = datetime.now(vn_tz)
        today_str = now_vn.strftime('%Y-%m-%d')
        
        # Lấy tất cả attendance logs trong ngày (using VN timezone format)
        response = (
            db.supabase
            .table("attendance_logs")
            .select("student_id, action, created_at, students(name, phone, gender)")
            .gte("created_at", f"{today_str}T00:00:00+07:00")
            .lte("created_at", f"{today_str}T23:59:59+07:00")
            .order("created_at", desc=True)
            .execute()
        )

        # Lọc ra những học sinh có status cuối cùng là IN
        student_status = {}
        for log in response.data:
            student_id = log['student_id']
            if student_id not in student_status:
                student_status[student_id] = {
                    'student_id': student_id,
                    'name': log['students']['name'] if log.get('students') else 'Unknown',
                    'phone': log['students']['phone'] if log.get('students') else '',
                    'gender': log['students']['gender'] if log.get('students') else '',
                    'action': log['action'],
                    'last_seen': log['created_at']
                }

        # Chỉ lấy những người có status IN
        present_students = [
            student for student in student_status.values() 
            if student['action'] == 'IN'
        ]

        return {
            "success": True,
            "date": today_str,
            "total_present": len(present_students),
            "students": present_students
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "students": []
        }


@router.get("/stats")
async def get_attendance_stats(
    user=Depends(require_role(["admin", "teacher"]))
):
    """Lấy thống kê điểm danh"""
    try:
        stats = db.get_summary_stats()
        
        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stats": {}
        }
