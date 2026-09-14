import os
from sqlalchemy import inspect, text

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
        _ensure_extension_workflow_schema()

        # Build RAG index
        from .services.rag_service import RAGService
        RAGService.build_index()

    return app


def _ensure_extension_workflow_schema():
    """Add workflow columns needed by older local SQLite databases."""
    inspector = inspect(db.engine)
    connection = db.engine.connect()
    try:
        required_tables = {
            'case_review': {
                'analysis_id': 'INTEGER',
                'status': "VARCHAR(30) DEFAULT 'under_review'",
                'decision': "VARCHAR(30) DEFAULT 'under_review'",
                'confirmed_disease': 'VARCHAR(100)',
                'notes': 'TEXT',
                'expert_advisory': 'TEXT',
                'lab_name': 'VARCHAR(150)',
                'lab_sample_id': 'VARCHAR(100)',
                'lab_notes': 'TEXT',
                'lab_result': 'TEXT',
                'lab_referred_at': 'DATETIME',
                'reviewed_by': 'VARCHAR(100)',
                'reviewed_at': 'DATETIME',
            },
            'case_follow_up': {
                'analysis_id': 'INTEGER',
                'review_id': 'INTEGER',
                'assigned_to': "VARCHAR(100) DEFAULT 'admin'",
                'priority': "VARCHAR(20) DEFAULT 'moderate'",
                'status': "VARCHAR(20) DEFAULT 'pending'",
                'action': "TEXT DEFAULT ''",
                'due_date': 'DATE',
                'next_action': 'TEXT',
                'notes': 'TEXT',
                'created_at': 'DATETIME',
                'updated_at': 'DATETIME',
            },
        }

        for table_name, columns in required_tables.items():
            if table_name not in inspector.get_table_names():
                continue
            existing = {column['name'] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
        connection.commit()
    finally:
        connection.close()
