from flask import render_template, flash, redirect, request, url_for
from flask_login import current_user
from . import admin
from ..account.forms import ChangeProviderInfoForm, ChangePayerInfoForm
from ..account.forms import ProviderPayerSetupAddForm, ProviderPayerSetupEditForm
from ..account.forms import SingleCsvForm, BillingCodeForm, DoctorForm
from ..account.forms import UserSetupAdminForm, EditAccountAdminForm
from .. import models, db
from ..models import login_required


@admin.route('/user/<int:user_id>/settings', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_settings(user_id):
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


@admin.route('/user/<int:user_id>/settings/payers')
@login_required(roles=['admin'])
def user_settings_payers(user_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    payers = user.provider.payers

    return render_template('settings-payers.html', payers=payers, user=user)


@admin.route('/user/<int:user_id>/settings/payer/add', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_settings_payer_add(user_id):
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
        return redirect(url_for('admin.user_settings_payers', user_id=user_id))

    form.current_user_id.data = user_id

    return render_template('settings-payer-form.html', form=form, user=user)


@admin.route('/user/<int:user_id>/settings/payer/<int:payer_id>/edit',
            methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_settings_payer_edit(user_id, payer_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    payer = models.Payer.query.get(payer_id)

    if not payer or payer not in user.provider.payers:
        flash('The payer #%d is not found.' % payer_id)
        return redirect(url_for('admin.user_settings_payers', user_id=user_id))

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


@admin.route('/user/<int:user_id>/settings/payer/csv', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_settings_payer_csv(user_id):
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
        return redirect(url_for('admin.user_settings_payers', user_id=user_id))

    return render_template('settings-payers-csv.html', form=form, user=user)


@admin.route('/user/<int:user_id>/settings/billing-code/add',
            methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_billing_code_add(user_id):
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
        return redirect(url_for('admin.user_billing_codes', user_id=user_id))

    return render_template('billing-code-form.html', form=form, user=user)


@admin.route('/user/<int:user_id>/settings/billing-code/csv',
            methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_billing_code_add_csv(user_id):
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
        return redirect(url_for('admin.user_billing_codes', user_id=user_id))

    return render_template('billing-code-form-csv.html', form=form, user=user)


@admin.route('/user/<int:user_id>/settings/billing-codes')
@login_required(roles=['admin'])
def user_billing_codes(user_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    bill_codes = user.provider.billing_codes

    return render_template('billing-codes.html', bill_codes=bill_codes,
                           user=user)


@admin.route('/user/<int:user_id>/settings/billing-code/<int:bill_id>',
            methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_billing_code_edit(user_id, bill_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    bill_code = models.BillingCode.query.get(bill_id)

    if not bill_code:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('admin.user_billing_codes', user_id=user_id))

    if bill_code.provider.id != user.provider.id:
        flash('No billing code #%d found.' % gop_id)
        return redirect(url_for('admin.user_billing_codes', user_id=user_id))

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


@admin.route('/user/<int:user_id>/settings/doctors')
@login_required(roles=['admin'])
def user_doctors(user_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    doctors = user.provider.doctors

    return render_template('doctors.html', doctors=doctors, user=user)


@admin.route('/user/<int:user_id>/settings/doctor/add', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_doctor_add(user_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    form = DoctorForm()

    if form.validate_on_submit():
        photo_filename = photo_file_name_santizer(form.photo)

        doctor = models.Doctor(provider=user.provider,
                               name=form.name.data,
                               department=form.department.data,
                               doctor_type=form.doctor_type.data,
                               photo=photo_filename)

        db.session.add(doctor)
        flash('New doctor has been added.')
        return redirect(url_for('admin.user_doctors', user_id=user_id))

    return render_template('doctor-form.html', form=form, user=user)


@admin.route('/user/<int:user_id>/settings/doctor/csv', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_doctor_add_csv(user_id):
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
        return redirect(url_for('admin.user_doctors', user_id=user_id))

    return render_template('doctor-form-csv.html', form=form, user=user)


@admin.route('/user/<int:user_id>/settings/doctor/<int:doctor_id>/edit',
            methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_doctor_edit(user_id, doctor_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    doctor = models.Doctor.query.get(doctor_id)

    if not doctor or doctor.provider.id != user.provider.id:
        flash('No doctor #%d found.' % doctor_id)
        return redirect(url_for('admin.user_doctors', user_id=user_id))

    form = DoctorForm()

    if form.validate_on_submit():
        doctor.photo = photo_file_name_santizer(form.photo)

        doctor.name = form.name.data
        doctor.department = form.department.data
        doctor.doctor_type = form.doctor_type.data

        db.session.add(doctor)
        flash('The doctor has been updated.')
        return redirect(url_for('admin.user_doctors', user_id=user_id))

    if request.method != 'POST':
        form.doctor_type.default = doctor.doctor_type
        form.process()

        form.name.data = doctor.name
        form.department.data = doctor.department

    return render_template('doctor-form.html', form=form, user=user,
                                               doctor=doctor)


@admin.route('/user/<int:user_id>/setup', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_setup(user_id):
    user = models.User.query.get(user_id)

    if not user:
        flash('User #%d is not found.' % user_id)
        return redirect(url_for('main.index'))

    return render_template('setup.html', user=user)


@admin.route('/user/<int:user_id>/settings/user-setup', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_settings_user_setup(user_id):
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


@admin.route('/user/<int:user_id>/settings/account', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def user_settings_account(user_id):
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