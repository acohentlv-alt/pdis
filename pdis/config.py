from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    database_url: str = "postgresql://localhost/pdis"
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    scrape_page_delay_min: float = 1.5
    scrape_page_delay_max: float = 3.5
    scrape_max_pages: int = 10
    scrape_request_timeout: int = 15
    api_host: str = "0.0.0.0"
    api_port: int = 8090
    log_level: str = "INFO"
    log_format: str = "json"


settings = Settings()
