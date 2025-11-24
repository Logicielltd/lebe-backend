from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Base class (must be defined before models for Alembic)

Base = declarative_base()

# Database URL
DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("SQLALCHEMY_DATABASE_URL is not set in environment variables")

# SQLAlchemy Engine

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

# SessionLocal

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency for FastAPI

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
