import string
import random

from datetime import datetime

from flask import render_template, redirect, request, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message

from . import auth
from .forms import LoginForm, RegistrationForm, ForgotPasswordForm
from .. import mail
from ..models import db, User, Provider, Payer


def pass_generator(size=6, chars=string.ascii_uppercase + string.digits):
    '''
    generates a random passoword to be sent to new payers registration
    '''
    return ''.join(random.choice(chars) for _ in range(size))


def login_validation(form):
    '''
    user login validation operation
    '''
    user = User.query.filter_by(email=form.email.data, role='admin').first()

    if not user:
        if form.user_type.data:
            user = User.query.filter_by(email=form.email.data,
                user_type=form.user_type.data).first()
        else:
            user = User.query.filter_by(email=form.email.data).first()

    if user is not None:
        if not user.bad_logins:
            user.bad_logins = 0
            db.session.add(user)

        if user.bad_logins >= 5 and \
            (datetime.now() - user.last_attempt).total_seconds() < 600 and \
            request.environ['REMOTE_ADDR'] == user.last_login_ip:
            # if there's more than 5 bad logins, block login for 10 minutes
            flash('Invalid username or password. ' + \
                  'You have been blocked for 10 minutes. ')
            return render_template('auth/login.html', form=form)

    if user is not None and user.verify_password(form.password.data):
        login_user(user, form.remember_me.data)
        user.bad_logins = 0
        user.last_attempt = datetime.now()
        user.last_login_ip = request.environ['REMOTE_ADDR']
        db.session.add(user)

        return redirect(request.args.get('next') or url_for('main.index'))
    else:
        if user is not None:
            if request.environ['REMOTE_ADDR'] != user.last_login_ip:
                user.bad_logins = 0
            user.bad_logins += 1
            user.last_attempt = datetime.now()
            user.last_login_ip = request.environ['REMOTE_ADDR']
            db.session.add(user)

        flash('Invalid username or password.')
        return render_template('auth/login.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    '''
    logging in a user
    '''
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()

    if form.validate_on_submit():
        return login_validation(form)

    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    '''
    logging out a user
    '''
    logout_user()

    # if the user has the notification session variable
    # containing the GOP statuses, we delete it when
    # the user is logged out
    if session.get('curr_gops', None):
        del session['curr_gops']

    flash('You have been logged out.')
    return redirect(url_for('main.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    '''
    register new payer and providers
    '''
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegistrationForm()

    if form.validate_on_submit():
        if form.user_type.data == 'provider':
            user = User(email=form.email.data,
                    role='user',
                    premium=0,
                    password=form.password.data,
                    user_type=form.user_type.data,
                    provider=Provider())
        elif form.user_type.data == 'payer':
            user = User(email=form.email.data,
                    role='user',
                    premium=0,
                    password=form.password.data,
                    user_type=form.user_type.data,
                    payer=Payer())

        db.session.add(user)
        flash('You can now login.')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)


@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    '''
    forgot password operation
    '''
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        rand_pass = pass_generator(size=8)
        user.password = rand_pass
        db.session.add(user)

        msg = Message("Forgot password email",
                      sender=("MediPay",
                              "request@app.medipayasia.com"),
                      recipients=[user.email])

        msg.html = """
        <h3>You have requested a new password for your MediPay account.</h3>
        <p>Here is your access credentials:</p>
        <p>Login: %s<br>
        Password: %s</p>
        """ % (user.email, rand_pass)

        mail.send(msg)
        flash('Please, check your email for a new password.')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form)

