import csv
import StringIO
import io
import time, os
import string
import random
import sys
import re
from datetime import datetime
from sqlalchemy import or_,and_
from werkzeug.utils import secure_filename
from flask import render_template, flash, redirect, request, session, jsonify
from flask import url_for, make_response, send_from_directory
from flask_login import login_user, login_required, current_user
from flask_mail import Message
from . import main
from .forms import ChangeProviderInfoForm, ChangePayerInfoForm, GOPForm, SingleCsvForm
from .forms import GOPApproveForm, ProviderSetupForm, BillingCodeForm
from .forms import EditAccountForm, DoctorForm, ProviderPayerSetupEditForm
from .forms import ProviderPayerSetupAddForm, EditAccountAdminForm
from .forms import UserSetupForm, UserSetupAdminForm, UserUpgradeForm
from .. import models, db, config, mail, create_app
from .. import auth
from ..auth.forms import LoginForm
from ..auth.views import login_validation
from .helpers import prepare_gops_list
from ..models import User

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1] in config['development'].ALLOWED_EXTENSIONS

def pass_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def csv_ouput(csv_file_name, data):
    si = StringIO.StringIO()
    cw = csv.writer(si)
    cw.writerows(data)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=%s.csv" %csv_file_name
    output.headers["Content-type"] = "text/csv"
    return output

def validate_email_address(data):
    """Returns True or False"""
    if data:
        match = re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"\
          ,data)
        if match == None:
            return False

        if len(data) < 1 or len(data) > 64:
            return False

        return True

def to_float_or_zero(value):
    try:
        value = float(value)
    except ValueError:
        value = 0.0
    return value


@main.route('/', methods=['GET', 'POST'])
def index():
    if not current_user.is_authenticated:
        form = LoginForm()
        if form.validate_on_submit():
            return login_validation(form)
            
        return render_template('home.html', menu_unpin=True, form=form,
            hide_help_widget=True)

    page = request.args.get('page')
    status = request.args.get('status',None)

    # if it is an admin account
    if current_user.role == 'admin':
        gops = models.GuaranteeOfPayment.query.filter(
            models.GuaranteeOfPayment.state == None)

        in_review_count = models.GuaranteeOfPayment.query.filter_by(
            status='in review').filter(
            models.GuaranteeOfPayment.state == None).count()
        approved_count = models.GuaranteeOfPayment.query.filter_by(
            status='approved').filter(
            models.GuaranteeOfPayment.state == None).count()
        rejected_count = models.GuaranteeOfPayment.query.filter_by(
            status='declined').filter(
            models.GuaranteeOfPayment.state == None).count()
        total_count = gops.count()
        pending_count = total_count - (approved_count + rejected_count + \
            in_review_count)
        
        pagination = gops.paginate()

        # count all GOP's by its providers' country
        by_country_count = db.session\
            .query(models.Provider.country, db.func.count(
                models.Provider.country))\
            .join(models.GuaranteeOfPayment,
                  models.GuaranteeOfPayment.provider_id == models.Provider.id)\
            .group_by(models.Provider.country)\
            .filter(models.GuaranteeOfPayment.state == None).all()

        # count all GOP's by its providers' company
        by_provider_count = db.session\
            .query(models.Provider.company, db.func.count(
                models.Provider.company))\
            .join(models.GuaranteeOfPayment,
                  models.GuaranteeOfPayment.provider_id == models.Provider.id)\
            .group_by(models.Provider.company)\
            .filter(models.GuaranteeOfPayment.state == None).all()

        # count all GOP's by its payers's company
        by_payer_count = db.session\
            .query(models.Payer.company, db.func.count(
                models.Payer.company))\
            .join(models.GuaranteeOfPayment,
                  models.GuaranteeOfPayment.payer_id == models.Payer.id)\
            .group_by(models.Payer.company)\
            .filter(models.GuaranteeOfPayment.state == None).all()

        today = datetime.now()

        if page or pagination.pages > 1:
            try:
                page = int(page)
            except (ValueError, TypeError):
                page = 1
            gops = gops.paginate(page=page).items

        context = {
            'gops': gops,
            'pagination': pagination,
            'status':status,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'total_count': total_count,
            'in_review_count': in_review_count,
            'pending_count': pending_count,
            'by_country_count': by_country_count,
            'by_provider_count': by_provider_count,
            'by_payer_count': by_payer_count,
            'today': today
        }

        return render_template('index.html', **context)

    if current_user.user_type == 'provider':
        if status == 'approved' or status == 'declined' or status == 'in_review':
            gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider, status=status.replace('_',' ')).filter(
            models.GuaranteeOfPayment.state == None)
        elif status == 'pending':
            gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider).filter(
            and_(models.GuaranteeOfPayment.state == None,
            or_(models.GuaranteeOfPayment.status == None,models.GuaranteeOfPayment.status == 'pending')))
        elif status == 'initial':
            gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider).filter(
            and_(models.GuaranteeOfPayment.status == 'approved',models.GuaranteeOfPayment.state == None,models.GuaranteeOfPayment.final == None))
        elif status == 'final':
            gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider).filter(
            and_(models.GuaranteeOfPayment.status == 'approved',models.GuaranteeOfPayment.state == None,models.GuaranteeOfPayment.final != None))
        else:
            gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider).filter(
            models.GuaranteeOfPayment.state == None)

        in_review_count = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider, status='in review').filter(
            models.GuaranteeOfPayment.state == None).count()
        approved_count = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider, status='approved').filter(
            models.GuaranteeOfPayment.state == None).count()
        rejected_count = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider, status='declined').filter(
            models.GuaranteeOfPayment.state == None).count()
        pending_count = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider).filter(
            and_(models.GuaranteeOfPayment.state == None,
            or_(models.GuaranteeOfPayment.status == None,models.GuaranteeOfPayment.status == 'pending'))).count()
        total_count = gops.count()
        
        pagination = gops.paginate()

    elif current_user.user_type == 'payer':
        if status == 'approved' or status == 'declined' or status == 'in_review':
            gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer, status=status.replace('_',' ')).filter(
            models.GuaranteeOfPayment.state == None)
        elif status == 'pending':
            gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer).filter(
            and_(models.GuaranteeOfPayment.state == None,
            or_(models.GuaranteeOfPayment.status == None,models.GuaranteeOfPayment.status == 'pending')))
        elif status == 'initial':
            gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer).filter(
            and_(or_(models.GuaranteeOfPayment.status == None,models.GuaranteeOfPayment.status == 'pending',models.GuaranteeOfPayment.status == 'in review'),
                models.GuaranteeOfPayment.state == None,
                models.GuaranteeOfPayment.final == None))
        elif status == 'final':
            gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer).filter(
            and_(or_(models.GuaranteeOfPayment.status == None,models.GuaranteeOfPayment.status == 'pending',models.GuaranteeOfPayment.status == 'in review'),
                models.GuaranteeOfPayment.state == None,
                models.GuaranteeOfPayment.final != None))
        else:
            gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer).filter(
            models.GuaranteeOfPayment.state == None)
            
        in_review_count = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer, status='in review').filter(
            models.GuaranteeOfPayment.state == None).count()
        approved_count = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer, status='approved').filter(
            models.GuaranteeOfPayment.state == None).count()
        rejected_count = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer, status='declined').filter(
            models.GuaranteeOfPayment.state == None).count()
        pending_count = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer).filter(
            and_(models.GuaranteeOfPayment.state == None,
            or_(models.GuaranteeOfPayment.status == None,models.GuaranteeOfPayment.status == 'pending'))).count()
        total_count = gops.count()
        
        pagination = gops.paginate()

    today = datetime.now()

    if page or pagination.pages > 1:
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
        gops = gops.paginate(page=page).items

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
@login_required
def block_unauthenticated_url(filename):
    return send_from_directory(os.path.join('static','uploads'),filename)


@main.route('/requests/by/<by>')
@login_required
def requests_sorted(by):
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    page = request.args.get('page')

    allowed = ['provider', 'payer', 'status', 'country']

    if by not in allowed:
        return redirect(url_for('main.index'))

    gops = models.GuaranteeOfPayment.query.filter(
            models.GuaranteeOfPayment.state == None)

    pagination = gops.paginate()

    if page or pagination.pages > 1:
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
        gops = gops.paginate(page=page).items

    return render_template('requests-all.html', by=by, gops=gops,
                           pagination=pagination)


@main.route('/request', methods=['GET', 'POST'])
@login_required
def request_form():
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    payers = current_user.provider.payers
    form = GOPForm()

    form.payer.choices = [('0', 'None')]
    form.payer.choices += [(p.id, p.company) for p in \
                           current_user.provider.payers]

    form.icd_codes.choices = [(i.id, i.code) for i in \
        models.ICDCode.query.filter(models.ICDCode.code != 'None' and \
        models.ICDCode.code != '')]
    
    form.doctor_name.choices = [('0', 'None')]
    form.doctor_name.choices += [(d.id, d.name + ' (%s)' % d.doctor_type) \
                                for d in current_user.provider.doctors]

    if form.validate_on_submit():
        dob = datetime.strptime(form.dob.data, '%d/%m/%Y')
        admission_date = datetime.strptime(form.admission_date.data + ' ' + \
            form.admission_time.data, '%d/%m/%Y %I:%M %p')
        admission_time = admission_date

        if form.medical_details_previously_admitted.data:
            previously_admitted = datetime.strptime(
                form.medical_details_previously_admitted.data, '%d/%m/%Y')
        else:
            previously_admitted = None

        filename = secure_filename(form.member_photo.data.filename)

        if filename and allowed_file(filename):
            filename = str(random.randint(100000, 999999)) + filename
            form.member_photo.data.save(
                os.path.join(config['development'].UPLOAD_FOLDER, filename))

        if not filename:
            filename = ''

        member = models.Member.query.filter_by(
            national_id=form.national_id.data).first()

        if not member:
            if filename:
                photo_filename = '/static/uploads/' + filename
            else:
                photo_filename = '/static/img/person-solid.png'

            member = models.Member(
                name=form.name.data,
                dob=dob,
                gender=form.gender.data,
                national_id=form.national_id.data,
                tel=form.tel.data,
                photo=photo_filename,
                policy_number=form.policy_number.data)

        medical_details = models.MedicalDetails(
            symptoms=form.medical_details_symptoms.data,
            temperature=form.medical_details_temperature.data,
            heart_rate=form.medical_details_heart_rate.data,
            respiration=form.medical_details_respiration.data,
            blood_pressure=form.medical_details_blood_pressure.data,
            physical_finding=form.medical_details_physical_finding.data,
            health_history=form.medical_details_health_history.data,
            previously_admitted=previously_admitted,
            diagnosis=form.medical_details_diagnosis.data,
            in_patient=form.medical_details_in_patient.data,
            test_results=form.medical_details_test_results.data,
            current_therapy=form.medical_details_current_therapy.data,
            treatment_plan=form.medical_details_treatment_plan.data
        )

        # try to convert the values to float or, if error, convert to zero
        room_price = to_float_or_zero(form.room_price.data)
        doctor_fee = to_float_or_zero(form.doctor_fee.data)
        surgery_fee = to_float_or_zero(form.surgery_fee.data)
        medication_fee = to_float_or_zero(form.medication_fee.data)
        quotation = to_float_or_zero(form.quotation.data)

        payer = models.Payer.query.get(form.payer.data)
        gop = models.GuaranteeOfPayment(
                provider=current_user.provider,
                payer=payer,
                member=member,
                patient_action_plan=form.patient_action_plan.data,
                doctor_name=models.Doctor.query.get(int(form.doctor_name.data)).name,
                admission_date=admission_date,
                admission_time=admission_time,
                reason=form.reason.data,
                room_price=room_price,
                status='pending',
                room_type=form.room_type.data,
                patient_medical_no=form.patient_medical_no.data,
                doctor_fee=doctor_fee,
                surgery_fee=surgery_fee,
                medication_fee=medication_fee,
                timestamp=datetime.now(),
                quotation=quotation,
                medical_details=medical_details
                )

        for icd_code_id in form.icd_codes.data:
            icd_code = models.ICDCode.query.get(int(icd_code_id))
            gop.icd_codes.append(icd_code)
        
        db.session.add(gop)
        db.session.commit()
        
        # initializing user and random password 
        user = None
        rand_pass = None
        
        # if the payer is registered as a user in our system
        if gop.payer.user:
            if gop.payer.pic_email:
                recipient_email = gop.payer.pic_email
            elif gop.payer.pic_alt_email:
                recipient_email = gop.payer.pic_alt_email
            else:
                recipient_email = gop.payer.user.email
            # getting payer id for sending notification    
            notification_payer_id = gop.payer.user.id
            
        # if no, we register him, set the random password and send
        # the access credentials to him
        else:
            recipient_email = gop.payer.pic_email
            rand_pass = pass_generator(size=8)
            user = models.User(email=gop.payer.pic_email,
                    password=rand_pass,
                    user_type='payer',
                    payer=gop.payer)
            db.session.add(user)
            # getting payer id for sending notification 
            notification_payer_id = user.id

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
        
        # Creating notification message
        notification_message = "Request for Intial GOP - %s" % gop.provider.company
        notification_message = notification_message + "<BR>"
        notification_message = notification_message + "<a href=/request/%s>Go To GOP</a>" %(str(gop.id))
        
        notification = models.Notification(message=notification_message,user_id=notification_payer_id)
        db.session.add(notification)
        db.session.commit()
        
        flash('Your GOP request has been sent.')
        return redirect(url_for('main.index'))

    #~ icd_codes = models.ICDCode.query.all()

    return render_template('request-form.html', form=form, payers=payers,
        bill_codes=current_user.provider.billing_codes)


@main.route('/request/<int:gop_id>', methods=['GET', 'POST'])
@login_required
def request_page(gop_id):
    # prevents request page from crashing when the gop_id is larger than a integer
    if gop_id > sys.maxsize:
        flash('Request Out Of Range')
        return redirect(url_for('main.index'))

    gop = models.GuaranteeOfPayment.query.get(gop_id)
    if gop:
        icd_codes = gop.icd_codes

        # admin can see any GOP request
        if current_user.role == 'admin':
            return render_template('request.html', gop=gop,
                                   icd_codes=icd_codes)

        if current_user.user_type == 'payer':

            if gop.payer.id != current_user.payer.id:
                flash('The GOP request #%d is not found.' % gop_id)
                return redirect(url_for('main.index'))

            if not gop.status or gop.status == 'pending':
                gop.status = 'in review'
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
                
                # Creating notification message
                if gop.status == 'approved':
                    notification_message = "%s GOP Request %s" %(gop.payer.company,form.status.data)
                elif gop.status == 'declined':
                    notification_message = "%s GOP Request %s <BR> Reason: %s" %(gop.payer.company,form.status.data,form.reason_decline.data)
                else:
                    notification_message = "%s GOP Request %s" %(gop.payer.company,'In Review')
                
                notification_message = notification_message + "<BR>"
                notification_message = notification_message + "<a href=/request/%s>Go To GOP</a>" %(str(gop.id))
        
                notification = models.Notification(message=notification_message,user_id=gop.provider.user.id)
                db.session.add(notification)
                db.session.commit()
                
                flash('The GOP request has been %s.' % form.status.data)
                return redirect(url_for('main.index'))

            context = {
                'gop': gop,
                'icd_codes': icd_codes,
                'form': form,
            }
            return render_template('request.html', **context)

        if gop.provider.id != current_user.provider.id:
            flash('The GOP request #%d is not found.' % gop_id)
            return redirect(url_for('main.index'))

        return render_template('request.html', gop=gop, icd_codes=icd_codes)
    else:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))


@main.route('/request/<int:gop_id>/set-stamp-author', methods=['GET'])
@login_required
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
@login_required
def request_page_download(gop_id):
    # only providers can download the GOP's request
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    if not current_user.premium:
        flash('To download the GOP request you need to upgrade your account.')
        return redirect(url_for('main.user_upgrade'))

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
        elif gop.status == 'in review':
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


@main.route('/upgrade', methods=['GET', 'POST'])
@login_required
def user_upgrade():
    # god user cannot upgrade the account
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # user cannot upgrade the account twice
    if current_user.premium:
        flash('Your account is already upgraded to Premium.')
        return redirect(url_for('main.index'))

    form = UserUpgradeForm()

    if form.validate_on_submit():
        admins = models.User.query.filter_by(role='admin').all()
        admin_emails = []
        for admin in admins:
            admin_emails.append(admin.email)

        admin_msg = Message("Upgrade Request for the %s account" % (
                            current_user.email),
                            sender=("MediPay", "request@app.medipayasia.com"),
                            recipients=admin_emails)

        user_msg = Message("Upgrade Request for the %s account" % (
                           current_user.email),
                           sender=("MediPay", "request@app.medipayasia.com"),
                           recipients=[form.email.data])

        admin_msg.html = render_template('upgrade-admin-email.html',
                                         user=current_user,
                                         root=request.url_root,
                                         email_invoice=form.email.data)

        user_msg.html = render_template('upgrade-user-email.html',
                                        user=current_user,
                                        root=request.url_root,
                                        email_invoice=form.email.data)

        # send the emails
        mail.send(admin_msg)
        mail.send(user_msg)

        flash('Your request for a Premium account has been sent.')
        return redirect(url_for('main.index'))

    return render_template('user-upgrade.html', form=form)


@main.route('/request/<int:gop_id>/edit', methods=['GET', 'POST'])
@login_required
def request_page_edit(gop_id):
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers can edit the GOP's request details
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    gop = models.GuaranteeOfPayment.query.get(gop_id)

    # if no GOP is found or it is not the current user's GOP, 
    # redirect to the home page
    if not gop or gop.provider.id != current_user.provider.id:
        flash('GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    if gop.state == 'closed':
        flash('GOP request #%d is closed.' % gop_id)
        return redirect(url_for('main.index'))

    form = GOPForm()

    if not gop.medical_details:
        medical_details = models.MedicalDetails(guarantee_of_payment=gop)
        db.session.add(gop)

    # as a provider can't change the GOP's payer after
    # request is sent we leave only the one select choice
    form.payer.choices = [(gop.payer.id, gop.payer.company)]

    form.icd_codes.choices = [(i.id, i.code) for i in \
        models.ICDCode.query.filter(models.ICDCode.code != 'None' and \
        models.ICDCode.code != '')]

    form.doctor_name.choices = [('0', 'None')]
    form.doctor_name.choices += [(d.id, d.name + ' (%s)' % d.doctor_type) \
                                for d in current_user.provider.doctors]

    final = request.args.get('final')

    # if the GOP's info is updated
    if form.validate_on_submit():
        # check if it's the FINAL GOP request sending

        if final and not gop.final:
            gop.final = True

        # convert the str() to the datetime python objects
        dob = datetime.strptime(form.dob.data, '%d/%m/%Y')
        admission_date = datetime.strptime(form.admission_date.data + ' ' + \
            form.admission_time.data, '%d/%m/%Y %I:%M %p')
        admission_time = admission_date
        if form.medical_details_previously_admitted.data:
            previously_admitted = datetime.strptime(
                form.medical_details_previously_admitted.data, '%d/%m/%Y')
        else:
            previously_admitted = None

        # try to convert the values to float or, if error, convert to zero
        room_price = to_float_or_zero(form.room_price.data)
        doctor_fee = to_float_or_zero(form.doctor_fee.data)
        surgery_fee = to_float_or_zero(form.surgery_fee.data)
        medication_fee = to_float_or_zero(form.medication_fee.data)
        quotation = to_float_or_zero(form.quotation.data)

        # get and set the payer object
        payer = models.Payer.query.get(form.payer.data)
        gop.payer = payer

        filename = secure_filename(form.member_photo.data.filename)
        if filename and allowed_file(filename):
            filename = str(random.randint(100000, 999999)) + filename
            form.member_photo.data.save(
                os.path.join(config['development'].UPLOAD_FOLDER, filename))

        if not filename:
            filename = ''

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
        gop.medical_details.previously_admitted = previously_admitted
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
        gop.member.name = form.name.data
        gop.member.dob = dob
        gop.member.national_id = form.national_id.data
        gop.member.gender = form.gender.data
        gop.member.tel = form.tel.data
        gop.member.policy_number = form.policy_number.data

        if filename:
            gop.member.photo = '/static/uploads/' + filename

        for icd_code_id in form.icd_codes.data:
            icd_code = models.ICDCode.query.get(int(icd_code_id))
            gop.icd_codes.append(icd_code)

        gop.patient_action_plan = form.patient_action_plan.data
        gop.doctor_name = models.Doctor.query.get(int(form.doctor_name.data)).name
        gop.admission_date = admission_date
        gop.admission_time = admission_time
        gop.reason = form.reason.data
        gop.room_price = room_price
        gop.room_type = form.room_type.data
        gop.patient_medical_no = form.patient_medical_no.data
        gop.doctor_fee = doctor_fee
        gop.surgery_fee = surgery_fee
        gop.medication_fee = medication_fee
        gop.quotation = quotation

        if gop.final:
            gop.status = None

        db.session.add(gop)

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
            
            # Creating notification message
            notification_message = "Request for Final GOP - %s" % gop.provider.company
            notification_message = notification_message + "<BR>"
            notification_message = notification_message + "<a href=/request/%s>Go To GOP</a>" %(str(gop.id))
        
            notification = models.Notification(message=notification_message,user_id=gop.payer.user.id)
            db.session.add(notification)
            db.session.commit()

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

    if gop.medical_details.previously_admitted:
        # convert the datetime python object to the string representation
        form.medical_details_previously_admitted.data = \
          gop.medical_details.previously_admitted.strftime('%d/%m/%Y')

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
    form.dob.data = gop.member.dob.strftime('%d/%m/%Y')
    form.gender.data = gop.member.gender
    form.tel.data = gop.member.tel
    form.policy_number.data = gop.member.policy_number
    form.patient_action_plan.data = gop.patient_action_plan
    # convert the datetime python object to the string representation
    form.admission_date.data = gop.admission_date.strftime('%d/%m/%Y')
    # convert the datetime python object to the string representation
    form.admission_time.data = gop.admission_time.strftime('%I:%M %p')
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
@login_required
def request_page_resend(gop_id):
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers can resend the GOP's request
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

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
@login_required
def request_page_close(gop_id, reason):
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers can close the GOP's request
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    gop = models.GuaranteeOfPayment.query.get(gop_id)

    # if no GOP is found, redirect to the home page
    if not gop or gop.provider.id != current_user.provider.id:
        flash('The GOP request #%d is not found.' % gop_id)
        return redirect(url_for('main.index'))

    if gop.state == 'closed':
        flash('The GOP request #%d is already closed.' % gop_id)
        return redirect(url_for('main.index'))

    gop.state = 'closed'
    gop.reason_close = reason
    db.session.add(gop)

    flash('The GOP request has been closed.')
    return redirect(url_for('main.request_page', gop_id=gop.id))


@main.route('/history')
@login_required
def history():
    # if it is admin, show him all the closed requests
    page = request.args.get('page')

    if current_user.role == 'admin':
        gops = models.GuaranteeOfPayment.query.filter_by(state='closed')
        return render_template('history.html', gops=gops)

    if current_user.user_type == 'provider':
        gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider, state='closed')
    elif current_user.user_type == 'payer':
        gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer, state='closed')

    pagination = gops.paginate()

    if page or pagination.pages > 1:
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
        gops = gops.paginate(page=page).items


    return render_template('history.html', gops=gops, pagination=pagination)


@main.route('/users')
@login_required
def users():
    # only admins can see the list of users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    page = request.args.get('page')

    users = models.User.query.filter(models.User.id > 0)
    pagination = users.paginate()

    if page or pagination.pages > 1:
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
        users = users.paginate(page=page).items

    return render_template('users.html', users=users, pagination=pagination)


@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    # admin does not have the settings
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    if current_user.user_type == 'provider':
        form = ChangeProviderInfoForm()
        if form.validate_on_submit():
            current_user.provider.company = form.company.data
            current_user.provider.provider_type = form.provider_type.data
            current_user.provider.pic = form.pic.data
            current_user.provider.pic_email = form.pic_email.data
            current_user.provider.pic_alt_email = form.pic_alt_email.data
            current_user.provider.tel = form.tel.data

            if form.country.data == 'Other' and form.other_country.data:
                current_user.provider.country = form.other_country.data
            else:
                current_user.provider.country = form.country.data

            current_user.provider.street_name = form.street_name.data
            current_user.provider.street_number = form.street_number.data
            current_user.provider.state = form.state.data
            current_user.provider.postcode = form.postcode.data
            db.session.add(current_user)
            flash('Data has been updated.')

        if request.method != 'POST':
            if current_user.provider.country:
                if (current_user.provider.country, current_user.provider.country) \
                    not in form.country.choices:
                    # select the 'Other' option
                    form.country.default = 'Other'
                    form.process()
                    form.other_country.data = current_user.provider.country
                else:
                    form.country.default = current_user.provider.country
                    form.process()

            form.company.data = current_user.provider.company
            form.provider_type.data = current_user.provider.provider_type
            form.pic.data = current_user.provider.pic
            form.pic_email.data = current_user.provider.pic_email
            form.pic_alt_email.data = current_user.provider.pic_alt_email
            form.tel.data = current_user.provider.tel
            form.street_name.data = current_user.provider.street_name
            form.street_number.data = current_user.provider.street_number
            form.state.data = current_user.provider.state
            form.postcode.data = current_user.provider.postcode

    elif current_user.user_type == 'payer':
        form = ChangePayerInfoForm()
        if form.validate_on_submit():
            current_user.payer.company = form.company.data
            current_user.payer.payer_type = form.payer_type.data
            current_user.payer.pic = form.pic.data
            current_user.payer.pic_email = form.pic_email.data
            current_user.payer.pic_alt_email = form.pic_alt_email.data
            current_user.payer.tel = form.tel.data

            if form.country.data == 'Other' and form.other_country.data:
                current_user.payer.country = form.other_country.data
            else:
                current_user.payer.country = form.country.data

            current_user.payer.street_name = form.street_name.data
            current_user.payer.street_number = form.street_number.data
            current_user.payer.state = form.state.data
            current_user.payer.postcode = form.postcode.data
            db.session.add(current_user)
            flash('Data has been updated.')

        if request.method != 'POST':
            if current_user.payer.country:
                if (current_user.payer.country, current_user.payer.country) \
                    not in form.country.choices:
                    # select the 'Other' option
                    form.country.default = 'Other'
                    form.process()
                    form.other_country.data = current_user.payer.country
                else:
                    form.country.default = current_user.payer.country
                    form.process()

            form.company.data = current_user.payer.company
            form.payer_type.data = current_user.payer.payer_type
            form.pic.data = current_user.payer.pic
            form.pic_email.data = current_user.payer.pic_email
            form.pic_alt_email.data = current_user.payer.pic_alt_email
            form.tel.data = current_user.payer.tel
            form.street_name.data = current_user.payer.street_name
            form.street_number.data = current_user.payer.street_number
            form.state.data = current_user.payer.state
            form.postcode.data = current_user.payer.postcode

    return render_template('settings.html', form=form, user=current_user)


@main.route('/user/<int:user_id>/settings', methods=['GET', 'POST'])
@login_required
def user_settings(user_id):
    # only admins can see the settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    if user.user_type == 'provider':
        form = ChangeProviderInfoForm()
        if form.validate_on_submit():
            user.provider.company = form.company.data
            user.provider.provider_type = form.provider_type.data
            user.provider.pic = form.pic.data
            user.provider.pic_email = form.pic_email.data
            user.provider.pic_alt_email = form.pic_alt_email.data
            user.provider.tel = form.tel.data

            if form.country.data == 'Other' and form.other_country.data:
                user.provider.country = form.other_country.data
            else:
                user.provider.country = form.country.data

            user.provider.street_name = form.street_name.data
            user.provider.street_number = form.street_number.data
            user.provider.state = form.state.data
            user.provider.postcode = form.postcode.data
            db.session.add(user)
            flash('Data has been updated.')

        if request.method != 'POST':
            if user.provider.country:
                if (user.provider.country, user.provider.country) \
                    not in form.country.choices:
                    # select the 'Other' option
                    form.country.default = 'Other'
                    form.process()
                    form.other_country.data = user.provider.country
                else:
                    form.country.default = user.provider.country
                    form.process()

            form.company.data = user.provider.company
            form.provider_type.data = user.provider.provider_type
            form.pic.data = user.provider.pic
            form.pic_email.data = user.provider.pic_email
            form.pic_alt_email.data = user.provider.pic_alt_email
            form.tel.data = user.provider.tel
            form.street_name.data = user.provider.street_name
            form.street_number.data = user.provider.street_number
            form.state.data = user.provider.state
            form.postcode.data = user.provider.postcode

    elif user.user_type == 'payer':
        form = ChangePayerInfoForm()
        if form.validate_on_submit():
            user.payer.company = form.company.data
            user.payer.payer_type = form.payer_type.data
            user.payer.pic = form.pic.data
            user.payer.pic_email = form.pic_email.data
            user.payer.pic_alt_email = form.pic_alt_email.data
            user.payer.tel = form.tel.data

            if form.country.data == 'Other' and form.other_country.data:
                user.payer.country = form.other_country.data
            else:
                user.payer.country = form.country.data

            user.payer.street_name = form.street_name.data
            user.payer.street_number = form.street_number.data
            user.payer.state = form.state.data
            user.payer.postcode = form.postcode.data
            db.session.add(user)
            flash('Data has been updated.')

        if request.method != 'POST':
            if user.payer.country:
                if (user.payer.country, user.payer.country) \
                    not in form.country.choices:
                    # select the 'Other' option
                    form.country.default = 'Other'
                    form.process()
                    form.other_country.data = user.payer.country
                else:
                    form.country.default = user.payer.country
                    form.process()

            form.company.data = user.payer.company
            form.payer_type.data = user.payer.payer_type
            form.pic.data = user.payer.pic
            form.pic_email.data = user.payer.pic_email
            form.pic_alt_email.data = user.payer.pic_alt_email
            form.tel.data = user.payer.tel
            form.street_name.data = user.payer.street_name
            form.street_number.data = user.payer.street_number
            form.state.data = user.payer.state
            form.postcode.data = user.payer.postcode

    return render_template('settings.html', form=form, user=user)


@main.route('/settings/payers')
@login_required
def settings_payers():
    # admin does not have a payer setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have payer setup
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    payers = current_user.provider.payers

    return render_template('settings-payers.html', payers=payers)


@main.route('/user/<int:user_id>/settings/payers')
@login_required
def user_settings_payers(user_id):
    # only admins can see the payer setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    payers = user.provider.payers

    return render_template('settings-payers.html', payers=payers, user=user)


@main.route('/settings/payer/add', methods=['GET', 'POST'])
@login_required
def settings_payer_add():
    # admin does not have a payer setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have payer setup
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its payers
    if current_user.role != 'user_admin':
        # flash('To add the payers you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To add the payers you need to be the admin.')
        return redirect(url_for('main.settings_payers'))

    form = ProviderPayerSetupAddForm()

    if form.validate_on_submit():
        payer = models.Payer.query.filter_by(
            pic_email=form.pic_email.data).first()
        if not payer:
            payer_user = models.User.query.filter_by(
                email=form.pic_email.data, user_type='payer').first()
            if payer_user:
                payer = payer_user.payer
        if not payer:

            if form.country.data == 'Other' and form.other_country.data:
                set_country = form.other_country.data
            else:
                set_country = form.country.data

            payer = models.Payer(company=form.company.data,
                                 payer_type=form.payer_type.data,
                                 pic_email=form.pic_email.data,
                                 pic_alt_email=form.pic_alt_email.data,
                                 pic=form.pic.data,
                                 tel=form.tel.data,
                                 country=set_country)

        if form.contract_number.data:
            contract = models.Contract(provider=current_user.provider,
                                       payer=payer,
                                       number=form.contract_number.data)
        else:
            contract = models.Contract(provider=current_user.provider,
                                       payer=payer,
                                       number=None)

        current_user.provider.payers.append(payer)
        db.session.add(payer)
        db.session.add(contract)
        db.session.add(current_user.provider)
        flash('New payer has been added.')
        return redirect(url_for('main.settings_payers'))

    form.current_user_id.data = current_user.id

    return render_template('settings-payer-form.html', form=form)


@main.route('/user/<int:user_id>/settings/payer/add', methods=['GET', 'POST'])
@login_required
def user_settings_payer_add(user_id):
    # only admins can see the payer setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = ProviderPayerSetupAddForm()

    if form.validate_on_submit():
        payer = models.Payer.query.filter_by(
            pic_email=form.pic_email.data).first()
        if not payer:
            payer_user = models.User.query.filter_by(
                email=form.pic_email.data, user_type='payer').first()
            if payer_user:
                payer = payer_user.payer
        if not payer:

            if form.country.data == 'Other' and form.other_country.data:
                set_country = form.other_country.data
            else:
                set_country = form.country.data

            payer = models.Payer(company=form.company.data,
                                 payer_type=form.payer_type.data,
                                 pic_email=form.pic_email.data,
                                 pic_alt_email=form.pic_alt_email.data,
                                 pic=form.pic.data,
                                 tel=form.tel.data,
                                 country=set_country)

        if form.contract_number.data:
            contract = models.Contract(provider=user.provider,
                                       payer=payer,
                                       number=form.contract_number.data)
        else:
            contract = models.Contract(provider=user.provider,
                                       payer=payer,
                                       number=None)

        user.provider.payers.append(payer)
        db.session.add(payer)
        db.session.add(contract)
        db.session.add(user.provider)
        flash('New payer has been added.')
        return redirect(url_for('main.user_settings_payers', user_id=user_id))

    form.current_user_id.data = user_id

    return render_template('settings-payer-form.html', form=form, user=user)


@main.route('/settings/payer/<int:payer_id>/edit', methods=['GET', 'POST'])
@login_required
def settings_payer_edit(payer_id):
    # admin does not have a payer setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have payer setup
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its payers
    if current_user.role != 'user_admin':
        # flash('To edit the payers you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To edit the payers you need to be the admin.')
        return redirect(url_for('main.payers'))

    payer = models.Payer.query.get(payer_id)

    if not payer or payer not in current_user.provider.payers:
        flash('The payer #%d is not found.' % payer_id)
        return redirect(url_for('main.settings_payers'))

    form = ProviderPayerSetupEditForm()

    if form.validate_on_submit():
        payer.company = form.company.data
        payer.payer_type = form.payer_type.data
        payer.pic_email = form.pic_email.data
        payer.pic_alt_email = form.pic_alt_email.data
        payer.pic = form.pic.data
        payer.tel = form.tel.data
        payer.contract().number = form.contract_number.data

        if form.country.data == 'Other' and form.other_country.data:
            payer.country = form.other_country.data
        else:
            payer.country = form.country.data

        db.session.add(payer)
        flash('The payer has been updated.')

    if request.method != 'POST':
        if payer.country:
            if (payer.country, payer.country) not in form.country.choices:
                # select the 'Other' option
                form.country.default = 'Other'
                form.process()
                form.other_country.data = payer.country
            else:
                form.country.default = payer.country
                form.process()

        form.company.data = payer.company
        form.payer_type.data = payer.payer_type
        form.contract_number.data = payer.contract().number
        form.pic_email.data = payer.pic_email
        form.pic_alt_email.data = payer.pic_alt_email
        form.pic.data = payer.pic
        form.tel.data = payer.tel

    form.current_payer_id.data = payer.id
    form.current_user_id.data = current_user.id

    return render_template('settings-payer-form.html', form=form)


@main.route('/user/<int:user_id>/settings/payer/<int:payer_id>/edit',
            methods=['GET', 'POST'])
@login_required
def user_settings_payer_edit(user_id, payer_id):
    # only admins can see the payer setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    payer = models.Payer.query.get(payer_id)

    if not payer or payer not in user.provider.payers:
        flash('The payer #%d is not found.' % payer_id)
        return redirect(url_for('main.user_settings_payers', user_id=user_id))

    form = ProviderPayerSetupEditForm()

    if form.validate_on_submit():
        payer.company = form.company.data
        payer.payer_type = form.payer_type.data
        payer.contract(user).number = form.contract_number.data
        payer.pic_email = form.pic_email.data
        payer.pic_alt_email = form.pic_alt_email.data
        payer.pic = form.pic.data
        payer.tel = form.tel.data

        if form.country.data == 'Other' and form.other_country.data:
            payer.country = form.other_country.data
        else:
            payer.country = form.country.data

        db.session.add(payer)
        flash('The payer has been updated.')

    if request.method != 'POST':
        if payer.country:
            if (payer.country, payer.country) not in form.country.choices:
                # select the 'Other' option
                form.country.default = 'Other'
                form.process()
                form.other_country.data = payer.country
            else:
                form.country.default = payer.country
                form.process()

        form.company.data = payer.company
        form.payer_type.data = payer.payer_type
        form.contract_number.data = payer.contract(user).number
        form.pic_email.data = payer.pic_email
        form.pic_alt_email.data = payer.pic_alt_email
        form.pic.data = payer.pic
        form.tel.data = payer.tel

    form.current_payer_id.data = payer.id
    form.current_user_id.data = user_id

    return render_template('settings-payer-form.html', form=form, user=user)


@main.route('/settings/payer/csv', methods=['GET', 'POST'])
@login_required
def settings_payer_csv():
    # admin does not have a payer setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its payers
    if current_user.role != 'user_admin':
        # flash('To bulk upload the payers you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To bulk upload the payers you need to upgrade your account.')
        return redirect(url_for('main.payers'))

    form = SingleCsvForm()
    if form.validate_on_submit():
        csv_file = request.files['csv_file']

        stream = io.StringIO(csv_file.stream.read().decode("UTF8"),
                             newline=None)
        reader = csv.reader(stream)
        payers_num = 0
        for idx, row in enumerate(reader):
            if len(row) == 7:
                if not validate_email_address(row[2]):
                    flash('The pic email "%s" is wrong on line %d.' % (
                        row[2], idx + 1))
                    return render_template('settings-payers-csv.html',
                                           form=form)

                payer = models.Payer.query.filter_by(company=row[0],
                                                     payer_type=row[1],
                                                     country=row[6],
                                                     pic_email=row[2]).first()
                if payer:
                    current_user.provider.payers.append(payer)
                else:
                    payer = models.Payer(company=row[0],
                                         payer_type=row[1],
                                         pic_email=row[2],
                                         pic_alt_email=row[3],
                                         pic=row[4],
                                         tel=row[5],
                                         country=row[6])

                current_user.provider.payers.append(payer)
                db.session.add(payer)
                db.session.add(current_user.provider)
                payers_num += 1
            else:
                flash('Your csv file is wrong.')
                return render_template('settings-payers-csv.html', form=form)

        if not payers_num:
            flash('Your csv file is empty.')
            return render_template('settings-payers-csv.html', form=form)

        flash('Added %d payers' % payers_num)
        return redirect(url_for('main.settings_payers'))

    return render_template('settings-payers-csv.html', form=form)


@main.route('/user/<int:user_id>/settings/payer/csv', methods=['GET', 'POST'])
@login_required
def user_settings_payer_csv(user_id):
    # only admins can see the payer setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = SingleCsvForm()
    if form.validate_on_submit():
        csv_file = request.files['csv_file']

        stream = io.StringIO(csv_file.stream.read().decode("UTF8"),
                             newline=None)
        reader = csv.reader(stream)
        payers_num = 0
        for idx, row in enumerate(reader):
            if len(row) == 7:
                if not validate_email_address(row[2]):
                    flash('The pic email "%s" is wrong on line %d.' % (
                        row[2], idx + 1))
                    return render_template('settings-payers-csv.html',
                                           form=form)

                payer = models.Payer.query.filter_by(company=row[0],
                                                     payer_type=row[1],
                                                     country=row[6],
                                                     pic_email=row[2]).first()
                if payer:
                    user.provider.payers.append(payer)
                else:
                    payer = models.Payer(company=row[0],
                                     payer_type=row[1],
                                     pic_email=row[2],
                                     pic_alt_email=row[3],
                                     pic=row[4],
                                     tel=row[5],
                                     country=row[6])

                user.provider.payers.append(payer)
                db.session.add(payer)
                db.session.add(user.provider)
                payers_num += 1
            else:
                flash('Your csv file is wrong.')
                return render_template('settings-payers-csv.html', form=form,
                                       user=user)

        if not payers_num:
            flash('Your csv file is empty.')
            return render_template('settings-payers-csv.html', form=form,
                                       user=user)

        flash('Added %d payers' % payers_num)
        return redirect(url_for('main.user_settings_payers', user_id=user_id))

    return render_template('settings-payers-csv.html', form=form, user=user)


@main.route('/settings/billing-codes')
@login_required
def billing_codes():
    # admin does not have a billing code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have billing codes
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    bill_codes = current_user.provider.billing_codes

    return render_template('billing-codes.html', bill_codes=bill_codes)


@main.route('/user/<int:user_id>/settings/billing-codes')
@login_required
def user_billing_codes(user_id):
    # only admins can see the billing setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    bill_codes = user.provider.billing_codes

    return render_template('billing-codes.html', bill_codes=bill_codes,
                           user=user)


@main.route('/settings/billing-code/add', methods=['GET', 'POST'])
@login_required
def billing_code_add():
    # admin does not have a billing code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have billing codes
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its billing codes
    if current_user.role != 'user_admin':
        # flash('To add the billing codes you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To add the billing codes you need to be the admin.')
        return redirect(url_for('main.billing_codes'))

    form = BillingCodeForm()

    if form.validate_on_submit():
        # try to convert the values to float or, if error, convert to zero
        room_and_board = to_float_or_zero(form.room_and_board.data)
        doctor_visit_fee = to_float_or_zero(form.doctor_visit_fee.data)
        doctor_consultation_fee = to_float_or_zero(
                                    form.doctor_consultation_fee.data)
        specialist_visit_fee = to_float_or_zero(form.specialist_visit_fee.data)
        specialist_consultation_fee = to_float_or_zero(
                                        form.specialist_consultation_fee.data)
        medicines = to_float_or_zero(form.medicines.data)
        administration_fee = to_float_or_zero(form.administration_fee.data)

        bill_code = models.BillingCode(
                provider=current_user.provider,
                room_and_board=room_and_board,
                doctor_visit_fee=doctor_visit_fee,
                doctor_consultation_fee=doctor_consultation_fee,
                specialist_visit_fee=specialist_visit_fee,
                specialist_consultation_fee=specialist_consultation_fee,
                medicines=medicines,
                administration_fee=administration_fee
            )
        db.session.add(bill_code)
        flash('The billing code has been added.')
        return redirect(url_for('main.billing_codes'))

    return render_template('billing-code-form.html', form=form)


@main.route('/user/<int:user_id>/settings/billing-code/add',
            methods=['GET', 'POST'])
@login_required
def user_billing_code_add(user_id):
    # only admins can see the billing setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = BillingCodeForm()

    if form.validate_on_submit():
        # try to convert the values to float or, if error, convert to zero
        room_and_board = to_float_or_zero(form.room_and_board.data)
        doctor_visit_fee = to_float_or_zero(form.doctor_visit_fee.data)
        doctor_consultation_fee = to_float_or_zero(
                                    form.doctor_consultation_fee.data)
        specialist_visit_fee = to_float_or_zero(form.specialist_visit_fee.data)
        specialist_consultation_fee = to_float_or_zero(
                                        form.specialist_consultation_fee.data)
        medicines = to_float_or_zero(form.medicines.data)
        administration_fee = to_float_or_zero(form.administration_fee.data)

        bill_code = models.BillingCode(
                provider=user.provider,
                room_and_board=room_and_board,
                doctor_visit_fee=doctor_visit_fee,
                doctor_consultation_fee=doctor_consultation_fee,
                specialist_visit_fee=specialist_visit_fee,
                specialist_consultation_fee=specialist_consultation_fee,
                medicines=medicines,
                administration_fee=administration_fee
            )
        db.session.add(bill_code)
        flash('The billing code has been added.')
        return redirect(url_for('main.user_billing_codes', user_id=user_id))

    return render_template('billing-code-form.html', form=form, user=user)


@main.route('/settings/billing-code/csv', methods=['GET', 'POST'])
@login_required
def billing_code_add_csv():
    # admin does not have a billing code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its billing codes
    if current_user.role != 'user_admin':
        # flash('To bulk upload the billing codes you need ' + \
        #       'to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To bulk upload the billing codes you need to be the admin.')
        return redirect(url_for('main.billing_codes'))

    form = SingleCsvForm()
    if form.validate_on_submit():
        csv_file = request.files['csv_file']

        stream = io.StringIO(csv_file.stream.read().decode("UTF8"),
                             newline=None)
        reader = csv.reader(stream)

        doc_num = 0
        for row in reader:
            if len(row) == 7:
                # try to convert the values to float or, if error, convert to zero
                room_and_board = to_float_or_zero(row[0])
                doctor_visit_fee = to_float_or_zero(row[1])
                doctor_consultation_fee = to_float_or_zero(row[2])
                specialist_visit_fee = to_float_or_zero(row[3])
                specialist_consultation_fee = to_float_or_zero(row[4])
                medicines = to_float_or_zero(row[5])
                administration_fee = to_float_or_zero(row[6])

                bill_code = models.BillingCode(
                    provider=current_user.provider,
                    room_and_board=room_and_board,
                    doctor_visit_fee=doctor_visit_fee,
                    doctor_consultation_fee=doctor_consultation_fee,
                    specialist_visit_fee=specialist_visit_fee,
                    specialist_consultation_fee=specialist_consultation_fee,
                    medicines=medicines,
                    administration_fee=administration_fee
                )
                db.session.add(bill_code)
                doc_num += 1

            else:
                flash('Your csv file is wrong.')
                return render_template('billing-code-form-csv.html', form=form)

        if not doc_num:
            flash('Your csv file is empty.')
            return render_template('billing-code-form-csv.html', form=form)

        flash('Added %d lines' % doc_num)
        return redirect(url_for('main.billing_codes'))

    return render_template('billing-code-form-csv.html', form=form)


@main.route('/user/<int:user_id>/settings/billing-code/csv',
            methods=['GET', 'POST'])
@login_required
def user_billing_code_add_csv(user_id):
    # only admins can see the billing setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = SingleCsvForm()
    if form.validate_on_submit():
        csv_file = request.files['csv_file']

        stream = io.StringIO(csv_file.stream.read().decode("UTF8"),
                             newline=None)
        reader = csv.reader(stream)

        doc_num = 0
        for row in reader:
            if len(row) == 7:
                # try to convert the values to float or, if error, convert to zero
                room_and_board = to_float_or_zero(row[0])
                doctor_visit_fee = to_float_or_zero(row[1])
                doctor_consultation_fee = to_float_or_zero(row[2])
                specialist_visit_fee = to_float_or_zero(row[3])
                specialist_consultation_fee = to_float_or_zero(row[4])
                medicines = to_float_or_zero(row[5])
                administration_fee = to_float_or_zero(row[6])

                bill_code = models.BillingCode(
                    provider=user.provider,
                    room_and_board=room_and_board,
                    doctor_visit_fee=doctor_visit_fee,
                    doctor_consultation_fee=doctor_consultation_fee,
                    specialist_visit_fee=specialist_visit_fee,
                    specialist_consultation_fee=specialist_consultation_fee,
                    medicines=medicines,
                    administration_fee=administration_fee
                )
                db.session.add(bill_code)
                doc_num += 1
            else:
                flash('Your csv file is wrong.')
                return render_template('billing-code-form-csv.html', form=form,
                    user=user)

        if not doc_num:
            flash('Your csv file is empty.')
            return render_template('billing-code-form-csv.html', form=form,
                    user=user)

        flash('Added %d lines' % doc_num)
        return redirect(url_for('main.user_billing_codes', user_id=user_id))

    return render_template('billing-code-form-csv.html', form=form, user=user)


@main.route('/settings/billing-code/<int:bill_id>', methods=['GET', 'POST'])
@login_required
def billing_code_edit(bill_id):
    # admin does not have a billing code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have billing codes
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its billing codes
    if current_user.role != 'user_admin':
        # flash('To edit the billing codes you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To edit the billing codes you need to be the admin.')
        return redirect(url_for('main.billing_codes'))

    bill_code = models.BillingCode.query.get(bill_id)

    if not bill_code:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('main.billing_codes'))

    if bill_code.provider.id != current_user.provider.id:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('main.billing_codes'))

    form = BillingCodeForm()

    if form.validate_on_submit():
        # try to convert the values to float or, if error, convert to zero
        room_and_board = to_float_or_zero(form.room_and_board.data)
        doctor_visit_fee = to_float_or_zero(form.doctor_visit_fee.data)
        doctor_consultation_fee = to_float_or_zero(
                                            form.doctor_consultation_fee.data)
        specialist_visit_fee = to_float_or_zero(form.specialist_visit_fee.data)
        specialist_consultation_fee = to_float_or_zero(
                                        form.specialist_consultation_fee.data)
        medicines = to_float_or_zero(form.medicines.data)
        administration_fee = to_float_or_zero(form.administration_fee.data)

        bill_code.room_and_board = room_and_board
        bill_code.doctor_visit_fee = doctor_visit_fee
        bill_code.doctor_consultation_fee = doctor_consultation_fee
        bill_code.specialist_visit_fee = specialist_visit_fee
        bill_code.specialist_consultation_fee = specialist_consultation_fee
        bill_code.medicines = medicines
        bill_code.administration_fee = administration_fee

        db.session.add(bill_code)
        flash('The billing code has been updated.')

    if request.method != 'POST':
        form.room_and_board.data = bill_code.room_and_board
        form.doctor_visit_fee.data = bill_code.doctor_visit_fee
        form.doctor_consultation_fee.data = bill_code.doctor_consultation_fee
        form.specialist_visit_fee.data = bill_code.specialist_visit_fee
        form.specialist_consultation_fee.data = \
            bill_code.specialist_consultation_fee
        form.medicines.data = bill_code.medicines
        form.administration_fee.data = bill_code.administration_fee

    return render_template('billing-code-form.html', form=form)


@main.route('/user/<int:user_id>/settings/billing-code/<int:bill_id>',
            methods=['GET', 'POST'])
@login_required
def user_billing_code_edit(user_id, bill_id):
    # only admins can see the billing setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    bill_code = models.BillingCode.query.get(bill_id)

    if not bill_code:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('main.user_billing_codes', user_id=user_id))

    if bill_code.provider.id != user.provider.id:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('main.user_billing_codes', user_id=user_id))

    form = BillingCodeForm()

    if form.validate_on_submit():
        # try to convert the values to float or, if error, convert to zero
        room_and_board = to_float_or_zero(form.room_and_board.data)
        doctor_visit_fee = to_float_or_zero(form.doctor_visit_fee.data)
        doctor_consultation_fee = to_float_or_zero(
                                            form.doctor_consultation_fee.data)
        specialist_visit_fee = to_float_or_zero(form.specialist_visit_fee.data)
        specialist_consultation_fee = to_float_or_zero(
                                        form.specialist_consultation_fee.data)
        medicines = to_float_or_zero(form.medicines.data)
        administration_fee = to_float_or_zero(form.administration_fee.data)

        bill_code.room_and_board = room_and_board
        bill_code.doctor_visit_fee = doctor_visit_fee
        bill_code.doctor_consultation_fee = doctor_consultation_fee
        bill_code.specialist_visit_fee = specialist_visit_fee
        bill_code.specialist_consultation_fee = specialist_consultation_fee
        bill_code.medicines = medicines
        bill_code.administration_fee = administration_fee

        db.session.add(bill_code)
        flash('The billing code has been updated.')

    if request.method != 'POST':
        form.room_and_board.data = bill_code.room_and_board
        form.doctor_visit_fee.data = bill_code.doctor_visit_fee
        form.doctor_consultation_fee.data = bill_code.doctor_consultation_fee
        form.specialist_visit_fee.data = bill_code.specialist_visit_fee
        form.specialist_consultation_fee.data = \
            bill_code.specialist_consultation_fee
        form.medicines.data = bill_code.medicines
        form.administration_fee.data = bill_code.administration_fee

    return render_template('billing-code-form.html', form=form, user=user)


@main.route('/billing-code/<int:bill_id>/get', methods=['GET'])
@login_required
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


@main.route('/settings/doctors')
@login_required
def doctors():
    # admin does not have a doctor code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have doctors
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    doctors = current_user.provider.doctors

    return render_template('doctors.html', doctors=doctors)


@main.route('/user/<int:user_id>/settings/doctors')
@login_required
def user_doctors(user_id):
    # only admins can see the doctor setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    doctors = user.provider.doctors

    return render_template('doctors.html', doctors=doctors, user=user)


@main.route('/settings/doctor/add', methods=['GET', 'POST'])
@login_required
def doctor_add():
    # admin does not have a doctor code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have doctors
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its doctors
    if current_user.role != 'user_admin':
        # flash('To add the doctors you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To add the doctors you need to be the admin.')
        return redirect(url_for('main.doctors'))

    form = DoctorForm()

    if form.validate_on_submit():
        filename = secure_filename(form.photo.data.filename)
        if filename and allowed_file(filename):
            filename = str(random.randint(100000, 999999)) + filename
            form.photo.data.save(
                os.path.join(config['development'].UPLOAD_FOLDER, filename))

        if not filename:
            filename = ''

        if filename:
            photo_filename = '/static/uploads/' + filename
        else:
            photo_filename = '/static/img/person-solid.png'

        doctor = models.Doctor(provider=current_user.provider,
                               name=form.name.data,
                               department=form.department.data,
                               doctor_type=form.doctor_type.data,
                               photo=photo_filename)

        db.session.add(doctor)
        flash('New doctor has been added.')
        return redirect(url_for('main.doctors'))

    return render_template('doctor-form.html', form=form)


@main.route('/user/<int:user_id>/settings/doctor/add', methods=['GET', 'POST'])
@login_required
def user_doctor_add(user_id):
    # only admins can see the doctor setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = DoctorForm()

    if form.validate_on_submit():
        filename = secure_filename(form.photo.data.filename)
        if filename and allowed_file(filename):
            filename = str(random.randint(100000, 999999)) + filename
            form.photo.data.save(
                os.path.join(config['development'].UPLOAD_FOLDER, filename))

        if not filename:
            filename = ''

        if filename:
            photo_filename = '/static/uploads/' + filename
        else:
            photo_filename = '/static/img/person-solid.png'

        doctor = models.Doctor(provider=user.provider,
                               name=form.name.data,
                               department=form.department.data,
                               doctor_type=form.doctor_type.data,
                               photo=photo_filename)

        db.session.add(doctor)
        flash('New doctor has been added.')
        return redirect(url_for('main.user_doctors', user_id=user_id))

    return render_template('doctor-form.html', form=form, user=user)


@main.route('/settings/doctor/csv', methods=['GET', 'POST'])
@login_required
def doctor_add_csv():
    # admin does not have a doctor code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its doctors
    if current_user.role != 'user_admin':
        # flash('To bulk upload the doctors you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To bulk upload the doctors you need to be the admin.')
        return redirect(url_for('main.doctors'))

    form = SingleCsvForm()
    if form.validate_on_submit():
        csv_file = request.files['csv_file']

        stream = io.StringIO(csv_file.stream.read().decode("UTF8"),
                             newline=None)
        reader = csv.reader(stream)
        doc_num = 0
        for row in reader:
            if len(row) == 3:
                doctor = models.Doctor(provider=current_user.provider,
                                       name=row[0],
                                       department=row[1],
                                       doctor_type=row[2])
                db.session.add(doctor)
                doc_num += 1
            else:
                flash('Your csv file is wrong.')
                return render_template('doctor-form-csv.html', form=form)

        if not doc_num:
            flash('Your csv file is empty.')
            return render_template('doctor-form-csv.html', form=form)

        flash('Added %d doctors' % doc_num)
        return redirect(url_for('main.doctors'))

    return render_template('doctor-form-csv.html', form=form)


@main.route('/user/<int:user_id>/settings/doctor/csv', methods=['GET', 'POST'])
@login_required
def user_doctor_add_csv(user_id):
    # only admins can see the doctor setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = SingleCsvForm()
    if form.validate_on_submit():
        csv_file = request.files['csv_file']

        stream = io.StringIO(csv_file.stream.read().decode("UTF8"),
                             newline=None)
        reader = csv.reader(stream)
        doc_num = 0

        for row in reader:
            if len(row) == 3:
                doctor = models.Doctor(provider=user.provider,
                                       name=row[0],
                                       department=row[1],
                                       doctor_type=row[2])
                db.session.add(doctor)
                doc_num += 1
            else:
                flash('Your csv file is wrong.')
                return render_template('doctor-form-csv.html', form=form,
                    user=user)

        if not doc_num:
            flash('Your csv file is empty.')
            return render_template('doctor-form-csv.html', form=form,
                    user=user)

        flash('Added %d doctors' % doc_num)
        return redirect(url_for('main.user_doctors', user_id=user_id))

    return render_template('doctor-form-csv.html', form=form, user=user)


@main.route('/settings/doctor/<int:doctor_id>/edit', methods=['GET', 'POST'])
@login_required
def doctor_edit(doctor_id):
    # admin does not have a doctor code setup
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have doctors
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its doctors
    if current_user.role != 'user_admin':
        # flash('To edit the doctors you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To edit the doctors you need to be the admin.')
        return redirect(url_for('main.doctors'))

    doctor = models.Doctor.query.get(doctor_id)

    if not doctor or doctor.provider.id != current_user.provider.id:
        flash('No doctor #%d found.' % doctor_id)
        return redirect(url_for('main.doctors'))

    form = DoctorForm()

    if form.validate_on_submit():
        filename = secure_filename(form.photo.data.filename)
        if filename and allowed_file(filename):
            filename = str(random.randint(100000, 999999)) + filename
            form.photo.data.save(
                os.path.join(config['development'].UPLOAD_FOLDER, filename))

        if not filename:
            filename = ''

        if filename:
            photo_filename = '/static/uploads/' + filename
            doctor.photo = photo_filename

        doctor.name = form.name.data
        doctor.department = form.department.data
        doctor.doctor_type = form.doctor_type.data

        db.session.add(doctor)
        flash('The doctor has been updated.')
        return redirect(url_for('main.doctors'))

    if request.method != 'POST':
        form.doctor_type.default = doctor.doctor_type
        form.process()

        form.name.data = doctor.name
        form.department.data = doctor.department

    return render_template('doctor-form.html', form=form, doctor=doctor)


@main.route('/user/<int:user_id>/settings/doctor/<int:doctor_id>/edit',
            methods=['GET', 'POST'])
@login_required
def user_doctor_edit(user_id, doctor_id):
    # only admins can see the doctor setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    doctor = models.Doctor.query.get(doctor_id)

    if not doctor or doctor.provider.id != user.provider.id:
        flash('No doctor #%d found.' % doctor_id)
        return redirect(url_for('main.user_doctors', user_id=user_id))

    form = DoctorForm()

    if form.validate_on_submit():
        filename = secure_filename(form.photo.data.filename)
        if filename and allowed_file(filename):
            filename = str(random.randint(100000, 999999)) + filename
            form.photo.data.save(
                os.path.join(config['development'].UPLOAD_FOLDER, filename))

        if not filename:
            filename = ''

        if filename:
            photo_filename = '/static/uploads/' + filename
            doctor.photo = photo_filename

        doctor.name = form.name.data
        doctor.department = form.department.data
        doctor.doctor_type = form.doctor_type.data

        db.session.add(doctor)
        flash('The doctor has been updated.')
        return redirect(url_for('main.user_doctors', user_id=user_id))

    if request.method != 'POST':
        form.doctor_type.default = doctor.doctor_type
        form.process()

        form.name.data = doctor.name
        form.department.data = doctor.department

    return render_template('doctor-form.html', form=form, user=user,
                                               doctor=doctor)


@main.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    # admin does not have a setup section
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only providers have the setup section
    if current_user.user_type != 'provider':
        return redirect(url_for('main.index'))

    # only user_admin can edit its setup settings
    if current_user.role != 'user_admin':
        # flash('To edit the setup settings you need to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To edit the system settings you need to be the admin.')
        return redirect(url_for('main.settings'))

    form = ProviderSetupForm()

    if form.validate_on_submit():
        current_user.provider.setup_serial_number = form.serial_number.data
        current_user.provider.setup_server_url = form.server_url.data
        current_user.provider.setup_server_port = form.server_port.data
        current_user.provider.setup_module_name = form.module_name.data
        current_user.provider.setup_proxy_url = form.proxy_url.data
        current_user.provider.setup_proxy_port = form.proxy_port.data
        current_user.provider.setup_username = form.username.data
        current_user.provider.setup_password = form.password.data
        current_user.provider.setup_request_url = form.request_url.data
        current_user.provider.setup_default_path = form.default_path.data
        current_user.provider.setup_language = form.language.data
        db.session.add(current_user)
        flash('Data has been updated.')

    if request.method != 'POST':
        if current_user.provider.setup_language:
            form.language.default = current_user.provider.setup_language
            form.process()
        form.serial_number.data = current_user.provider.setup_serial_number
        form.server_url.data = current_user.provider.setup_server_url
        form.server_port.data = current_user.provider.setup_server_port
        form.module_name.data = current_user.provider.setup_module_name
        form.proxy_url.data = current_user.provider.setup_proxy_url
        form.proxy_port.data = current_user.provider.setup_proxy_port
        form.username.data = current_user.provider.setup_username
        form.password.data = current_user.provider.setup_password
        form.request_url.data = current_user.provider.setup_request_url
        form.default_path.data = current_user.provider.setup_default_path

    return render_template('setup.html', form=form)


@main.route('/user/<int:user_id>/setup', methods=['GET', 'POST'])
@login_required
def user_setup(user_id):
    # only admins can see the setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = ProviderSetupForm()

    if form.validate_on_submit():
        user.provider.setup_serial_number = form.serial_number.data
        user.provider.setup_server_url = form.server_url.data
        user.provider.setup_server_port = form.server_port.data
        user.provider.setup_module_name = form.module_name.data
        user.provider.setup_proxy_url = form.proxy_url.data
        user.provider.setup_proxy_port = form.proxy_port.data
        user.provider.setup_username = form.username.data
        user.provider.setup_password = form.password.data
        user.provider.setup_request_url = form.request_url.data
        user.provider.setup_default_path = form.default_path.data
        user.provider.setup_language = form.language.data
        db.session.add(user)
        flash('Data has been updated.')

    if request.method != 'POST':
        if user.provider.setup_language:
            form.language.default = user.provider.setup_language
            form.process()
        form.serial_number.data = user.provider.setup_serial_number
        form.server_url.data = user.provider.setup_server_url
        form.server_port.data = user.provider.setup_server_port
        form.module_name.data = user.provider.setup_module_name
        form.proxy_url.data = user.provider.setup_proxy_url
        form.proxy_port.data = user.provider.setup_proxy_port
        form.username.data = user.provider.setup_username
        form.password.data = user.provider.setup_password
        form.request_url.data = user.provider.setup_request_url
        form.default_path.data = user.provider.setup_default_path

    return render_template('setup.html', form=form, user=user)


@main.route('/settings/user-setup', methods=['GET', 'POST'])
@login_required
def settings_user_setup():
    # admin does not have a user setup section
    if current_user.role == 'admin':
        return redirect(url_for('main.index'))

    # only user_admin can edit its user setup settings
    if current_user.role != 'user_admin':
        # flash('To edit the user setup settings you need ' + \
        #       'to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To edit the user settings you need to be the admin.')
        return redirect(url_for('main.settings'))

    form = UserSetupForm()

    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.email = form.email.data
        flash('Your user settings have been updated.')
        db.session.add(current_user)

    if request.method != 'POST':
        form.name.data = current_user.name
        form.email.data = current_user.email

    form.current_user_id.data = current_user.id

    return render_template('settings-user-setup.html', form=form)


@main.route('/user/<int:user_id>/settings/user-setup', methods=['GET', 'POST'])
@login_required
def user_settings_user_setup(user_id):
    # only admins can see the setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = UserSetupAdminForm()

    if form.validate_on_submit():
        user.name = form.name.data
        user.email = form.email.data
        user.role = form.role.data
        user.premium = form.premium.data
        flash('The user\'s settings have been updated.')
        db.session.add(user)

    if request.method != 'POST':
        form.role.default = user.role
        form.premium.default = user.premium
        form.process()

        form.name.data = user.name
        form.email.data = user.email

    form.current_user_id.data = user.id

    return render_template('settings-user-setup.html', form=form, user=user)


@main.route('/settings/account', methods=['GET', 'POST'])
@login_required
def settings_account():
    # only user_admin and admit can edit its account settings
    if current_user.role != 'user_admin' and current_user.role != 'admin':
        # flash('To edit the account settings you need ' + \
        #       'to upgrade your account.')
        # return redirect(url_for('main.user_upgrade'))
        flash('To edit the account settings you need to be the admin.')
        return redirect(url_for('main.settings'))

    form = EditAccountForm()

    if form.validate_on_submit():
        current_user.password = form.password.data
        flash('Your account settings have been updated.')
        db.session.add(current_user)

    return render_template('settings-account.html', form=form)


@main.route('/user/<int:user_id>/settings/account', methods=['GET', 'POST'])
def user_settings_account(user_id):
    # only admins can see the setup settings of other users
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = EditAccountAdminForm()

    if form.validate_on_submit():
        user.password = form.password.data
        flash('The user\'s account settings have been updated.')
        db.session.add(user)

    return render_template('settings-account.html', form=form, user=user)


@main.route('/help')
@login_required
def help():
    name = current_user.email
    return render_template('help.html', name=name)


@main.app_errorhandler(404)
def page_not_found(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'not found'})
        response.status_code = 404
        return response
    return render_template('404.html'), 404


@main.app_errorhandler(500)
def internal_server_error(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'internal server error'})
        response.status_code = 500
        return response
    return render_template('500.html'), 500


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
    found = []
    query = request.args.get('query')
    query = query.lower()
    
    if not query:
        return render_template('icd-code-search-results.html',
                               icd_codes=None, query=query)

    icd_codes = models.ICDCode.query.all()

    for icd_code in icd_codes:
        if query in icd_code.code.lower() \
        or query in icd_code.description.lower() \
        or query in icd_code.common_term.lower():
            found.append(icd_code)
            continue

    return render_template('icd-code-search-results.html', icd_codes=found,
                               query=query)


@main.route('/requests/filter', methods=['GET'])
@login_required
def requests_filter():
    # only admin account has filters
    if current_user.role != 'admin':
        return 'ERROR'

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
                   .filter(models.GuaranteeOfPayment.state == None)

    elif country:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(models.Provider.country == country)\
                   .filter(models.GuaranteeOfPayment.state == None)

    elif provider:
        gops = gops.join(models.Provider,
                         models.GuaranteeOfPayment.provider_id == \
                         models.Provider.id)\
                   .filter(models.Provider.company == provider)\
                   .filter(models.GuaranteeOfPayment.state == None)

    if payer:
        gops = gops.join(models.Payer,
                         models.GuaranteeOfPayment.payer_id == \
                         models.Payer.id)\
                   .filter(models.Payer.company == payer)\
                   .filter(models.GuaranteeOfPayment.state == None)

    if status:
        gops = gops.filter(models.GuaranteeOfPayment.status == status)\
                   .filter(models.GuaranteeOfPayment.state == None)

    gops = gops.all()

    return render_template('requests-filter-results.html', gops=gops)


@main.route('/get-gops', methods=['GET'])
@login_required
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
                       .filter(models.GuaranteeOfPayment.state == None)

        elif country:
            gops = gops.join(models.Provider,
                             models.GuaranteeOfPayment.provider_id == \
                             models.Provider.id)\
                       .filter(models.Provider.country == country)\
                       .filter(models.GuaranteeOfPayment.state == None)

        elif provider:
            gops = gops.join(models.Provider,
                             models.GuaranteeOfPayment.provider_id == \
                             models.Provider.id)\
                       .filter(models.Provider.company == provider)\
                       .filter(models.GuaranteeOfPayment.state == None)

        if payer:
            gops = gops.join(models.Payer,
                             models.GuaranteeOfPayment.payer_id == \
                             models.Payer.id)\
                       .filter(models.Payer.company == payer)\
                       .filter(models.GuaranteeOfPayment.state == None)

        if status:
            gops = gops.filter(models.GuaranteeOfPayment.status == status)\
                       .filter(models.GuaranteeOfPayment.state == None)

    elif current_user.user_type == 'provider':
        gops = models.GuaranteeOfPayment.query.filter_by(
            provider=current_user.provider).filter(
            models.GuaranteeOfPayment.state == None)

    elif current_user.user_type == 'payer':
        gops = models.GuaranteeOfPayment.query.filter_by(
            payer=current_user.payer).filter(
            models.GuaranteeOfPayment.state == None)

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


@main.route('/generate-api-key', methods=['GET'])
@login_required
def generate_api_key():
    api_key = pass_generator(size=16)

    current_user.api_key = api_key
    db.session.add(current_user)

    return current_user.api_key or 'None'

@main.route('/check-notification')
@login_required
def check_notifications():
    """This view function provides the notifications functionality.
    It compares the GOP request statuses from the user session varibale
    with the current statuses of GOP requests from the database"""

    notification = None
    if current_user.user_type == 'payer':
        pass
    elif current_user.user_type == 'provider':
        pass
    else:
        return jsonify({})
    
    # Send notification To The Required User
    notification = models.Notification.query.filter_by(user_id=current_user.id).first()
    if notification is None:
        return jsonify({})

    Message = notification.message
    if Message is None:
        return jsonify({})
    
    # After Notification Has Been Sent, Delete It From Table 
    db.session.delete(notification)
    db.session.commit()
    
    notification_message = {}
    notification_message['msg'] = Message
        
    return jsonify(notification_message)
    
    #~ # only providers can get notifications
    #~ if current_user.user_type == 'provider':
        #~ gops = current_user.provider.guarantees_of_payment

    #~ # otherwise return an empty JSON array
    #~ else:
        #~ return jsonify({})

    #~ # initialize an empty changes dictionary
    #~ changes = {}

    #~ # initialize the dictionary with the GOP request id's and statuses
    #~ new_gops = {}
    #~ for gop in gops:
        #~ new_gops[gop.id] = gop.status

    #~ curr_gops = session.get('curr_gops', None)

    #~ # if there is no notification session variable,
    #~ # return an empty JSON array
    #~ if not curr_gops:
        #~ return jsonify({})

    #~ # iterate through the current GOP statuses list in the
    #~ # user session varibale and compare it to the actually
    #~ # GOP statuses from the database
    #~ for id, curr_gop in curr_gops.iteritems():
        #~ id = int(id)
        #~ if new_gops[id] != curr_gop:
            #~ changes[id] = new_gops[id]

    #~ # if there were any changes in the GOP statuses,
    #~ # replace the current session variable with the actual
    #~ # data from the database
    #~ if changes:
        #~ del session['curr_gops']
        #~ session['curr_gops'] = new_gops
        #~ session.modified = True

    #~ return jsonify(changes)
