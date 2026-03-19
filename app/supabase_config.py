from supabase import create_client, Client
from app.config import settings
from app.logger import setup_logger

logger = setup_logger(__name__)


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = settings.supabase_url
    key = settings.supabase_key

    logger.info("Initializing Supabase client")
    
    # Check for placeholder values
    if url in ["your_supabase_project_url", "https://your-project-id.supabase.co"] or key in [
        "your_supabase_anon_key",
        "your_anon_key"
    ]:
        logger.error(
            "Supabase credentials contain placeholder values. Please set real values in .env file"
        )
        return None

    try:
        client = create_client(url, key)
        logger.info("Supabase client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


def get_supabase_storage_client() -> Client:
    """Initialize and return Supabase client with service role key for storage operations."""
    url = settings.supabase_url
    # Use service role key if available, otherwise fall back to anon key
    key = settings.supabase_service_role_key or settings.supabase_key

    logger.info("Initializing Supabase storage client")
    
    # Check for placeholder values
    if url in ["your_supabase_project_url", "https://your-project-id.supabase.co"] or key in [
        "your_supabase_anon_key",
        "your_anon_key",
        "your_supabase_service_role_key",
        "your_service_role_key"
    ]:
        logger.warning(
            "Supabase storage credentials contain placeholder values. Storage operations may fail."
        )
        # Still try to create client with anon key as fallback
        if not settings.supabase_service_role_key:
            logger.warning("Service role key not set. Using anon key (may have RLS restrictions).")

    try:
        client = create_client(url, key)
        logger.info("Supabase storage client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase storage client: {e}")
        return None


# Initialize Supabase client
supabase: Client = get_supabase_client()

# Initialize Supabase storage client (with service role key if available)
supabase_storage: Client = get_supabase_storage_client()
