#!venv/bin/python
import os
import warnings
warnings.filterwarnings("ignore")

basedir = os.path.abspath(os.path.dirname(__file__))

try:
    from project import config_mysql
    os.environ['DATABASE_URL'] = 'mysql://%s:%s@localhost/%s' % (
        config_mysql.username, config_mysql.password, config_mysql.db)

except ImportError:
    os.environ['DATABASE_URL'] = 'sqlite:///' \
        + os.path.join(basedir, 'project/app.db')

from flup.server.fcgi import WSGIServer

from project import create_app, db
from flask_script import Manager, Shell
from flask_migrate import Migrate, MigrateCommand

app = create_app('production')
manager = Manager(app)
migrate = Migrate(app, db)

if __name__ == '__main__':
    WSGIServer(app).run()

    from socketio.server import SocketIOServer
    SocketIOServer(('0.0.0.0', 8080), app,
        resource="socket.io", policy_server=False).serve_forever()