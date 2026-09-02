from celery import Celery
from database import supabase, s3_client, BUCKET_NAME
import time
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.html import partition_html
from unstructured.chunking.title import chunk_by_title
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import os


# Initialize LLM for Summarization
llm = ChatOpenAI(model='gpt-4o-min', temperature=0)

# Create Celery App
celery_app = Celery(
    'document_processor',   # Name of our Celery app
    broker="redis://localhost:6379/0",    # Where tasks are queued by default redis has 16 dbs. 0 is the first
    backend="redis://localhost:6379/0"    # Where result will be stored
)


def update_status(document_id: str, status: str, details: dict = None):
    """ Update document processing status with optional details """

    # Get current document 
    result = supabase.table("project_documents").select("processing_details").eq("id", document_id).execute()

    # Start with existing details or empty dict
    current_details = {}

    if result.data and result.data[0]["processing_details"]:
        current_details = result.data[0]["processing_details"]

    
    # Add new details if provided
    if details: 
        current_details.update(details)
    

    # Update document 
    supabase.table("project_documents").update({
        "processing_status": status, 
        "processing_details": current_details
    }).eq("id", document_id).execute()
    

@celery_app.task
def process_document(document_id: str):
    """
        Real document Processing
    """

    try: 

        doc_result = supabase.table("project_documents").select("*").eq("id", document_id).execute()
        document = doc_result.data[0]
        source_type = document.get('source_type', 'file')

        # step 1: Download and partition 
        update_status(document_id, "partitioning")
        elements = download_and_partition(document_id, document)


        # step 2: Chunk elements 
        chunks, chunking_metrics = chunk_elements(elements)
        update_status(document_id, "summarising", {
            "chunking": chunking_metrics
        })
        

        #3 Step 3: Summarising chunks 
        processed_chunks = summarise_chunks(chunks, document_id, source_type)

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
        
    elements_summary = analyze_elements(elements)

    update_status(document_id, "chunking", {
        "partitioning": {
            "elements_found": elements_summary
        }
    })
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
        

def analyze_elements(elements):
    """ Count different types of elements found in the document """

    text_count = 0
    table_count = 0
    image_count = 0
    title_count = 0
    other_count = 0

    # Go through each element and count what type it is 
    for element in elements: 
        element_name = type(element).__name__    #Get the class name like "Table" or "NarrativeText"

        if element_name == "Table":
            table_count += 1
        elif element_name == "Image": 
            image_count += 1
        elif element_name in ["Title", "Header"]:
            title_count += 1
        elif element_name in ["NarrativeText", "Text", "ListItem", "FigureCaption"]:
            text_count += 1
        else:
            other_count += 1

    # Return a simple dictionary
    return {
        "text": text_count,
        "tables": table_count,
        "images": image_count,
        "titles": title_count,
        "other": other_count
    }


def chunk_elements(elements):
    """ Chunk elements using title-based strategy and collect metrics """

    print("🔨 Creating smart chunks...")
        
    chunks = chunk_by_title(
        elements, # The parsed PDF elements from previous step
        max_characters=3000, # Hard limit - never exceed 3000 characters per chunk
        new_after_n_chars=2400, # Try to start a new chunk after 2400 characters
        combine_text_under_n_chars=500 # Merge tiny chunks under 500 chars with neighbors
    )

    # Collect chunking metrics 
    total_chunks = len(chunks)

    chunking_metrics = {
        "total_chunks": total_chunks
    }

    print(f"✅ Created {total_chunks} chunks from {len(elements)} elements")

    return chunks, chunking_metrics


def summarise_chunks(chunks, document_id, source_type="file"):
    """Transform chunks into searchable content with AI summaries"""
    print("🧠 Processing chunks with AI Summarisation...")
    
    processed_chunks = []
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks):
        current_chunk = i + 1    # Keeps track of the current chunk number
        
        # Update progress directly
        update_status(document_id, 'summarising', {
            "summarising": {
                "current_chunk": current_chunk,     # improves transparency
                "total_chunks": total_chunks
            }
        })
        
        # Extract content from the chunk
        content_data = separate_content_types(chunk, source_type)

        # Debug prints
        print(f"     Types found: {content_data['types']}")
        print(f"     Tables: {len(content_data['tables'])}, Images: {len(content_data['images'])}")
        
        # Decide if we need AI summarisation
        if content_data['tables'] or content_data['images']:
            print(f"     Creating AI summary for mixed content...")
            enhanced_content = create_ai_summary( 
                content_data['text'], 
                content_data['tables'], 
                content_data['images']
            )
        else:
            enhanced_content = content_data['text']
        
        # Build the original_content structure (a dict with text, tables & images)
        original_content = {'text': content_data['text']}
        if content_data['tables']:
            original_content['tables'] = content_data['tables']
        if content_data['images']:
            original_content['images'] = content_data['images']
        
        # Create processed chunk with all data
        processed_chunk = {
            'content': enhanced_content,
            'original_content': original_content, 
            'type': content_data['types'],
            'page_number': get_page_number(chunk, i),
            'char_count': len(enhanced_content)
        }
        
        processed_chunks.append(processed_chunk)
    
    print(f"✅ Processed {len(processed_chunks)} chunks")
    return processed_chunks


def separate_content_types(chunk, source_type="file"):
    """Analyze what types of content are in a chunk"""
    is_url_source = source_type == 'url'
    
    content_data = {
        'text': chunk.text,
        'tables': [],
        'images': [],
        'types': ['text']
    }
    
    # Check for tables and images in original elements
    if hasattr(chunk, 'metadata') and hasattr(chunk.metadata, 'orig_elements'):
        for element in chunk.metadata.orig_elements:
            element_type = type(element).__name__
            
            # Handle tables
            if element_type == 'Table':
                content_data['types'].append('table')
                table_html = getattr(element.metadata, 'text_as_html', element.text)
                content_data['tables'].append(table_html)
            
            # Handle images (skip for URL sources)
            elif element_type == 'Image' and not is_url_source:
                if (hasattr(element, 'metadata') and 
                    hasattr(element.metadata, 'image_base64') and 
                    element.metadata.image_base64 is not None):
                    content_data['types'].append('image')
                    content_data['images'].append(element.metadata.image_base64)
    
    content_data['types'] = list(set(content_data['types']))
    return content_data


def create_ai_summary(text, tables_html, images_base64):
    """Create AI-enhanced summary for mixed content"""
    
    try:
        # Build the text prompt with more efficient instructions
        prompt_text = f"""Create a searchable index for this document content.

CONTENT:
{text}

"""
        
        # Add tables if present
        if tables_html:
            prompt_text += "TABLES:\n"
            for i, table in enumerate(tables_html):
                prompt_text += f"Table {i+1}:\n{table}\n\n"
        
        # More concise but effective prompt
        prompt_text += """
Generate a structured search index (aim for 250-400 words):

QUESTIONS: List 5-7 key questions this content answers (use what/how/why/when/who variations)

KEYWORDS: Include:
- Specific data (numbers, dates, percentages, amounts)
- Core concepts and themes
- Technical terms and casual alternatives
- Industry terminology

VISUALS (if images present):
- Chart/graph types and what they show
- Trends and patterns visible
- Key insights from visualizations

DATA RELATIONSHIPS (if tables present):
- Column headers and their meaning
- Key metrics and relationships
- Notable values or patterns

Focus on terms users would actually search for. Be specific and comprehensive.

SEARCH INDEX:"""
        
        # Build message content starting with the text prompt
        message_content = [{"type": "text", "text": prompt_text}]
        
        # Add images to the message
        for i, image_base64 in enumerate(images_base64):
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
            })
            print(f"🖼️ Image {i+1} included in summary request")
        
        message = HumanMessage(content=message_content)
        
        response = llm.invoke([message])
        
        return response.content
        
    except Exception as e:
        print(f" AI summary failed: {e}")
        

def get_page_number(chunk, chunk_index):
    """Get page number from chunk or use fallback"""
    if hasattr(chunk, 'metadata'):
        page_number = getattr(chunk.metadata, 'page_number', None)
        if page_number is not None:
            return page_number
    
    # Fallback: use chunk index as page number
    return chunk_index + 1
