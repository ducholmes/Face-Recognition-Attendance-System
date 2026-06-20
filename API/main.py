from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from API.routes.students import router as student_router
from API.routes.attendance import router as attendance_router
from API.routes.register import router as register_router
from API.routes.recognize import router as recognize_router
from API.routes.student_detail import router as student_detail_router
from API.routes.health import router as health_router
from API.routes.auth import router as auth_router
from API.routes.snapshots import router as snapshots_router
from API.routes.admin_config import router as admin_config_router
from API.websocket_handler import websocket_endpoint

app = FastAPI(title="Face Recognition API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5001",
        "http://localhost:5001",
        "http://127.0.0.1:5000",
        "http://localhost:5000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(register_router)
app.include_router(student_router)
app.include_router(attendance_router)
app.include_router(recognize_router)
app.include_router(student_detail_router)
app.include_router(health_router)
app.include_router(snapshots_router)
app.include_router(admin_config_router)
app.websocket("/ws")(websocket_endpoint)
app.include_router(auth_router)