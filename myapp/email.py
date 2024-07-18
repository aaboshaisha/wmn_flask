from flask import Blueprint, current_app, request, g, redirect, url_for
from myapp.auth import login_required
import smtplib
from email.mime.text import MIMEText

bp = Blueprint('email', __name__)

import os
from dotenv import load_dotenv
load_dotenv()

def send_email(subject, body, to_email):
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = smtp_username
    msg['To'] = to_email

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)

@bp.route('/send', methods=['POST'])
@login_required
def send():
    if g.user is None:
        return redirect(url_for('auth.login'))
    user_email = g.user['email']
    try:
        send_email("writemynotes - Your Clinical Note", request.form.get('output'), user_email)
        return "Email sent successfully!"
        
    except Exception as e:
       return f'An error has occured while trying to send email: {str(e)}' 

@bp.route('/send_feedback', methods=['POST'])
@login_required
def send_feedback():
    if g.user is None:
        return redirect(url_for('auth.login'))
    user_email = g.user['email']
    username = request.form.get('name')
    email = g.user['email']
    feedback_message = request.form.get('feedback')
    try:
        send_email("writemynotes - User Feedback", feedback_message , 'support@writemynotes.co.uk')
        return redirect(url_for('index.thank_you'))
    except Exception as e:
       return f'An error has occured while trying to send email: {str(e)}' 


# from postmarker.core import PostmarkClient

# @login_required
# @bp.route('/send', methods=['POST'])
# def send():
#     if g.user is None:
#         return redirect(url_for('auth.login'))
#     user_email = g.user['email']
#     # Create an instance of the Postmark client
#     postmark = PostmarkClient(server_token=current_app.config.get('POSTMARK_SERVER_API_TOKEN'))

#     try:
#         # Send an email
#         postmark.emails.send(
#         From='support@writemynotes.co.uk',
#         To=user_email,
#         Subject='writemynotes - Your Clinical Note',
#         HtmlBody=f"<html><body>{request.form.get('output')}</body></html>"
#         )
#         return 'Email sent successfully'
#     except Exception as e:
#         return f'An error has occured while trying to send email: {str(e)}'
