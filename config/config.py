import os
from pathlib import Path
from dotenv import load_dotenv

# Tải file .env từ thư mục gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


# Supabase Upload Directory
upload_dir = "snapshots"

# Smallest Face Size Threshold (H & W)
MIN_FACE_SIZE = 140

# IoU Threshold for face tracking
IOU_THRESHOLD = 0.5

# Face Recognition Threshold (Euclidean distance/score)
RECOGNITION_THRESHOLD = 0.80

# Supabase Settings
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Pinecone Settings
PINECONE_KEY = os.getenv('PINECONE_API_KEY') or os.getenv('PINECONE_KEY')
PINECONE_INDEX = os.getenv('PINECONE_INDEX')
PINECONE_NAMESPACE = os.getenv('PINECONE_NAMESPACE')

# Model Path
FACE_LANDMARKER_PATH = "resources/face_landmarker.task"
FACE_DETECTOR_PATH = "resources/blaze_face_full_range.tflite"
ARCFACE_MODEL_PATH = "resources/w600k_mbf.onnx"

# Check if Supabase and Pinecone settings exist
if not SUPABASE_URL or SUPABASE_URL == 'your_supabase_url_here':
    raise RuntimeError("❌ SUPABASE_URL is missing. Please fill it in .env")
if not SUPABASE_KEY or SUPABASE_KEY == 'your_supabase_key_here':
    raise RuntimeError("❌ SUPABASE_KEY is missing. Please fill it in .env")

if not PINECONE_KEY or PINECONE_KEY == 'your_pinecone_api_key_here' or PINECONE_KEY == 'your_pinecone_api_key_here':
    raise RuntimeError("❌ PINECONE_API_KEY is missing. Please fill it in .env")
if not PINECONE_INDEX or PINECONE_INDEX == 'your_pinecone_index_here':
    raise RuntimeError("❌ PINECONE_INDEX is missing. Please fill it in .env")
if not PINECONE_NAMESPACE or PINECONE_NAMESPACE == 'your_pinecone_namespace_here':
    raise RuntimeError("❌ PINECONE_NAMESPACE is missing. Please fill it in .env")