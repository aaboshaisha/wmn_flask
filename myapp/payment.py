from flask import (Blueprint, request, jsonify, current_app, flash, redirect, render_template, url_for)
from flask import session as flask_session
import stripe
import os
from myapp.db import get_db
from dotenv import load_dotenv
from datetime import datetime
from myapp.auth import login_required

bp = Blueprint('payment', __name__, url_prefix='/payment')

load_dotenv()
SUBSCRIPTION_PLANS = {
    'basic': {'name': 'Basic', 'price': 500, 'audio_limit': 12000, 'word_limit': 40000, 'stripe_price_id': os.getenv('BASIC_PRICE_ID')},
    'standard': {'name': 'Standard', 'price': 1000, 'audio_limit': 30000, 'word_limit': 100000, 'stripe_price_id': os.getenv('STANDARD_PRICE_ID')},
    'premium': {'name': 'Premium', 'price': 2000, 'audio_limit': 60000, 'word_limit': 200000, 'stripe_price_id': os.getenv('PREMIUM_PRICE_ID')}
}

# @bp.route('/checkout', methods=['GET'])
# def checkout():
#     email = request.args.get('email')
#     return render_template('payment/checkout.html', email=email)

@bp.route('/checkout', methods=['GET'])
@login_required
def checkout():
    db = get_db()
    user = db.execute('SELECT * FROM user WHERE id = ?', (flask_session['user_id'],)).fetchone()
    
    # Determine if this is a new subscription or an upgrade
    is_new = user['subscription_status'] == 'trial' or not user['stripe_customer_id']
    
    return render_template('payment/checkout.html', email=user['email'], is_new=is_new)


@bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    domain_url = current_app.config.get('DOMAIN_URL')
    
    db = get_db()
    user = db.execute('SELECT * FROM user WHERE id = ?', (flask_session['user_id'],)).fetchone()
    
    plan = request.form.get('plan')
    
    if plan not in SUBSCRIPTION_PLANS:
        return jsonify(error='Invalid plan selected'), 400
    
    try:
        if not user['stripe_customer_id']:
            # Create a new Stripe customer
            stripe_customer = stripe.Customer.create(email=user['email'])
            
            # Update the user in the database with the new Stripe customer ID
            db.execute('UPDATE user SET stripe_customer_id = ? WHERE id = ?', (stripe_customer.id, user['id']))
            db.commit()
            
            # Fetch the updated user information
            user = db.execute('SELECT * FROM user WHERE id = ?', (flask_session['user_id'],)).fetchone()

        # Create a checkout session for the customer
        checkout_session = stripe.checkout.Session.create(
            customer=user['stripe_customer_id'],
            line_items=[{'price': SUBSCRIPTION_PLANS[plan]['stripe_price_id'], 'quantity': 1}],
            mode='subscription',
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
    db = get_db()
    user = db.execute('SELECT * FROM user WHERE id = ?', (flask_session['user_id'],)).fetchone()
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('index.index'))

    if user['subscription_status'] == 'trial' or not user['stripe_customer_id']:
        # If the user is on trial or doesn't have a Stripe customer ID, redirect to checkout
        return redirect(url_for('payment.checkout', email=user['email']))

    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    try:
        session = stripe.billing_portal.Session.create(
            customer=user['stripe_customer_id'],
            return_url=url_for('index.index', _external=True),
        )
        return redirect(session.url)
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('index.index'))


endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

@bp.route('/webhook', methods=['POST'])
def webhook():
    logging.basicConfig(level=logging.INFO)
    logging.info("Webhook received")
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400

    if event['type'] == 'invoice.paid':
        handle_invoice_paid(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription_deleted(event['data']['object'])

    return jsonify(success=True)

import logging

def handle_invoice_paid(invoice):
    logging.info(f"Handling paid invoice: {invoice['id']}")
    customer_id = invoice['customer']
    subscription_id = invoice['subscription']
    billing_reason = invoice['billing_reason']

    db = get_db()
    user = db.execute('SELECT * FROM user WHERE stripe_customer_id = ?', (customer_id,)).fetchone()

    if not user:
        logging.error(f"User not found for customer {customer_id}")
        return

    logging.info(f"Found user: {user['id']} for customer: {customer_id}")

    if billing_reason == 'subscription_create':
        logging.info("New subscription created")
        update_user_subscription(user['id'], subscription_id, invoice['lines']['data'][0]['price']['id'], 'active')
    elif billing_reason == 'subscription_cycle':
        logging.info("Subscription renewed")
        update_subscription_end_date(user['id'], subscription_id)
    elif billing_reason == 'subscription_update':
        logging.info("Subscription updated")
        subscription = stripe.Subscription.retrieve(subscription_id)
        update_user_subscription(user['id'], subscription_id, subscription['items']['data'][0]['price']['id'], 'active')

    # Verify the update
    updated_user = db.execute('SELECT * FROM user WHERE id = ?', (user['id'],)).fetchone()
    logging.info(f"Updated user data: {updated_user}")

def handle_subscription_deleted(subscription):
    customer_id = subscription['customer']
    db = get_db()
    user = db.execute('SELECT * FROM user WHERE stripe_customer_id = ?', (customer_id,)).fetchone()

    if not user:
        print(f"User not found for customer {customer_id}")
        return

    db.execute('''
        UPDATE user 
        SET subscription_status = 'inactive', 
            subscription_id = NULL, 
            subscription_price_id = NULL, 
            subscription_end_date = NULL 
        WHERE id = ?
    ''', (user['id'],))
    db.commit()

def update_user_subscription(user_id, subscription_id, price_id, status):
    subscription = stripe.Subscription.retrieve(subscription_id)
    end_date = datetime.fromtimestamp(subscription['current_period_end'])

    db = get_db()
    db.execute('''
        UPDATE user 
        SET subscription_status = ?, 
            subscription_id = ?, 
            subscription_price_id = ?, 
            subscription_end_date = ?,
            word_count = ? 
        WHERE id = ?
    ''', (status, subscription_id, price_id, end_date, 0, user_id))
    db.commit()

def update_subscription_end_date(user_id, subscription_id):
    subscription = stripe.Subscription.retrieve(subscription_id)
    new_end_date = datetime.fromtimestamp(subscription['current_period_end'])

    db = get_db()
    db.execute('UPDATE user SET subscription_end_date = ? WHERE id = ?', (new_end_date, user_id))
    db.commit()