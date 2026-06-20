from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from API.db.config_manager import config_manager
from API.utils.auth import require_role

router = APIRouter(prefix="/admin/configs", tags=["Admin Configs"])

class ConfigUpdateModel(BaseModel):
    value: str
    data_type: str = None # Tùy chọn, nếu không gửi sẽ tự suy luận hoặc lấy từ db

@router.get("")
async def get_all_configs(user = Depends(require_role(["admin"]))):
    """Lấy danh sách toàn bộ cấu hình hệ thống (Dành cho Admin)"""
    return config_manager.get_all()

@router.get("/{key}")
async def get_config(key: str, user = Depends(require_role(["admin"]))):
    """Lấy một cấu hình cụ thể"""
    val = config_manager.get(key)
    if val is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"key": key, "value": val}

@router.put("/{key}")
async def update_config(key: str, data: ConfigUpdateModel, user = Depends(require_role(["admin"]))):
    """Cập nhật giá trị cấu hình (Admin)"""
    success, message = config_manager.update_config(key, data.value, data.data_type)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message, "new_value": config_manager.get(key)}
