import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from config import Config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
bcrypt = Bcrypt()
cache = Cache()


def create_app():
    """Application factory for PikDrishti AI Flask app."""
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)

    # Cache config - FileSystem for dev, upgrade to Redis for prod
    app.config.setdefault('CACHE_TYPE', 'FileSystemCache')
    app.config.setdefault('CACHE_DIR', os.path.join(app.instance_path, 'flask_cache'))
    app.config.setdefault('CACHE_DEFAULT_TIMEOUT', 86400)  # 24h

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    cache.init_app(app)

    # Register blueprints
    from .auth import auth_bp
    from .main import main_bp
    from .api import api_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Ensure database tables exist and build RAG index
    with app.app_context():
        # import models to ensure they are known to SQLAlchemy
        from . import models
        db.create_all()

        # Build RAG index
        from .services.rag_service import RAGService
        RAGService.build_index()

    return app
