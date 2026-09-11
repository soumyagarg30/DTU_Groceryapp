from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "8"))
    provider_headless: bool = os.getenv("PROVIDER_HEADLESS", "false").lower() == "true"
    provider_use_persistent_context: bool = os.getenv("PROVIDER_USE_PERSISTENT_CONTEXT", "true").lower() == "true"
    provider_browser_channel: str = os.getenv("PROVIDER_BROWSER_CHANNEL", "chrome")
    provider_manual_bootstrap: bool = os.getenv("PROVIDER_MANUAL_BOOTSTRAP", "false").lower() == "true"
    provider_debug: bool = os.getenv("PROVIDER_DEBUG", "false").lower() == "true"
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "180"))
    hot_query_cache_max_entries: int = int(os.getenv("HOT_QUERY_CACHE_MAX_ENTRIES", "20"))
    top_k_results: int = int(os.getenv("TOP_K_RESULTS", "15"))
    match_high_threshold: float = float(os.getenv("MATCH_HIGH_THRESHOLD", "0.85"))
    match_min_threshold: float = float(os.getenv("MATCH_MIN_THRESHOLD", "0.72"))
    use_mock_providers: bool = os.getenv(
        "USE_MOCK_PROVIDERS",
        "true" if os.getenv("APP_ENV", "development") == "development" else "false",
    ).lower() == "true"


settings = Settings()

DTU_LOCATION = {
    "display_name": "Delhi Technological University",
    "address": "Shahbad Daulatpur, Delhi",
    "city": "Delhi",
}
