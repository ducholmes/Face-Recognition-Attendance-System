from pydantic import BaseModel
from typing import List


class RecognizeRequest(BaseModel):
    embedding: List[float]