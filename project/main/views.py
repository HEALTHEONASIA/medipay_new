import csv
import StringIO
import io
import time, os
import string
import random
import sys
import re
from datetime import datetime
from sqlalchemy import or_, and_
from flask import render_template, flash, redirect, request, session, jsonify
from flask import url_for, make_response, send_from_directory
from flask_login import login_user, current_user
from flask_mail import Message
from . import main
from .forms import GOPForm, GOPApproveForm
from .helpers import photo_file_name_santizer, pass_generator, csv_ouput
from .helpers import to_float_or_zero, validate_email_address
from .services import GuaranteeOfPaymentService, UserService
from .services import MedicalDetailsService, MemberService
from .. import models, db, config, mail, create_app
from .. import auth
from ..auth.forms import LoginForm
from ..auth.views import login_validation
from .helpers import prepare_gops_list
from ..models import User, login_required

gop_service = GuaranteeOfPaymentService()
user_service = UserService()
medical_details_service = MedicalDetailsService()
member_service = MemberService()

@main.route('/', methods=['GET', 'POST'])
def index():
    if not current_user.is_authenticated:
        form = LoginForm()
        if form.validate_on_submit():
            return login_validation(form)

        return render_template('home.html', menu_unpin=True, form=form,
                                            hide_help_widget=True)

    status = request.args.get('status',None)

    # if it is an admin account
    if current_user.get_role() == 'admin':
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
    return send_from_directory(os.path.join('static','uploads'),filename)


@main.route('/request', methods=['GET', 'POST'])
@login_required(types=['provider'])
def request_form():
    payers = current_user.provider.payers
    form = GOPForm()

    form.payer.choices += [(p.id, p.company) for p in \
        current_user.provider.payers]

    form.icd_codes.choices = [(i.id, i.code) for i in \
        models.ICDCode.query.filter(models.ICDCode.code != 'None' and \
        models.ICDCode.code != '')]

    form.doctor_name.choices += [(d.id, d.name + ' (%s)' % d.doctor_type) \
        for d in current_user.provider.doctors]

    # fixes a validation error when user didn't
    # fill in the previous admitted date field
    if request.method != 'POST':
        form.medical_details_previously_admitted.data = datetime.now()

    if form.validate_on_submit():
        photo_filename = photo_file_name_santizer(form.member_photo)

        member = models.Member.query.filter_by(
            national_id=form.national_id.data).first()

        if not member:
            member = models.Member(photo=photo_filename)
            member_service.update_from_form(member, form,
                                            exclude=['member_photo'])

        medical_details = medical_details_service.create(
            **{field.name.replace('medical_details_', ''): field.data \
            for field in form \
            if field.name.replace('medical_details_', '') \
            in medical_details_service.columns})

        payer = models.Payer.query.get(form.payer.data)

        gop = models.GuaranteeOfPayment(
            provider=current_user.provider,
            payer=payer,
            member=member,
            doctor_name=models.Doctor.query.get(form.doctor_name.data).name,
            status='pending',
            medical_details=medical_details)

        for icd_code_id in form.icd_codes.data:
            icd_code = models.ICDCode.query.get(icd_code_id)

            if icd_code:
                gop.icd_codes.append(icd_code)

        # update the gop request data from the form
        exclude = ['doctor_name', 'status', 'icd_codes']
        gop_service.update_from_form(gop, form, exclude=exclude)

        # if the payer is registered as a user in our system
        if gop.payer.user:
            recipient_email = gop.payer.pic_email \
                or gop.payer.pic_alt_email \
                or gop.payer.user.email

        # if no, we register him, set the random password and send
        # the access credentials to him
        else:
            recipient_email = gop.payer.pic_email
            user = models.User(email=gop.payer.pic_email,
                               password=pass_generator(size=8),
                               user_type='payer',
                               payer=gop.payer)
            db.session.add(user)

        msg = Message("Request for GOP - %s" % gop.provider.company,
                      sender=("MediPay",
                              "request@app.medipayasia.com"),
                      recipients=[recipient_email])

        msg.html = render_template("request-email.html", gop=gop,
                                   root=request.url_root, user=user,
                                   rand_pass = rand_pass, gop_id=gop.id)

        # send the email
        try:
            mail.send(msg)
        except Exception as e:
            pass

        flash('Your GOP request has been sent.')
        return redirect(url_for('main.index'))

    return render_template('request-form.html', form=form, payers=payers,
        bill_codes=current_user.provider.billing_codes)


@main.route('/request/<int:gop_id>', methods=['GET', 'POST'])
@login_required()
def request_page(gop_id):
    # prevents request page from crashing when the gop_id is larger than a integer
    if gop_id > sys.maxsize:
        flash('Request out of range')
        return redirect(url_for('main.index'))

    gop = models.GuaranteeOfPayment.query.get(gop_id)

    if not gop:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    # admin can see any GOP request
    if current_user.get_role() == 'admin':
        return redirect(url_for('admin.request_page', gop_id=gop.id))

    if current_user.get_type() == 'payer':
        if gop.payer.id != current_user.payer.id:
            flash('The GOP request #%d is not found.' % gop_id)
            return redirect(url_for('main.index'))

        if gop.status == 'pending':
            gop.status = 'in_review'
            gop.timestamp_edited = datetime.now()
            db.session.add(gop)

        if not gop.medical_details:
            medical_details = models.MedicalDetails(guarantee_of_payment=gop)
            db.session.add(gop)

        form = GOPApproveForm()
        if form.validate_on_submit():
            if form.reason_decline.data:
                gop.reason_decline = form.reason_decline.data
            gop.status = form.status.data
            gop.timestamp_edited = datetime.now()

            db.session.add(gop)
            
            flash('The GOP request has been %s.' % form.status.data)
            return redirect(url_for('main.index'))

        context = {
            'gop': gop,
            'icd_codes': gop.icd_codes,
            'form': form,
        }
        return render_template('request.html', **context)

    if gop.provider.id != current_user.provider.id:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    return render_template('request.html', gop=gop, icd_codes=gop.icd_codes)


@main.route('/request/<int:gop_id>/set-stamp-author', methods=['GET'])
@login_required()
def request_set_stamp_author(gop_id):
    if current_user.user_type != 'payer':
        return 'ERROR'

    gop = models.GuaranteeOfPayment.query.get(gop_id)

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

    gop = models.GuaranteeOfPayment.query.get(gop_id)

    # if no GOP is found, redirect to the home page
    if not gop:
        flash('No Guarantee of payment request #%d found.' % gop_id)
        return redirect(url_for('main.index'))

    csv_file_name = '%d_%s_GOP_Request' % (gop_id,
                                    gop.member.name.replace(' ', '_'))

    data = []
    # prepring the data to be written in csv
    data.append(['GOP Request Details'])
    data.append(['Payer Company Name',gop.payer.company])
    if gop.status and gop.payer.pic:
        if gop.status == 'approved':
            data.append(['Approved By',gop.payer.pic])
        elif gop.status == 'declined':
            data.append(['Rejected By',gop.payer.pic])
        elif gop.status == 'pending':
            data.append(['Sent By',gop.payer.pic])
        elif gop.status == 'in_review':
            data.append(['Reviewed By',gop.payer.pic])
        else:
            data.append(['Reviewed By',gop.payer.pic])
        data.append(['Time Stamp',gop.timestamp.strftime('%I:%M%p %m/%d/%Y')])
    else:
        if gop.payer.pic:
            data.append(['Reviewed By',gop.payer.pic])
            data.append(['Time Stamp',gop.timestamp.strftime('%I:%M%p %m/%d/%Y')])
        else:
            data.append(['Reviewed By','Unnamed'])
    if gop.provider.pic:
        data.append(['Requested By',gop.provider.pic])
        data.append(['Time Stamp',gop.timestamp.strftime('%I:%M %p')])
    else:
        data.append(['Requested By','Unnamed'])
        data.append(['Time Stamp','Unknown'])

    data.append(['Patient Details'])
    if gop.member.policy_number:
        data.append(['Policy Number',gop.member.policy_number])
    data.append(['Medical Record Number',gop.patient_medical_no])
    data.append(['Patient Name',gop.member.name])
    data.append(['Date Of Birth Name',gop.member.dob.strftime('%m/%d/%Y')])
    data.append(['Gender',gop.member.gender.title()])
    data.append(['Telephone Number',gop.member.tel])

    data.append(['Cost Estimation'])
    data.append(['Addmission Date',gop.admission_date.strftime('%m/%d/%Y')])
    data.append(['Addmission Time',gop.admission_time.strftime('%I:%M %p')])
    data.append(['Room Type',gop.room_type.upper()])
    data.append(['Room Price','%0.2f' % gop.room_price])
    data.append(['Doctor Fee','%0.2f' % gop.doctor_fee])
    data.append(['Surgery Fee','%0.2f' % gop.surgery_fee])
    data.append(['Medication Fee','%0.2f' % gop.medication_fee])
    data.append(['Total Price','%0.2f' % gop.quotation])

    data.append(['Medical Details'])
    data.append(['Doctor Name',gop.doctor_name])
    data.append(['Plan Of Action',gop.patient_action_plan])
    for icd_counter, icd_code in enumerate(gop.icd_codes):
        if icd_counter == 0:
            data.append(['ICD Codes', icd_code.code])
        else:
            data.append([' ', icd_code.code])

    return csv_ouput(csv_file_name, data)


@main.route('/request/<int:gop_id>/edit', methods=['GET', 'POST'])
@login_required(types=['provider'])
def request_page_edit(gop_id):
    gop = models.GuaranteeOfPayment.query.get(gop_id)

    # if no GOP is found or it is not the current user's GOP, 
    # redirect to the home page
    if not gop or gop.provider.id != current_user.provider.id:
        flash('GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    if gop.closed:
        flash('GOP request #%d is closed.' % gop_id)
        return redirect(url_for('main.index'))

    form = GOPForm()

    # as a provider can't change the GOP's payer after
    # request is sent we leave only the one select choice
    form.payer.choices = [(gop.payer.id, gop.payer.company)]

    form.icd_codes.choices = [(i.id, i.code) for i in \
        models.ICDCode.query.filter(models.ICDCode.code != 'None' and \
        models.ICDCode.code != '')]

    form.doctor_name.choices += [(d.id, d.name + ' (%s)' % d.doctor_type) \
                                for d in current_user.provider.doctors]

    final = request.args.get('final')

    # if the GOP's info is updated
    if form.validate_on_submit():
        # check if it's the FINAL GOP request sending

        if final and not gop.final:
            gop.final = True

        # get and set the payer object
        payer = models.Payer.query.get(form.payer.data)
        gop.payer = payer

        filename = photo_file_name_santizer(form.member_photo)

        # update patient's medical details
        gop.medical_details.symptoms = \
            form.medical_details_symptoms.data
        gop.medical_details.temperature = \
            form.medical_details_temperature.data
        gop.medical_details.heart_rate = \
            form.medical_details_heart_rate.data
        gop.medical_details.respiration = \
            form.medical_details_respiration.data
        gop.medical_details.blood_pressure = \
            form.medical_details_blood_pressure.data
        gop.medical_details.physical_finding = \
            form.medical_details_physical_finding.data
        gop.medical_details.health_history = \
            form.medical_details_health_history.data
        gop.medical_details.previously_admitted = \
            form.medical_details_previously_admitted.data
        gop.medical_details.diagnosis = \
            form.medical_details_diagnosis.data
        gop.medical_details.in_patient = \
            form.medical_details_in_patient.data
        gop.medical_details.test_results = \
            form.medical_details_test_results.data
        gop.medical_details.current_therapy = \
            form.medical_details_current_therapy.data
        gop.medical_details.treatment_plan = \
            form.medical_details_treatment_plan.data

        # update the patient info
        member_service.update_from_form(gop.member, form,
                                        exclude=['member_photo'])

        if filename:
            gop.member.photo = filename

        for icd_code_id in form.icd_codes.data:
            icd_code = models.ICDCode.query.get(int(icd_code_id))
            gop.icd_codes.append(icd_code)

        gop.doctor_name = models.Doctor.query.get(int(form.doctor_name.data)).name

        if gop.final:
            gop.status = None

        exclude = ['doctor_name', 'status', 'icd_codes']
        gop_service.update_from_form(gop, form, exclude=exclude)

        if gop.final and final:
            if gop.payer.user:
                if gop.payer.pic_email:
                    recipient_email = gop.payer.pic_email
                elif gop.payer.pic_alt_email:
                    recipient_email = gop.payer.pic_alt_email
                else:
                    recipient_email = gop.payer.user.email
            else:
                recipient_email = gop.payer.pic_email

            msg = Message("Request for GOP - %s" % gop.provider.company,
                          sender=("MediPay",
                                  "request@app.medipayasia.com"),
                          recipients=[recipient_email])

            msg.html = render_template("request-email.html", gop=gop,
                                       root=request.url_root)

            # send the email
            try:
                mail.send(msg)
            except Exception as e:
                pass

        flash('The GOP request has been updated.')
        return redirect(url_for('main.request_page', gop_id=gop.id))

    # set the default select option as the current GOP's payer
    form.payer.default = gop.payer.id
    # set the default radio choice as the current GOP's room type
    form.room_type.default = gop.room_type
    form.reason.default = gop.reason
    doctor =  models.Doctor.query.filter_by(name=gop.doctor_name).first()
    form.doctor_name.default = doctor.id if doctor else 0

    icd_code_ids = []
    icd_code_id_name_web = []
    for icd_code in gop.icd_codes:
            icd_code_ids.append(icd_code.id)
            icd_code_id_name_web.append((icd_code.id,icd_code.common_term))

    form.icd_codes.default = icd_code_ids
    form.medical_details_in_patient.default = \
        gop.medical_details.in_patient

    # when update the form field's properties, we need to reinitiate the form
    form.process()

    # fill in medical details
    form.medical_details_symptoms.data = gop.medical_details.symptoms
    form.medical_details_temperature.data = \
        gop.medical_details.temperature
    form.medical_details_heart_rate.data = \
        gop.medical_details.heart_rate
    form.medical_details_respiration.data = \
        gop.medical_details.respiration
    form.medical_details_blood_pressure.data = \
        gop.medical_details.blood_pressure
    form.medical_details_physical_finding.data = \
        gop.medical_details.physical_finding
    form.medical_details_health_history.data = \
        gop.medical_details.health_history
    form.medical_details_previously_admitted.data = \
        gop.medical_details.previously_admitted
    form.medical_details_diagnosis.data = gop.medical_details.diagnosis
    form.medical_details_test_results.data = \
        gop.medical_details.test_results
    form.medical_details_current_therapy.data = \
        gop.medical_details.current_therapy
    form.medical_details_treatment_plan.data = \
        gop.medical_details.treatment_plan

    form.name.data = gop.member.name
    form.national_id.data = gop.member.national_id
    form.current_national_id.data = gop.member.national_id
    # convert the datetime python object to the string representation
    form.dob.data = gop.member.dob
    form.gender.data = gop.member.gender
    form.tel.data = gop.member.tel
    form.policy_number.data = gop.member.policy_number
    form.patient_action_plan.data = gop.patient_action_plan
    # convert the datetime python object to the string representation
    form.admission_date.data = gop.admission_date
    # convert the datetime python object to the string representation
    form.admission_time.data = gop.admission_time
    form.room_price.data = gop.room_price
    form.patient_medical_no.data = gop.patient_medical_no
    form.doctor_fee.data = gop.doctor_fee
    form.surgery_fee.data = gop.surgery_fee
    form.medication_fee.data = gop.medication_fee
    form.quotation.data = gop.quotation
    
    return render_template('request-form.html', form=form,
        member_photo=gop.member.photo, bill_codes=gop.provider.billing_codes,
        gop_id=gop.id, final=final, icd_code_id_name_web=icd_code_id_name_web)


@main.route('/request/<int:gop_id>/resend', methods=['GET'])
@login_required(types=['provider'])
def request_page_resend(gop_id):
    gop = models.GuaranteeOfPayment.query.get(gop_id)

    # if no GOP is found, redirect to the home page
    if not gop or gop.provider.id != current_user.provider.id:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    gop.status = ""
    gop.timestamp_edited = None
    gop.timestamp = datetime.now()

    if gop.payer.user:
        if gop.payer.pic_email:
            recipient_email = gop.payer.pic_email
        elif gop.payer.pic_alt_email:
            recipient_email = gop.payer.pic_alt_email
        else:
            recipient_email = gop.payer.user.email
    else:
        recipient_email = gop.payer.pic_email

    msg = Message("Request for GOP - %s" % gop.provider.company,
                  sender=("MediPay",
                          "request@app.medipayasia.com"),
                  recipients=[recipient_email])

    msg.html = render_template("request-email.html", gop=gop,
                               root=request.url_root)

    # send the email
    mail.send(msg)

    db.session.add(gop)
    flash('The GOP request has been resent.')
    return redirect(url_for('main.request_page', gop_id=gop.id))


@main.route('/request/<int:gop_id>/close/<reason>', methods=['GET'])
@login_required(types=['provider'])
def request_page_close(gop_id, reason):
    gop = models.GuaranteeOfPayment.query.get(gop_id)

    # if no GOP is found, redirect to the home page
    if not gop or gop.provider.id != current_user.provider.id:
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
    if current_user.role == 'admin':
        return redirect(url_for('admin.history'))

    if current_user.user_type == 'provider':
        gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider, closed=True)
    elif current_user.user_type == 'payer':
        gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer, closed=True)

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

    gops_all = models.GuaranteeOfPayment.query.all()
    gops_current = []

    if current_user.role == 'admin':
        gops_current = gops_all
    else:
        if current_user.user_type == 'provider':
            for gop in gops_all:
                if gop.provider.id == current_user.provider.id:
                    gops_current.append(gop)

        elif current_user.user_type == 'payer':
            for gop in gops_all:
                if gop.payer.id == current_user.payer.id:
                    gops_current.append(gop)

    for gop in gops_current:
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

    icd_codes = models.ICDCode.query.all()

    result = []
    fields = ['code', 'description', 'common_term']
    find = lambda query, obj, attr: query in getattr(obj, attr).lower()
    
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

    gops = models.GuaranteeOfPayment.query.filter(
        models.GuaranteeOfPayment.id > 0)

    if country and provider:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(db.and_(models.Provider.country == country,
                                   models.Provider.company == provider))\
                   .filter(not models.GuaranteeOfPayment.closed)

    elif country:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(models.Provider.country == country)\
                   .filter(not models.GuaranteeOfPayment.closed)

    elif provider:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(models.Provider.company == provider)\
                   .filter(not models.GuaranteeOfPayment.closed)

    if payer:
        gops = gops.join(models.Payer,
                         models.GuaranteeOfPayment.payer_id == \
                         models.Payer.id)\
                   .filter(models.Payer.company == payer)\
                   .filter(not models.GuaranteeOfPayment.closed)

    if status:
        gops = gops.filter(models.GuaranteeOfPayment.status == status)\
                   .filter(not models.GuaranteeOfPayment.closed)

    gops = gops.all()

    return render_template('requests-filter-results.html', gops=gops)

@main.route('/billing-code/<int:bill_id>/get', methods=['GET'])
@login_required()
def billing_code_get(bill_id):
    if not current_user.is_authenticated or \
      current_user.user_type != 'provider':
        return jsonify({})

    bill_code = models.BillingCode.query.get(bill_id)

    if not bill_code:
        return jsonify({})

    # if it is not the current provider's code
    if bill_code.provider.id != current_user.provider.id:
        return jsonify({})

    output = {
        'room_and_board': bill_code.room_and_board,
        'doctor_visit_fee': bill_code.doctor_visit_fee,
        'doctor_consultation_fee': bill_code.doctor_consultation_fee,
        'specialist_visit_fee': bill_code.specialist_visit_fee,
        'specialist_consultation_fee': bill_code.specialist_consultation_fee,
        'medicines': bill_code.medicines,
        'administration_fee': bill_code.administration_fee
    }

    return jsonify(output)


@main.route('/get-gops', methods=['GET'])
@login_required()
def get_gops():
    page = request.args.get('page')
    sort = request.args.get('sort')

    if current_user.role == 'admin':
        country = request.args.get('country')
        provider = request.args.get('provider')
        payer = request.args.get('payer')
        status = request.args.get('status')

        gops = models.GuaranteeOfPayment.query.filter(
            models.GuaranteeOfPayment.id > 0)

        if country and provider:
            gops = gops.join(models.Provider,
                             models.GuaranteeOfPayment.provider_id == \
                             models.Provider.id)\
                       .filter(db.and_(models.Provider.country == country,
                                       models.Provider.company == provider))\
                       .filter(not models.GuaranteeOfPayment.closed)

        elif country:
            gops = gops.join(models.Provider,
                             models.GuaranteeOfPayment.provider_id == \
                             models.Provider.id)\
                       .filter(models.Provider.country == country)\
                       .filter(not models.GuaranteeOfPayment.closed)

        elif provider:
            gops = gops.join(models.Provider,
                             models.GuaranteeOfPayment.provider_id == \
                             models.Provider.id)\
                       .filter(models.Provider.company == provider)\
                       .filter(not models.GuaranteeOfPayment.closed)

        if payer:
            gops = gops.join(models.Payer,
                             models.GuaranteeOfPayment.payer_id == \
                             models.Payer.id)\
                       .filter(models.Payer.company == payer)\
                       .filter(not models.GuaranteeOfPayment.closed)

        if status:
            gops = gops.filter(models.GuaranteeOfPayment.status == status)\
                       .filter(not models.GuaranteeOfPayment.closed)

    elif current_user.user_type == 'provider':
        gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider).filter(
            not models.GuaranteeOfPayment.closed)

    elif current_user.user_type == 'payer':
        gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer).filter(
            not models.GuaranteeOfPayment.closed)

    if sort:
        if sort == 'status':
            gops = gops.group_by(models.GuaranteeOfPayment.status)

        elif sort == 'patient':
            gops = gops.group_by(models.GuaranteeOfPayment.member.name)

        elif sort == 'payer':
            gops = gops.group_by(models.GuaranteeOfPayment.payer.company)

        elif sort == 'time':
            gops = gops.group_by(models.GuaranteeOfPayment.turnaround_time)

    if page or pagination.pages > 1:
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
        return jsonify(prepare_gops_list(gops.paginate(page=page).items))

    gops = gops.all()

    return jsonify(prepare_gops_list(gops))