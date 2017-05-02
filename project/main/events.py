import dateutil.parser
import json

from datetime import datetime
from flask import request, session, url_for
from flask_login import current_user
from flask_socketio import send, emit, join_room, leave_room

from .. import db, redis_store, socketio
from ..models import Chat, ChatMessage
from .helpers import notify, to_str
from .services import ChatService


chat_service = ChatService()


def date_handler(obj):
    """The function is used to JSON serialize datetime objects"""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError

@socketio.on('hello')
def handle_hello(message):
    print('received hello message: ' + str(message['data']))

    # create a room named with the user's id
    # to be able to send notifications to that user
    if current_user.is_authenticated:
        join_room(current_user.id)


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

    chat = Chat.query.filter_by(name=room).first()
    if not chat:
       chat = Chat(name=room, gop_id=int(room.replace('gop', '')))
       db.session.add(chat)
       db.session.commit(chat)

    try:
        chat_service.save_from_redis(chat)
    except:
        pass

    chat_messages = ChatMessage.query.order_by(ChatMessage.datetime)\
                                     .filter_by(chat_id=chat.id).all()

    chat_messages_list = []
    for chat_message in chat_messages:
        chat_messages_list.append({
            'name': chat_message.user.email,
            'msg': chat_message.text,
            'datetime': chat_message.datetime.strftime('%I:%M:%S %p %d/%m/%Y')
        })

    emit('status',
         {'name': session.get('name'),
          'msg': '<span style="color: green;">has entered the room.</span>',
          'datetime': datetime.now().strftime('%I:%M:%S %p %d/%m/%Y'),
         'messages': chat_messages_list},
         room=room)


@socketio.on('text', namespace='/chat')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""
    room = session.get('room')
    date_time = datetime.now()

    emit('message',
         {'name': session.get('name'),
          'msg': message['msg'],
          'datetime': date_time.strftime('%I:%M:%S %p %d/%m/%Y')},
         room=room)

    # notify the GOP request's provider
    # and payer about a new chat message
    title = 'New message'
    msg = 'New chat message in a GOP request'
    url = url_for('main.request_page', gop_id=session['gop_id'])

    notify(title=title, message=msg, url=url,
           user_id=session.get('provider_user_id'),
           room_name=room)
    notify(title=title, message=msg, url=url,
           user_id=session.get('payer_user_id'),
           room_name=room)

    # Push the message into Redis
    # try:
    msg_dict = {'message': message['msg'],
                'user_id': current_user.id,
                'datetime': date_time}
    msg_json = json.dumps(msg_dict, default=date_handler)

    user_msg_list = '%suser%d' % (room, current_user.id)
    redis_store.rpush(user_msg_list, msg_json)
    # except:
    #     pass # If saving to Redis failed, we should save it directly to MySQL


@socketio.on('left', namespace='/chat')
@socketio.on('disconnect', namespace='/chat')
def handle_chat_disconnect():
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    room = session.get('room')
    leave_room(room)
    emit('status',
         {'name': session.get('name'),
          'msg': '<span style="color: red;">has left the room.</span>',
          'datetime': datetime.now().strftime('%I:%M:%S %p %d/%m/%Y'),
         'messages': []},
         room=room)


    chat = Chat.query.filter_by(name=room).first()
    if not chat:
       chat = Chat(name=room, gop_id=int(room.replace('gop', '')))
       db.session.add(chat)
       db.session.commit(chat)

    chat_service.save_from_redis(chat)

