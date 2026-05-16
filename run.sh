#!/usr/bin/env bash
set -e

# Install dependencies if not present
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run the Flask app
python app.py
