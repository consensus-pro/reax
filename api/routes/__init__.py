from .auth import auth_bp
from .profile import profile_bp
from .chat import chat_bp
from .user import user_bp
from .admin import admin_bp
from .ai import ai_bp
from .captcha import captcha_bp

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(captcha_bp)