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
        'patient_id': str(gop.patient.id),
        'payer_company': gop.payer.company,
        'provider_company': gop.provider.company,
        'patient_name': gop.patient.name,
        'patient_dob': gop.patient.dob,
        'patient_tel': gop.patient.tel,
        'patient_gender': gop.patient.gender,
        'policy_number': gop.policy_number,
        'icd_codes': icd_codes_ids,
        'patient_action_plan': gop.patient_action_plan,
        'doctor_notes': gop.doctor_notes,
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