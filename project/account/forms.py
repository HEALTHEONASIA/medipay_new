import re

from flask_wtf import Form
from flask import request
from werkzeug.utils import secure_filename
from wtforms import StringField, RadioField, SubmitField, TextAreaField
from wtforms import HiddenField, SelectField, FileField, ValidationError
from wtforms import PasswordField, SelectMultipleField, BooleanField
from wtforms.validators import Required, Email, Length, EqualTo, URL
from flask_login import current_user

from ..models import Payer, Member, User, Provider


class BaseForm(Form):
    '''
    Base Class for all other form classes in the account section
    '''
    class Meta:
        '''
        Meta properties for binding fields for all oter form classes in the account section
        '''
        def bind_field(self, form, unbound_field, options):
            '''
            Removes trailing and leading spcaes from all fields submitted in form
            '''
            filters = unbound_field.kwargs.get('filters', [])
            filters.append(strip_filter)
            return unbound_field.bind(form=form, filters=filters, **options)


def strip_filter(value):
    '''
    removes leading and trailing white space
    '''
    if value is not None and hasattr(value, 'strip'):
        return value.strip()
    return value


def validate_email_address(form, field):
    '''
    validates email address
    '''
    if field.data:
        match = re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"\
          ,field.data)
        if match == None:
            raise ValidationError('Invalid Email address.')

        if len(field.data) < 1 or len(field.data) > 64:
            raise ValidationError('Field must be between 1 and 64 ' + \
             'characters long.')


def validate_numeric(form, field):
    '''
    validates numeric data type on the input field
    '''
    if field.data:
        match = re.match(r"^[0-9]+$", field.data)
        if match == None:
            raise ValidationError('Only digits are allowed.')


def validate_phone(form, field):
    '''
    validates phone data type on the input field
    '''
    if field.data:
        match = re.match(r"^\+?[0-9]+$", field.data)
        if match == None:
            raise ValidationError('Invalid phone number.')


def validate_payer_email_address(form, field):
    '''
    checks if email address is already registered in the system or not
    '''
    if field.data:
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

        if Payer.query.filter_by(pic_email=field.data).first() or \
            Payer.query.filter_by(pic_alt_email=field.data).first():
            raise ValidationError('Email already registered.')


def validate_comma_sep_dec(form, field):
    '''
    removes comma and minus sign from fee input and stores the value if it is greater than 0
    '''
    field.data = field.data.replace(',' ,'').replace('-','')
    try:
        field.data = float(field.data)
        if field.data < 0:
            raise ValidationError('Fee cannot be less than 0')
    except ValueError:
        field.data = 0.0
        
def validate_empty_fee(form, field):
    '''
    validates empty fee field on the form
    '''
    try:
        field.data = float(field.data)
        if field.data < 0:
            raise ValidationError('Fee cannot be less than 0')
    except ValueError:
        field.data = 0.0

def validate_pic_and_alt_email_not_equal(form, field):
    '''
    checks if both the email address provided are different or not
    '''
    if form.pic_email.data.lower() == form.pic_alt_email.data.lower():
        raise ValidationError('PIC and ALT email cannot be same')


class ChangeProviderInfoForm(BaseForm):
    '''
    Add provider information form
    '''
    company = StringField('Company')
    provider_type = StringField('Provider Type')
    pic = StringField('PIC')
    pic_email = StringField('PIC email', validators=[Required(),
                                                     validate_email_address])
    pic_alt_email = StringField('PIC alt. email',
                                validators=[validate_email_address,
                                            validate_pic_and_alt_email_not_equal])
    tel = StringField('Telephone', validators=[validate_phone])
    country = SelectField('Country', validators=[Required()],
                          choices=[('Singapore', 'Singapore'),
                                   ('Malaysia', 'Malaysia'),
                                   ('Indonesia', 'Indonesia'),
                                   ('Thailand', 'Thailand'),
                                   ('HK', 'HK'),
                                   ('China', 'China'),
                                   ('Vietnam', 'Vietnam'),
                                   ('Philippines', 'Philippines'),
                                   ('Other', 'Other')])
    other_country = StringField('Other country')
    street_name = StringField('Street name')
    street_number = StringField('Street number', validators=[validate_numeric])
    state = StringField('State')
    postcode = StringField('Postcode', validators=[validate_numeric])
    save = SubmitField('Save')


class ChangePayerInfoForm(BaseForm):
    '''
    Add payer information form
    '''
    company = StringField('Company')
    payer_type = SelectField('Type', validators=[Required()],
                             choices=[('Insurer', 'Insurer'),
                                      ('TPA', 'TPA'),
                                      ('Corporate', 'Corporate')])
    pic = StringField('PIC')
    pic_email = StringField('PIC email', validators=[Required(),
                                                     validate_email_address])
    pic_alt_email = StringField('PIC alt. email',
                                validators=[validate_email_address,
                                            validate_pic_and_alt_email_not_equal])
    tel = StringField('Telephone', validators=[validate_phone])
    country = SelectField('Country', validators=[Required()],
                          choices=[('Singapore', 'Singapore'),
                                   ('Malaysia', 'Malaysia'),
                                   ('Indonesia', 'Indonesia'),
                                   ('Thailand', 'Thailand'),
                                   ('HK', 'HK'),
                                   ('China', 'China'),
                                   ('Vietnam', 'Vietnam'),
                                   ('Philippines', 'Philippines'),
                                   ('Other', 'Other')])
    other_country = StringField('Other country')
    street_name = StringField('Street name')
    street_number = StringField('Street number', validators=[validate_numeric])
    state = StringField('State')
    postcode = StringField('Postcode', validators=[validate_numeric])
    save = SubmitField('Save')


class ProviderPayerSetupEditForm(BaseForm):
    '''
    Edit payer from provider form
    '''
    company = StringField('Name', validators=[Required()])
    payer_type = SelectField('Type', validators=[Required()],
                             choices=[('Insurer', 'Insurer'),
                                      ('TPA', 'TPA'),
                                      ('Corporate', 'Corporate')])
    pic_email = StringField('Email 1', validators=[Email(), Length(1, 64)])
    pic_alt_email = StringField('Email 2', validators=[Email(), Length(1, 64)])
    pic = StringField('PIC')
    tel = StringField('Telephone', validators=[validate_phone])
    country = SelectField('Country', validators=[Required()],
                          choices=[('Singapore', 'Singapore'),
                                   ('Malaysia', 'Malaysia'),
                                   ('Indonesia', 'Indonesia'),
                                   ('Thailand', 'Thailand'),
                                   ('HK', 'HK'),
                                   ('China', 'China'),
                                   ('Vietnam', 'Vietnam'),
                                   ('Philippines', 'Philippines'),
                                   ('Other', 'Other')])
    other_country = StringField('Other country')
    current_payer_id = HiddenField('Payer ID')
    current_user_id = HiddenField('User ID')
    contract_number = StringField('Contract reference number')
    submit = SubmitField('Save')

    def validate_pic_email(self, field):
        '''
        checks if the provider email address is already registered in the system or not
        '''
        if User.query.filter_by(
          email=field.data, user_type='provider').first():
            raise ValidationError('Email already registered.')

    def validate_company(self, field):
        '''
        checks if the provider name is already registered or not
        '''
        provider = Provider.query.filter_by(
            user_id=int(self.current_user_id.data)).first()
        count = 0
        for payer in provider.payers:
            if payer.company == field.data:
                count += 1
        if count > 1:
            raise ValidationError('The company name already exists.')


class ProviderPayerSetupAddForm(ProviderPayerSetupEditForm):
    '''
    Add payer from provider form
    '''
    def validate_company(self, field):
        '''
        checks if the payer name is already registered or not
        '''
        provider = Provider.query.filter_by(
            user_id=int(self.current_user_id.data)).first()
        count = 0
        for payer in provider.payers:
            if payer.company == field.data:
                count += 1
        if count > 0:
            raise ValidationError('The company name already exists.')


class EditAccountForm(BaseForm):
    '''
    Change password form for members
    '''
    old_password = PasswordField('Old password', validators=[Required()])
    password = PasswordField('Password', validators=[
        Required(), EqualTo('password2', message='Passwords must match.')])
    password2 = PasswordField('Confirm password', validators=[Required()])
    submit = SubmitField('Save')

    def validate_old_password(self, field):
        '''
        validates the old password before changing it to the new password
        '''
        if not current_user.verify_password(field.data):
              raise ValidationError('The password is wrong.')


class EditAccountAdminForm(BaseForm):
    '''
    Chnage password form for admin
    '''
    password = PasswordField('Password', validators=[
        Required(), EqualTo('password2', message='Passwords must match.')])
    password2 = PasswordField('Confirm password', validators=[Required()])
    submit = SubmitField('Save')


class UserSetupForm(BaseForm):
    '''
    User setup form
    '''
    name = StringField('Name')
    email = StringField('Email', validators=[Required(), Email(),
                                             Length(1, 64)])
    current_user_id = HiddenField('Current user id')
    submit = SubmitField('Save')

    def validate_email(self, field):
        '''
        checks if the user's email address already registered in the system or not
        '''
        payer = Payer.query.filter_by(pic_email=field.data).first()
        user = User.query.filter_by(email=field.data).first()
        # if there's a user with the given email and it's not the current one
        if (user and user.id != int(self.current_user_id.data)) or \
           (payer and not payer.user): # if there's a payer expecting to be registered
              raise ValidationError('Email already registered.')


class UserSetupAdminForm(UserSetupForm):
    '''
    Admin User setup form
    '''
    role = RadioField('Role', validators=[Required()],
                      choices=[('user_admin', 'Admin'),
                               ('user', 'User')])
    premium = RadioField('Premium', validators=[Required()],
                         choices=[('0', 'No'),
                                  ('1', 'Yes')])


class BillingCodeForm(BaseForm):
    '''
    Billing code form
    '''
    room_and_board = StringField('Room and board', validators=[Required(),
                                                      validate_comma_sep_dec])
    doctor_visit_fee = StringField('Doctor_visit_fee',
                                   validators=[validate_comma_sep_dec])
    doctor_consultation_fee = StringField('Doctor consultation fee',
                                           validators=[validate_comma_sep_dec])
    specialist_visit_fee = StringField('Specialist visit fee',
                                       validators=[validate_comma_sep_dec])
    specialist_consultation_fee = StringField('Specialist consultation fee',
                                           validators=[validate_comma_sep_dec])
    medicines = StringField('Medicines',
                            validators=[validate_comma_sep_dec])
    administration_fee = StringField('Administration fee',
                                     validators=[validate_comma_sep_dec])
    submit = SubmitField('Submit')


class DoctorForm(BaseForm):
    '''
    Add Doctor form
    '''
    name = StringField('Name', validators=[Required()])
    department = StringField('Department', validators=[Required()])
    photo = FileField('Photo')
    doctor_type = SelectField('Type', validators=[Required()],
                                      choices=[('GP', 'GP'),
                                               ('Specialist', 'Specialist'),
                                               ('Surgeon', 'Surgeon'),
                                               ('Internal Medicine',
                                                'Internal Mecicine'),
                                               ('Obstretic and Gynecologist',
                                                'Obstretic and Gynecologist'),
                                               ('Pediatrician', 'Pediatrician'),
                                               ('Skin Specialist',
                                                'Skin Specialist')])
    submit = SubmitField('Save')

    def validate_photo(self, field):
        '''
        validates the doctor image upload
        '''
        if field.data:
            filename = secure_filename(field.data.filename)
            allowed = ['jpg', 'jpeg', 'png', 'gif']
            if not ('.' in filename and filename.rsplit('.', 1)[1] in allowed):
              raise ValidationError("Only image files are allowed.")


class SingleCsvForm(BaseForm):
    '''
    CSV upload form
    '''
    csv_file = FileField('Csv file', validators=[Required()])
    submit = SubmitField('Save')

    def validate_csv_file(self, field):
        '''
        validates if the file uploaded is a csv or not
        '''
        filename = secure_filename(field.data.filename)
        if not ('.' in filename and filename.rsplit('.', 1)[1] == 'csv'):
          raise ValidationError("Only '.csv' files are allowed.")


class UserUpgradeForm(BaseForm):
    '''
    Upgrade to premium users form
    '''
    email = StringField('Email', validators=[Required(), Email(),
                                             Length(1, 64)])
    submit = SubmitField('Request upgrade to Premium')
