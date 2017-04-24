from flask import request
from flask_servicelayer import SQLAlchemyService

from .. import db, models

class ExtFuncsMixin(object):
    def __init__(self):
        self.columns = self.__model__.columns()

    def update_from_form(self, model, form, exclude=[]):
        # fill the models from the form
        for col in model.columns():
            if col not in exclude and hasattr(form, col):
                setattr(model, col, getattr(form, col).data)

        self.__db__.session.add(model)
        self.__db__.session.commit()

    def all_for_admin(self):
        return self.__model__.query.filter(self.__model__.id != False)

    def get_for_admin(self, id):
        return self.get(id)

    @staticmethod
    def prepare_pagination(items):
        # pagination
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
    __model__ = models.Claim
    __db__ = db

    def all_for_user(self, user):
        if user.get_type() == 'provider':
            return self._find(provider_id=user.provider.id)

        elif user.get_type() == 'payer':
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment if gop.claim]
            return self.__model__.query.filter(self.__model__.id.in_(claim_ids))

        elif user.get_role() == 'admin':
            return self.all_for_admin()

        return None

    def get_for_user(self, id, user):
        if user.get_type() == 'provider':
            return user.provider.claims.filter_by(id=id).first()

        elif user.get_type() == 'payer':
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment]
            return self.__model__.query.filter(self.__model__.id==id and \
                                        self.__model__.id.in_(claim_ids)).first()

        elif user.get_role() == 'admin':
            return self.get_for_admin(id)

        return None


class GuaranteeOfPaymentService(ExtFuncsMixin, SQLAlchemyService):
    __model__ = models.GuaranteeOfPayment
    __db__ = db

    def get_open_all(self):
        return self.__model__.query.filter_by(closed=False)

    def filter_for_user(self, query, user):
        if user.get_type() == 'provider':
            return query.filter_by(provider=user.provider)
        elif user.get_type() == 'payer':
            return query.filter_by(payer=user.payer)
        elif user.get_role() == 'admin':
            return query


class UserService(ExtFuncsMixin, SQLAlchemyService):
    __model__ = models.User
    __db__ = db


class MedicalDetailsService(ExtFuncsMixin, SQLAlchemyService):
    __model__ = models.MedicalDetails
    __db__ = db


class MemberService(ExtFuncsMixin, SQLAlchemyService):
    __model__ = models.Member
    __db__ = db

    def all_for_user(self, user):
        if user.get_type() == 'provider':
            return user.provider.members

        elif user.get_type() == 'payer':
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment]
            return self.__model__.query.join(models.Claim, self.__model__.claims)\
                                       .filter(models.Claim.id.in_(claim_ids))

        elif user.get_role() == 'admin':
            return self.all_for_admin()

        return None

    def get_for_user(self, id, user):
        if user.get_type() == 'provider':
            return user.provider.members.filter_by(id=id).first()

        elif user.get_type() == 'payer':
            claim_ids = [gop.claim.id for gop in user.payer.guarantees_of_payment]
            return self.__model__.query.join(models.Claim, self.__model__.claims)\
                                       .filter(models.Claim.id.in_(claim_ids))\
                                       .filter(self.__model__.id==id).first()

        elif user.get_role() == 'admin':
            return self.get_for_admin(id)

        return None


class TerminalService(ExtFuncsMixin, SQLAlchemyService):
    __model__ = models.Terminal
    __db__ = db

    def all_for_user(self, user):
        if user.get_type() == 'provider':
            return user.provider.terminals

        elif user.get_role() == 'admin':
            return self.all_for_admin()

        return None

    def get_for_user(self, id, user):
        if user.get_type() == 'provider':
            return self.first(id=id, provider_id=user.provider.id)

        elif user.get_role() == 'admin':
            return self.get_for_admin(id)

        return None