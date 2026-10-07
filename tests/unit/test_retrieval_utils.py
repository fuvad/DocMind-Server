import pytest
from src.rag.retrieval.utils import rrf_rank_and_fuse

def test_rrf_rank_and_fuse_empty():
    assert rrf_rank_and_fuse([]) == []
    assert rrf_rank_and_fuse([[], []]) == []

def test_rrf_rank_and_fuse_single_list():
    results = [
        [{"id": "doc1"}, {"id": "doc2"}]
    ]
    fused = rrf_rank_and_fuse(results, weights=[1.0], k=60)
    assert len(fused) == 2
    assert fused[0]["id"] == "doc1"
    assert fused[1]["id"] == "doc2"

def test_rrf_rank_and_fuse_multiple_lists():
    list1 = [{"id": "doc1"}, {"id": "doc2"}, {"id": "doc3"}]
    list2 = [{"id": "doc3"}, {"id": "doc1"}]
    
    fused = rrf_rank_and_fuse([list1, list2], k=60)
    assert len(fused) == 3
    
    assert fused[0]["id"] == "doc1"
    assert fused[1]["id"] == "doc3"
    assert fused[2]["id"] == "doc2"

def test_rrf_rank_and_fuse_with_custom_weights():
    list1 = [{"id": "doc1"}]
    list2 = [{"id": "doc2"}]
    
    fused = rrf_rank_and_fuse([list1, list2], weights=[0.1, 0.9], k=60)
    assert len(fused) == 2
    
    assert fused[0]["id"] == "doc2"
    assert fused[1]["id"] == "doc1"

def test_rrf_rank_and_fuse_ignores_missing_ids():
    results = [
        [{"id": "doc1"}, {"no_id": "val"}, {"id": "doc2"}]
    ]
    fused = rrf_rank_and_fuse(results)
    assert len(fused) == 2
    assert fused[0]["id"] == "doc1"
    assert fused[1]["id"] == "doc2"
