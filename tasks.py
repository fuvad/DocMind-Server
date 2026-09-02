from celery import Celery
from database import supabase
import time

# Create Celery App
celery_app = Celery(
    'document_processor',   # Name of our Celery app
    broker="redis://localhost:6379/0",    # Where tasks are queued by default redis has 16 dbs. 0 is the first
    backend="redis://localhost:6379/0"    # Where result will be stored
)

@celery_app.task
def process_document(document_id: str):
    """
        simple test task
    """
    
    # step 1: Update status to "processing"
    supabase.table("project_documents").update({
        "processing_status": "processing"
    }).eq("id", document_id).execute()
    
    print(f"Processing document {document_id}")
    
    # Step 2: Simulate actual work (partitioning, chunking,...)
    time.sleep(5)    # In real implementation, this is where we will process the document
    
    # Step 3: Update status to "completed"
    supabase.table("project_documents").update({
            "processing_status": "completed"
    }).eq("id", document_id).execute()
    
    print(f"Celery task completed for document: {document_id}")
    
    return {
        "status": "success",
        "document_id": document_id
    }   # not necessary, coz it'll be stored in redis, which won't use