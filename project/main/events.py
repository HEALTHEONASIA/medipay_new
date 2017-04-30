from flask import request, session
from flask_login import current_user
from flask_socketio import send, emit, join_room, leave_room

from .. import redis_store, socketio

clients = {}

@socketio.on('hello')
def handle_hello(message):
    print('received hello message: ' + str(message))
    # try:
    if current_user.is_authenticated:
        join_room(current_user.id)
    # except:
    #     pass


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


@socketio.on('joined', namespace='/chat')
def joined(message):
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    room = session.get('room')
    join_room(room)
    emit('status',
         {'name': session.get('name'),
          'msg': 'has entered the room.'},
         room=room)


@socketio.on('text', namespace='/chat')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""
    room = session.get('room')
    emit('message',
         {'name': session.get('name'),
          'msg': message['msg']},
         room=room)


@socketio.on('left', namespace='/chat')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    room = session.get('room')
    leave_room(room)
    emit('status',
         {'name': session.get('name'),
          'msg': 'has left the room.'},
         room=room)