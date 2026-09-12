import os
import sys

# Add parent directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db

# Initialize database tables on serverless cold start
init_db()

# Export Flask application object for Vercel WSGI
app = app
