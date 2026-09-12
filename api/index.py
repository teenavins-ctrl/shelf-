import os
import sys

# Ensure parent directory is on python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db

# Initialize database tables on serverless function startup
try:
    with app.app_context():
        init_db()
except Exception as e:
    print("Database initialization note:", str(e))

# WSGI handler for Vercel
handler = app
