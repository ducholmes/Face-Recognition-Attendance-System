from fastapi import APIRouter, Depends
from API.models.recognize_model import RecognizeRequest
from API.services.recognition import recognize_face
from API.utils.auth import require_role

router = APIRouter()


@router.post("/recognize")
async def recognize(
    request: RecognizeRequest,
    user=Depends(require_role(["admin", "teacher"]))
):

    result = recognize_face(request.embedding)

    return result