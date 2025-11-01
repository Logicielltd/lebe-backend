from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL from environment variable
DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("SQLALCHEMY_DATABASE_URL is not set in environment variables")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

# Create a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for declarative models
Base = declarative_base()

# Dependency for FastAPI (if you're using it)
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()