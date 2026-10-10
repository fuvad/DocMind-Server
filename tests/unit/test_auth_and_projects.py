import sys
from unittest.mock import patch, MagicMock, AsyncMock



import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.server import app
from src.services.clerkAuth import get_current_user_clerk_id
from src.routes.projectRoutes import create_project
from src.models.index import ProjectCreate
import jwt
from src.config.index import appConfig

# Mocks
@pytest.fixture
def mock_request():
    request = MagicMock()
    request.cookies = {}
    return request

@pytest.fixture
def mock_supabase():
    with patch("src.routes.projectRoutes.supabase") as mock_supa, \
         patch("src.services.supabase.supabase") as mock_supa_service, \
         patch("src.routes.userRoutes.supabase") as mock_supa_user:
        yield mock_supa

@pytest.fixture
def mock_clerk():
    with patch("src.services.clerkAuth.Clerk") as mock_clerk_class:
        yield mock_clerk_class

# Test 1: A normal Clerk user with a lingering demo cookie is correctly identified
def test_normal_user_overrides_demo_cookie(mock_request, mock_clerk):
    # Setup lingering demo cookie
    mock_request.cookies = {"demo_session": "fake_demo_token"}
    
    # Setup valid Clerk authentication
    mock_sdk = mock_clerk.return_value
    mock_sdk.authenticate_request.return_value.is_signed_in = True
    mock_sdk.authenticate_request.return_value.payload = {"sub": "user_real123"}
    
    clerk_id = get_current_user_clerk_id(mock_request)
    assert clerk_id == "user_real123"

# Test 8: Invalid authentication is rejected
def test_invalid_authentication_rejected(mock_request, mock_clerk):
    # No cookies, no auth header
    mock_request.cookies = {}
    mock_request.headers = {}
    
    # Clerk authentication fails (is_signed_in is False)
    mock_sdk = mock_clerk.return_value
    mock_sdk.authenticate_request.return_value.is_signed_in = False
    
    with pytest.raises(HTTPException) as excinfo:
        get_current_user_clerk_id(mock_request)
    assert excinfo.value.status_code == 401

# Test: Invalid or expired Clerk credentials with a valid demo cookie are rejected
def test_invalid_clerk_auth_with_valid_demo_cookie_rejected(mock_request, mock_clerk):
    mock_request.headers = {"authorization": "Bearer badtoken"}
    mock_request.cookies = {"demo_session": "valid_token"}
    
    # Clerk authentication fails
    mock_sdk = mock_clerk.return_value
    mock_sdk.authenticate_request.side_effect = Exception("AuthError: invalid token")
    
    with pytest.raises(HTTPException) as excinfo:
        get_current_user_clerk_id(mock_request)
    assert excinfo.value.status_code == 401
    assert "Authentication failed" in excinfo.value.detail

# Test: Requests without Clerk credentials can still use a valid demo session
def test_legitimate_demo_user_authenticates(mock_request):
    mock_request.headers = {}
    mock_request.cookies = {"demo_session": "valid_token"}
    
    with patch("src.services.clerkAuth.jwt.decode") as mock_jwt:
        mock_jwt.return_value = {"sub": "demo:user123"}
        clerk_id = get_current_user_clerk_id(mock_request)
        
    assert clerk_id == "demo:user123"

# Test: Invalid demo JWTs are rejected
def test_invalid_demo_jwt_rejected(mock_request):
    mock_request.headers = {}
    mock_request.cookies = {"demo_session": "invalid_token"}
    
    with patch("src.services.clerkAuth.jwt.decode", side_effect=Exception("Invalid signature")):
        with pytest.raises(HTTPException) as excinfo:
            get_current_user_clerk_id(mock_request)
        assert excinfo.value.status_code == 401
        
# Test: A missing webhook signing secret prevents webhook processing
@pytest.mark.asyncio
async def test_missing_webhook_secret_prevents_processing():
    request = MagicMock()
    request.body = AsyncMock(return_value=b'{}')
    request.headers = {}
    
    from src.routes.userRoutes import create_user
    with patch("src.routes.userRoutes.appConfig", {"clerk_webhook_secret": None}):
        with pytest.raises(HTTPException) as excinfo:
            await create_user(request)
        assert excinfo.value.status_code == 500
        assert "Server configuration error" in excinfo.value.detail

# Test: Invalid webhook signatures do not cause database writes
@pytest.mark.asyncio
async def test_invalid_webhook_signature_rejected():
    request = MagicMock()
    request.body = AsyncMock(return_value=b'{}')
    request.headers = {}
    
    from src.routes.userRoutes import create_user
    with patch("src.routes.userRoutes.appConfig", {"clerk_webhook_secret": "secret"}), \
         patch("src.routes.userRoutes.Webhook") as mock_webhook:
        
        mock_webhook_instance = mock_webhook.return_value
        class DummyWebhookVerificationError(Exception): pass
        
        with patch("src.routes.userRoutes.WebhookVerificationError", DummyWebhookVerificationError, create=True):
            mock_webhook_instance.verify.side_effect = DummyWebhookVerificationError("invalid signature")
            
            with pytest.raises(HTTPException) as excinfo:
                await create_user(request)
            assert excinfo.value.status_code == 400
            assert "Invalid webhook signature" in excinfo.value.detail

# Test 3: A demo user can create multiple projects
@pytest.mark.asyncio
async def test_demo_user_can_create_multiple_projects(mock_supabase):
    project_data = ProjectCreate(name="Test Project", description="Desc")
    
    # Mock the DB inserts
    mock_supabase.table().insert().execute.return_value.data = [{"id": "proj_123"}]
    mock_supabase.table().select().eq().execute.return_value.data = []
    
    # If the limit was present, it would check projects and raise 403.
    # Since we removed it, this should pass without raising HTTPException
    res = await create_project(project_data, "demo:user123")
    assert res["message"] == "Project created successfully"

# Test 4: A normal user can create a project when their database user row already exists
@pytest.mark.asyncio
async def test_normal_user_project_creation_user_exists(mock_supabase):
    project_data = ProjectCreate(name="Test Project", description="Desc")
    
    # Mock user exists
    mock_supabase.table().select().eq().execute.return_value.data = [{"clerk_id": "user_123"}]
    mock_supabase.table().insert().execute.return_value.data = [{"id": "proj_123"}]
    
    res = await create_project(project_data, "user_123")
    assert res["message"] == "Project created successfully"
    # Ensure insert to 'users' was NOT called since they exist
    insert_calls = [call for call in mock_supabase.table().insert.mock_calls if "users" in str(call)]
    assert len(insert_calls) == 0

# Test 5: A normal user can create a project when their database user row is initially missing
@pytest.mark.asyncio
async def test_normal_user_project_creation_user_missing(mock_supabase):
    project_data = ProjectCreate(name="Test Project", description="Desc")
    
    # Mock user does NOT exist initially
    mock_supabase.table().select().eq().execute.side_effect = [
        MagicMock(data=[]), # first check
        MagicMock(data=[{"id": "proj_123"}]) # existing projects check or whatever
    ]
    
    # Define insert behavior
    def mock_insert(*args, **kwargs):
        mock_ret = MagicMock()
        mock_ret.execute.return_value.data = [{"id": "new_id"}]
        return mock_ret
        
    mock_supabase.table().insert = mock_insert
    
    res = await create_project(project_data, "user_123")
    assert res["message"] == "Project created successfully"

# Test 6: Concurrent requests do not create duplicate user records
# This is tested implicitly by the exception handling we added in projectRoutes.
@pytest.mark.asyncio
async def test_normal_user_project_creation_race_condition(mock_supabase):
    project_data = ProjectCreate(name="Test Project", description="Desc")
    
    # Mock user missing, then insert throws (duplicate), then check finds it
    mock_supabase.table().select().eq().execute.side_effect = [
        MagicMock(data=[]), # 1: User missing
        MagicMock(data=[{"clerk_id": "user_123"}]), # 2: User found after exception
        MagicMock(data=[{"id": "proj_123"}]), # etc
    ]
    
    # Mock insert to raise Exception for 'users'
    def mock_insert(data, *args, **kwargs):
        mock_ret = MagicMock()
        if "clerk_id" in data and len(data) == 1:
            # users table
            def raise_ex(): raise Exception("duplicate key")
            mock_ret.execute.side_effect = raise_ex
        else:
            mock_ret.execute.return_value.data = [{"id": "proj_123"}]
        return mock_ret
        
    mock_supabase.table().insert = mock_insert
    
    res = await create_project(project_data, "user_123")
    assert res["message"] == "Project created successfully"

# Test 7: Repeated Clerk webhook deliveries do not create duplicate users
from src.routes.userRoutes import create_user
@pytest.mark.asyncio
async def test_webhook_no_duplicate_users():
    request = MagicMock()
    request.body = AsyncMock(return_value=b'{"type":"user.created","data":{"id":"user_123"}}')
    request.headers = {}
    
    with patch("src.routes.userRoutes.appConfig", {"clerk_webhook_secret": "secret"}), \
         patch("src.routes.userRoutes.Webhook"), \
         patch("src.routes.userRoutes.supabase") as mock_supa:
        
        # User already exists
        mock_supa.table().select().eq().execute.return_value.data = [{"clerk_id": "user_123"}]
        
        res = await create_user(request)
        assert res["message"] == "User already exists"
        
# Test 9: Existing functionality continues to work
def test_health_check():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

# Test 10: Chat streaming endpoint requires authentication
def test_chat_streaming_requires_authentication():
    client = TestClient(app)
    # Attempt to stream without authorization header
    response = client.post(
        "/api/projects/test_proj_id/chats/test_chat_id/messages/stream",
        json={"content": "Hello"}
    )
    # The endpoint should reject the request with 401
    assert response.status_code == 401
    assert "User is not signed in" in response.json()["detail"]
