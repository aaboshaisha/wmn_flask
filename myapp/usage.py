from flask import g, redirect, url_for, current_app, flash
import re
from myapp.db import get_db
import wave, contextlib

def update_user_database_and_check_limits(attribute, value):
    if not g.user:
        return redirect(url_for('auth.login'))
    
    db = get_db()
    db.execute(f'UPDATE user SET {attribute} = {attribute} + ? WHERE id = ?', (value, g.user['id']))
    db.commit()
    
    updated_user = db.execute('SELECT * FROM user WHERE id = ?', (g.user['id'],)).fetchone()
    
    if has_user_exceeded_usage_limits(updated_user):
        handle_user_exceeding_usage_limits(updated_user)

def get_or_initialize_total_audio_length():
    if 'total_audio_length' not in g:
        g.total_audio_length = 0
    return g.total_audio_length


def get_audio_duration(file_path):
    with contextlib.closing(wave.open(file_path, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration = frames / float(rate)
    return duration

def calculate_and_update_audio_length(file_path):
        audio_length_seconds = get_audio_duration(file_path)
        # Update the total audio length
        g.total_audio_length = get_or_initialize_total_audio_length() + audio_length_seconds
        update_user_database_and_check_limits('audio_length', g.total_audio_length)
        
        return g.total_audio_length


def get_or_initialize_total_words():
    if 'total_words' not in g:
        g.total_words = 0
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
    'basic': {'name': 'Basic', 'price': 500, 'audio_limit': 7200, 'word_limit': 20000, 'stripe_price_id': os.getenv('BASIC_PRICE_ID')},
    'standard': {'name': 'Standard', 'price': 1000, 'audio_limit': 18000, 'word_limit': 50000, 'stripe_price_id': os.getenv('STANDARD_PRICE_ID')},
    'premium': {'name': 'Premium', 'price': 2000, 'audio_limit': 36000, 'word_limit': 100000, 'stripe_price_id': os.getenv('PREMIUM_PRICE_ID')}
}

def get_limits_by_price_id(stripe_price_id):
    for plan_details in SUBSCRIPTION_PLANS.values():
        if plan_details['stripe_price_id'] == stripe_price_id:
            return plan_details['audio_limit'], plan_details['word_limit']
    raise ValueError(f'No plan found for price id: {stripe_price_id}')


def has_user_exceeded_usage_limits(user):
    audio_limit, word_limit = get_limits_by_price_id(user['subscription_plan'])
    return user['audio_length'] > audio_limit or user['word_count'] > word_limit 


def handle_user_exceeding_usage_limits(user):
    current_app.logger.debug(f"Handling user exceeding usage limits for user ID: {user['id']}")
    db = get_db()
    db.execute('UPDATE user SET subscription_status = ? WHERE id = ?', ('exceeded', user['id']))
    db.commit()
    flash('You have exceeded your usage limit. Please renew your subscription or upgrade to continue using the service.', 'warning')
    current_app.logger.debug(f"Updated subscription status in the database for user ID: {user['id']}")
    
    # Redirect to the customer portal
    return redirect(url_for('payment.customer_portal', email=user['email']))