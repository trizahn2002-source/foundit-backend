import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from sqlalchemy import MetaData

app = Flask(__name__)

# SQLite while building; set DATABASE_URL to use PostgreSQL when deploying
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///foundit.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.json.compact = False

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
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])