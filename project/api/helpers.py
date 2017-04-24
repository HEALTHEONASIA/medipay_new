from flask import request
from flask_login import current_user

from .. import db, models

# prepare models dictionaries
def prepare_gop_dict(gop):
    """The function takes the GOP model object
    and convert it to the python dictionary"""

    if not gop.timestamp_edited:
        timestamp_edited = None
    else:
        timestamp_edited = gop.timestamp_edited.strftime('%I:%M %p %m/%d/%Y')

    icd_codes_ids = []
    for icd_code in gop.icd_codes:
        icd_codes_ids.append(icd_code.id)

    gop_dict = {
        'id': gop.id,
        'provider_id': str(gop.provider.id),
        'payer_id': str(gop.payer.id),
        'member_id': str(gop.member.id),
        'member_name': gop.member.name,
        'member_dob': gop.member.dob,
        'member_tel': gop.member.tel,
        'member_gender': gop.member.gender,
        'policy_number': gop.policy_number,
        'icd_codes': icd_codes_ids,
        'patient_action_plan': gop.patient_action_plan,
        'admission_date': gop.admission_date.strftime('%m/%d/%Y'),
        'admission_time': gop.admission_time.strftime('%I:%M %p'),
        'reason': gop.reason,
        'doctor_name': gop.doctor_name,
        'room_price': gop.room_price,
        'room_type': gop.room_type,
        'patient_medical_no': gop.patient_medical_no,
        'doctor_fee': gop.doctor_fee,
        'surgery_fee': gop.surgery_fee,
        'medication_fee': gop.medication_fee,
        'quotation': gop.quotation,
        'timestamp': gop.timestamp.strftime('%I:%M %p %m/%d/%Y'),
        'status': gop.status,
        'state': gop.state,
        'reason_decline': gop.reason_decline,
        'reason_close': gop.reason_close,
        'timestamp_edited': timestamp_edited,
        'stamp_author': gop.stamp_author,
        'turnaround_time': gop.turnaround_time()
    }

    return gop_dict


def prepare_provider_dict(provider):
    if not provider:
        return None

    gop_ids = []

    for gop in provider.guarantees_of_payment:
        gop_ids.append(str(gop.id))

    billing_code_ids = []

    for billing_code in provider.billing_codes:
        billing_code_ids.append(str(billing_code.id))

    doctor_ids = []

    for doctor in provider.doctors:
        doctor_ids.append(str(doctor.id))

    payer_ids = []

    for payer in provider.payers:
        payer_ids.append(str(payer.id))

    # contracts = []

    # for contract in provider.contracts:
    #     contracts.append(str(contract.id))

    provider_dict = {
        'id': provider.id,
        'company': provider.company,
        'provider_type': provider.provider_type,
        'pic': provider.pic,
        'pic_email': provider.pic_email,
        'pic_alt_email': provider.pic_alt_email,
        'tel': provider.tel,
        'country': provider.country,
        'street_name': provider.street_name,
        'street_number': provider.street_number,
        'state': provider.state,
        'postcode': provider.postcode,
        'guarantees_of_payment': gop_ids,
        'billing_codes': billing_code_ids,
        'doctors': doctor_ids,
        'payers': payer_ids,
        # 'contracts': contracts,
        # 'user_id':
        'setup_serial_number': provider.setup_serial_number,
        'setup_server_url': provider.setup_server_url,
        'setup_server_port': provider.setup_server_port,
        'setup_module_name': provider.setup_module_name,
        'setup_proxy_url': provider.setup_proxy_url,
        'setup_proxy_port': provider.setup_proxy_port,
        'setup_username': provider.setup_username,
        'setup_password': provider.setup_password,
        'setup_request_url': provider.setup_request_url,
        'setup_default_path': provider.setup_default_path,
        'setup_language': provider.setup_language
    }

    return provider_dict


def prepare_payer_dict(payer):
    if not payer:
        return None

    gop_ids = []

    for gop in payer.guarantees_of_payment:
        gop_ids.append(str(gop.id))

    provider_ids = []

    for provider in payer.providers:
        provider_ids.append(str(provider.id))

    # contracts = []

    # for contract in payer.contracts:
    #     contracts.append(str(contract.id))

    payer_dict = {
        'id': payer.id,
        'company': payer.company,
        'payer_type': payer.payer_type,
        'pic': payer.pic,
        'pic_email': payer.pic_email,
        'pic_alt_email': payer.pic_alt_email,
        'tel': payer.tel,
        'country': payer.country,
        'street_name': payer.street_name,
        'street_number': payer.street_number,
        'state': payer.state,
        'postcode': payer.postcode,
        'guarantees_of_payment': gop_ids,
        'providers': provider_ids,
        # 'contracts': contracts,
        # 'user_id':
    }

    return payer_dict


def prepare_doctor_dict(doctor):
    if not doctor:
        return None

    doctor_dict = {
        'id': doctor.id,
        'provider_id': doctor.provider_id,
        'name': doctor.name,
        'department': doctor.department,
        'doctor_type': doctor.doctor_type,
        'photo': doctor.photo
    }

    return doctor_dict


def prepare_billing_code_dict(billing_code):
    if not billing_code:
        return None

    billing_code_dict = {
        'id': billing_code.id,
        'provider_id': billing_code.provider_id,
        'room_and_board': billing_code.room_and_board,
        'doctor_visit_fee': billing_code.doctor_visit_fee,
        'doctor_consultation_fee': billing_code.doctor_consultation_fee,
        'specialist_visit_fee': billing_code.specialist_visit_fee,
        'specialist_consultation_fee': \
            billing_code.specialist_consultation_fee,
        'medicines': billing_code.medicines,
        'administration_fee': billing_code.administration_fee
    }

    return billing_code_dict


def prepare_icd_code_dict(icd_code):
    if not icd_code:
        return None

    icd_code_dict = {
        'id': icd_code.id,
        'code': icd_code.code,
        'edc': icd_code.edc,
        'description': icd_code.description,
        'common_term': icd_code.common_term
    }

    return icd_code_dict


def prepare_user_dict(user):
    if not user:
        return None

    if user.provider:
        provider_id = str(user.provider.id)
    else:
        provider_id = ''

    if user.payer:
        payer_id = str(user.payer.id)
    else:
        payer_id = ''

    user_dict = {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'provider_id': provider_id,
        'payer_id': payer_id,
        'user_type': user.user_type,
        'role': user.role,
    }

    return user_dict


# prepare models lists
def prepare_gops_list(gops):
    """The function takes the GOP model objects list and convert it to the
    python dictionary"""

    if not gops:
        return []

    # initialize the results list
    results = []

    for gop in gops:
        results.append(prepare_gop_dict(gop))

    return results


def prepare_providers_list(providers):
    if not providers:
        return []

    # initialize the results list
    results = []

    for provider in providers:
        results.append(prepare_provider_dict(provider))

    return results


def prepare_payers_list(payers):
    if not payers:
        return []

    # initialize the results list
    results = []

    for payer in payers:
        results.append(prepare_payer_dict(payer))

    return results


def prepare_doctors_list(doctors):
    """The function takes the GOP model objects list and convert it to the
    python dictionary"""

    if not doctors:
        return []

    # initialize the results list
    results = []

    for doctor in doctors:
        results.append(prepare_doctor_dict(doctor))

    return results


def prepare_billing_codes_list(billing_codes):
    if not billing_codes:
        return []

    # initialize the results list
    results = []

    for billing_code in billing_codes:
        results.append(prepare_billing_code_dict(billing_code))

    return results


def prepare_icd_codes_list(icd_codes):
    if not icd_codes:
        return []

    results = []  # Initialize the results list

    for icd_code in icd_codes:
        results.append(prepare_icd_code_dict(icd_code))

    return results


def prepare_users_list(users):
    if not users:
        return []

    results = [] # Initialize the results list

    for user in users:
        results.append(prepare_user_dict(user))

    return results


def from_post_to_dict(dest_dict, overwrite=False):
    for key, value in dest_dict.iteritems():
        if not overwrite:
            # If it is the adding operation,
            # the all parameters are required
            if request.form.get(key):
                dest_dict[key] = request.form.get(key)

            else:
                raise ValueError('Missing the required parameter "%s"', key)

        else:
            # In case it is the editing operaition, we change only
            # those parameters, that are available in the POST request
            if request.form.get(key):
                dest_dict[key] = request.form.get(key)

    return dest_dict


def from_json_to_dict(json_dict, dest_dict, overwrite=False):
    for key, value in dest_dict.iteritems():
        if not overwrite:
            # If it is the adding operation,
            # the all parameters are required
            if key in json_dict:
                dest_dict[key] = json_dict[key]

            else:
                raise ValueError('Missing the required parameter "%s"' % key)

        else:
            # In case it is the editing operaition, we change only
            # those parameters, that are available in the JSON
            if key in json_dict:
                dest_dict[key] = json_dict[key]

    return dest_dict


def authorize_api_key():
    api_key = request.args.get('api_key')

    if not api_key:
        # failure, return error, no user object
        return (False, 'API key is missing', None)

    user = models.User.query.filter_by(api_key=api_key).first()

    if not user:
        # failure, return error, no user object
        return (False, 'API key is wrong', None)

    # success, no errors, return user object
    return (True, None, user)


def exclude_keys(keys, dest):
    if keys:
        if type(dest) is dict:
            for key in keys:
                del dest[key]
        elif type(dest) is list:
            for row in dest:
                for key in keys:
                    del row[key]

    return dest
