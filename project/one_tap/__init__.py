from flask import Blueprint

one_tap = Blueprint('one_tap', __name__)

from . import views