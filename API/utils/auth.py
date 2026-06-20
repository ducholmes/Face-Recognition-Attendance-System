from fastapi import Header, HTTPException
from supabase import create_client
from config import SUPABASE_KEY, SUPABASE_URL
import logging


logger = logging.getLogger(__name__)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def require_role(allowed_roles: list):

    async def role_checker(
        authorization: str = Header(None)
    ):

        if authorization is None:
            logger.warning("Missing Authorization header")
            raise HTTPException(status_code=401, detail="Missing token")

        token = authorization.replace("Bearer ", "").strip()

        if not token:
            logger.warning("Empty token after stripping Bearer prefix")
            raise HTTPException(status_code=401, detail="Missing token")

        try:
            response = supabase.auth.get_user(token)
            user = response.user

            if user is None:
                logger.warning("supabase.auth.get_user returned None")
                raise HTTPException(status_code=401, detail="Invalid token")

            logger.info(f"User authenticated: {user.id}")

            profile = supabase.table("profiles") \
                .select("role") \
                .eq("id", user.id) \
                .execute()

            if not profile.data:
                logger.warning(f"No profile found for user {user.id}")
                raise HTTPException(status_code=403, detail="No profile")

            role = profile.data[0]["role"]
            logger.info(f"User role: {role}, allowed: {allowed_roles}")

            if role not in allowed_roles:
                logger.warning(f"Role '{role}' not in allowed {allowed_roles}")
                raise HTTPException(status_code=403, detail="Permission denied")

            return user

        except HTTPException:
            # Re-raise trực tiếp, không bọc lại thành 401
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}: {e}")
            raise HTTPException(status_code=401, detail=f"Auth error: {type(e).__name__}")

    return role_checker
