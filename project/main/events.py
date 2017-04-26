from flask import session
from flask_socketio import send, emit, join_room, leave_room

from .. import redis_store, socketio


@socketio.on('hello')
def handle_hello(message):
    print('received hello message: ' + str(message))


@socketio.on('disconnect')
def handle_disconnect():
    pass


@socketio.on('check-notifications')
def handle_notifications(data):
    # try connecting to redis server
    try:
        notification = redis_store.get('id' + str(data))
    except:
        notification = None

    if notification:
        # return notification text and delete it from redis
        emit('check-notifications', notification.decode('utf-8'))
        redis_store.delete('id' + str(data))


@socketio.on_error_default
def default_error_handler(e):
    pass