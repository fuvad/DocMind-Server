import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.services.supabase import supabase
from src.services.awsS3 import s3_client
from src.config.index import appConfig
from src.config.logging import get_logger

logger = get_logger(__name__)

def cleanup_demo_users():
    """
    Cleans up expired demo users and their associated S3 documents.
    Criteria: user_id starts with 'demo:' and created_at < NOW() - INTERVAL '24 hours'
    """
    try:
        logger.info("starting_demo_users_cleanup")

        # In Supabase/PostgREST, we can filter for created_at before 24 hours ago
        # But we need a custom query or we can just fetch all demo users and filter in python if the count is small
        # For a robust approach, we query demo users.
        
        # Using a raw SQL or just fetching all demo users.
        # "ilike" demo:%
        demo_users_res = supabase.table("users").select("*").like("clerk_id", "demo:%").execute()
        
        if not demo_users_res.data:
            logger.info("no_demo_users_found")
            return

        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        
        deleted_count = 0

        for user in demo_users_res.data:
            created_at_str = user.get("created_at")
            if not created_at_str:
                continue
                
            # Parse created_at 
            # Supabase format: "2026-10-07T12:00:00.000+00:00" or similar
            try:
                # Handle potential missing timezone by replacing Z with +00:00 or using fromisoformat
                if created_at_str.endswith('Z'):
                    created_at_str = created_at_str[:-1] + '+00:00'
                created_at = datetime.fromisoformat(created_at_str)
            except Exception as e:
                logger.error(f"failed_to_parse_date for user {user['clerk_id']}: {e}")
                continue
                
            if now - created_at > timedelta(hours=24):
                user_id = user["clerk_id"]
                logger.info("cleaning_up_expired_demo_user", user_id=user_id)

                # 1. Fetch project documents to delete from S3
                docs_res = supabase.table("project_documents").select("s3_key").eq("clerk_id", user_id).execute()
                
                if docs_res.data:
                    for doc in docs_res.data:
                        s3_key = doc.get("s3_key")
                        if s3_key:
                            try:
                                s3_client.delete_object(Bucket=appConfig["s3_bucket_name"], Key=s3_key)
                                logger.info("deleted_s3_object", s3_key=s3_key)
                            except Exception as e:
                                logger.error("failed_to_delete_s3_object", s3_key=s3_key, error=str(e))

                # 2. Delete user from database (cascades)
                try:
                    supabase.table("users").delete().eq("clerk_id", user_id).execute()
                    logger.info("deleted_demo_user_record", user_id=user_id)
                    deleted_count += 1
                except Exception as e:
                    logger.error("failed_to_delete_user_record", user_id=user_id, error=str(e))
                    
        logger.info("demo_users_cleanup_completed", deleted_count=deleted_count)

    except Exception as e:
        logger.error("demo_users_cleanup_error", error=str(e), exc_info=True)

if __name__ == "__main__":
    cleanup_demo_users()
