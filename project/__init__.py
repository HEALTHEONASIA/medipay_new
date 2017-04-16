from flask import Flask
from flask import session, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_login import current_user
from .config import config
from flask_mail import Mail
from datetime import timedelta

db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Auto Time Out After 60 Minutes For Session
    @app.before_request
    def before_request():
        session.permanent = True
        app.permanent_session_lifetime = timedelta(minutes=60)
        session.modified = True
        g.user = current_user

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from .main import events

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    from .account import account as account_blueprint
    app.register_blueprint(account_blueprint, url_prefix='/account')

    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from . import views, models
    return app
