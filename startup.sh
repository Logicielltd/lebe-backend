#!/bin/bash

# Set Python path to include the current directory
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Install dependencies (if needed)
pip install -r requirements.txt

# Run with single worker for Azure compatibility
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
