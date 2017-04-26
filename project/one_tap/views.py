import os

from calendar import month_abbr
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from flask import flash, render_template, redirect, request, url_for
from flask import jsonify, send_from_directory, session
from flask_login import current_user, login_user
from sqlalchemy import desc

from .forms import ClaimForm, MemberForm, TerminalForm
from .helpers import pass_generator, photo_file_name_santizer, percent_of
from .helpers import patients_amount
from . import one_tap
from .. import config, db, models
from ..main.forms import GOPForm
from ..main.helpers import is_admin, is_payer, is_provider
from ..main.services import MedicalDetailsService, MemberService, ClaimService
from ..main.services import GuaranteeOfPaymentService, TerminalService
from ..models import Claim, Member, Terminal, ICDCode, Provider, Payer
from ..models import Doctor, User, GuaranteeOfPayment
from ..models import monthdelta, login_required


medical_details_service = MedicalDetailsService()
member_service = MemberService()
claim_service = ClaimService()
gop_service = GuaranteeOfPaymentService()
terminal_service = TerminalService()


@one_tap.route('/')
@login_required()
def index():
    if is_provider(current_user):
        providers = []

    if is_payer(current_user):
        claim_ids = [gop.claim.id for gop in current_user.payer.guarantees_of_payment if gop.claim]
        providers = Provider.query.join(Claim, Provider.claims)\
            .filter(Claim.id.in_(claim_ids)).all()

    if is_admin(current_user):
        providers = Provider.query.all()

    members = member_service.all_for_user(current_user).all()

    claims_query = claim_service.all_for_user(current_user)\
                                .order_by(desc(Claim.datetime))
    claims = claims_query.all()
    total_claims = len(claims)

    # get the claims in the given month ranges
    months = ['0', '1', '3', '5', '6', '24']
    historical = {}
    for month in months:
        historical[month] = Claim.for_months(int(month))

    amount_summary = {'total': Claim.amount_sum(0)[0]}
    months = ['0', '1', '2', '3', '4', '5', '6', '24']
    for month in months:
        amount_summary[month] = Claim.amount_sum(int(month))

    in_patients = {
        'total': len(patients_amount(claims, 'in')),
        '1_month': len(patients_amount(historical['1'][0], 'in')),
        '3_months': len(patients_amount(historical['3'][0], 'in')),
        '6_months': len(patients_amount(historical['6'][0], 'in')),
        '24_months': len(patients_amount(historical['24'][0], 'in'))
    }

    out_patients = {
        'total': len(patients_amount(claims, 'out')),
        '1_month': len(patients_amount(historical['1'][0], 'out')),
        '3_months': len(patients_amount(historical['3'][0], 'out')),
        '6_months': len(patients_amount(historical['6'][0], 'out')),
        '24_months': len(patients_amount(historical['24'][0], 'out'))
    }

    by_cost = {}
    by_icd = {}

    # calculate values for the Historical Claims section table
    for key, value in historical.items():
        for claim in value[0]:
            # calculate values for the Medical Summary By Cost table
            if not claim.amount in by_cost:
                by_cost[claim.amount] = {}

            if not key in by_cost[claim.amount]:
                by_cost[claim.amount][key] = 1
            else:
                by_cost[claim.amount][key] += 1

            # calculate values for the Medical Summary By ICD Code table
            if not claim.icd_code in by_icd:
                by_icd[claim.icd_code] = {}

            if not key in by_icd[claim.icd_code]:
                by_icd[claim.icd_code][key] = 1
            else:
                by_icd[claim.icd_code][key] += 1

    in_patients_perc = percent_of(in_patients['total'],
                            out_patients['total'] + in_patients['total'])

    out_patients_perc = percent_of(out_patients['total'],
                            out_patients['total'] + in_patients['total'])

    open_claims = claims_query.filter_by(status="Open").all()
    open_claims_perc = percent_of(len(open_claims), len(claims))

    closed_claims =  claims_query.filter_by(status="Closed").all()
    closed_claims_perc = percent_of(len(closed_claims), len(claims))

    amount_chart_data = {
        'labels': [],
        'values': []
    }
    # fill in the chart data for the 5 months
    for months in reversed(range(6)):
        month_name = month_abbr[monthdelta(datetime.now(), months * -1).month]
        amount_chart_data['labels'].append(month_name)
        amount_chart_data['values'].append(amount_summary[str(months)][2])

    in_patients_data = [
        len(patients_amount(historical['5'][0], 'in')),
        len(patients_amount(historical['3'][0], 'in')),
        len(patients_amount(historical['0'][0], 'in'))
    ]
    out_patients_data = [
        len(patients_amount(historical['5'][0], 'out')),
        len(patients_amount(historical['3'][0], 'out')),
        len(patients_amount(historical['0'][0], 'out'))
    ]

    pagination, claims = claim_service.prepare_pagination(claims_query)

    context = {
        'providers': providers,
        'members': members,
        'claims': claims,
        'pagination': pagination,
        'historical': historical,
        'out_patients': out_patients,
        'in_patients': in_patients,
        'amount_summary': amount_summary,
        'total_claims': total_claims,
        'by_cost': by_cost,
        'by_icd': by_icd,
        'in_patients_perc': in_patients_perc,
        'out_patients_perc': out_patients_perc,
        'open_claims':open_claims,
        'open_claims_perc':open_claims_perc,
        'closed_claims':closed_claims,
        'closed_claims_perc':closed_claims_perc,
        'in_patients_data': in_patients_data,
        'out_patients_data': out_patients_data,
        'today': datetime.now(),
        'amount_chart_data': amount_chart_data
    }

    return render_template('one_tap/index.html', **context)


@one_tap.route('/static/uploads/<filename>')
@login_required()
def block_unauthenticated_url(filename):
    return send_from_directory(os.path.join('static','uploads'),filename)


@one_tap.route('/terminals')
@login_required(deny_types=['payer'])
def terminals():
    # retreive the all current user's terminals
    terminals = terminal_service.all_for_user(current_user)

    pagination, terminals = terminal_service.prepare_pagination(terminals)

    # render the "terminals.html" template with the given terminals
    return render_template('one_tap/terminals.html', terminals=terminals,
                                             pagination=pagination)


@one_tap.route('/terminal/<int:terminal_id>')
@login_required(deny_types=['payer'])
def terminal(terminal_id):
    terminal = terminal_service.get_for_user(terminal_id, current_user)

    claims = terminal.claims

    pagination, claims = claim_service.prepare_pagination(claims)

    # render the "terminal.html" template with the given terminal
    return render_template('one_tap/terminal.html', terminal=terminal,
                                            claims=claims,
                                            pagination=pagination)


@one_tap.route('/terminal/add', methods=['GET', 'POST'])
@login_required(types=['provider'])
def terminal_add():
    form = TerminalForm()

    # if the form was sent
    if form.validate_on_submit():
        terminal = Terminal(provider_id=current_user.provider.id)

        terminal_service.update_from_form(terminal, form)

        flash('The terminal has been added')
        return redirect(url_for('one_tap.terminals'))

    return render_template('one_tap/terminal-form.html', form=form)


@one_tap.route('/terminal/<int:terminal_id>/edit', methods=['GET', 'POST'])
@login_required(types=['provider'])
def terminal_edit(terminal_id):
    # retreive the current user's terminal by its ID
    terminal = terminal_service.get_for_user(terminal_id, current_user)

    form = TerminalForm()

    # if the form was sent
    if form.validate_on_submit():
        terminal_service.update_from_form(terminal, form)

        flash('Data has been updated.')

     # if the form was just opened
    if request.method != 'POST':
        form.prepopulate(terminal)

    # render the "terminal-form.html" template with the given terminal
    return render_template('one_tap/terminal-form.html', form=form, terminal=terminal)


@one_tap.route('/claims')
@login_required()
def claims():
    claims = claim_service.all_for_user(current_user)\
                          .order_by(desc(Claim.datetime))

    pagination, claims = claim_service.prepare_pagination(claims)

    # render the "claims.html" template with the given transactions
    return render_template('one_tap/claims.html', claims=claims,
                                          pagination=pagination)


@one_tap.route('/claim/<int:claim_id>', methods=['GET', 'POST'])
@login_required()
def claim(claim_id):
    claim = claim_service.get_for_user(claim_id, current_user)

    if claim.new_claim:
        claim.new_claim = 0
        db.session.add(claim)
        db.session.commit()

    form = GOPForm()

    form.payer.choices += [(p.id, p.company) for p in \
                           current_user.provider.payers]

    form.icd_codes.choices = [(i.id, i.code) for i in \
        ICDCode.query.filter(ICDCode.code != 'None' and ICDCode.code != '')]

    form.doctor_name.choices += [(d.id, d.name + ' (%s)' % d.doctor_type) \
                                for d in current_user.provider.doctors]

    if is_provider(current_user) and request.method != 'POST':
        form.name.data = claim.member.name
        form.dob.data = claim.member.dob
        form.policy_number.data = claim.member.policy_number
        form.admission_date.data = claim.datetime
        form.admission_time.data = claim.datetime
        form.quotation.data = claim.amount
        form.gender.data = claim.member.gender
        form.national_id.data = claim.member.national_id
        form.current_national_id.data = claim.member.national_id
        form.tel.data = claim.member.tel

        form.medical_details_previously_admitted.data = datetime.now()

    if form.validate_on_submit():
        photo_filename = photo_file_name_santizer(form.member_photo)

        member = Member.query.filter_by(
            national_id=form.national_id.data).first()

        if not member:
            member = Member(photo=photo_filename)

            member_service.update_from_form(member, form,
                                            exclude=['member_photo'])

        medical_details = medical_details_service.create(
            **{field.name.replace('medical_details_', ''): field.data \
               for field in form \
               if field.name.replace('medical_details_', '') \
               in medical_details_service.columns})

        payer = Payer.query.get(form.payer.data)

        gop = GuaranteeOfPayment(
                claim=claim,
                payer=payer,
                member=member,
                provider=current_user.provider,
                doctor_name=Doctor.query.get(int(form.doctor_name.data)).name,
                status='pending',
                medical_details=medical_details)

        for icd_code_id in form.icd_codes.data:
            icd_code = ICDCode.query.get(int(icd_code_id))
            gop.icd_codes.append(icd_code)

        exclude = ['doctor_name', 'status', 'icd_codes']
        gop_service.update_from_form(gop, form, exclude=exclude)

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
            user = User(email=gop.payer.pic_email,
                        password=rand_pass,
                        user_type='payer',
                        payer=gop.payer)
            db.session.add(user)
            # getting payer id for sending notification 
            notification_payer_id = user.id

        gop_service.send_email(gop=gop, recipient_email=recipient_email,
                               user=user, rand_pass=rand_pass)

        flash('Your GOP request has been sent.')

    if form:
        return render_template('one_tap/claim.html', claim=claim, form=form)
    else:
        return render_template('one_tap/claim.html', claim=claim)


@one_tap.route('/claim/add', methods=['GET', 'POST'])
@login_required(types=['provider'])
def claim_add():
    terminals = terminal_service.all_for_user(current_user)
    members = member_service.all_for_user(current_user)

    form = ClaimForm()

    form.terminal_id.choices += [(terminal.id, terminal.serial_number) \
                                 for terminal in terminals]
    form.member_id.choices += [(member.id, member.name) for member in members]

    # if the form was sent
    if form.validate_on_submit():
        claim = Claim(provider_id=current_user.provider.id)
        claim_service.update_from_form(claim, form)

        member = Member.query.get(form.member_id.data)

        flash('The claim has been added.')

        return redirect(url_for('one_tap.claims'))

    return render_template('one_tap/claim-form.html', form=form)


@one_tap.route('/claim/<int:claim_id>/edit', methods=['GET', 'POST'])
@login_required(deny_types=['payer'])
def claim_edit(claim_id):
    claim = claim_service.get_for_user(claim_id, current_user)
    members = member_service.all_for_user(current_user)
    terminals = terminal_service.all_for_user(current_user)

    form = ClaimForm()

    form.terminal_id.choices += [(terminal.id, terminal.serial_number) \
                                 for terminal in terminals]
    form.member_id.choices += [(member.id, member.name) for member in members]

    # if the form was sent
    if form.validate_on_submit():
        claim_service.update_from_form(claim, form)

        flash('Data has been updated')

     # if the form was just opened
    if request.method != 'POST':
        # fill in the form with the member's data
        form.prepopulate(model=claim, exclude=['datetime'])

        form.date.data = claim.datetime
        form.time.data = claim.datetime

    return render_template('one_tap/claim-form.html', form=form, claim=claim)


@one_tap.route('/members')
@login_required()
def members():
    members = member_service.all_for_user(current_user)

    pagination, members = member_service.prepare_pagination(members)

    # render the "members.html" template with the given members
    return render_template('one_tap/members.html', members=members,
                                           pagination=pagination)


@one_tap.route('/member/<int:member_id>')
@login_required()
def member(member_id):
    member = member_service.get_for_user(member_id, current_user)

    claims = member.claims

    pagination, claims = claim_service.prepare_pagination(claims)

    # render the "member.html" template with the given member
    return render_template('one_tap/member.html', member=member, claims=claims,
                                          pagination=pagination)


@one_tap.route('/member/add', methods=['GET', 'POST'])
@login_required(types=['provider'])
def member_add():
    form = MemberForm()

    # if the form was sent
    if form.validate_on_submit():
        # update the photo
        photo_filename = photo_file_name_santizer(form.photo)

        member = Member(photo=photo_filename)

        # append the patient to the provider
        # by which the patient has been created
        member.providers.append(current_user.provider)

        # save the form data to the object
        member_service.update_from_form(member, form, exclude=['photo'])

        return redirect(url_for('one_tap.members'))

    return render_template('one_tap/member-form.html', form=form)


@one_tap.route('/member/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required(types=['provider'])
def member_edit(member_id):
    # retreive the current user's member by its ID
    member = member_service.get_for_user(member_id, current_user)

    form = MemberForm()

    if form.validate_on_submit():
        if form.photo.data:
            member.photo = photo_file_name_santizer(form.photo)

        member_service.update_from_form(member, form, exclude=['photo'])

        return redirect(url_for('one_tap.member', member_id=member.id))

     # if the form was just opened
    if request.method != 'POST':
        form.marital_status.default = member.marital_status
        form.patient_type.default = member.patient_type
        form.gender.default = member.gender
        form.process()

        # fill in the form with the member's data
        exclude = ['marital_status', 'patient_type', 'gender']
        form.prepopulate(model=member, exclude=exclude)

    return render_template('one_tap/member-form.html', form=form, member=member)


@one_tap.route('/setup', methods=['GET', 'POST'])
@login_required()
def setup():
    return render_template('one_tap/setup.html')


@one_tap.route('/search', methods=['GET'])
def search():
    found = {
        'results': []
    }
    query = request.args.get('query')
    if not query or not current_user.is_authenticated:
        return jsonify(found)

    query = query.lower()

    claims = Claim.query.all()

    for claim in claims:
        # initialazing location variable to put the claim's terminal data here,
        # if no terminal in a claim's object, it remains None
        location = None

        if claim.terminal:
            location = claim.terminal.location

        if query in str(claim.status).lower() \
        or query in str(claim.claim_number).lower() \
        or query in str(claim.claim_type).lower() \
        or query in str(claim.datetime) \
        or query in str(claim.admitted) \
        or query in str(claim.discharged) \
        or query in str(location).lower() \
        or query in str(claim.amount) :
            found['results'].append(claim.id)
            continue

    return jsonify(found)


@one_tap.route('/icd-code/search', methods=['GET'])
def icd_code_search():
    query = request.args.get('query').lower()

    icd_codes = ICDCode.query.all()

    result = []
    fields = ['code', 'description', 'common_term']
    find = lambda query, obj, attr: query in getattr(obj, attr).lower()

    for icd_code in icd_codes:
        if any([find(query, icd_code, field) for field in fields]):
            result.append(icd_code)

    return render_template('one_tap/icd-code-search-results.html', icd_codes=result,
                               query=query)