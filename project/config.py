import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    WTF_CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
    UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
    ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'csv'])
    SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
    SQLALCHEMY_TRACK_MODIFICATIONS = True
        # email server
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = 'bulletproof.sell@gmail.com'
    MAIL_PASSWORD = 'bull3tpr00f.s3ll'

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')

class ProductionConfig(Config):
    try:
        from . import config_mysql
        SQLALCHEMY_DATABASE_URI = 'mysql://%s:%s@localhost/%s' % (
            config_mysql.username, config_mysql.password, config_mysql.db)

    except ImportError:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')

    try:
        import config_mail
        MAIL_SERVER = config_mail.server
        MAIL_PORT = config_mail.port
        MAIL_USE_TLS = False
        MAIL_USE_SSL = True
        MAIL_USERNAME = config_mail.email
        MAIL_PASSWORD = config_mail.password

    except ImportError:
        pass


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}