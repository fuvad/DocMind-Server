import pytest
import uuid
from src.services.supabase import supabase

@pytest.fixture()
def db_test_user_a(verify_local_database):
    test_clerk_id = f"test_user_A_{uuid.uuid4()}"
    supabase.table("users").insert({"clerk_id": test_clerk_id}).execute()
    yield test_clerk_id
    supabase.table("users").delete().eq("clerk_id", test_clerk_id).execute()

@pytest.fixture()
def db_test_user_b(verify_local_database):
    test_clerk_id = f"test_user_B_{uuid.uuid4()}"
    supabase.table("users").insert({"clerk_id": test_clerk_id}).execute()
    yield test_clerk_id
    supabase.table("users").delete().eq("clerk_id", test_clerk_id).execute()

def test_user_data_isolation(db_test_user_a, db_test_user_b):
    """
    Verifies that User B cannot retrieve User A's data using the application's
    clerk_id filtering approach.
    """
    # 1. Insert project for User A
    project_res = supabase.table("projects").insert({
        "name": "User A Project",
        "clerk_id": db_test_user_a
    }).execute()
    assert len(project_res.data) == 1
    project_a_id = project_res.data[0]["id"]

    # 2. Positive control: User A CAN retrieve their own data
    user_a_projects = supabase.table("projects").select("*").eq("clerk_id", db_test_user_a).execute()
    assert len(user_a_projects.data) == 1
    assert user_a_projects.data[0]["name"] == "User A Project"

    # 3. Isolation check: User B querying projects with their own clerk_id gets nothing
    user_b_projects = supabase.table("projects").select("*").eq("clerk_id", db_test_user_b).execute()
    assert len(user_b_projects.data) == 0

    # 4. Attempt to fetch User A's specific project by ID using User B's clerk_id (which is how the API protects single-item routes)
    user_b_fetch_specific = supabase.table("projects").select("*").eq("id", project_a_id).eq("clerk_id", db_test_user_b).execute()
    assert len(user_b_fetch_specific.data) == 0


def test_cascade_deletion(db_test_user_a):
    """
    Verifies the PostgreSQL foreign key ON DELETE CASCADE behavior.
    Hierarchy: user -> project -> document -> chunk, and project -> chat -> message.
    """
    user_id = db_test_user_a
    
    # 1. Create Project
    project = supabase.table("projects").insert({"name": "Cascade Project", "clerk_id": user_id}).execute().data[0]
    project_id = project["id"]
    
    # 2. Create Project Settings
    supabase.table("project_settings").insert({
        "project_id": project_id,
        "embedding_model": "test",
        "rag_strategy": "test",
        "agent_type": "test",
        "chunks_per_search": 1,
        "final_context_size": 1,
        "similarity_threshold": 0.5,
        "number_of_queries": 1,
        "reranking_enabled": False,
        "reranking_model": "test",
        "vector_weight": 0.5,
        "keyword_weight": 0.5
    }).execute()

    # 3. Create Document
    doc = supabase.table("project_documents").insert({
        "project_id": project_id,
        "clerk_id": user_id,
        "filename": "test.txt",
        "s3_key": "test_key",
        "file_size": 100,
        "file_type": "text/plain"
    }).execute().data[0]
    doc_id = doc["id"]

    # 4. Create Chunk
    embedding_vector = [0.1] * 1536
    supabase.table("document_chunks").insert({
        "document_id": doc_id,
        "content": "Test chunk content",
        "chunk_index": 0,
        "char_count": 18,
        "embedding": embedding_vector
    }).execute()

    # 5. Create Chat
    chat = supabase.table("chats").insert({
        "title": "Test Chat",
        "project_id": project_id,
        "clerk_id": user_id
    }).execute().data[0]
    chat_id = chat["id"]

    # 6. Create Message
    supabase.table("messages").insert({
        "content": "Hello",
        "chat_id": chat_id,
        "clerk_id": user_id
    }).execute()

    # 7. Delete the User
    supabase.table("users").delete().eq("clerk_id", user_id).execute()

    # 8. Verify everything cascaded properly
    projects_check = supabase.table("projects").select("*").eq("id", project_id).execute()
    assert len(projects_check.data) == 0

    docs_check = supabase.table("project_documents").select("*").eq("id", doc_id).execute()
    assert len(docs_check.data) == 0

    chats_check = supabase.table("chats").select("*").eq("id", chat_id).execute()
    assert len(chats_check.data) == 0
