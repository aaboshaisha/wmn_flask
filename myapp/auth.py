from flask import Blueprint, g, session, request, url_for, redirect, render_template, flash
from myapp.db import get_db
from werkzeug.security import generate_password_hash, check_password_hash
import functools
import re

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
EMAIL_ERROR = "Invalid email format. Please use a valid email address (e.g., user@example.com)."
PASS_RE = re.compile(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)[A-Za-z\d]{8,}$')
PASS_ERROR = "Password must be at least 8 characters long, contain at least one uppercase letter, one lowercase letter, and one digit."

def valid_email(email):
    return EMAIL_RE.match(email)

def valid_password(password):
    return PASS_RE.match(password)

# create blueprint for auth file
bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        password2 = request.form.get('password2')
        error = None
        db = get_db()

        if not valid_email(email):
            error = EMAIL_ERROR
        elif not valid_password(password):
            error = PASS_ERROR
        elif password != password2:
            error = 'Passwords must match.'
        elif db.execute('SELECT id FROM user WHERE email = ?', (email,)).fetchone():
            error = f'User {email} already exists. Try to login instead.'

        if error is None:
            db.execute('INSERT INTO user (email, password, subscription_status) VALUES (?, ?, ?)',
                       (email, generate_password_hash(password), 'trial'))
            db.commit()
            return redirect(url_for('auth.login', email=email))
        
        flash(error)
    return render_template('auth/register.html')  # handle GET

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        error = None
        db = get_db()
        user = db.execute('SELECT * FROM user WHERE email = ?', (email,)).fetchone()
        if user is None:
            error = 'Incorrect Email'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect Password'
        elif user['subscription_status'] not in ['active', 'trial']:
            error = 'Subscription required. Please subscribe first.'
            return redirect(url_for('payment.checkout', email=email))
        else:
            session.clear()
            session['user_id'] = user['id']
            if user['subscription_status'] == 'exceeded':
                error = 'You have exceeded your usage limit. Please update your subscription to continue.'
                return redirect(url_for('payment.customer_portal'))
            elif user['subscription_status'] not in ['active', 'canceled', 'trial']:
                return redirect(url_for('payment.checkout', email=email))
            else:
                return redirect(url_for('notes.main'))
        
        flash(error)
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index.index'))

# now we have user_id stored in session. Before requests, user should be loaded if available
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()


from myapp.usage import has_user_exceeded_usage_limits

def is_subscription_active(user):
    return user['subscription_status'] in ['active', 'trial']

# Use this decorator instead of the original login_required
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        if not is_subscription_active(g.user):
            flash('Your subscription has ended. Please renew to continue using the service.', 'warning')
            return redirect(url_for('payment.checkout'))
        
        if has_user_exceeded_usage_limits(g.user):
            flash('You have exceeded your usage limit. Please upgrade your plan to continue.', 'warning')
            return redirect(url_for('payment.customer_portal'))
        
        return view(**kwargs)
    return wrapped_view