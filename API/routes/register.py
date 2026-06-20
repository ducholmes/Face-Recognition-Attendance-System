from fastapi import APIRouter, Depends
from pydantic import BaseModel
from API.utils.auth import require_role
from typing import List, Optional
from datetime import date
from API.utils.tasks import process_registration_background
from API.db.database_module import FaceAttendanceDB

db = FaceAttendanceDB()
router = APIRouter()


class RegisterRequest(BaseModel):
    student_id: str
    name: str
    email: Optional[str] = None
    birthday: date
    phone: str
    gender: str
    embedding: List[float]


@router.post("/register")
def register_user(
    data: RegisterRequest,
    user=Depends(require_role(["admin", "student"]))
):
    email = data.email
    if not email:
        user_role = "student"
        if hasattr(user, "id"):
            profile_res = db.supabase.table("profiles").select("role").eq("id", user.id).execute()
            if profile_res.data:
                user_role = profile_res.data[0]["role"]
                
        if user_role == "student":
            email = getattr(user, "email", "")
        else:
            email = None

    # Gọi tác vụ nền Celery
    task = process_registration_background.delay(
        student_id=data.student_id,
        name=data.name,
        email=email,
        birthday=str(data.birthday),
        phone=data.phone,
        gender=data.gender,
        face_vector=data.embedding
    )

    return {
        "success": True,
        "message": "Hồ sơ đã được tiếp nhận và đang lưu ngầm vào hệ thống!",
        "task_id": task.id
    }