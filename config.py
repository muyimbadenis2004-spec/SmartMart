import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    database_url = os.environ.get("DATABASE_URL", "sqlite:///smartmart.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    STORE_NAME = os.environ.get("STORE_NAME", "SmartMart")
    STORE_ADDRESS = os.environ.get("STORE_ADDRESS", "123 Market Street")
    STORE_PHONE = os.environ.get("STORE_PHONE", "+1 555 0100")
    STORE_TAX_RATE = float(os.environ.get("STORE_TAX_RATE", "0.16"))
    CURRENCY = os.environ.get("CURRENCY", "$")
    POINT_VALUE = 100


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
