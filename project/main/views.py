import csv
import random
import re
import os
import string
import sys
import time

from datetime import datetime

from flask import flash, jsonify, render_template, redirect, request, session
from flask import make_response, send_from_directory, url_for
from flask_login import current_user, login_user
from sqlalchemy import and_, or_

from . import main
from .forms import GOPForm, GOPApproveForm
from .helpers import csv_ouput, pass_generator, photo_file_name_santizer
from .helpers import to_float_or_zero, validate_email_address
from .helpers import prepare_gops_list, notify, is_admin, is_provider, is_payer
from .services import GuaranteeOfPaymentService, UserService
from .services import MedicalDetailsService, MemberService
from .. import config, create_app, db, redis_store, models
from .. import auth
from ..auth.forms import LoginForm
from ..auth.views import login_validation
from ..models import BillingCode, Chat, ChatMessage, Doctor
from ..models import GuaranteeOfPayment, ICDCode, login_required, Member
from ..models import Payer, Provider, User


gop_service = GuaranteeOfPaymentService()
medical_details_service = MedicalDetailsService()
member_service = MemberService()
user_service = UserService()


@main.route('/', methods=['GET', 'POST'])
def index():
    if not current_user.is_authenticated:
        form = LoginForm()

        if form.validate_on_submit():
            return login_validation(form)

        return render_template('home.html', menu_unpin=True, form=form,
                               hide_help_widget=True)

    status = request.args.get('status', None)

    # if it is an admin account
    if is_admin(current_user):
        return redirect(url_for('admin.index'))

    open_gops = gop_service.get_open_all()

    user_gops = gop_service.filter_for_user(open_gops, current_user)

    if status in ['approved', 'declined', 'in_review', 'pending']:
        gops = user_gops.filter_by(status=status)
    elif status == 'initial':
        gops = user_gops.filter_by(final=False)
    elif status == 'final':
        gops = user_gops.filter_by(final=True)
    else:
        gops = user_gops

    in_review_count = user_gops.filter_by(status='in_review').count()
    approved_count = user_gops.filter_by(status='approved').count()
    rejected_count = user_gops.filter_by(status='declined').count()
    pending_count = user_gops.filter_by(status='pending').count()

    total_count = gops.count()

    today = datetime.now()

    pagination, gops = gop_service.prepare_pagination(gops)

    context = {
        'gops': gops,
        'pagination': pagination,
        'status':status,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'total_count': total_count,
        'in_review_count': in_review_count,
        'pending_count': pending_count,
        'today': today
    }

    return render_template('index.html', **context)


@main.route('/static/uploads/<filename>')
@login_required()
def block_unauthenticated_url(filename):
    return send_from_directory(os.path.join('static', 'uploads'), filename)


@main.route('/request', methods=['GET', 'POST'])
@login_required(types=['provider'])
def request_form():
    form = GOPForm()

    form.payer.choices = [('0', 'None')]
    form.payer.choices += [(p.id, p.company) for p \
                           in current_user.provider.payers]

    form.icd_codes.choices = [(i.id, i.code) for i in ICDCode.query.all()]

    form.doctor_name.choices = [('0', 'None')]
    form.doctor_name.choices += [(d.id, d.name + ' (%s)' % d.doctor_type) \
                                 for d in current_user.provider.doctors]

    # fixes a validation error when user didn't
    # fill in the previous admitted date field
    if request.method != 'POST':
        form.medical_details_previously_admitted.data = datetime.now()

    if form.validate_on_submit():
        photo_filename = photo_file_name_santizer(form.member_photo)

        member = Member.query.filter_by(
            national_id=form.national_id.data).first()

        if not member:
            member = Member(photo=photo_filename)
            member_service.update_from_form(member, form,
                                            exclude=['member_photo'])

        # prepare a medical_details args* dict
        mdetails_dict = {}

        for field in form:
            fname = field.name.replace('medical_details_', '')

            if fname in medical_details_service.columns:
                mdetails_dict[fname] = field.data

        medical_details = medical_details_service.create(**mdetails_dict)

        payer = Payer.query.get(form.payer.data)

        gop = GuaranteeOfPayment(provider=current_user.provider,
                                 payer=payer,
                                 member=member,
                                 doctor_name=Doctor.query.get(
                                    form.doctor_name.data).name,
                                 status='pending',
                                 medical_details=medical_details)

        for icd_code_id in form.icd_codes.data:
            icd_code = ICDCode.query.get(icd_code_id)

            if icd_code:
                gop.icd_codes.append(icd_code)

        # update the gop request data from the form
        exclude = ['doctor_name', 'status', 'icd_codes']
        gop_service.update_from_form(gop, form, exclude=exclude)

        chat = Chat(name='gop%d' % gop.id, gop_id=gop.id)
        db.session.add(chat)
        db.session.commit()

        msg = 'New GOP request is added'
        url = url_for('main.request_page', gop_id=gop.id)
        notify('New GOP request', msg, url, user=gop.payer.user)

        gop_service.send_email(gop)

        flash('Your GOP request has been sent.')
        return redirect(url_for('main.index'))

    return render_template('request-form.html', form=form,
                           bill_codes=current_user.provider.billing_codes)


@main.route('/request/<int:gop_id>', methods=['GET', 'POST'])
@login_required()
def request_page(gop_id):
    # prevents request page from crashing when the gop_id is larger than a integer
    if gop_id > sys.maxsize:
        flash('Request out of range')
        return redirect(url_for('main.index'))

    gop = GuaranteeOfPayment.query.get(gop_id)

    if not gop:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    gop_service.set_chat_room(gop)

    # admin can see any GOP request
    if is_admin(current_user):
        return redirect(url_for('admin.request_page', gop_id=gop.id))

    if is_payer(current_user):
        if gop.payer.id != current_user.payer.id:
            flash('The GOP request #%d is not found.' % gop_id)
            return redirect(url_for('main.index'))

        if gop.status == 'pending':

            msg = 'GOP request is under review'
            url = url_for('main.request_page', gop_id=gop.id)
            notify('Your GOP request is under review', msg, url,
                   user=gop.provider.user)

            gop.status = 'in_review'
            gop.timestamp_edited = datetime.now()
            db.session.add(gop)

        form = GOPApproveForm()
        if form.validate_on_submit():
            if form.reason_decline.data:
                gop.reason_decline = form.reason_decline.data

            gop.status = form.status.data
            gop.timestamp_edited = datetime.now()

            db.session.add(gop)

            msg = 'GOP request status is changed to "%s"' % gop.status
            url = url_for('main.request_page', gop_id=gop.id)
            notify('Your GOP request status is changed', msg, url,
                   user=gop.provider.user)

            flash('The GOP request has been %s.' % form.status.data)
            return redirect(url_for('main.index'))

        context = {
            'gop': gop,
            'icd_codes': gop.icd_codes,
            'form': form
        }
        return render_template('request.html', **context)

    if gop.provider.id != current_user.provider.id:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    return render_template('request.html', gop=gop, icd_codes=gop.icd_codes)


@main.route('/request/<int:gop_id>/set-stamp-author', methods=['GET'])
@login_required()
def request_set_stamp_author(gop_id):
    if not is_payer(current_user):
        return 'ERROR'

    gop = GuaranteeOfPayment.query.get(gop_id)

    if not gop:
        return 'ERROR'

    if gop.payer.id != current_user.payer.id:
        return 'ERROR'

    name = request.args.get('name')

    if name:
        gop.stamp_author = name
        db.session.add(gop)
        return 'SUCCESS'
    else:
        return 'ERROR'


@main.route('/request/<int:gop_id>/download', methods=['GET'])
@login_required(types=['provider'])
def request_page_download(gop_id):
    if not current_user.premium:
        flash('To download the GOP request you need to upgrade your account.')
        return redirect(url_for('account.user_upgrade'))

    gop = gop_service.get_or_404(gop_id)

    csv_file_name = '%d_%s_GOP_Request' % (gop_id,
                                           gop.member.name.replace(' ', '_'))

    header = [
        'payer_company',
        'reviewed_by',
        'requested_by',
        'timestamp',
        'policy_number',
        'medical_record_no',
        'patient_name',
        'date_of_birth',
        'gender',
        'telephone',
        'admission_date',
        'admission_time',
        'room_type',
        'room_price',
        'doctor_fee',
        'surgery_fee',
        'medication_fee',
        'total_price',
        'doctor_name',
        'plan_of_action',
        'icd_codes'
    ]

    icd_codes = ', '.join([icd_code.code for icd_code in gop.icd_codes])

    data = [
        gop.payer.company,
        gop.payer.pic,
        gop.provider.pic,
        gop.timestamp.strftime('%I:%M %p'),
        gop.member.policy_number,
        gop.patient_medical_no,
        gop.member.name,
        gop.member.dob.strftime('%m/%d/%Y'),
        gop.member.gender.title(),
        gop.member.tel,
        gop.admission_date.strftime('%m/%d/%Y'),
        gop.admission_time.strftime('%I:%M %p'),
        gop.room_type.upper(),
        '%0.2f' % gop.room_price,
        '%0.2f' % gop.doctor_fee,
        '%0.2f' % gop.surgery_fee,
        '%0.2f' % gop.medication_fee,
        '%0.2f' % gop.quotation,
        gop.doctor_name,
        gop.patient_action_plan,
        icd_codes
    ]

    result = [header, data]

    return csv_ouput(csv_file_name, result)


@main.route('/request/<int:gop_id>/edit', methods=['GET', 'POST'])
@login_required(types=['provider'])
def request_page_edit(gop_id):
    gop = gop_service.get_or_404(gop_id)

    # if no GOP is found or it is not the current user's GOP, 
    # redirect to the home page
    if gop.provider.id != current_user.provider.id:
        flash('GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    if gop.closed:
        flash('GOP request #%d is closed.' % gop_id)
        return redirect(url_for('main.index'))

    form = GOPForm()

    # Provider cannot change a payer while editing
    form.payer.choices = [(gop.payer.id, gop.payer.company)]

    form.icd_codes.choices = [(i.id, i.code) for i in ICDCode.query.all()]

    form.doctor_name.choices = [('0', 'None')]
    form.doctor_name.choices += [(d.id, d.name + ' (%s)' % d.doctor_type) \
                                 for d in current_user.provider.doctors]

    final = request.args.get('final', None)

    # if the GOP's info is updated
    if form.validate_on_submit():
        # check if it's the FINAL GOP request sending

        if final:
            gop.final = True

        gop.member.photo = photo_file_name_santizer(form.member_photo)

        # update patient's medical details
        gop.medical_details.symptoms = form.medical_details_symptoms.data
        gop.medical_details.temperature = form.medical_details_temperature.data
        gop.medical_details.heart_rate = form.medical_details_heart_rate.data
        gop.medical_details.respiration = form.medical_details_respiration.data
        gop.medical_details.blood_pressure = \
            form.medical_details_blood_pressure.data
        gop.medical_details.physical_finding = \
            form.medical_details_physical_finding.data
        gop.medical_details.health_history = \
            form.medical_details_health_history.data
        gop.medical_details.previously_admitted = \
            form.medical_details_previously_admitted.data
        gop.medical_details.diagnosis = form.medical_details_diagnosis.data
        gop.medical_details.in_patient = form.medical_details_in_patient.data
        gop.medical_details.test_results = \
            form.medical_details_test_results.data
        gop.medical_details.current_therapy = \
            form.medical_details_current_therapy.data
        gop.medical_details.treatment_plan = \
            form.medical_details_treatment_plan.data

        # update the patient info
        member_service.update_from_form(gop.member, form,
                                        exclude=['member_photo'])

        for icd_code_id in form.icd_codes.data:
            icd_code = ICDCode.query.get(icd_code_id)
            gop.icd_codes.append(icd_code)

        gop.doctor_name = Doctor.query.get(form.doctor_name.data).name
        gop.status = 'pending'

        exclude = ['doctor_name', 'status', 'icd_codes']
        gop_service.update_from_form(gop, form, exclude=exclude)

        msg = 'GOP request status is changed to "%s" FINAL' % gop.status
        url = url_for('main.request_page', gop_id=gop.id)
        notify('The GOP request status is changed', msg, url,
               user=gop.payer.user)

        if gop.final:
            gop_service.send_email(gop)

        flash('The GOP request has been updated.')
        return redirect(url_for('main.request_page', gop_id=gop.id))

    # set the default select option as the current GOP's payer
    form.payer.default = gop.payer.id
    # set the default radio choice as the current GOP's room type
    form.room_type.default = gop.room_type
    form.reason.default = gop.reason
    doctor = Doctor.query.filter_by(name=gop.doctor_name).first()
    form.doctor_name.default = doctor.id if doctor else 0

    icd_code_ids = []
    icd_code_id_name_web = []
    for icd_code in gop.icd_codes:
        icd_code_ids.append(icd_code.id)
        icd_code_id_name_web.append((icd_code.id, icd_code.common_term))

    form.icd_codes.default = icd_code_ids
    form.medical_details_in_patient.default = gop.medical_details.in_patient

    # when update the form field's properties, we need to reinitiate the form
    form.process()

    m_details = gop.medical_details # shortcut

    # fill in medical details
    form.medical_details_symptoms.data = m_details.symptoms
    form.medical_details_temperature.data = m_details.temperature
    form.medical_details_heart_rate.data = m_details.heart_rate
    form.medical_details_respiration.data = m_details.respiration
    form.medical_details_blood_pressure.data = m_details.blood_pressure
    form.medical_details_physical_finding.data = m_details.physical_finding
    form.medical_details_health_history.data = m_details.health_history
    form.medical_details_previously_admitted.data = m_details.previously_admitted
    form.medical_details_diagnosis.data = gop.medical_details.diagnosis
    form.medical_details_test_results.data = m_details.test_results
    form.medical_details_current_therapy.data = m_details.current_therapy
    form.medical_details_treatment_plan.data = m_details.treatment_plan

    form.name.data = gop.member.name
    form.national_id.data = gop.member.national_id
    form.current_national_id.data = gop.member.national_id
    form.dob.data = gop.member.dob
    form.gender.data = gop.member.gender
    form.tel.data = gop.member.tel
    form.policy_number.data = gop.member.policy_number
    form.patient_action_plan.data = gop.patient_action_plan
    form.admission_date.data = gop.admission_date
    form.admission_time.data = gop.admission_time
    form.room_price.data = gop.room_price
    form.patient_medical_no.data = gop.patient_medical_no
    form.doctor_fee.data = gop.doctor_fee
    form.surgery_fee.data = gop.surgery_fee
    form.medication_fee.data = gop.medication_fee
    form.quotation.data = gop.quotation
    
    return render_template('request-form.html', form=form,
                           member_photo=gop.member.photo,
                           bill_codes=gop.provider.billing_codes,
                           gop_id=gop.id, final=final,
                           icd_code_id_name_web=icd_code_id_name_web)


@main.route('/request/<int:gop_id>/resend', methods=['GET'])
@login_required(types=['provider'])
def request_page_resend(gop_id):
    gop = GuaranteeOfPayment.query.get(gop_id)

    # if no GOP is found, redirect to the home page
    if not gop or gop.provider.id != current_user.provider.id:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    gop.status = 'pending'
    gop.timestamp_edited = None
    gop.timestamp = datetime.now()

    gop_service.send_email(gop)

    db.session.add(gop)
    flash('The GOP request has been resent.')
    return redirect(url_for('main.request_page', gop_id=gop.id))


@main.route('/request/<int:gop_id>/close/<reason>', methods=['GET'])
@login_required(types=['provider'])
def request_page_close(gop_id, reason):
    gop = gop_service.get_or_404(gop_id)

    # if no GOP is found, redirect to the home page
    if gop.provider.id != current_user.provider.id:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    if gop.closed:
        flash('The GOP request #%d is already closed.' % gop_id)
        return redirect(url_for('main.index'))

    gop.closed = True
    gop.reason_close = reason
    db.session.add(gop)

    flash('The GOP request has been closed.')
    return redirect(url_for('main.request_page', gop_id=gop.id))


@main.route('/history')
@login_required()
def history():
    # if it is admin, show him all the closed requests
    if is_admin(current_user):
        return redirect(url_for('admin.history'))

    if is_provider(current_user):
        gops = GuaranteeOfPayment.query.filter_by(provider=current_user.provider,
                                                  closed=True)
    elif is_payer(current_user):
        gops = GuaranteeOfPayment.query.filter_by(payer=current_user.payer,
                                                  closed=True)

    pagination, gops = gop_service.prepare_pagination(gops)


    return render_template('history.html', gops=gops, pagination=pagination)


@main.route('/search', methods=['GET'])
def search():
    found = {
        'results': []
    }
    query = request.args.get('query')

    if not query or not current_user.is_authenticated:
        return jsonify(found)

    query = query.lower()

    if is_admin(current_user):
        gops = gop_service.all()
    elif is_provider(current_user):
        gops = gop_service.find(provider_id=current_user.provider.id)
    elif is_payer(current_user):
        gops = gop_service.find(payer_id=current_user.payer.id)

    for gop in gops:
        # if query in gop.icd_codes.lower() \
        if query in gop.patient_action_plan.lower() \
        or query in gop.doctor_name.lower() \
        or query in str(gop.room_price) \
        or query in gop.room_type.lower() \
        or query in str(gop.patient_medical_no) \
        or query in str(gop.doctor_fee) \
        or query in str(gop.surgery_fee) \
        or query in str(gop.medication_fee) \
        or query in gop.member.name.lower() \
        or query in gop.member.gender.lower() \
        or query in str(gop.member.tel) \
        or (gop.payer.company and query in gop.payer.company.lower()):
            found['results'].append(gop.id)
            continue

    return jsonify(found)


@main.route('/icd-code/search', methods=['GET'])
def icd_code_search():
    query = request.args.get('query').lower()
    
    if not query:
        return render_template('icd-code-search-results.html',
                               icd_codes=None, query=query)

    icd_codes = ICDCode.query.all()

    result = []
    fields = ['code', 'description', 'common_term']

    def find(query, obj, attr): return query in getattr(obj, attr).lower()

    for icd_code in icd_codes:
        if any([find(query, icd_code, field) for field in fields]):
            result.append(icd_code)

    return render_template('icd-code-search-results.html', icd_codes=result,
                           query=query)


@main.route('/requests/filter', methods=['GET'])
@login_required(roles=['admin'])
def requests_filter():
    country = request.args.get('country')
    provider = request.args.get('provider')
    payer = request.args.get('payer')
    status = request.args.get('status')

    gops = gop_service.get_open_all()

    if country and provider:
        gops = gops.join(Provider,
                         GuaranteeOfPayment.provider_id == Provider.id)\
                   .filter(db.and_(Provider.country == country,
                                   Provider.company == provider))

    elif country:
        gops = gops.join(Provider,
                         GuaranteeOfPayment.provider_id == Provider.id)\
                   .filter(Provider.country == country)

    elif provider:
        gops = gops.join(Provider,
                         GuaranteeOfPayment.provider_id == Provider.id)\
                   .filter(Provider.company == provider)

    if payer:
        gops = gops.join(Payer,
                         GuaranteeOfPayment.payer_id == Payer.id)\
                   .filter(Payer.company == payer)

    if status:
        gops = gops.filter_by(status=status)

    gops = gops.all()

    return render_template('requests-filter-results.html', gops=gops)

@main.route('/billing-code/<int:bill_id>/get', methods=['GET'])
@login_required()
def billing_code_get(bill_id):
    if is_provider(current_user):
        return jsonify({})

    bill_code = BillingCode.query.get(bill_id)

    if not bill_code:
        return jsonify({})

    if bill_code.provider.id != current_user.provider.id:
        return jsonify({})

    output = {col: getattr(bill_code, col) for col in bill_code.columns()}

    return jsonify(output)


@main.route('/get-gops', methods=['GET'])
@login_required()
def get_gops():
    page = request.args.get('page')
    sort = request.args.get('sort')

    if is_admin(current_user):
        country = request.args.get('country')
        provider = request.args.get('provider')
        payer = request.args.get('payer')
        status = request.args.get('status')

        open_gops = gop_service.get_open_all()

        if country and provider:
            gops = open_gops.join(Provider,
                             GuaranteeOfPayment.provider_id == \
                             Provider.id)\
                       .filter(db.and_(Provider.country == country,
                                       Provider.company == provider))

        elif country:
            gops = open_gops.join(Provider,
                             GuaranteeOfPayment.provider_id == \
                             Provider.id)\
                       .filter(Provider.country == country)

        elif provider:
            gops = open_gops.join(Provider,
                             GuaranteeOfPayment.provider_id == \
                             Provider.id)\
                       .filter(Provider.company == provider)

        if payer:
            gops = open_gops.join(Payer,
                             GuaranteeOfPayment.payer_id == \
                             Payer.id)\
                       .filter(Payer.company == payer)

        if status:
            gops = open_gops.filter_by(status=status)

    elif is_provider(current_user):
        gops = GuaranteeOfPayment.query.filter_by(provider=current_user.provider,
                                                  closed=False)

    elif is_payer(current_user):
        gops = GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer, closed=False)

    if sort:
        if sort == 'status':
            gops = gops.group_by(GuaranteeOfPayment.status)

        elif sort == 'patient':
            gops = gops.group_by(GuaranteeOfPayment.member.name)

        elif sort == 'payer':
            gops = gops.group_by(GuaranteeOfPayment.payer.company)

        elif sort == 'time':
            gops = gops.group_by(GuaranteeOfPayment.turnaround_time)

    if page or pagination.pages > 1:
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
        return jsonify(prepare_gops_list(gops.paginate(page=page).items))

    gops = gops.all()

    return jsonify(prepare_gops_list(gops))