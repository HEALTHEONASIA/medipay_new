import re
from datetime import datetime
from flask import request, jsonify, render_template
from flask_mail import Message
from .. import models, db, mail
from . import api
from .helpers import *

# ============== GENERAL API ==============
# GET a list of objects.
# These are requests which return the list
# of objects. Some of them takes filter
# parameters in their queries

@api.route('/general/requests', methods=['GET'])
def general_requests():
    """The function returns all the GOP requests"""

    gops = models.GuaranteeOfPayment.query.all()

    # return the result in a JSON format
    return jsonify(prepare_gops_list(gops))


@api.route('/general/requests/filter/', methods=['GET'])
def general_requests_filter():
    """The function returns the GOP requests filtered by the
    following GET parameters: country, provider, payer, status.
    There are four statuses available:
        'approved', 'declined', 'pending', 'in review'
    And the two states:
        'open', 'closed'
    The parameters and their order are not mandatory
    """

    country = request.args.get('country')
    provider = request.args.get('provider')
    payer = request.args.get('payer')
    status = request.args.get('status')
    state = request.args.get('state')

    gops = models.GuaranteeOfPayment.query.filter(
        models.GuaranteeOfPayment.id > 0)

    if country and provider:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(db.and_(models.Provider.country == country,
                                   models.Provider.company == provider))

    elif country:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(models.Provider.country == country)

    elif provider:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(models.Provider.company == provider)

    if payer:
        gops = gops.join(models.Payer,
                         models.GuaranteeOfPayment.payer_id == \
                         models.Payer.id)\
                   .filter(models.Payer.company == payer)

    if status:
        gops = gops.filter(models.GuaranteeOfPayment.status == status)

    if state:
        if state == 'closed':
            gops = gops.filter(models.GuaranteeOfPayment.state == state)

        elif state == 'open':
            gops = gops.filter(models.GuaranteeOfPayment.state == None)

    gops = gops.all()

    # return the result in a JSON format
    return jsonify(prepare_gops_list(gops))


@api.route('/general/providers', methods=['GET'])
def general_providers():
    """The function returns the all providers"""

    providers = models.Provider.query.all()

    if not providers:
        return jsonify([])

    # return the result in a JSON format
    return jsonify(prepare_providers_list(providers))


@api.route('/general/payers', methods=['GET'])
def general_payers():
    """The function returns the all payers"""

    payers = models.Payer.query.all()

    if not payers:
        return jsonify([])

    # return the result in a JSON format
    return jsonify(prepare_payers_list(payers))


@api.route('/general/doctors', methods=['GET'])
def general_doctors():
    """The function returns the all doctors"""

    doctors = models.Doctor.query.all()

    if not doctors:
        return jsonify([])

    # return the result in a JSON format
    return jsonify(prepare_doctors_list(doctors))


@api.route('/general/billing-codes', methods=['GET'])
def general_billing_codes():
    """The function returns the all billing codes"""

    billing_codes = models.BillingCode.query.all()

    if not billing_codes:
        return jsonify([])

    # return the result in a JSON format
    return jsonify(prepare_billing_codes_list(billing_codes))


@api.route('/general/icd-codes', methods=['GET'])
def general_icd_codes():
    """The function returns the all icd codes"""

    icd_codes = models.ICDCode.query.all()

    if not icd_codes:
        return jsonify([])

    # return the result in a JSON format
    return jsonify(prepare_icd_codes_list(icd_codes))


@api.route('/general/users', methods=['GET'])
def general_users():
    """The function returns the all registered users"""

    users = models.User.query.all()

    if not users:
        return jsonify([])

    # return the result in a JSON format
    return jsonify(prepare_users_list(users))


# GET a single object.
# These are requests which return the single
# object by its ID in a JSON format. It is
# a list containg the one found element

@api.route('/general/request/<int:gop_id>', methods=['GET'])
def general_request_get(gop_id):
    """The function returns the GOP by its ID"""

    gop = models.GuaranteeOfPayment.query.get(gop_id)

    if not gop:
        return jsonify({})

    # return the result in a JSON format.
    # The one request is returned like a list
    # with the single element
    return jsonify([prepare_gop_dict(gop)])


@api.route('/general/provider/<int:provider_id>', methods=['GET'])
def general_provider_get(provider_id):
    """The function returns the provider by its ID"""

    provider = models.Provider.query.get(provider_id)

    if not provider:
        return jsonify([])

    return jsonify([prepare_provider_dict(provider)])


@api.route('/general/payer/<int:payer_id>', methods=['GET'])
def general_payer_get(payer_id):
    """The function returns the payer by its ID"""
    payer = models.Payer.query.get(payer_id)

    if not payer:
        return jsonify([])

    return jsonify([prepare_payer_dict(payer)])


@api.route('/general/doctor/<int:doctor_id>', methods=['GET'])
def general_doctor_get(doctor_id):
    doctor = models.Doctor.query.get(doctor_id)

    if not doctor:
        return jsonify([])

    return jsonify([prepare_doctor_dict(doctor)])


@api.route('/general/billing-code/<int:billing_code_id>', methods=['GET'])
def general_billing_code_get(billing_code_id):
    billing_code = models.BillingCode.query.get(billing_code_id)

    if not billing_code:
        return jsonify([])

    return jsonify([prepare_billing_code_dict(billing_code)])


@api.route('/general/icd-code/<int:icd_code_id>', methods=['GET'])
def general_icd_code_get(icd_code_id):
    icd_code = models.ICDCode.query.get(icd_code_id)

    if not icd_code:
        return jsonify([])

    return jsonify([prepare_icd_code_dict(icd_code)])


@api.route('/general/user/<int:user_id>', methods=['GET'])
def general_user_get(user_id):
    user = models.User.query.get(user_id)

    if not user:
        return jsonify([])

    return jsonify(prepare_user_dict(user))


# POST a single object.
# These are requests which allow to add
# a single object and return a status of
# an operation in a JSON format.

# @api.route('/general/request/add', methods=['POST'])
# def general_request_add():
#     """The function allows to add a new GOP request to
#     the system. The request's info is passed by the POST method.
#     All the parameters are mandatory.
#     """
#     gop_dict = {
#         'provider_id': None,
#         'payer_id': None,
#         'patient_medical_no': None,
#         'admission_time': None,
#         'admission_date': None,
#         'patient_name': None,
#         'patient_gender': None,
#         'patient_dob': None,
#         'patient_tel': None,
#         'patient_id': None,
#         'policy_number': None,
#         'reason': None,
#         'doctor_name': None,
#         'doctor_notes': None,
#         'patient_action_plan': None,
#         'icd_codes': None,
#         'room_price': None,
#         'room_type': None,
#         'doctor_fee': None,
#         'surgery_fee': None
#     }

#     # write the POST paramteres into the dictionary
#     gop_dict = from_post_to_dict(gop_dict)

#     return jsonify(gop_dict)


@api.route('/general/request/add/json', methods=['POST'])
def general_request_add_json():
    json = request.get_json()

    gops_list = []

    for row in json:
        gop_dict = {
            'provider_id': None,
            'payer_id': None,
            'patient_medical_no': None,
            'admission_time': None,
            'admission_date': None,
            'patient_name': None,
            'patient_gender': None,
            'patient_dob': None,
            'patient_tel': None,
            'patient_id': None,
            'policy_number': None,
            'reason': None,
            'doctor_name': None,
            'doctor_notes': None,
            'patient_action_plan': None,
            'icd_codes': None,
            'room_price': None,
            'room_type': None,
            'doctor_fee': None,
            'surgery_fee': None
        }
        gop_dict = from_json_to_dict(row, gop_dict)
        gops_list.append(gop_dict)

    return jsonify(gops_list)


# @api.route('/general/provider/add', methods=['POST'])
# def general_provider_add():
#     """The function allows to add a new provider to the system.
#     The provider's info is passed by the POST method in a JSON format.
#     """
#     provider_dict = {
#         'company': None,
#         'provider_type': None,
#         'pic': None,
#         'pic_email': None,
#         'pic_alt_email': None,
#         'tel': None,
#         'country': None,
#         'street_name': None,
#         'street_number': None,
#         'state': None,
#         'postcode': None,
#         'guarantees_of_payment': None,
#         'billing_codes': None,
#         'doctors': None,
#         'payers': None,
#         'contracts': None,
#         'user_id': None,
#         'setup_serial_number': None,
#         'setup_server_url': None,
#         'setup_server_port': None,
#         'setup_module_name': None,
#         'setup_proxy_url': None,
#         'setup_proxy_port': None,
#         'setup_username': None,
#         'setup_password': None,
#         'setup_request_url': None,
#         'setup_default_path': None,
#         'setup_language': None
#     }

#     # write the POST paramteres into the dictionary
#     provider_dict = from_post_to_dict(provider_dict)

#     return jsonify(provider_dict)


@api.route('/general/provider/add/json', methods=['POST'])
def general_provider_add_json():
    """The function allows to bulk add new providers to the system.
    Although the single provider can also be added like a single element of
    the list. The providers' info is passed by the POST method in a JSON
    format as there are existing the listing values.
    """

    json = request.get_json()

    providers_list = []

    for row in json:
        provider_dict = {
            'company': None,
            'provider_type': None,
            'pic': None,
            'pic_email': None,
            'pic_alt_email': None,
            'tel': None,
            'country': None,
            'street_name': None,
            'street_number': None,
            'state': None,
            'postcode': None,
            # 'guarantees_of_payment': None, # list
            'billing_codes': None, # list
            'doctors': None, # list
            'payers': None, # list
            # 'contracts': None, # list
            # 'user_id': None,
            'setup_serial_number': None,
            'setup_server_url': None,
            'setup_server_port': None,
            'setup_module_name': None,
            'setup_proxy_url': None,
            'setup_proxy_port': None,
            'setup_username': None,
            'setup_password': None,
            'setup_request_url': None,
            'setup_default_path': None,
            'setup_language': None
        }
        # write the JSON parameteres into the dictionary
        provider_dict = from_json_to_dict(row, provider_dict)

        providers_list.append(provider_dict)

    return jsonify(providers_list)


# @api.route('/general/payer/add', methods=['POST'])
# def general_payer_add():
#     """The function allows to add a new payer to the system.
#     The payer's info is passed by the POST method.
#     """
#     payer_dict = {
#         'company': None,
#         'payer_type': None,
#         'pic': None,
#         'pic_email': None,
#         'pic_alt_email': None,
#         'tel': None,
#         'country': None,
#         'street_name': None,
#         'street_number': None,
#         'state': None,
#         'postcode': None,
#         # 'guarantees_of_payment': None,
#         # 'user_id': None,
#     }

#     # write the POST paramteres into the dictionary
#     payer_dict = from_post_to_dict(payer_dict)

#     return jsonify(payer_dict)


@api.route('/general/payer/add/json', methods=['POST'])
def general_payer_add_json():
    """The function allows to bulk add new payers to the system.
    Although the single payer can also be added like a single element of the
    list.
    """
    json = request.get_json()

    payers_list = []

    for row in json: 
        payer_dict = {
            'company': None,
            'payer_type': None,
            'pic': None,
            'pic_email': None,
            'pic_alt_email': None,
            'tel': None,
            'country': None,
            'street_name': None,
            'street_number': None,
            'state': None,
            'postcode': None,
            # 'guarantees_of_payment': None,
            # 'user_id': None,
        }

        # write the JSON paramteres into the dictionary
        payer_dict = from_json_to_dict(row, payer_dict)
        payers_list.append(payer_dict)

    return jsonify(payers_list)


# @api.route('/general/doctor/add', methods=['POST'])
# def general_doctor_add():
#     doctor_dict = {
#         'provider_id': None,
#         'name': None,
#         'department': None,
#         'doctor_type': None,
#         'photo': None
#     }

#     # write the POST paramteres into the dictionary
#     doctor_dict = from_post_to_dict(doctor_dict)

#     return jsonify(doctor_dict)


@api.route('/general/doctor/add/json', methods=['POST'])
def general_doctor_add_json():
    json = request.get_json()

    doctors_list = []

    for row in json:
        doctor_dict = {
            'provider_id': None,
            'name': None,
            'department': None,
            'doctor_type': None,
            'photo': None
        }
        doctor_dict = from_json_to_dict(row, doctor_dict)
        doctors_list.append(doctor_dict)

    return jsonify(doctors_list)


# @api.route('/general/billing-code/add', methods=['POST'])
# def general_billing_code_add():
#     billing_code_dict = {
#         'provider_id': None,
#         'room_and_board': None,
#         'doctor_visit_fee': None,
#         'doctor_consultation_fee': None,
#         'specialist_visit_fee': None,
#         'specialist_consultation_fee': None,
#         'medicines': None,
#         'administration_fee': None
#     }

#     # write the POST paramteres into the dictionary
#     billing_code_dict = from_post_to_dict(billing_code_dict)

#     return jsonify(billing_code_dict)


@api.route('/general/billing-code/add/json', methods=['POST'])
def general_billing_code_add_json():
    json = request.get_json()

    billing_codes_list = []

    for row in json:
        billing_code_dict = {
            'provider_id': None,
            'room_and_board': None,
            'doctor_visit_fee': None,
            'doctor_consultation_fee': None,
            'specialist_visit_fee': None,
            'specialist_consultation_fee': None,
            'medicines': None,
            'administration_fee': None
        }
        billing_code_dict = from_json_to_dict(row, billing_code_dict)
        billing_codes_list.append(billing_code_dict)

    return jsonify(billing_codes_list)


# @api.route('/general/icd-code/add', methods=['POST'])
# def general_icd_code_add():
#     icd_code_dict = {
#         'code': None,
#         'edc': None,
#         'description': None,
#         'common_term': None
#     }

#     # write the POST paramteres into the dictionary
#     icd_code_dict = from_post_to_dict(icd_code_dict)

#     return jsonify(icd_code_dict)


@api.route('/general/icd-code/add/json', methods=['POST'])
def general_icd_code_add_json():
    json = request.get_json()

    icd_codes_list = []

    for row in json:
        icd_code_dict = {
            'code': None,
            'edc': None,
            'description': None,
            'common_term': None
        }
        icd_code_dict = from_json_to_dict(row, icd_code_dict)
        icd_codes_list.append(icd_code_dict)

    return jsonify(icd_codes_list)


# @api.route('/general/user/add', methods=['POST'])
# def general_user_add():
#     user_dict = {
#         'name': None,
#         'email': None,
#         'user_type': None,
#         # role
#         # provider
#         # payer
#         # password_hash
#         'password': None # instead of the password it'll be a password_hash
#     }

#     # write the POST paramteres into the dictionary
#     user_dict = from_post_to_dict(user_dict)

#     return jsonify(user_dict)


@api.route('/general/user/add/json', methods=['POST'])
def general_user_add_json():
    json = request.get_json()

    users_list = []

    for row in json:
        user_dict = {
            'name': None,
            'email': None,
            'user_type': None,
            # role
            # provider
            # payer
            # password_hash
            'password': None # instead of the password it'll be a password_hash
        }
        user_dict = from_json_to_dict(row, user_dict)
        users_list.append(user_dict)

    return jsonify(users_list)


# POST to edit a single object.
# These are requests which allow to add
# a single object and return a status of
# the operation in a JSON format

@api.route('/general/request/<int:gop_id>/edit', methods=['POST'])
def general_request_edit(gop_id):
    """The function allows to edit the GOP request data. The parameters are
    the same as in the request_add function"""
    gop = models.GuaranteeOfPayment.query.get(gop_id)

    # if the object is not found, return an empty JSON list
    if not gop:
        return jsonify([])

    # put the found object's data in a dictionary
    gop_dict = prepare_gop_dict(gop)

    # write the POST paramteres into the dictionary
    gop_dict = from_post_to_dict(gop_dict, overwrite=True)

    return jsonify(gop_dict)


@api.route('/general/request/edit/json', methods=['POST'])
def general_request_edit_json():
    """The function allows to edit the GOP request data. The
    parameters are the same as in the request_add function"""

    json = request.get_json()

    gops_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        gop_id = key
        gop = models.GuaranteeOfPayment.query.get(gop_id)

        if not gop:
            raise ValueError('The GOP Request with the ' + \
                    'id = %s is not found.' % gop_id)

        # put the found object's data in a dictionary
        gop_dict = prepare_gop_dict(gop)

        gop_dict = from_json_to_dict(value, gop_dict, overwrite=True)
        gops_list.append(gop_dict)

    return jsonify(gops_list)


@api.route('/general/provider/<int:provider_id>/edit', methods=['POST'])
def general_provider_edit(provider_id):
    """The function allows to edit the provider data. The parameters are
    the same as in the provider_add function and they are not mandatory"""

    provider = models.Provider.query.get(provider_id)

    # if the object is not found, return an empty JSON list
    if not provider:
        return jsonify([])

    # put the found object's data in a dictionary
    provider_dict = prepare_provider_dict(provider)

    # write the POST paramteres into the dictionary
    provider_dict = from_post_to_dict(provider_dict, overwrite=True)

    return jsonify(provider_dict)


@api.route('/general/provider/edit/json', methods=['POST'])
def general_provider_edit_json():
    json = request.get_json()

    providers_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        provider_id = key
        provider = models.Provider.query.get(provider_id)

        if not provider:
            raise ValueError('The Provider with the ' + \
                    'id = %s is not found.' % provider_id)

        # put the found object's data in a dictionary
        provider_dict = prepare_provider_dict(provider)

        provider_dict = from_json_to_dict(value, provider_dict, overwrite=True)
        providers_list.append(provider_dict)

    return jsonify(providers_list)


@api.route('/general/payer/<int:payer_id>/edit', methods=['POST'])
def general_payer_edit(payer_id):
    """The function allows to edit the payer data. The parameters are
    the same as in the payer_add function"""
    payer = models.Payer.query.get(payer_id)

    # if the object is not found, return an empty JSON list
    if not payer:
        return jsonify([])

    # put the found object's data in a dictionary
    payer_dict = prepare_payer_dict(payer)

    # write the POST paramteres into the dictionary
    payer_dict = from_post_to_dict(payer_dict, overwrite=True)

    return jsonify(payer_dict)


@api.route('/general/payer/edit/json', methods=['POST'])
def general_payer_edit_json():
    json = request.get_json()

    payers_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        payer_id = key
        payer = models.Payer.query.get(payer_id)

        if not payer:
            raise ValueError('The Payer with the ' + \
                    'id = %s is not found.' % payer_id)

        # put the found object's data in a dictionary
        payer_dict = prepare_payer_dict(payer)

        payer_dict = from_json_to_dict(value, payer_dict, overwrite=True)
        payers_list.append(payer_dict)

    return jsonify(payers_list)


@api.route('/general/doctor/<int:doctor_id>/edit', methods=['POST'])
def general_doctor_edit(doctor_id):
    doctor = models.Doctor.query.get(doctor_id)

    # if the object is not found, return an empty JSON list
    if not doctor:
        return jsonify([])

    # put the found provider's data in a dictionary
    doctor_dict = prepare_doctor_dict(doctor)

    # write the POST paramteres into the dictionary
    doctor_dict = from_post_to_dict(doctor_dict, overwrite=True)

    return jsonify(doctor_dict)


@api.route('/general/doctor/edit/json', methods=['POST'])
def general_doctor_edit_json():
    json = request.get_json()

    doctors_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        doctor_id = key
        doctor = models.Doctor.query.get(doctor_id)

        if not doctor:
            raise ValueError('The Doctor with the ' + \
                    'id = %s is not found.' % doctor_id)

        # put the found object's data in a dictionary
        doctor_dict = prepare_doctor_dict(doctor)

        doctor_dict = from_json_to_dict(value, doctor_dict, overwrite=True)
        doctors_list.append(doctor_dict)

    return jsonify(doctors_list)


@api.route('/general/billing-code/<int:billing_code_id>/edit', methods=['POST'])
def general_billing_code_edit(billing_code_id):
    billing_code = models.BillingCode.query.get(billing_code_id)

    # if the object is not found, return an empty JSON list
    if not billing_code:
        return jsonify([])

    # put the found object's data in a dictionary
    billing_code_dict = prepare_billing_code_dict(billing_code)

    # write the POST paramteres into the dictionary
    billing_code_dict = from_post_to_dict(billing_code_dict, overwrite=True)

    return jsonify(billing_code_dict)


@api.route('/general/billing-code/edit/json', methods=['POST'])
def general_billing_code_edit_json():
    json = request.get_json()

    billing_codes_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        billing_code_id = key
        billing_code = models.BillingCode.query.get(billing_code_id)

        if not billing_code:
            raise ValueError('The Billing Code with the ' + \
                    'id = %s is not found.' % billing_code_id)

        # put the found object's data in a dictionary
        billing_code_dict = prepare_billing_code_dict(billing_code)

        billing_code_dict = from_json_to_dict(value, billing_code_dict,
                                              overwrite=True)
        billing_codes_list.append(billing_code_dict)

    return jsonify(billing_codes_list)


@api.route('/general/icd-code/<int:icd_code_id>/edit', methods=['POST'])
def general_icd_code_edit(icd_code_id):
    icd_code = models.ICDCode.query.get(icd_code_id)

    # if the object is not found, return an empty JSON list
    if not icd_code:
        return jsonify([])

    # put the found object's data in a dictionary
    icd_code_dict = prepare_icd_code_dict(icd_code)

    # write the POST paramteres into the dictionary
    icd_code_dict = from_post_to_dict(icd_code_dict, overwrite=True)

    return jsonify(icd_code_dict)


@api.route('/general/icd-code/edit/json', methods=['POST'])
def general_icd_code_edit_json():
    json = request.get_json()

    icd_codes_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        icd_code_id = key
        icd_code = models.ICDCode.query.get(icd_code_id)

        if not icd_code:
            raise ValueError('The ICD Code with the ' + \
                    'id = %s is not found.' % icd_code_id)

        # put the found object's data in a dictionary
        icd_code_dict = prepare_icd_code_dict(icd_code)

        icd_code_dict = from_json_to_dict(value, icd_code_dict, overwrite=True)
        icd_codes_list.append(icd_code_dict)

    return jsonify(icd_codes_list)


@api.route('/general/user/<int:user_id>/edit', methods=['POST'])
def general_user_edit(user_id):
    user = models.User.query.get(user_id)

    # if the object is not found, return an empty JSON list
    if not user:
        return jsonify([])

    # put the found object's data in a dictionary
    user_dict = prepare_user_dict(user)
    # write the POST paramteres into the dictionary
    user_dict = from_post_to_dict(user_dict, overwrite=True)

    return jsonify(user_dict)


@api.route('/general/user/edit/json', methods=['POST'])
def general_user_edit_json():
    json = request.get_json()

    users_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        user_id = key
        user = models.User.query.get(user_id)

        if not user:
            raise ValueError('The User with the ' + \
                    'id = %s is not found.' % user_id)

        # put the found object's data in a dictionary
        user_dict = prepare_user_dict(user)

        user_dict = from_json_to_dict(value, user_dict, overwrite=True)
        users_list.append(user_dict)

    return jsonify(users_list)