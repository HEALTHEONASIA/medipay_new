import dateutil.parser
import json

from flask import request, render_template, session
from flask_login import current_user
from flask_mail import Message
from flask_servicelayer import SQLAlchemyService

from .. import db, models, mail, redis_store
from ..models import Chat, ChatMessage, User
from .helpers import is_admin, is_payer, is_provider, pass_generator, to_str


class ExtFuncsMixin(object):
    '''
    base class for medipay operations
    '''
    def __init__(self):
        self.columns = self.__model__.columns()

    def update_from_form(self, model, form, exclude=[]):
        '''fill the models from the form'''
        for col in model.columns():
            if col not in exclude and hasattr(form, col):
                setattr(model, col, getattr(form, col).data)

        self.__db__.session.add(model)
        self.__db__.session.commit()

    def all_for_admin(self):
        '''
        obtains the id for all the admin registed in the system. Used as a decorator in the view section
        '''
        return self.__model__.query.filter(self.__model__.id != False)

    def get_for_admin(self, id):
        '''
        obtains the admin id
        '''
        return self.get(id)

    @staticmethod
    def prepare_pagination(items):
        '''
        restricts results of each page to 10
        '''
        pagination = items.paginate(per_page=10)

        page = request.args.get('page')

        # if some page is chosen otherwise than the first
        if page or pagination.pages > 1:
            try:
                page = int(page)
            except (ValueError, TypeError):
                page = 1
            items = items.paginate(page=page, per_page=10).items

        return (pagination, items)


class ClaimService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for obtaining claims data
    '''
    __model__ = models.Claim
    __db__ = db

    def all_for_user(self, user):
        '''
        get claim id requested by specific user 
        '''
        if is_provider(user):
            return self._find(provider_id=user.provider.id)

        elif is_payer(user):
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment if gop.claim]
            return self.__model__.query.filter(self.__model__.id.in_(claim_ids))

        elif is_admin(user):
            return self.all_for_admin()

        return None

    def get_for_user(self, id, user):
        '''
        get all claim id from the all the users
        '''
        if is_provider(user):
            return user.provider.claims.filter_by(id=id).first()

        elif is_payer(user):
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment]
            return self.__model__.query.filter(self.__model__.id==id and \
                                        self.__model__.id.in_(claim_ids)).first()

        elif is_admin(user):
            return self.get_for_admin(id)

        return None


class GuaranteeOfPaymentService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for obtaining GOP data
    '''
    __model__ = models.GuaranteeOfPayment
    __db__ = db

    def get_open_all(self):
        '''
        obtain all open GOP requests
        '''
        return self.__model__.query.filter_by(closed=False)

    def filter_for_user(self, query, user):
        '''
        obtain all GOP requests for a particular user
        '''
        if is_provider(user):
            return query.filter_by(provider=user.provider)
        elif is_payer(user):
            return query.filter_by(payer=user.payer)
        elif is_admin(user):
            return query

    def send_email(self, gop):
        '''
        creates a random password for unregistered payer and sends a notification email
        '''
        user = None
        rand_pass = None

        # if the payer is registered as a user in our system
        if gop.payer.user:
            recipient_email = gop.payer.pic_email \
                or gop.payer.pic_alt_email \
                or gop.payer.user.email

        # If no, register him, set the random password and send
        # the access credentials to him
        else:
            rand_pass = pass_generator(size=8)
            recipient_email = gop.payer.pic_email
            user = User(email=gop.payer.pic_email,
                        password=rand_pass,
                        user_type='payer',
                        payer=gop.payer)
            db.session.add(user)

        msg = Message("Request for GOP - %s" % gop.provider.company,
                      sender=("MediPay", "request@app.medipayasia.com"),
                      recipients=[recipient_email])

        msg.html = render_template("request-email.html", gop=gop,
                                   root=request.url_root, user=user,
                                   rand_pass=rand_pass)

        # send the email
        try:
            mail.send(msg)
        except:
            pass

    def set_chat_room(self, gop):
        '''
        creates a chat room for the user
        '''
        session['room'] = 'gop' + str(gop.id)
        session['name'] = current_user.email
        session['provider_user_id'] = gop.provider.user.id
        session['payer_user_id'] = gop.payer.user.id
        session['gop_id'] = gop.id


class UserService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for obtaining user data
    '''
    __model__ = models.User
    __db__ = db


class PayerService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for obtaining payer data
    '''
    __model__ = models.Payer
    __db__ = db


class MedicalDetailsService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for additional medical details data
    '''
    __model__ = models.MedicalDetails
    __db__ = db


class ICDCodeService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for ICD codes data
    '''
    __model__ = models.ICDCode
    __db__ = db


class MemberService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for member data
    '''
    __model__ = models.Member
    __db__ = db

    def all_for_user(self, user):
        '''
        obtains claim id for all users
        '''
        if is_provider(user):
            return user.provider.members

        elif is_payer(user):
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment]
            return self.__model__.query.join(models.Claim, self.__model__.claims)\
                                       .filter(models.Claim.id.in_(claim_ids))

        elif is_admin(user):
            return self.all_for_admin()

        return None

    def get_for_user(self, id, user):
        '''
        obtains claim id for specific user
        '''
        if is_provider(user):
            return user.provider.members.filter_by(id=id).first()

        elif is_payer(user):
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment]
            return self.__model__.query.join(models.Claim, self.__model__.claims)\
                                       .filter(models.Claim.id.in_(claim_ids))\
                                       .filter(self.__model__.id==id).first()

        elif is_admin(user):
            return self.get_for_admin(id)

        return None


class TerminalService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for terminal data
    '''
    __model__ = models.Terminal
    __db__ = db

    def all_for_user(self, user):
        '''
        obtains all terminal id for all users
        '''
        if is_provider(user):
            return user.provider.terminals

        elif is_admin(user):
            return self.all_for_admin()

        return None

    def get_for_user(self, id, user):
        '''
        obtains terminal id for specific user
        '''
        if is_provider(user):
            return self.first(id=id, provider_id=user.provider.id)

        elif is_admin(user):
            return self.get_for_admin(id)

        return None


class ChatService(ExtFuncsMixin, SQLAlchemyService):
    '''
    helper class for chat rooms service
    '''
    __model__ = models.Chat
    __db__ = db

    def save_for_user(self, chat, user_id):
        '''function saves each user's history to MySQL'''
        user_msg_list = '%suser%d' % (chat.name, user_id)
        msg_list = redis_store.lrange(user_msg_list, 0, -1)

        if msg_list:
            for msg_json in msg_list:
                msg_dict = json.loads(to_str(msg_json))
                msg_dict['datetime'] = dateutil.parser.parse(msg_dict['datetime'])

                chat_message = ChatMessage(chat=chat,
                                           text=msg_dict['message'],
                                           user_id=msg_dict['user_id'],
                                           datetime=msg_dict['datetime'])
                db.session.add(chat_message)

            db.session.commit()
            redis_store.delete(user_msg_list)

    def save_from_redis(self, chat):
        '''function saves each user's history to Redis'''
        self.save_for_user(chat, chat.guarantee_of_payment.provider.user.id)
        self.save_for_user(chat, chat.guarantee_of_payment.payer.user.id)
