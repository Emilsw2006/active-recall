from supabase import create_client, Client
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_client: Client | None = None
_service_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
        logger.info("Cliente Supabase (anon) inicializado")
    return _client


def get_service_client() -> Client:
    global _service_client
    if _service_client is None:
        _service_client = create_client(
            settings.supabase_url, settings.supabase_service_key
        )
        logger.info("Cliente Supabase (service) inicializado")
    return _service_client
