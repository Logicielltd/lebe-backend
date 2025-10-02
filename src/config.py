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

    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    KID: str = "p04355e094faa6ca2dfgc8w5666b7a9563b93f7099f6f0f4caskdghdjakdbfgsha"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 360
    REDIS_HOST: str = 'redis-1'
    REDIS_PORT: str = 6379
    REDIS_PASSWORD: str = 'redisPword'
    RABBIT_MQ_URL: str = 'amqp://lebe:admin321@rabbitmq/'
    RABBIT_MQ_ROUTING_KEY: str = ''
    RABBIT_MQ_AUDIT_QUEUE: str = 'audit_queue'
    SMS_MQ_QUEUE: str = 'sms_queue'
    EMAIL_MQ_QUEUE: str = 'email_queue'
    BASE_FRONTEND_URL: str = 'https://lebeapp.com'
    BATCH_CUSTOMER_UPLOAD_QUEUE: str = 'batch_customer_upload_queue'
    COMPANY_QUEUE: str = 'company_creation_queue'


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
