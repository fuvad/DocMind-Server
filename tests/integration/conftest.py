import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.server import app
from src.services.clerkAuth import get_current_user_clerk_id

FAKE_CLERK_ID = "test_clerk_user_123"


def _override_clerk_auth():
    return FAKE_CLERK_ID


@pytest.fixture()
def authenticated_client():
    app.dependency_overrides[get_current_user_clerk_id] = _override_clerk_auth
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def unauthenticated_client():
    from fastapi import HTTPException

    def _deny():
        raise HTTPException(status_code=401, detail="User is not signed in")

    app.dependency_overrides[get_current_user_clerk_id] = _deny
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def make_supabase_response(data=None):
    mock_response = MagicMock()
    mock_response.data = data
    return mock_response

import uuid
from urllib.parse import urlparse
from src.config.index import appConfig
from src.services.supabase import supabase

@pytest.fixture()
def verify_local_database():
    """Fail closed if the database URL points to production."""
    url = appConfig.get("supabase_api_url")
    if not url:
        pytest.fail("SUPABASE_API_URL is missing. Aborting database tests.")
        
    try:
        parsed_url = urlparse(url)
    except Exception:
        pytest.fail(f"SUPABASE_API_URL could not be parsed: {url}")
        
    hostname = parsed_url.hostname
    if not hostname:
        pytest.fail(f"SUPABASE_API_URL hostname could not be determined: {url}")
        
    if "supabase.co" in hostname.lower():
        pytest.fail(f"PRODUCTION DATABASE DETECTED. SUPABASE_API_URL contains supabase.co: {url}")
        
    allowed_hosts = ["127.0.0.1", "localhost"]
    if hostname not in allowed_hosts:
        pytest.fail(f"SUPABASE_API_URL hostname {hostname} is not allowed. Allowed hosts: {allowed_hosts}")

@pytest.fixture()
def db_test_user(verify_local_database):
    """Generates a unique test clerk_id, creates a user, and cleans up strictly via cascade."""
    test_clerk_id = f"test_user_{uuid.uuid4()}"
    
    result = supabase.table("users").insert({"clerk_id": test_clerk_id}).execute()
    if not result.data:
        pytest.fail(f"Failed to create test user {test_clerk_id}")
        
    yield test_clerk_id
    
    # Teardown: Clean up test user and let DB cascade
    res = supabase.table("users").delete().eq("clerk_id", test_clerk_id).execute()
    if not res.data:
        print(f"Warning: Failed to cleanup test user {test_clerk_id}")

