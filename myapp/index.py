from flask import Blueprint, render_template
from myapp.auth import login_required

bp = Blueprint('index', __name__)

@bp.route('/')
def index():
    return render_template('index/index.html')

@bp.route('/pricing')
def pricing():
    return render_template('index/pricing.html')

@bp.route('/feedback')
@login_required
def feedback():
    return render_template('index/feedback.html')

@bp.route('/faq')
def faq():
    return render_template('index/faq.html')

@bp.route('/thank_you')
@login_required
def thank_you():
    return render_template('index/thank_you.html')