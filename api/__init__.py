from flask import Flask
import os
from .routes import register_routes

def create_app():
    app = Flask(__name__, template_folder='../template')
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    register_routes(app)
    return app