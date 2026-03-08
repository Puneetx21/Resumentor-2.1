import os
from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from .extensions import db
from .core.routes import core_bp
# from .extensions import db
# from .core.routes import core_bp
from .auth.routes import auth_bp  # ADD THIS LINE
from .dashboard.routes import dashboard_bp
from .resume.routes import resume_bp
from .interview.routes import interview_bp
from authlib.integrations.flask_client import OAuth


# Load .env variables
load_dotenv()


def create_app():
    app = Flask(__name__)

    # Load config from .env
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback')
    app.config['FLASK_ENV'] = os.getenv('FLASK_ENV', 'development')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///dev.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Session configuration for Flask-Login
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

    # Initialize extensions
    db.init_app(app)
    
    # Initialize OAuth
    oauth = OAuth(app)
    app.config.update({
        'GOOGLE_OAUTH_CLIENT_ID': os.getenv('GOOGLE_CLIENT_ID'),
        'GOOGLE_OAUTH_CLIENT_SECRET': os.getenv('GOOGLE_CLIENT_SECRET'),
    })

    # Register Google OAuth client
    google = oauth.register(
        'google',
        client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
        client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
    
    # Store oauth in app for access in routes
    app.oauth = oauth
    
    # Initialize Flask-Login
    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # User loader for Flask-Login
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables
    with app.app_context():
        _ensure_auth_columns()
        db.create_all()

    # Register blueprint
    # app.register_blueprint(core_bp)
    # Register blueprint
    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)  # Add this line
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(interview_bp)
    return app


def _ensure_auth_columns():
    """Apply lightweight schema compatibility updates for auth fields."""
    try:
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        if 'user' not in table_names:
            return

        columns = {col['name'] for col in inspector.get_columns('user')}
        if 'password_hash' not in columns:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN password_hash VARCHAR(255)'))
            db.session.commit()
    except Exception:
        db.session.rollback()
