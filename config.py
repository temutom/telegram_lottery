# config.py
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_secret_key_for_flask_sessions'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///lottery.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID') # For admin notifications if desired
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'adminpass' # Simple admin pass for now
    TICKET_RESERVATION_EXPIRY_HOURS = 1 # Tickets expire after 1 hour if not paid