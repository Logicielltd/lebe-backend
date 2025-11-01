#!/bin/bash

# Set Python path to include the current directory
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Install dependencies (if needed)
pip install -r requirements.txt

# Run with single worker for Azure compatibility
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app

