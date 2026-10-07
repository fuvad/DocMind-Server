import pytest
from src.services.supabase import supabase

@pytest.fixture()
def db_rpc_test_data(db_test_user):
    """Creates a project, a document, and chunks required for RPC tests."""
    user_id = db_test_user
    
    # 1. Project
    project = supabase.table("projects").insert({"name": "RPC Project", "clerk_id": user_id}).execute().data[0]
    project_id = project["id"]
    
    # 2. Document
    doc = supabase.table("project_documents").insert({
        "project_id": project_id,
        "clerk_id": user_id,
        "filename": "rpc_test_doc.txt",
        "s3_key": "rpc_test",
        "file_size": 100,
        "file_type": "text/plain"
    }).execute().data[0]
    doc_id = doc["id"]

    # 3. Chunks
    # Chunk A (Target for keyword and vector search)
    embedding_a = [0.1] * 1536
    chunk_a = supabase.table("document_chunks").insert({
        "document_id": doc_id,
        "content": "This paragraph explains the unique principles of quantum physics and entanglement.",
        "chunk_index": 0,
        "char_count": 82,
        "embedding": embedding_a
    }).execute().data[0]

    # Chunk B (Noise)
    embedding_b = [-0.1] * 1536
    chunk_b = supabase.table("document_chunks").insert({
        "document_id": doc_id,
        "content": "This paragraph is completely unrelated and discusses making an omelette with cheese.",
        "chunk_index": 1,
        "char_count": 84,
        "embedding": embedding_b
    }).execute().data[0]

    # Create another document to verify document filtering
    doc2 = supabase.table("project_documents").insert({
        "project_id": project_id,
        "clerk_id": user_id,
        "filename": "rpc_test_doc2.txt",
        "s3_key": "rpc_test2",
        "file_size": 100,
        "file_type": "text/plain"
    }).execute().data[0]
    
    chunk_c = supabase.table("document_chunks").insert({
        "document_id": doc2["id"],
        "content": "Another quantum physics text but in a different document.",
        "chunk_index": 0,
        "char_count": 57,
        "embedding": embedding_a
    }).execute().data[0]

    yield {"doc_id": doc_id, "doc2_id": doc2["id"], "chunk_a": chunk_a, "chunk_b": chunk_b, "chunk_c": chunk_c}


def test_keyword_search_rpc(db_rpc_test_data):
    """Verifies full text search RPC works via real DB matching."""
    doc_id = db_rpc_test_data["doc_id"]
    chunk_a_id = db_rpc_test_data["chunk_a"]["id"]
    
    # 1. Search for unique keyword inside document 1
    response = supabase.rpc("keyword_search_document_chunks", {
        "query_text": "quantum entanglement",
        "filter_document_ids": [doc_id],
        "chunks_per_search": 5
    }).execute()
    
    assert len(response.data) == 1
    assert response.data[0]["id"] == chunk_a_id

    # 2. Search for keyword in document 1 but with irrelevant terms
    response_none = supabase.rpc("keyword_search_document_chunks", {
        "query_text": "dinosaurs",
        "filter_document_ids": [doc_id]
    }).execute()
    assert len(response_none.data) == 0


def test_vector_search_rpc(db_rpc_test_data):
    """Verifies vector search RPC distance and filtering via pgvector."""
    doc_id = db_rpc_test_data["doc_id"]
    doc2_id = db_rpc_test_data["doc2_id"]
    chunk_a_id = db_rpc_test_data["chunk_a"]["id"]
    
    # query matching chunk A exactly
    query_vector = [0.1] * 1536
    
    # 1. Search in document 1. Should return chunk A, but filter out chunk B due to high distance
    response = supabase.rpc("vector_search_document_chunks", {
        "query_embedding": query_vector,
        "filter_document_ids": [doc_id],
        "match_threshold": 0.5,
        "chunks_per_search": 5
    }).execute()
    
    assert len(response.data) == 1
    assert response.data[0]["id"] == chunk_a_id

    # 2. Verify filter_document_ids works (Chunk C has identical vector, but is in doc2)
    response_both = supabase.rpc("vector_search_document_chunks", {
        "query_embedding": query_vector,
        "filter_document_ids": [doc_id, doc2_id],
        "match_threshold": 0.5,
        "chunks_per_search": 5
    }).execute()
    
    assert len(response_both.data) == 2
    
    # 3. Check very high similarity requirement
    response_high_thresh = supabase.rpc("vector_search_document_chunks", {
        "query_embedding": [-0.1] * 1536, # Opposite vector
        "filter_document_ids": [doc_id],
        "match_threshold": 0.9, # Very strict
        "chunks_per_search": 5
    }).execute()
    
    # Chunk A is opposite, Chunk B matches exactly. So it should only return B.
    assert len(response_high_thresh.data) == 1
    assert response_high_thresh.data[0]["id"] == db_rpc_test_data["chunk_b"]["id"]

