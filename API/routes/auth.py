from fastapi import APIRouter, HTTPException, Depends
from API.models.auth_models import LoginRequest, RegisterRequest
from API.db.database_module import FaceAttendanceDB
from API.utils.auth import require_role

router = APIRouter(prefix="/auth", tags=["Auth"])

db = FaceAttendanceDB()


@router.post("/register")
async def register(data: RegisterRequest):
    """Đăng ký tài khoản mới cho sinh viên"""
    try:
        # Chỉ cho phép đăng ký với role student
        if data.role != 'student':
            raise HTTPException(
                status_code=403, 
                detail="Chỉ sinh viên mới có thể tự đăng ký tài khoản. Liên hệ quản trị viên để được cấp tài khoản giáo viên."
            )

        # Đăng ký tài khoản với Supabase Auth
        response = db.supabase.auth.sign_up({
            "email": data.email,
            "password": data.password
        })

        if not response.user:
            raise HTTPException(
                status_code=400,
                detail="Đăng ký thất bại. Email có thể đã được sử dụng."
            )

        user = response.user

        # Tạo profile với role student
        profile_data = {
            "id": user.id,
            "role": "student"
        }

        db.supabase.table("profiles").insert(profile_data).execute()

        return {
            "success": True,
            "message": "Đăng ký tài khoản thành công! Vui lòng đăng nhập.",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": "student"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print("REGISTER ERROR:", e)
        error_message = str(e)
        
        # Xử lý các lỗi phổ biến
        if "already registered" in error_message.lower() or "already exists" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Email này đã được đăng ký. Vui lòng sử dụng email khác hoặc đăng nhập."
            )
        
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi đăng ký. Vui lòng thử lại sau."
        )


@router.post("/login")
async def login(data: LoginRequest):

    try:

        # LOGIN SUPABASE AUTH
        response = db.supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

        user = response.user
        session = response.session

        # GET ROLE FROM profiles TABLE
        profile_res = db.supabase.table("profiles") \
            .select("role") \
            .eq("id", user.id) \
            .execute()

        role = None

        if profile_res.data:
            role = profile_res.data[0]["role"]

        return {
            "success": True,
            "message": "Login successful",
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": role
            }
        }

    except Exception as e:

        print("LOGIN ERROR:", e)

        raise HTTPException(status_code=401, detail="Invalid email or password")

@router.get("/me")
async def get_current_user(
    user=Depends(require_role(["admin", "teacher", "student"]))
):
    """Lấy thông tin user hiện tại"""
    try:
        profile_res = db.supabase.table("profiles") \
            .select("role") \
            .eq("id", user.id) \
            .execute()

        role = None
        if profile_res.data:
            role = profile_res.data[0]["role"]

        return {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": role
            }
        }
    except Exception as e:
        print("GET CURRENT USER ERROR:", e)
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy thông tin người dùng."
        )