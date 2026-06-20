import os
from supabase import create_client, Client

# Import từ các module khác của dự án
from config import SUPABASE_URL, SUPABASE_KEY, upload_dir
from .time import get_date, get_timestamp

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_image(file_content, extension = '.jpg'):
    response = (
        supabase.storage
        .from_(upload_dir)
        .upload(
            file=file_content,
            path=f"{get_date()}/{get_timestamp()}{extension}",
            file_options={"cache-control": "3600", "upsert": "false"}
        )
    )

    return response