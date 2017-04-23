from datetime import timedelta

from flask import Flask
from flask import g, session
from flask_cors import CORS, cross_origin
from flask_redis import FlaskRedis
from flask_login import LoginManager
from flask_login import current_user
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

from .config import config

db = SQLAlchemy()
mail = Mail()
socketio = SocketIO()
redis_store = FlaskRedis()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.session_protection = 'strong'

def create_app(config_name):
    app = Flask(__name__)
    cors = CORS(app, resources={r"/api/*": {"origins": 
        "*"}})
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Auto Time Out After 60 Minutes For Session
    @app.before_request
    def before_request():
        app.permanent_session_lifetime = timedelta(minutes=60)
        g.user = current_user
        session.permanent = True
        session.modified = True

    db.init_app(app)
    redis_store.init_app(app)
    socketio.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    from .account import account as account_blueprint
    app.register_blueprint(account_blueprint, url_prefix='/account')

    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from .one_tap import one_tap as one_tap_blueprint
    app.register_blueprint(one_tap_blueprint, url_prefix='/1tap')

    from . import models
    return app
