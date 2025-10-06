from pydantic import BaseSettings
from sqlalchemy.engine.url import URL
import os


class Settings(BaseSettings):
    SERVICE_NAME: str = "Lebe Backend"
    DEBUG: bool = False

    DB_DRIVER: str = "postgresql+asyncpg"
    DB_HOST: str = os.environ.get('DB_HOST')
    DB_PORT: int = os.environ.get('DB_PORT')
    DB_USER: str = os.environ.get('DB_USER')
    DB_PASSWORD: str = os.environ.get('DB_PASSWORD')
    DB_DATABASE: str = os.environ.get('DB_DATABASE')
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 0
    DB_ECHO: bool = False

    SECRET_KEY: str = os.environ.get('SECRET_KEY')
    ALGORITHM: str = os.environ.get('ALGORITHM')
    KID: str = os.environ.get('KID')
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES')
    REFRESH_TOKEN_EXPIRE_MINUTES: int = os.environ.get('REFRESH_TOKEN_EXPIRE_MINUTES')
    REDIS_HOST: str = os.environ.get('REDIS_HOST')
    REDIS_PORT: str = os.environ.get('REDIS_PORT')
    REDIS_PASSWORD: str = os.environ.get('REDIS_PASSWORD')
    RABBIT_MQ_URL: str = os.environ.get('RABBIT_MQ_URL')
    RABBIT_MQ_ROUTING_KEY: str = os.environ.get('RABBIT_MQ_ROUTING_KEY')
    RABBIT_MQ_AUDIT_QUEUE: str = os.environ.get('RABBIT_MQ_AUDIT_QUEUE')
    SMS_MQ_QUEUE: str = os.environ.get('SMS_MQ_QUEUE')
    EMAIL_MQ_QUEUE: str = os.environ.get('EMAIL_MQ_QUEUE')
    BASE_FRONTEND_URL: str = os.environ.get('BASE_FRONTEND_URL')
    BATCH_CUSTOMER_UPLOAD_QUEUE: str = os.environ.get('BATCH_CUSTOMER_UPLOAD_QUEUE')
    COMPANY_QUEUE: str = os.environ.get('COMPANY_QUEUE')


    @property
    def DB_DSN(self) -> URL:
        return URL.create(
            self.DB_DRIVER,
            self.DB_USER,
            self.DB_PASSWORD,
            self.DB_HOST,
            self.DB_PORT,
            self.DB_DATABASE,
        )

    @property
    def DB_URL_STRING(self) -> str:
        return f'{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}?async_fallback=true'

    def MULTI_TENANT_DB_STRING(self, migration_id: str) -> str:
        return (f'jdbc:postgresql://{self.DB_HOST}:'
                f'{self.DB_PORT}/{migration_id}?ApplicationName=MultiTenant')
        
    # MongoDB Logging
    MONGO_URI: str = "mongodb://localhost:27017/"
    MONGO_DB_NAME: str = "api_logs_db"
    
    # Logging levels
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()