import time
from API.db.database_module import FaceAttendanceDB
from API.utils.tasks import confirm_attendance_background

db = FaceAttendanceDB()

last_checkin = {}
COOLDOWN = 30  # seconds


def save_attendance(student_id, snapshot_url=None):
    print(f"[save_attendance] Called with student_id={student_id}, snapshot_url={snapshot_url}")
    
    now = time.time()

    # chống spam check-in
    if student_id in last_checkin:
        diff = now - last_checkin[student_id]

        if diff < COOLDOWN:
            print(f"[save_attendance] Cooldown active: {diff:.1f}s < {COOLDOWN}s")
            return {
                "success": False,
                "message": f"Vui lòng đợi {int(COOLDOWN - diff)}s trước khi điểm danh lại"
            }

    last_checkin[student_id] = now

    try:
        print(f"[save_attendance] Queuing confirm_attendance_background task in Celery...")
        task = confirm_attendance_background.delay(student_id, snapshot_url)
        print(f"[save_attendance] ✅ Queued task: {task.id}")
        return {
            "success": True,
            "data": {
                "task_id": task.id,
                "student_id": student_id,
                "snapshot_url": snapshot_url
            }
        }

    except Exception as e:
        print(f"[save_attendance] ❌ Error queuing task: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }