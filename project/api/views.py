import re
from datetime import datetime
from flask import request, jsonify, render_template
from flask_mail import Message
from .. import models, db, mail
from . import api
from .helpers import *

# Steps to get access to the system API:
# 1. Client manually registers in the system.
# 2. On the settings page he takes an API Key for access to his account
#    through the system API.
# 3. For the provider and the payer account there are different
#    allowed actions.
# 4. a) The Provider is able to:
#       - get its GOP requests list;
#       - get its single GOP request;
#       - get the settings (the 'Provider' model);
#       - get its payers list (the 'Payer' model);
#       - get its single payer (the 'Payer' model);
#       - get its billing codes list (the 'BillingCode' model);
#       - get its single billing code (the 'BillingCode' model);
#       - get its doctors list (the 'Doctor' model);
#       - get its single doctor (the 'Doctor' model);
#       - get its System Setup settings (the 'Provider' model);
#       - get its User Setup settings (the 'User' model);
#       - get the ICD Codes list;
#       - get the ICD Code single;

#       - add the GOP Request (single or bulk upload via JSON);
#       - add payers;
#       - edit the GOP Request (single or bulk, if the status is 'Approved' or 'Declined');
#       - add bill codes;
#       - edit bill codes;
#       - add doctors;
#       - edit doctors;
#       - edit payers;
#       - edit the System Setup settings ('Provider' model);
#       - edit the settings;
#       - edit the User Setup settings ('User' model);

#       [**- (ADD EXCLUSION) get its Account Setup settings (the 'User' model);**]
#       [**- (ADD EXCLUSION, DB, RESTRICTION, VALIDATION) edit the Account Setup settings ('User' model);**]

#    b) The Payer is able to:
#       - get its GOP Requests list;
#       - get its single GOP request;
#       - get the settings ('Payer' model);
#       - get the User Setup settings (the 'User' model);
#       - get the ICD Codes list;
#       - get the ICD Code single;

#       - edit the settings (the 'Payer' model);
#       - edit the User Setup settings ('User' model);

#       - edit the GOP Request status (single or bulk);

#       [**- (ADD EXCLUSION) get its Account Setup settings (the 'User');**]
#       [**- (ADD DB, EXCLUSION, RESTRICTION, VALIDATION) edit the Account Setup settings ('User' model).**]


# =============== USER API ================

def validate_email_address(data):
    if data:
        match = re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"\
          ,data)
        if match == None:
            return (False, 'invalid email address')
        else:
            return (True, '')
    else:
        return (False, 'the parameter is required')


@api.route('/requests', methods=['GET'])
def requests():
    """The function returns all the GOP requests"""

    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        gops = models.GuaranteeOfPayment.query.filter_by(
            provider=user.provider).all()

    elif user.user_type == 'payer':
        gops = models.GuaranteeOfPayment.query.filter_by(
            payer=user.payer).all()

    else:
        return 'Error: no user is found.'

    # return the result in a JSON format
    return jsonify(prepare_gops_list(gops))


@api.route('/request/<int:gop_id>', methods=['GET'])
def request_get(gop_id):
    """The function returns the GOP by its ID"""

    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        gop = models.GuaranteeOfPayment.query.filter_by(id=gop_id,
            provider=user.provider).first()

    elif user.user_type == 'payer':
        gop = models.GuaranteeOfPayment.query.filter_by(id=gop_id,
            payer=user.payer).first()

    else:
        return 'Error: no user is found'

    if not gop:
        return 'Error: no GOP Request #%d is found' % gop_id

    # return the result in a JSON format.
    # The one request is returned like a list
    # with the single element
    return jsonify([prepare_gop_dict(gop)])


@api.route('/settings', methods=['GET'])
def settings():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        exclude = [
            'billing_codes',
            'doctors',
            'guarantees_of_payment',
            'payers',
            'setup_default_path',
            'setup_language',
            'setup_module_name',
            'setup_password',
            'setup_proxy_port',
            'setup_proxy_url',
            'setup_request_url',
            'setup_serial_number',
            'setup_server_port',
            'setup_server_url',
            'setup_username'
        ]

        provider_dict = exclude_keys(exclude,
                                     prepare_provider_dict(user.provider))

        return jsonify([provider_dict])

    elif user.user_type == 'payer':
        exclude = [
            'guarantees_of_payment'
        ]

        payer_dict = exclude_keys(exclude, prepare_payer_dict(user.payer))

        return jsonify([payer_dict])

    else:
        return 'Error: no user is found'


@api.route('/payers', methods=['GET'])
def payers():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        exclude = [
            'providers',
            'guarantees_of_payment'
        ]
        payers_list = exclude_keys(exclude,
                                   prepare_payers_list(user.provider.payers))

        return jsonify(payers_list)

    elif user.user_type == 'payer':
        return 'Error: the payer does not have payers'

    else:
        return 'Error: your account does not have the payers'


@api.route('/payer/<int:payer_id>', methods=['GET'])
def payer_get(payer_id):
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        payer = models.Payer.query.filter(
            db.and_(models.Payer.providers.any(id=user.provider.id), 
                    models.Provider.id==payer_id)).first()

        if not payer:
            return 'Error: no payer #%d is found in your payers' % payer_id

        exclude = [
            'providers',
            'guarantees_of_payment'
        ]
        payer_dict = exclude_keys(exclude, prepare_payer_dict(payer))
        return jsonify([payer_dict])

    elif user.user_type == 'payer':
        return 'Error: the payer does not have payers'

    else:
        return 'Error: your account does not have the payers'


@api.route('/billing-codes', methods=['GET'])
def billing_codes():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        billing_codes = user.provider.billing_codes

        return jsonify(prepare_billing_codes_list(billing_codes))

    elif user.user_type == 'payer':
        return 'Error: the payer does not have billing codes'

    else:
        return 'Error: your account does not have billing codes'


@api.route('/billing-code/<int:billing_code_id>', methods=['GET'])
def billing_code_get(billing_code_id):
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        billing_code = models.BillingCode.query.filter_by(id=billing_code_id,
                                                provider=user.provider).first()

        if not billing_code:
            return 'Error: no billing code #%d is found in your billing codes'\
                % billing_code_id

        return jsonify([prepare_billing_code_dict(billing_code)])

    elif user.user_type == 'payer':
        return 'Error: the payer does not have billing codes'

    else:
        return 'Error: your account does not have billing codes'


@api.route('/icd-codes', methods=['GET'])
def icd_codes():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    icd_codes = models.ICDCode.query.all()

    return jsonify(prepare_icd_codes_list(icd_codes))


@api.route('/icd-code/<int:icd_code_id>', methods=['GET'])
def icd_code_get(icd_code_id):
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    icd_code = models.ICDCode.query.get(icd_code_id)

    if not icd_code:
        return 'Error: no ICD code #%d is found' % icd_code_id

    return jsonify([prepare_icd_code_dict(icd_code)])


@api.route('/doctors', methods=['GET'])
def doctors():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        doctors = user.provider.doctors

        return jsonify(prepare_doctors_list(doctors))

    elif user.user_type == 'payer':
        return 'Error: the payer does not have doctors'

    else:
        return 'Error: your account does not have doctors'


@api.route('/doctor/<int:doctor_id>', methods=['GET'])
def doctor_get(doctor_id):
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        doctor = models.Doctor.query.filter_by(id=doctor_id,
                                               provider=user.provider).first()

        if not doctor:
            return 'Error: no doctor #%d is found in your doctors'\
                % doctor_id

        return jsonify([prepare_doctor_dict(doctor)])

    elif user.user_type == 'payer':
        return 'Error: the payer does not have doctors'

    else:
        return 'Error: your account does not have doctors'


@api.route('/system-settings', methods=['GET'])
def system_settings():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        exclude = [
            'billing_codes',
            'company',
            'country',
            'doctors',
            'guarantees_of_payment',
            'payers',
            'pic',
            'pic_alt_email',
            'pic_email',
            'postcode',
            'provider_type',
            'state',
            'street_name',
            'street_number',
            'tel',
            'id'
        ]
        provider_dict = exclude_keys(exclude,
                                     prepare_provider_dict(user.provider))

        return jsonify([provider_dict])

    elif user.user_type == 'payer':
        return 'Error: the payer does not have the system setup'

    else:
        return 'Error: your account does not the system setup'


@api.route('/user-settings', methods=['GET'])
def user_settings():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    exclude = [
        'id',
        'payer_id',
        'provider_id',
        'user_type'
    ]

    user_dict = exclude_keys(exclude, prepare_user_dict(user))

    return jsonify([user_dict])


# @api.route('/account-settings', methods=['GET'])
# def account_settings():
#     authorized, error, user = authorize_api_key()

#     if not authorized:
#         return error

#     return jsonify([prepare_user_dict(user)])


@api.route('/request/add/json', methods=['POST'])
def request_add_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider':
        return 'Error: you are not able to add the GOP requests'

    json = request.get_json()

    gops_list = []

    for row in json:
        gop_dict = {
            'provider_id': None,
            'payer_id': None,
            'patient_medical_no': None,
            'admission_time': None,
            'admission_date': None,
            'member_name': None,
            'member_gender': None,
            'member_dob': None,
            'member_tel': None,
            # 'patient_id': None,
            'policy_number': None,
            'reason': None,
            'doctor_name': None,
            'patient_action_plan': None,
            'icd_codes': None,
            'room_price': None,
            'room_type': None,
            'doctor_fee': None,
            'surgery_fee': None,
            'medication_fee': None,
            'quotation': None
        }
        gop_dict = from_json_to_dict(row, gop_dict, overwrite=True)
        gops_list.append(gop_dict)

    for row_num, row in enumerate(gops_list):
        payer = models.Payer.query.filter(
            db.and_(models.Payer.providers.any(id=user.provider.id), 
                    models.Payer.id==row['payer_id'])).first()

        if not payer:
            return 'Error: no payer #%s is found in your payers list' \
                % str(row['payer_id'])

        if type(row['icd_codes']) is not list:
            return 'Error: "icd_codes" parameter must be a list'

        room_types = ['na', 'i', 'ii', 'iii', 'iv', 'vip']
        reasons = ['general', 'specialist', 'emergency', 'scheduled']
        genders = ['male', 'female']

        if row['room_type'] not in room_types:
            return 'Error: the "room_type" is wrong, must be one of the' \
                + ' following parameteres: %s' % ' '.join(room_types)

        if row['reason'] not in reasons:
            return 'Error: the "reason" is wrong, must be one of the' \
                + ' following parameteres: %s' % ' '.join(reasons)

        if row['member_gender'] not in genders:
            return 'Error: the "member_gender" is wrong, must be the one' \
                + ' of the following parameteres: %s' % ' '.join(genders)

        try:
            row['room_price'] = float(row['room_price'])
        except (ValueError, TypeError):
            row['room_price'] = 0.0

        try:
            row['doctor_fee'] = float(row['doctor_fee'])
        except (ValueError, TypeError):
            row['doctor_fee'] = 0.0

        try:
            row['surgery_fee'] = float(row['surgery_fee'])
        except (ValueError, TypeError):
            row['surgery_fee'] = 0.0

        try:
            row['medication_fee'] = float(row['medication_fee'])
        except (ValueError, TypeError):
            row['medication_fee'] = 0.0

        try:
            row['quotation'] = float(row['quotation'])
        except (ValueError, TypeError):
            row['quotation'] = 0.0

        admission_date = datetime.strptime(row['admission_date'] + ' ' + \
            row['admission_time'], '%m/%d/%Y %I:%M %p')
        admission_time = admission_date

        dob = datetime.strptime(row['member_dob'], '%m/%d/%Y')

        member = models.Member(name=row['member_name'], dob=dob,
                gender=row['member_gender'], tel=row['member_tel'])

        gop = models.GuaranteeOfPayment(
                provider_id=user.provider.id,
                payer_id=payer.id,
                patient_medical_no=row['patient_medical_no'],
                admission_time=admission_time,
                admission_date=admission_date,
                patient=patient,
                policy_number=row['policy_number'],
                reason=row['reason'],
                doctor_name=row['doctor_name'],
                patient_action_plan=row['patient_action_plan'],
                room_price=row['room_price'],
                room_type=row['room_type'],
                doctor_fee=row['doctor_fee'],
                surgery_fee=row['surgery_fee'],
                medication_fee=row['medication_fee'],
                quotation=row['quotation'],
                timestamp=datetime.now()
            )
        for icd_code_id in row['icd_codes']:
            icd_code = models.ICDCode.query.get(icd_code_id)
            if not icd_code:
                return 'Error: no ICD code #%d is found' % icd_code_id
            gop.icd_codes.append(icd_code)

        db.session.add(gop)
        db.session.commit()

        # initializing user and random password 
        payer_user = None
        rand_pass = None
        
        # if the payer is registered as a user in our system
        if payer.user:
            if payer.pic_email:
                recipient_email = payer.pic_email
            elif payer.pic_alt_email:
                recipient_email = payer.pic_alt_email
            else:
                recipient_email = payer.user.email
        # if no, we register him, set the random password and send
        # the access credentials to him
        else:
            recipient_email = payer.pic_email
            rand_pass = pass_generator(size=8)
            payer_user = models.User(email=payer.pic_email,
                    password=rand_pass,
                    user_type='payer',
                    payer=payer)
            db.session.add(payer_user)

        msg = Message("Request for GOP - %s" % user.provider.company,
                      sender=("MediPay",
                              "request@app.medipayasia.com"),
                      recipients=[recipient_email])

        msg.html = render_template("request-email.html", gop=gop,
                                   root=request.url_root, user=payer_user,
                                   rand_pass = rand_pass, gop_id=gop.id)

        # send the email
        mail.send(msg)

        gops_list[row_num]['id'] = gop.id

    return jsonify(gops_list)


@api.route('/request/edit/json', methods=['POST'])
def request_edit_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider':
        return 'Error: you are not able to edit the GOP requests'

    json = request.get_json()

    gops_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        gop_id = key
        gop = models.GuaranteeOfPayment.query.filter_by(id=gop_id,
                                            provider=user.provider).first()

        if not gop:
            return 'Error: the GOP Request with the id = %s is not found' \
                % gop_id

        if gop.state == 'closed':
            return ('Error: you are not able to edit the GOP Request #%s, as' +\
                ' it has been closed') % gop_id

        if gop.status != 'approved' or gop.status != 'declined':
            return ('Error: you are not able to edit the GOP Request #%s, as' +\
                ' it has not been approved or declined yet') % gop_id

        # put the found object's data in a dictionary
        gop_dict = prepare_gop_dict(gop)

        gop_dict = from_json_to_dict(value, gop_dict, overwrite=True)
        gops_list.append(gop_dict)

    for row in gops_list:
        gop = models.GuaranteeOfPayment.query.filter_by(id=row['id'],
                                            provider=user.provider).first()

        dob = datetime.strptime(row['member_dob'], '%m/%d/%Y')
        admission_date = datetime.strptime(row['admission_date'] + ' ' + \
            row['admission_time'], '%m/%d/%Y %I:%M %p')
        admission_time = admission_date

        if type(row['icd_codes']) is not list:
            return 'Error: "icd_codes" parameter must be a list'

        room_types = ['na', 'i', 'ii', 'iii', 'iv', 'vip']
        reasons = ['general', 'specialist', 'emergency', 'scheduled']
        genders = ['male', 'female']

        if row['room_type'] not in room_types:
            return 'Error: the "room_type" is wrong, must be one of the' \
                + ' following parameteres: %s' % ' '.join(room_types)

        if row['reason'] not in reasons:
            return 'Error: the "reason" is wrong, must be one of the' \
                + ' following parameteres: %s' % ' '.join(reasons)

        if row['member_gender'] not in genders:
            return 'Error: the "member_gender" is wrong, must be one' \
                + ' of the following parameteres: %s' % ' '.join(genders)

        # if the price is set in the wrong format, set it to zero
        try:
            row['room_price'] = float(row['room_price'])
        except (ValueError, TypeError):
            row['room_price'] = 0.0

        try:
            row['doctor_fee'] = float(row['doctor_fee'])
        except (ValueError, TypeError):
            row['doctor_fee'] = 0.0

        try:
            row['surgery_fee'] = float(row['surgery_fee'])
        except (ValueError, TypeError):
            row['surgery_fee'] = 0.0

        try:
            row['medication_fee'] = float(row['medication_fee'])
        except (ValueError, TypeError):
            row['medication_fee'] = 0.0

        try:
            row['quotation'] = float(row['quotation'])
        except (ValueError, TypeError):
            row['quotation'] = 0.0

        try:
            row['policy_number'] = int(row['policy_number'])
        except (ValueError, TypeError):
            row['policy_number'] = None

        try:
            row['patient_medical_no'] = int(row['patient_medical_no'])
        except (ValueError, TypeError):
            row['patient_medical_no'] = None

        # update the patient info
        gop.member.name = row['member_name']
        gop.member.dob = dob
        gop.member.gender = row['member_gender']
        gop.member.tel = row['member_tel']

        for icd_code_id in row['icd_codes']:
            icd_code = models.ICDCode.query.get(int(icd_code_id))
            gop.icd_codes.append(icd_code)

        gop.policy_number = row['policy_number']
        gop.patient_action_plan = row['patient_action_plan']
        gop.doctor_name = row['doctor_name']
        gop.admission_date = admission_date
        gop.admission_time = admission_time
        gop.reason = row['reason']
        gop.room_price = row['room_price']
        gop.room_type = row['room_type']
        gop.patient_medical_no = row['patient_medical_no']
        gop.doctor_fee = row['doctor_fee']
        gop.surgery_fee = row['surgery_fee']
        gop.medication_fee = row['medication_fee']
        gop.quotation = row['quotation']

        db.session.add(gop)

    return jsonify(gops_list)


@api.route('/request/set-status/json', methods=['POST'])
def request_set_status_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'payer':
        return 'Error: you are not able to change a request status ' + \
            'as your account is not of payer type'

    json = request.get_json()

    gops_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        gop_id = key
        gop = models.GuaranteeOfPayment.query.filter_by(id=gop_id,
                                            payer=user.payer).first()

        if not gop:
            return 'Error: the GOP Request with the id = %s is not found' \
                % gop_id

        if gop.state == 'closed':
            return ('Error: you are not able to edit the GOP Request #%s, as' +\
                ' it has been closed') % gop_id

        if not value['status']:
            return 'Error: the "status" parameter is required'

        statuses = ['approved', 'declined']

        if value['status'] not in statuses:
            return 'Error: the "status" is wrong, must be one of the'\
                + ' following parameteres: %s' % ' '.join(statuses)

        if gop.status == 'approved' or gop.status == 'declined':
            return 'Error: the GOP request status is already approved or ' + \
                'declined'

        if value['status'] == 'declined' and not value['reason_decline']:
            return 'Error: the "reason_decline" parameter is required' + \
                ' when declining'

        if not value['stamp_author']:
            return 'Error: the "stamp_author" parameter is required'

        gop.status = value['status']
        gop.timestamp_edited = datetime.now()
        gop.stamp_author = value['stamp_author']
        if value['reason_decline']:
            gop.reason_decline = value['reason_decline']

        db.session.add(gop)

        # put the found object's data in a dictionary
        gop_dict = prepare_gop_dict(gop)

        gop_dict = from_json_to_dict(value, gop_dict, overwrite=True)
        gops_list.append(gop_dict)

    return jsonify(gops_list)


@api.route('/settings/edit', methods=['POST'])
def settings_edit():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type == 'provider':
        provider = user.provider

        exclude = [
            'billing_codes',
            'doctors',
            'guarantees_of_payment',
            'payers',
            'setup_default_path',
            'setup_language',
            'setup_module_name',
            'setup_password',
            'setup_proxy_port',
            'setup_proxy_url',
            'setup_request_url',
            'setup_serial_number',
            'setup_server_port',
            'setup_server_url',
            'setup_username'
        ]

        # put the found object's data in a dictionary
        provider_dict = exclude_keys(exclude, prepare_provider_dict(provider))

        # write the POST paramteres into the dictionary
        provider_dict = from_post_to_dict(provider_dict, overwrite=True)

        validated, error = validate_email_address(provider_dict['pic'])
        if not validated:
            return 'Error: the "pic_email" parameter is wrong: %s' % error

        validated, error = validate_email_address(provider_dict['pic_alt_email'])
        if not validated:
            return 'Error: the "pic_alt_email" parameter is wrong: %s' % error

        user.provider.company = provider_dict['company']
        user.provider.country = provider_dict['country']
        user.provider.pic = provider_dict['pic']
        user.provider.pic_alt_email = provider_dict['pic_alt_email']
        user.provider.pic_email = provider_dict['pic_email']
        user.provider.postcode = provider_dict['postcode']
        user.provider.provider_type = provider_dict['provider_type']
        user.provider.state = provider_dict['state']
        user.provider.street_name = provider_dict['street_name']
        user.provider.street_number = provider_dict['street_number']
        user.provider.tel = provider_dict['tel']

        db.session.add(user.provider)

        return jsonify(provider_dict)

    elif user.user_type == 'payer':
        payer = user.payer

        exclude = [
            'guarantees_of_payment',
            'providers'
        ]

        # put the found object's data in a dictionary
        payer_dict = exclude_keys(exclude, prepare_payer_dict(payer))

        # write the POST paramteres into the dictionary
        payer_dict = from_post_to_dict(payer_dict, overwrite=True)

        validated, error = validate_email_address(payer_dict['pic_email'])
        if not validated:
            return 'Error: the "pic_email" parameter is wrong: %s' % error

        validated, error = validate_email_address(payer_dict['pic_alt_email'])
        if not validated:
            return 'Error: the "pic_alt_email" parameter is wrong: %s' % error

        user.payer.company = payer_dict['company']
        user.payer.country = payer_dict['country']
        user.payer.pic = payer_dict['pic']
        user.payer.pic_alt_email = payer_dict['pic_alt_email']
        user.payer.pic_email = payer_dict['pic_email']
        user.payer.postcode = payer_dict['postcode']
        user.payer.payer_type = payer_dict['payer_type']
        user.payer.state = payer_dict['state']
        user.payer.street_name = payer_dict['street_name']
        user.payer.street_number = payer_dict['street_number']
        user.payer.tel = payer_dict['tel']

        db.session.add(user.payer)

        return jsonify(payer_dict)

    else:
        return 'Error: no user is found'


@api.route('/payer/add/json', methods=['POST'])
def payer_add_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider' or user.role != 'user_admin':
        return 'Error: you are not able to add payers'

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
            'contract_number': None
            # 'guarantees_of_payment': None,
            # 'user_id': None,
        }

        # write the JSON paramteres into the dictionary
        payer_dict = from_json_to_dict(row, payer_dict)
        payers_list.append(payer_dict)

    for row_num, row in enumerate(payers_list):
        payer = models.Payer.query.filter_by(
            pic_email=row['pic_email']).first()
        if not payer:
            payer_user = models.User.query.filter_by(
                email=row['pic_email'], user_type='payer').first()
            if payer_user:
                payer = payer_user.payer

        validated, error = validate_email_address(row['pic_email'])
        if not validated:
            return 'Error: the "pic_email" parameter is wrong: %s' % error

        validated, error = validate_email_address(row['pic_alt_email'])
        if not validated:
            return 'Error: the "pic_alt_email" parameter is wrong: %s' % error

        if models.User.query.filter_by(
          email=row['pic_email'], user_type='provider').first():
            return 'Error: the "pic_email" is already registered'

        if not payer:
            payer = models.Payer(company=row['company'],
                                 payer_type=row['payer_type'],
                                 pic_email=row['pic_email'],
                                 pic_alt_email=row['pic_alt_email'],
                                 pic=row['pic'],
                                 tel=row['tel'],
                                 country=row['country'])

        if row['contract_number']:
            contract = models.Contract(provider=user.provider,
                                       payer=payer,
                                       number=row['contract_number'])
        else:
            contract = models.Contract(provider=user.provider,
                                       payder=payer,
                                       number=None)

        user.provider.payers.append(payer)

        db.session.add(payer)
        db.session.add(contract)
        db.session.add(user.provider)
        db.session.commit()

        payers_list[row_num]['id'] = payer.id

    return jsonify(payers_list)


@api.route('/payer/edit/json', methods=['POST'])
def payer_edit_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider' or user.role != 'user_admin':
        return 'Error: you are not able to edit payers'

    json = request.get_json()

    payers_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        payer_id = key
        payer = models.Payer.query.filter(
            db.and_(models.Payer.providers.any(id=user.provider.id), 
                    models.Provider.id==payer_id)).first()

        if not payer:
            return 'The Payer with the ' + \
                    'id = %s is not found.' % payer_id

        exclude = [
            'providers',
            'guarantees_of_payment',
            'state',
            'postcode',
            'street_name',
            'street_number',
        ]

        # put the found object's data in a dictionary
        payer_dict = exclude_keys(exclude, prepare_payer_dict(payer))

        payer_dict = from_json_to_dict(value, payer_dict, overwrite=True)
        payers_list.append(payer_dict)

    for row in payers_list:
        payer = models.Payer.query.get(row['id'])

        validated, error = validate_email_address(row['pic_email'])
        if not validated:
            return 'Error: the "pic_email" parameter is wrong: %s' % error

        validated, error = validate_email_address(row['pic_alt_email'])
        if not validated:
            return 'Error: the "pic_alt_email" parameter is wrong: %s' % error

        if models.User.query.filter_by(
          email=row['pic_email'], user_type='provider').first():
            return 'Error: the "pic_email" is already registered'

        row['contract_number'] = payer.contract(user).number

        if json[str(row['id'])]['contract_number']:
            row['contract_number'] = json[str(row['id'])]['contract_number']

        payer.company = row['company']
        payer.payer_type = row['payer_type']
        payer.pic_email = row['pic_email']
        payer.pic_alt_email = row['pic_alt_email']
        payer.pic = row['pic']
        payer.tel = row['tel']
        payer.contract(user).number = row['contract_number']
        payer.country = row['country']

        db.session.add(payer)

    return jsonify(payers_list)


@api.route('/billing-code/add/json', methods=['POST'])
def billing_code_add_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider' or user.role != 'user_admin':
        return 'Error: you are not able to add billing codes'

    json = request.get_json()

    billing_codes_list = []

    for row in json:
        billing_code_dict = {
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

    for row_num, row in enumerate(billing_codes_list):
        try:
            row['room_and_board'] = float(row['room_and_board'])
        except (ValueError, TypeError):
            row['room_and_board'] = 0.0

        try:
            row['doctor_visit_fee'] = float(row['doctor_visit_fee'])
        except (ValueError, TypeError):
            row['doctor_visit_fee'] = 0.0

        try:
            row['doctor_consultation_fee'] = float(row['doctor_consultation_fee'])
        except (ValueError, TypeError):
            row['doctor_consultation_fee'] = 0.0

        try:
            row['specialist_visit_fee'] = float(row['specialist_visit_fee'])
        except (ValueError, TypeError):
            row['specialist_visit_fee'] = 0.0

        try:
            row['specialist_consultation_fee'] = float(
                row['specialist_consultation_fee'])
        except (ValueError, TypeError):
            row['specialist_consultation_fee'] = 0.0

        try:
            row['medicines'] = float(row['medicines'])
        except (ValueError, TypeError):
            row['medicines'] = 0.0

        try:
            row['administration_fee'] = float(row['administration_fee'])
        except (ValueError, TypeError):
            row['administration_fee'] = 0.0

        billing_code = models.BillingCode(
                provider=user.provider,
                room_and_board=row['room_and_board'],
                doctor_visit_fee=row['doctor_visit_fee'],
                doctor_consultation_fee=row['doctor_consultation_fee'],
                specialist_visit_fee=row['specialist_visit_fee'],
                specialist_consultation_fee=row['specialist_consultation_fee'],
                medicines=row['medicines'],
                administration_fee=row['administration_fee']
            )
        db.session.add(billing_code)
        db.session.commit()

        billing_codes_list[row_num]['id'] = billing_code.id

    return jsonify(billing_codes_list)


@api.route('/doctor/add/json', methods=['POST'])
def doctor_add_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider' or user.role != 'user_admin':
        return 'Error: you are not able to add doctors'

    json = request.get_json()

    doctors_list = []

    for row in json:
        doctor_dict = {
            'name': None,
            'department': None,
            'doctor_type': None,
            'photo': None
        }

        doctor_dict = from_json_to_dict(row, doctor_dict)
        doctors_list.append(doctor_dict)

    for row_num, row in enumerate(doctors_list):
        if row['photo']:
            photo_filename = row['photo']
        else:
            photo_filename = '/static/img/person-solid.png'

        doctor_types = ['GP', 'Specialist']

        if not row['name']:
            return 'Error: the "name" parameter cannot be empty'

        if not row['department']:
            return 'Error: the "department" parameter cannot be empty'

        if row['doctor_type'] not in doctor_types:
            return 'Error: the "doctor_type" is wrong, must be one of the'\
                + ' following parameteres: %s' % ' '.join(doctor_types)

        doctor = models.Doctor(provider=user.provider,
                               name=row['name'],
                               department=row['department'],
                               doctor_type=row['doctor_type'],
                               photo=photo_filename)

        db.session.add(doctor)
        db.session.commit()

        doctors_list[row_num]['id'] = doctor.id

    return jsonify(doctors_list)


@api.route('/billing-code/edit/json', methods=['POST'])
def billing_code_edit_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider' or user.role != 'user_admin':
        return 'Error: you are not able to edit billing codes'

    json = request.get_json()

    billing_codes_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        billing_code_id = key
        billing_code = models.BillingCode.query.filter_by(
            id=billing_code_id, provider=user.provider).first()

        if not billing_code:
            return 'The Billing Code with the ' + \
                    'id = %s is not found.' % billing_code_id

        # put the found object's data in a dictionary
        billing_code_dict = prepare_billing_code_dict(billing_code)

        billing_code_dict = from_json_to_dict(value, billing_code_dict,
                                              overwrite=True)
        billing_codes_list.append(billing_code_dict)

    for row in billing_codes_list:
        billing_code = models.BillingCode.query.get(row['id'])

        try:
            row['room_and_board'] = float(row['room_and_board'])
        except (ValueError, TypeError):
            row['room_and_board'] = 0.0

        try:
            row['doctor_visit_fee'] = float(row['doctor_visit_fee'])
        except (ValueError, TypeError):
            row['doctor_visit_fee'] = 0.0

        try:
            row['doctor_consultation_fee'] = float(row['doctor_consultation_fee'])
        except (ValueError, TypeError):
            row['doctor_consultation_fee'] = 0.0

        try:
            row['specialist_visit_fee'] = float(row['specialist_visit_fee'])
        except (ValueError, TypeError):
            row['specialist_visit_fee'] = 0.0

        try:
            row['specialist_consultation_fee'] = float(
                row['specialist_consultation_fee'])
        except (ValueError, TypeError):
            row['specialist_consultation_fee'] = 0.0

        try:
            row['medicines'] = float(row['medicines'])
        except (ValueError, TypeError):
            row['medicines'] = 0.0

        try:
            row['administration_fee'] = float(row['administration_fee'])
        except (ValueError, TypeError):
            row['administration_fee'] = 0.0

        billing_code.room_and_board = row['room_and_board']
        billing_code.doctor_visit_fee = row['doctor_visit_fee']
        billing_code.doctor_consultation_fee = row['doctor_consultation_fee']
        billing_code.specialist_visit_fee = row['specialist_visit_fee']
        billing_code.specialist_consultation_fee = row['specialist_consultation_fee']
        billing_code.medicines = row['medicines']
        billing_code.administration_fee = row['administration_fee']

        db.session.add(billing_code)

    return jsonify(billing_codes_list)


@api.route('/doctor/edit/json', methods=['POST'])
def doctor_edit_json():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider' or user.role != 'user_admin':
        return 'Error: you are not able to edit doctors'

    json = request.get_json()

    doctors_list = []

    # the keys of the json dictionary are the IDs of the objects
    for key, value in json.iteritems():
        doctor_id = key
        doctor = models.Doctor.query.filter_by(
            id=doctor_id, provider=user.provider).first()

        if not doctor:
            return 'The Doctor with the ' + \
                    'id = %s is not found.' % doctor_id

        # put the found object's data in a dictionary
        doctor_dict = prepare_doctor_dict(doctor)

        doctor_dict = from_json_to_dict(value, doctor_dict, overwrite=True)
        doctors_list.append(doctor_dict)

    for row in doctors_list:
        doctor = models.Doctor.query.get(row['id'])

        if row['photo']:
            photo_filename = row['photo']
        else:
            photo_filename = '/static/img/person-solid.png'

        doctor_types = ['GP', 'Specialist']

        if not row['name']:
            return 'Error: the "name" parameter cannot be empty'

        if not row['department']:
            return 'Error: the "department" parameter cannot be empty'

        if row['doctor_type'] not in doctor_types:
            return 'Error: the "doctor_type" is wrong, must be one of the'\
                + ' following parameteres: %s' % ' '.join(doctor_types)

        doctor.name = row['name']
        doctor.department = row['department']
        doctor.doctor_type = row['doctor_type']
        doctor.photo = photo_filename

        db.session.add(doctor)

    return jsonify(doctors_list)


@api.route('/system-settings/edit', methods=['POST'])
def system_settings_edit():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.user_type != 'provider' or user.role != 'user_admin':
        return 'Error: you are not able to edit the system settings'

    provider = user.provider

    # if the object is not found, return an empty JSON list
    if not provider:
        return jsonify([])

    exclude = [
        'billing_codes',
        'company',
        'country',
        'doctors',
        'guarantees_of_payment',
        'payers',
        'pic',
        'pic_alt_email',
        'pic_email',
        'postcode',
        'provider_type',
        'state',
        'street_name',
        'street_number',
        'tel',
        'id'
    ]

    # put the found object's data in a dictionary
    provider_dict = exclude_keys(exclude, prepare_provider_dict(provider))

    # write the POST paramteres into the dictionary
    provider_dict = from_post_to_dict(provider_dict, overwrite=True)

    user.provider.setup_serial_number = provider_dict['setup_serial_number']
    user.provider.setup_server_url = provider_dict['setup_server_url']
    user.provider.setup_server_port = provider_dict['setup_server_port']
    user.provider.setup_module_name = provider_dict['setup_module_name']
    user.provider.setup_proxy_url = provider_dict['setup_proxy_url']
    user.provider.setup_proxy_port = provider_dict['setup_proxy_port']
    user.provider.setup_username = provider_dict['setup_username']
    user.provider.setup_password = provider_dict['setup_password']
    user.provider.setup_request_url = provider_dict['setup_request_url']
    user.provider.setup_default_path = provider_dict['setup_default_path']
    user.provider.setup_language = provider_dict['setup_language']

    db.session.add(user.provider)

    return jsonify(provider_dict)


@api.route('/user-settings/edit', methods=['POST'])
def user_settings_edit():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    if user.role != 'user_admin':
        return 'Error: you are not able to change user settings'

    exclude = [
        'id',
        'provider_id',
        'payer_id',
        'user_type',
    ]

    # put the found object's data in a dictionary
    user_dict = exclude_keys(exclude, prepare_user_dict(user))
    # write the POST paramteres into the dictionary
    user_dict = from_post_to_dict(user_dict, overwrite=True)

    validated, error = validate_email_address(user_dict['email'])
    if not validated:
        return 'Error: the "email" parameter is wrong: %s' % error

    if models.User.query.filter_by(
          email=user_dict['email']).first() and \
            user.email != user_dict['email']:
            return 'Error: the "email" is already registered'

    user.name = user_dict['name']
    user.email = user_dict['email']
    db.session.add(user)

    return jsonify(user_dict)


@api.route('/account-settings/edit', methods=['POST'])
def account_settings_edit():
    authorized, error, user = authorize_api_key()

    if not authorized:
        return error

    # put the found object's data in a dictionary
    user_dict = prepare_user_dict(user)
    # write the POST paramteres into the dictionary
    user_dict = from_post_to_dict(user_dict, overwrite=True)

    return jsonify(user_dict)