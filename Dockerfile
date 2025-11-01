# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY src/requirements.txt ./requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port (if using FastAPI/Uvicorn, default is 8000)
EXPOSE 8000

# Default command (can be overridden by docker-compose)
CMD ["python", "src/main.py"]
