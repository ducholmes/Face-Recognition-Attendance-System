from fastapi import APIRouter, Depends
from API.db.database_module import FaceAttendanceDB
from API.utils.auth import require_role

db = FaceAttendanceDB()

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("")
async def get_students(
    user=Depends(require_role(["admin", "teacher"]))
):

    response = db.supabase.table("students") \
        .select("*") \
        .execute()

    return response.data