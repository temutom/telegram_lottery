# config.py
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_secret_key_for_flask_sessions'
    
    # Use the DATABASE_URL environment variable provided by Render PostgreSQL
    # If not set, it's good practice to have a local default, perhaps an in-memory SQLite
    # for dev if you don't want to spin up local Postgres.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///:memory:' # Use in-memory for local dev if no DATABASE_URL
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'adminpass'
    TICKET_RESERVATION_EXPIRY_HOURS = 1