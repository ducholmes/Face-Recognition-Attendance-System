from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, RedirectResponse
from API.db.database_module import FaceAttendanceDB
from API.utils.auth import require_role
from config import upload_dir
import logging

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])

db = FaceAttendanceDB()
logger = logging.getLogger(__name__)


@router.get("/{image_path:path}")
async def get_snapshot(
    image_path: str,
    user=Depends(require_role(["admin", "teacher"]))
):
    """
    Lấy ảnh snapshot từ Supabase Storage.
    Thử download trực tiếp, nếu lỗi thì fallback sang public URL.
    """
    logger.info(f"[SNAPSHOT] Fetching: {image_path}")
    print(f"[SNAPSHOT] Fetching: {image_path}")
    print(f"[SNAPSHOT] User: {user}")
    print(f"[SNAPSHOT] Using bucket: {upload_dir}")

    # --- Thử 1: download bytes về rồi stream ---
    try:
        print(f"[SNAPSHOT] Attempting download from bucket '{upload_dir}' with path: {image_path}")
        data = db.supabase.storage.from_(upload_dir).download(image_path)
        if data and len(data) > 0:
            print(f"[SNAPSHOT] Download OK, size={len(data)}")
            return Response(
                content=data,
                media_type="image/jpeg",
                headers={
                    "Content-Disposition": f"inline; filename={image_path.split('/')[-1]}",
                    "Cache-Control": "public, max-age=3600",
                }
            )
    except Exception as e:
        print(f"[SNAPSHOT] Download failed: {type(e).__name__}: {e}")
        logger.error(f"[SNAPSHOT] Download error: {e}")

    # --- Thử 2: lấy public URL rồi redirect ---
    try:
        print(f"[SNAPSHOT] Attempting to get public URL...")
        public_url = db.supabase.storage.from_(upload_dir).get_public_url(image_path)
        if public_url:
            print(f"[SNAPSHOT] Redirecting to public URL: {public_url}")
            return RedirectResponse(url=public_url, status_code=302)
    except Exception as e:
        print(f"[SNAPSHOT] Public URL failed: {type(e).__name__}: {e}")
        logger.error(f"[SNAPSHOT] Public URL error: {e}")

    # --- Thử 3: List files để debug ---
    try:
        print(f"[SNAPSHOT] Listing files in bucket to debug...")
        # Lấy folder từ image_path (ví dụ: "2026-05-20" từ "2026-05-20/177929.jpg")
        folder = image_path.split('/')[0] if '/' in image_path else ''
        files = db.supabase.storage.from_(upload_dir).list(folder)
        print(f"[SNAPSHOT] Files in folder '{folder}': {[f['name'] for f in files[:5]]}")  # Show first 5 files
    except Exception as e:
        print(f"[SNAPSHOT] List files failed: {e}")

    raise HTTPException(
        status_code=404, 
        detail={
            "error": "not_found",
            "message": f"Object not found",
            "path": image_path,
            "bucket": upload_dir
        }
    )
