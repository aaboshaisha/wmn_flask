from flask import g, redirect, url_for, current_app, flash
import re
from myapp.db import get_db

def update_user_database_and_check_limits(attribute, value):
    if not g.user:
        return redirect(url_for('auth.login'))
    
    db = get_db()
    db.execute(f'UPDATE user SET {attribute} = {attribute} + ? WHERE id = ?', (value, g.user['id']))
    db.commit()
    
    updated_user = db.execute('SELECT * FROM user WHERE id = ?', (g.user['id'],)).fetchone()
    
    if has_user_exceeded_usage_limits(updated_user):
        handle_user_exceeding_usage_limits(updated_user)


def get_or_initialize_total_words():
    if 'total_words' not in g: g.total_words = 0
    return g.total_words

def count_alphabetic_words(text):
    words = re.sub(r'[^a-zA-Z\s]', '', text).split()
    return len(words)

def calculate_and_update_word_count(response_count):
    g.total_words = get_or_initialize_total_words() + response_count
    update_user_database_and_check_limits('word_count', g.total_words)
    return g.total_words


from dotenv import load_dotenv
load_dotenv()
import os

SUBSCRIPTION_PLANS = {
    'basic': {'name': 'Basic', 'word_limit': os.getenv('BASIC_WORD_LIMIT'), 'stripe_price_id': os.getenv('BASIC_PRICE_ID')},
    'standard': {'name': 'Standard', 'word_limit': os.getenv('STANDARD_WORD_LIMIT'), 'stripe_price_id': os.getenv('STANDARD_PRICE_ID')},
    'premium': {'name': 'Premium', 'word_limit': os.getenv('PREMIUM_WORD_LIMIT'), 'stripe_price_id': os.getenv('PREMIUM_PRICE_ID')}
}


def get_usage_limits(user):
    trial_word_limit = 1000
    if user['subscription_status'] == 'trial':
        return trial_word_limit
    else:
        for plan_details in SUBSCRIPTION_PLANS.values():
            if plan_details['stripe_price_id'] == user['subscription_price_id']:
                return int(plan_details['word_limit'])
        raise ValueError(f'No plan found for price id: {user['subscription_price_id']}')


def has_user_exceeded_usage_limits(user):
    word_limit = get_usage_limits(user)
    return user['word_count'] > word_limit 


def handle_user_exceeding_usage_limits(user):
    # current_app.logger.debug(f"Handling user exceeding usage limits for user ID: {user['id']}")
    db = get_db()
    db.execute('UPDATE user SET subscription_status = ? WHERE id = ?', ('exceeded', user['id']))
    db.commit()
    flash('You have exceeded your usage limit. Please renew your subscription or upgrade to continue using the service.', 'warning')
    # current_app.logger.debug(f"Updated subscription status in the database for user ID: {user['id']}")

    return redirect(url_for('payment.customer_portal', email=user['email']))