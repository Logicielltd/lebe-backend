#!/bin/bash

# Change to src directory
cd src

# Install dependencies (if needed)
pip install -r requirements.txt

# Run the FastAPI app with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4