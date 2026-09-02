from celery import Celery
from database import supabase, s3_client, BUCKET_NAME
import time
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.html import partition_html
import os

# Create Celery App
celery_app = Celery(
    'document_processor',   # Name of our Celery app
    broker="redis://localhost:6379/0",    # Where tasks are queued by default redis has 16 dbs. 0 is the first
    backend="redis://localhost:6379/0"    # Where result will be stored
)

@celery_app.task
def process_document(document_id: str):
    """
        Real document Processing
    """

    try: 

        doc_result = supabase.table("project_documents").select("*").eq("id", document_id).execute()
        document = doc_result.data[0]

        # step 1: Download and partition 
        elements = download_and_partition(document_id, document)

        tables = sum(1 for e in elements if e.category == "Table")
        images = sum(1 for e in elements if e.category == "Image")
        text_elements = sum(1 for e in elements if e.category in ["NarrativeText", "Title", "Text"])
        print(f"📊 Extracted: {tables} tables, {images} images, {text_elements} text elements")


        # step 2: Chunk elements 

        #3 Step 3: Summarising chunks 

        #4 Step 4: Vectorization & storing 
        
    

        return {
            "status": "success", 
            "document_id": document_id
        }

    except Exception as e: 
        pass
    
def download_and_partition(document_id: str, document: dict):
    """ Download document from S3 / Crawl URL and partition into elements  """
    
    print(f"Downloading and partitioning document {document_id}")

    source_type = document.get("source_type", "file")

    if source_type == "url":
        # Crawl URL 
        pass

    else:
        # Handle file processing
        
        # First download the file from s3
        s3_key = document["s3_key"]
        filename = document["filename"]
        file_type = filename.split(".")[-1].lower()

        #  Download to a temporary location 
        temp_file = f"/tmp/{document_id}.{file_type}"    # tmp sits at the very root of our computer
        s3_client.download_file(BUCKET_NAME, s3_key, temp_file)

        elements = partition_document(temp_file, file_type, source_type="file")


    os.remove(temp_file)    # after partitioning temp_file is not needed

    return elements


def partition_document(temp_file: str, file_type: str, source_type: str = "file"):
    """ Partition document based on file type and source type """

    if source_type == "url": 
        pass

    if file_type == "pdf":
        return partition_pdf(
            filename=temp_file,  # Path to your PDF file
            strategy="hi_res", # Use the most accurate (but slower) processing method of extraction
            infer_table_structure=True, # Keep tables as structured HTML, not jumbled text
            extract_image_block_types=["Image"], # Grab images found in the PDF
            extract_image_block_to_payload=True # Store images as base64 data you can actually use
        )

