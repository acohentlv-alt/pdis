from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    database_url: str = "postgresql://localhost/pdis"
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    scrape_page_delay_min: float = 1.5
    scrape_page_delay_max: float = 3.5
    scrape_max_pages: int = 10
    scrape_request_timeout: int = 15
    # Madlan scraping
    madlan_page_size: int = 200
    madlan_request_timeout: int = 20
    madlan_delay_min: float = 2.0
    madlan_delay_max: float = 4.0
    api_host: str = "0.0.0.0"
    api_port: int = 8090
    log_level: str = "INFO"
    log_format: str = "json"
    cron_secret: str = ""
    ingest_secret: str = ""
    fb_ingestion_enabled: bool = False
    fb_scans_per_day: int = 2
    vm_trigger_url: str = ""        # e.g. http://129.159.158.214:8787/trigger
    vm_trigger_secret: str = ""     # shared with trigger_server.py on VM
    yad2_vm_ingestion_enabled: bool = False
    govmap_ingestion_enabled: bool = False
    # Yad2 phone fetch (per-listing customer endpoint on gw.yad2.co.il)
    yad2_phone_fetch_enabled: bool = False
    yad2_phone_backfill_batch_size: int = 310
    yad2_phone_scan_cap: int = 40
    yad2_phone_fetch_delay_seconds: float = 0.6
    yad2_phone_retry_cooldown_days: int = 7


settings = Settings()
