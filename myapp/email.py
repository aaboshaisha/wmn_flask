from flask import Blueprint, current_app, request, g, redirect, url_for
from flask_mail import Message
from . import mail
from myapp.auth import login_required

bp = Blueprint('email', __name__)

@login_required
@bp.route('/send', methods=['POST'])
def send():
    if g.user is None:
        return redirect(url_for('auth.login'))
    user_email = g.user['email']
    msg = Message(
        'writemynotes - Your Clinical Note',
        sender = 'info@writemynotes.co.uk',
        # recipients=['amralaauk@icloud.com'] #for testing
        recipients=[user_email]
    )
    msg.body = request.form.get('output')

    try:
        mail.send(msg)
        return 'Email sent successfully'
    except Exception as e:
        return f'An error has occured while trying to send email: {str(e)}'