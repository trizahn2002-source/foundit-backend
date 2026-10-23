import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from sqlalchemy import MetaData

app = Flask(__name__)

#  DATABASE_URL comes from .env (PostgreSQL)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///foundit.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.json.compact = False


from datetime import timedelta

# ---------- Session Security ----------

app.config["SESSION_COOKIE_HTTPONLY"] = True

# Development uses HTTP localhost.
# Production must use HTTPS.
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("SESSION_COOKIE_SECURE", "false")
    .lower() == "true"
)

# Use "Lax" when frontend/backend are same-site.
# Cross-site production hosting may require "None"
# together with SESSION_COOKIE_SECURE=True.
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv(
    "SESSION_COOKIE_SAMESITE", "Lax"
)

# Session lifetime: 8 hours.
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    hours=8
)

# Do not renew the cookie on every request.
app.config["SESSION_REFRESH_EACH_REQUEST"] = False


# Naming rules so migrations don't break on SQLite
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})

db = SQLAlchemy(metadata=metadata)
db.init_app(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)

# Let the React app (Vite on port 5173) send cookies to Flask
frontend_urls = os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")
CORS(app, supports_credentials=True, origins=frontend_urls)