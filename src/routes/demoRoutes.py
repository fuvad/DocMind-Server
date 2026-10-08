from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from src.config.index import appConfig
from src.services.supabase import supabase
from src.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["demoRoutes"])

class DemoSessionResponse(BaseModel):
    message: str
    userId: str

@router.post("/session", response_model=DemoSessionResponse)
async def create_demo_session(response: Response):
    """
    Creates a new temporary demo session.
    - Generates a unique demo user ID.
    - Adds the user to the database to satisfy foreign keys.
    - Sets a secure HttpOnly cookie with the session token.
    """
    try:
        # Generate unique demo user ID
        demo_user_id = f"demo:{uuid.uuid4()}"
        logger.info("creating_demo_session", user_id=demo_user_id)

        # Insert into users table
        user_creation_result = (
            supabase.table("users")
            .insert({"clerk_id": demo_user_id})
            .execute()
        )

        if not user_creation_result.data:
            logger.error("demo_user_creation_failed", user_id=demo_user_id)
            raise HTTPException(
                status_code=500,
                detail="Failed to create demo user",
            )

        # Create JWT token valid for 24 hours
        expiration = datetime.now(timezone.utc) + timedelta(hours=24)
        payload = {
            "sub": demo_user_id,
            "exp": expiration
        }
        token = jwt.encode(
            payload, 
            appConfig["demo_jwt_secret"], 
            algorithm="HS256"
        )

        # Set HttpOnly cookie
        response.set_cookie(
            key="demo_session",
            value=token,
            httponly=True,
            secure=True,          # Secure true, meaning HTTPS only
            samesite="none",      # For cross-origin requests
            max_age=24 * 60 * 60, # 24 hours in seconds
            path="/"
        )

        logger.info("demo_session_created_successfully", user_id=demo_user_id)
        return DemoSessionResponse(
            message="Demo session created successfully",
            userId=demo_user_id
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("demo_session_creation_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while creating demo session: {str(e)}",
        )
