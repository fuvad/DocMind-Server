from src.config.index import appConfig
from fastapi import Request, HTTPException
import jwt


from clerk_backend_api import Clerk
from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions


def get_current_user_clerk_id(request: Request):
    clerk_error = None
    try:
        sdk = Clerk(appConfig["clerk_secret_key"])
        
        # request_state = JWT Token
        request_state = sdk.authenticate_request(
            request,
            options=AuthenticateRequestOptions(authorized_parties=appConfig["domain"]),
        )
        
        if request_state.is_signed_in:
            clerk_id = request_state.payload.get("sub")
            if clerk_id:
                return clerk_id
    except Exception as e:
        clerk_error = str(e)

    # If an Authorization header is present but Clerk authentication failed,
    # reject immediately without falling back to demo_session.
    auth_header = request.headers.get("authorization")
    if auth_header:
        if clerk_error:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {clerk_error}")
        raise HTTPException(status_code=401, detail="Invalid or expired Clerk token")

    # If no Authorization header is present, fall back to demo session cookie
    demo_cookie = request.cookies.get("demo_session")
    if demo_cookie:
        try:
            payload = jwt.decode(
                demo_cookie, 
                appConfig["demo_jwt_secret"], 
                algorithms=["HS256"]
            )
            clerk_id = payload.get("sub")
            if clerk_id and clerk_id.startswith("demo:"):
                return clerk_id
        except Exception:
            pass  # Demo cookie is invalid

    # Neither authentication method worked
    if clerk_error:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {clerk_error}")
    raise HTTPException(status_code=401, detail="User is not signed in")
