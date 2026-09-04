CREATE OR REPLACE FUNCTION vector_search_document_chunks(
    query_embedding vector,     -- Embedding of the user's query
    filter_document_ids uuid[],     -- only search chunks belonging to those docs
    match_threshold double precision DEFAULT 0.3, 
    chunks_per_search integer DEFAULT 20
)
RETURNS TABLE(
    id uuid, 
    document_id uuid, 
    content text, 
    chunk_index integer, 
    created_at timestamp with time zone, 
    page_number integer, 
    char_count integer, 
    type jsonb, 
    original_content jsonb, 
    embedding vector
)
LANGUAGE sql
AS $function$
SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    dc.created_at,
    dc.page_number,
    dc.char_count,
    dc.type,
    dc.original_content,
    dc.embedding
FROM
    document_chunks dc
WHERE
    dc.document_id = ANY(filter_document_ids)
    -- Only search chunks belonging to the documents supplied through the filter_document_ids input
    AND dc.embedding IS NOT NULL
    -- Only consider chunks that actually have an embedding
    AND (1 - (dc.embedding <=> query_embedding)) > match_threshold  
    -- dc.embedding <=> query_embedding -> pgvector distance operator. calculates cosine distance between the chunk's embedding and the query embedding
    -- 1 - distance converts cosine distance into a cosine similarity-like score
    -- Then checks whether it's greater than match_threshold
ORDER BY 
    dc.embedding <=> query_embedding ASC  
    -- sorts the chunks by distance (lowest to highest)
LIMIT 
    chunks_per_search;
$function$;






-- Keyword search function 
-- DO NOT REMOVE THIS BELOW CODE. KEEP THIS IN THE SAME FILE AND RUN THE MIGRATION TOGETHER. 

CREATE OR REPLACE FUNCTION keyword_search_document_chunks(
    query_text text,     -- User's search query
    filter_document_ids uuid[],     -- Search only inside these particular documents
    chunks_per_search integer DEFAULT 20
)    -- Function input
RETURNS TABLE(
    id uuid, 
    document_id uuid, 
    content text, 
    chunk_index integer, 
    created_at timestamp with time zone, 
    page_number integer, 
    char_count integer, 
    type jsonb, 
    original_content jsonb, 
    embedding vector
)    -- Function output
LANGUAGE sql
AS $function$    -- Beginning of Function
SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    dc.created_at,
    dc.page_number,
    dc.char_count,
    dc.type,
    dc.original_content,
    dc.embedding
FROM
    document_chunks dc
WHERE
    dc.fts @@ websearch_to_tsquery('english', query_text)    
    -- document_chunks table has fts col (it's a tsvector col)
    -- Then it takes the user's search text and converts it into a PostgreSQL full-text search query
    -- @@ tells whether this text-search vector match this text-search query
    AND dc.document_id = ANY(filter_document_ids)
    -- Only consider chunks whose document_id is present in filter_document_id
ORDER BY 
    ts_rank_cd(dc.fts, websearch_to_tsquery('english', query_text)) DESC
    -- ts_rank_cd(...) calculates a relevance score for the full-text search match and then ranks them from highest to lowest
LIMIT 
    chunks_per_search;    -- Limit results
$function$;

-- ts_rank_cd calculates relevance score based on frequency, proximity, position and coverage