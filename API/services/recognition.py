from API.db.database_module import FaceAttendanceDB
from API.db.config_manager import config_manager
import numpy as np
import json

db = FaceAttendanceDB()


def to_vector(v):
    if v is None:
        return np.zeros(512, dtype=np.float32)

    if isinstance(v, str):
        v = json.loads(v)

    v = np.array(v, dtype=np.float32)

    # normalize embedding để score ổn định hơn
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm

    return v.reshape(-1)


def recognize_face(new_embedding):

    vector = to_vector(new_embedding).tolist()

    result = db.index.query(
        vector=vector,
        top_k=3,   # nên để 3 cho ổn định
        include_metadata=True,
        namespace=db.namespace
    )

    print(f"# ======= Print result ======= # \n {result} \n # ============================ #")
    
    matches = result.matches

    if not matches:
        return {"recognized": False}

    best = min(matches, key=lambda x: x.score)
    score = best.score

    print("SCORE:", score)

    current_threshold = config_manager.get('RECOGNITION_THRESHOLD')
    if score > current_threshold:
        return {
            "recognized": False,
            "similarity": score
        }

    student_id = best.metadata.get("student_id")
    if not student_id:
        return {"recognized": False, "error": "missing student_id metadata"}

    res = db.supabase.table("students") \
        .select("*") \
        .eq("student_id", student_id) \
        .execute()

    student = res.data[0] if res.data else None

    return {
        "recognized": True,
        "student_id": student_id,
        "name": student["name"] if student else None,
        "similarity": score
    }