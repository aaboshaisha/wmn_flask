from flask import (Blueprint, request, jsonify, current_app, flash, redirect, render_template, url_for)
from flask import session as flask_session
import stripe
import os
from myapp.db import get_db
from dotenv import load_dotenv
import time

bp = Blueprint('payment', __name__, url_prefix='/payment')

load_dotenv()
SUBSCRIPTION_PLANS = {
    'basic': {'name': 'Basic', 'price': 500, 'audio_limit': 12000, 'word_limit': 40000, 'stripe_price_id': os.getenv('BASIC_PRICE_ID')},
    'standard': {'name': 'Standard', 'price': 1000, 'audio_limit': 30000, 'word_limit': 100000, 'stripe_price_id': os.getenv('STANDARD_PRICE_ID')},
    'premium': {'name': 'Premium', 'price': 2000, 'audio_limit': 60000, 'word_limit': 200000, 'stripe_price_id': os.getenv('PREMIUM_PRICE_ID')}
}

@bp.route('/checkout', methods=['GET'])
def checkout():
    email = request.args.get('email')
    return render_template('payment/checkout.html', email=email)

@bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    domain_url = current_app.config.get('DOMAIN_URL')

    email = request.form.get('email')
    plan = request.form.get('plan')
    
    if plan not in SUBSCRIPTION_PLANS:
        return jsonify(error='Invalid plan selected'), 400
    
    try:
        # Create a checkout session with a 7-day free trial
        checkout_session = stripe.checkout.Session.create(
            customer_email=email,
            line_items=[{'price': SUBSCRIPTION_PLANS[plan]['stripe_price_id'], 'quantity': 1}],
            mode='subscription',
            subscription_data={
                'trial_period_days': 7  # This adds a 7-day free trial
            },
            success_url=f"{domain_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{domain_url}/payment/cancel"
        )
        return redirect(checkout_session.url)

    except stripe.error.StripeError as e:
        return str(e), 403

@bp.route('/success')
def success():
    flash('You have successfully subscribed! You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/cancel')
def cancel():
    return render_template('payment/cancel.html')

@bp.route('/customer-portal')
def customer_portal():
    # Ensure user is logged in
    if 'user_id' not in flask_session:
        return redirect(url_for('auth.login'))

    db = get_db()
    user = db.execute('SELECT * FROM user WHERE id = ?', (flask_session['user_id'], )).fetchone()

    if not user:
        flash('User not found', 'error')
        return redirect(url_for('index'))

    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')

    try:
        session = stripe.billing_portal.Session.create(
            customer=user['stripe_customer_id'],
            return_url=url_for('index', _external=True),)
        return redirect(session.url)
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('index'))


endpoint_secret = 'whsec_ecd13216721967c54f8c939599a198a559158a8039415195dcbeef8a9502e8b2'


import logging
logging.basicConfig(level=logging.DEBUG)

@bp.route('/webhook', methods=['POST'])
def webhook():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    payload = request.data
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        logging.error(f"Invalid payload: {e}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        logging.error(f"Invalid signature: {e}")
        return 'Invalid signature', 400
    
    logging.debug(f"Received event: {event['type']}")
    db = get_db()
    
    event_handlers = {
        'checkout.session.completed': handle_checkout_session_completed,
        'customer.subscription.updated': handle_subscription_updated,
    }
    
    event_type = event['type']
    if event_type in event_handlers:
        try:
            event_handlers[event_type](event['data']['object'], db)
        except Exception as e:
            logging.error(f"Error handling {event_type}: {str(e)}")
            return 'Error processing webhook', 500
    
    return '', 200

def handle_checkout_session_completed(session, db):
    customer_email = session.get('customer_details', {}).get('email')
    subscription_id = session.get('subscription')
    
    if customer_email and subscription_id:
        subscription = stripe.Subscription.retrieve(subscription_id)
        customer_id = subscription.customer
        plan_id = subscription['items']['data'][0]['price']['id']
        current_period_end = subscription['current_period_end']
        
        db.execute('''UPDATE user 
                      SET stripe_customer_id = ?,
                          subscription_status = ?, 
                          subscription_plan = ?,
                          subscription_end_date = ?,
                          audio_length = ?,
                          word_count = ?
                      WHERE email = ?''', 
                   (customer_id, 'active', plan_id, current_period_end, 0, 0, customer_email))
        db.commit()
        logging.debug(f"User updated successfully for email: {customer_email}")

def handle_subscription_updated(subscription, db):
    customer_id = subscription['customer']
    status = subscription['status']
    plan_id = subscription['items']['data'][0]['price']['id']
    current_period_end = subscription['current_period_end']
    
    db.execute('''UPDATE user 
               SET subscription_plan = ?,
               subscription_end_date = ?,
               audio_length = ?,
               word_count = ?
               WHERE stripe_customer_id = ?''', 
               (plan_id, current_period_end, 0, 0, customer_id))
    db.commit()
    logging.debug(f"User subscription updated for customer: {customer_id}")

