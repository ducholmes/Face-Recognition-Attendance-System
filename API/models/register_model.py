from pydantic import BaseModel
from typing import List
from datetime import date

class RegisterRequest(BaseModel):
    student_id: str
    name: str
    email: str
    birthday: date
    phone: str
    gender: str
    embedding: List[float]