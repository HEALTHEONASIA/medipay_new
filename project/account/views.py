from flask import render_template, flash, redirect, request, url_for
from flask_login import current_user
from flask_mail import Message

from . import account
from .forms import ChangeProviderInfoForm, ChangePayerInfoForm
from .forms import ProviderPayerSetupAddForm, ProviderPayerSetupEditForm
from .forms import BillingCodeForm, SingleCsvForm, DoctorForm, UserSetupForm
from .forms import UserSetupAdminForm, UserUpgradeForm, EditAccountForm
from .. import models, db, mail
from ..main.helpers import photo_file_name_santizer
from ..models import login_required

@account.route('/settings', methods=['GET', 'POST'])
@login_required(types=['provider', 'payer'])
def settings():
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


@account.route('/settings/payers')
@login_required(types=['provider'])
def settings_payers():
    payers = current_user.provider.payers

    return render_template('settings-payers.html', payers=payers)


@account.route('/settings/payer/add', methods=['GET', 'POST'])
@login_required(types=['provider'])
def settings_payer_add():
    # only user_admin can edit its payers
    if current_user.role != 'user_admin':
        flash('To add the payers you need to be the admin.')
        return redirect(url_for('account.settings_payers'))

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
        return redirect(url_for('account.settings_payers'))

    form.current_user_id.data = current_user.id

    return render_template('settings-payer-form.html', form=form)


@account.route('/settings/payer/<int:payer_id>/edit', methods=['GET', 'POST'])
@login_required(types=['provider'])
def settings_payer_edit(payer_id):
    # only user_admin can edit its payers
    if current_user.role != 'user_admin':
        flash('To edit the payers you need to be the admin.')
        return redirect(url_for('main.payers'))

    payer = models.Payer.query.get(payer_id)

    if not payer or payer not in current_user.provider.payers:
        flash('The payer #%d is not found.' % payer_id)
        return redirect(url_for('account.settings_payers'))

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


@account.route('/settings/payer/csv', methods=['GET', 'POST'])
@login_required(types=['provider'])
def settings_payer_csv():
    # only user_admin can edit its payers
    if current_user.role != 'user_admin':
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
        return redirect(url_for('account.settings_payers'))

    return render_template('settings-payers-csv.html', form=form)


@account.route('/settings/billing-codes')
@login_required(types=['provider'])
def billing_codes():
    bill_codes = current_user.provider.billing_codes

    return render_template('billing-codes.html', bill_codes=bill_codes)


@account.route('/settings/billing-code/add', methods=['GET', 'POST'])
@login_required(types=['provider'])
def billing_code_add():
    # only user_admin can edit its billing codes
    if current_user.role != 'user_admin':
        flash('To add the billing codes you need to be the admin.')
        return redirect(url_for('account.billing_codes'))

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
        return redirect(url_for('account.billing_codes'))

    return render_template('billing-code-form.html', form=form)


@account.route('/settings/billing-code/csv', methods=['GET', 'POST'])
@login_required(types=['provider'])
def billing_code_add_csv():
    # only user_admin can edit its billing codes
    if current_user.role != 'user_admin':
        flash('To bulk upload the billing codes you need to be the admin.')
        return redirect(url_for('account.billing_codes'))

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
        return redirect(url_for('account.billing_codes'))

    return render_template('billing-code-form-csv.html', form=form)


@account.route('/settings/billing-code/<int:bill_id>', methods=['GET', 'POST'])
@login_required(types=['provider'])
def billing_code_edit(bill_id):
    # only user_admin can edit its billing codes
    if current_user.role != 'user_admin':
        flash('To edit the billing codes you need to be the admin.')
        return redirect(url_for('account.billing_codes'))

    bill_code = models.BillingCode.query.get(bill_id)

    if not bill_code:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('account.billing_codes'))

    if bill_code.provider.id != current_user.provider.id:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('account.billing_codes'))

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


@account.route('/settings/doctors')
@login_required(types=['provider'])
def doctors():
    doctors = current_user.provider.doctors

    return render_template('doctors.html', doctors=doctors)


@account.route('/settings/doctor/add', methods=['GET', 'POST'])
@login_required(types=['provider'])
def doctor_add():
    # only user_admin can edit its doctors
    if current_user.role != 'user_admin':
        flash('To add the doctors you need to be the admin.')
        return redirect(url_for('account.doctors'))

    form = DoctorForm()

    if form.validate_on_submit():
        photo_filename = photo_file_name_santizer(form.photo)

        doctor = models.Doctor(provider=current_user.provider,
                               name=form.name.data,
                               department=form.department.data,
                               doctor_type=form.doctor_type.data,
                               photo=photo_filename)

        db.session.add(doctor)
        flash('New doctor has been added.')
        return redirect(url_for('account.doctors'))

    return render_template('doctor-form.html', form=form)


@account.route('/settings/doctor/csv', methods=['GET', 'POST'])
@login_required(types=['provider'])
def doctor_add_csv():
    # only user_admin can edit its doctors
    if current_user.role != 'user_admin':
        flash('To bulk upload the doctors you need to be the admin.')
        return redirect(url_for('account.doctors'))

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
        return redirect(url_for('account.doctors'))

    return render_template('doctor-form-csv.html', form=form)


@account.route('/settings/doctor/<int:doctor_id>/edit', methods=['GET', 'POST'])
@login_required(types=['provider'])
def doctor_edit(doctor_id):
    # only user_admin can edit its doctors
    if current_user.role != 'user_admin':
        flash('To edit the doctors you need to be the admin.')
        return redirect(url_for('account.doctors'))

    doctor = models.Doctor.query.get(doctor_id)

    if not doctor or doctor.provider.id != current_user.provider.id:
        flash('No doctor #%d found.' % doctor_id)
        return redirect(url_for('account.doctors'))

    form = DoctorForm()

    if form.validate_on_submit():
        photo_filename = photo_file_name_santizer(form.photo)

        doctor.photo = photo_filename

        doctor.name = form.name.data
        doctor.department = form.department.data
        doctor.doctor_type = form.doctor_type.data

        db.session.add(doctor)
        flash('The doctor has been updated.')
        return redirect(url_for('account.doctors'))

    if request.method != 'POST':
        form.doctor_type.default = doctor.doctor_type
        form.process()

        form.name.data = doctor.name
        form.department.data = doctor.department

    return render_template('doctor-form.html', form=form, doctor=doctor)


@account.route('/setup', methods=['GET', 'POST'])
@login_required(types=['provider'])
def setup():
    # only user_admin can edit its setup settings
    if current_user.role != 'user_admin':
        flash('To edit the system settings you need to be the admin.')
        return redirect(url_for('account.settings'))

    return render_template('setup.html')


@account.route('/settings/user-setup', methods=['GET', 'POST'])
@login_required(types=['provider'])
def settings_user_setup():
    # only user_admin can edit its user setup settings
    if current_user.role != 'user_admin':
        flash('To edit the user settings you need to be the admin.')
        return redirect(url_for('account.settings'))

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


@account.route('/settings/account', methods=['GET', 'POST'])
@login_required()
def settings_account():
    # only user_admin and admin can edit its account settings
    if current_user.role != 'user_admin' and current_user.role != 'admin':
        flash('To edit the account settings you need to be the admin.')
        return redirect(url_for('account.settings'))

    form = EditAccountForm()

    if form.validate_on_submit():
        current_user.password = form.password.data
        flash('Your account settings have been updated.')
        db.session.add(current_user)

    return render_template('settings-account.html', form=form)


@account.route('/upgrade', methods=['GET', 'POST'])
@login_required(types=['provider', 'payer'])
def user_upgrade():
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


@account.route('/generate-api-key', methods=['GET'])
@login_required()
def generate_api_key():
    api_key = pass_generator(size=16)

    current_user.api_key = api_key
    db.session.add(current_user)

    return current_user.api_key or 'None'