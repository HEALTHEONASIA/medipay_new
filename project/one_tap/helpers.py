import os, random, string
from werkzeug.utils import secure_filename
from .. import config, redis_store

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1] in config['production'].ALLOWED_EXTENSIONS

def pass_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def photo_file_name_santizer(photo):
    filename = secure_filename(photo.data.filename)

    if filename and allowed_file(filename):
        filename = str(random.randint(100000, 999999)) + filename
        photo.data.save(
            os.path.join(config['production'].UPLOAD_FOLDER, filename))

    if not filename:
        filename = ''

    if filename:
        photo_filename = '/static/uploads/' + filename
    else:
        photo_filename = '/static/img/person-solid.png'

    return photo_filename

def safe_div(dividend, divisor):
    try:
        result = dividend / divisor
    except ZeroDivisionError:
        result = 0.00
    return result

def percent_of(part, total):
    return safe_div(float(part), float(total)) * 100

def patients_amount(claims, _type):
    """Returns the in-patients for the given claims."""
    result = []

    for claim in claims:
        if claim.member.patient_type == _type:
            result.append(claim.member.id)

    result = list(set(result))

    return result