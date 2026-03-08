from flask import Blueprint, redirect, url_for, render_template, session, current_app, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from ..models import User
from ..extensions import db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login')
def login():
    # Redirect to dashboard if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return render_template('login.html')


@auth_bp.route('/login/password', methods=['POST'])
def login_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    remember = request.form.get('remember') == 'on'

    if not email or not password:
        flash('Please enter both email and password.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash('Invalid email or password.', 'error')
        return redirect(url_for('auth.login'))

    login_user(user, remember=remember)
    flash(f'Welcome back, {user.name}!', 'success')
    return redirect(url_for('dashboard.dashboard'))


@auth_bp.route('/register', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    confirm_password = request.form.get('confirm_password') or ''

    if not name or not email or not password or not confirm_password:
        flash('Please fill in all registration fields.', 'error')
        return redirect(url_for('auth.login'))

    if len(password) < 8:
        flash('Password must be at least 8 characters long.', 'error')
        return redirect(url_for('auth.login'))

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('auth.login'))

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('An account with this email already exists. Please login.', 'warning')
        return redirect(url_for('auth.login'))

    user = User(
        google_id=User.build_local_google_id(),
        email=email,
        name=name,
        role='candidate',
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    flash(f'Welcome {user.name}! Your account has been created.', 'success')
    return redirect(url_for('dashboard.dashboard'))


@auth_bp.route('/auth/google')
def google_login():
    # Get OAuth instance from app
    oauth = current_app.oauth
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/google/callback')
def google_callback():
    try:
        # Get OAuth instance from app
        oauth = current_app.oauth
        
        # Get access token
        token = oauth.google.authorize_access_token()
        
        # Get user info from Google
        resp = oauth.google.get('https://www.googleapis.com/oauth2/v2/userinfo')
        user_info = resp.json()

        # Find existing user by Google ID first.
        user = User.query.filter_by(google_id=user_info['id']).first()

        # If not found, try matching local account by email and link it.
        if not user and user_info.get('email'):
            user = User.query.filter_by(email=user_info['email'].lower()).first()
            if user:
                user.google_id = user_info['id']
                db.session.commit()
                flash('Google account linked successfully.', 'success')
        
        if not user:
            # Create new user
            user = User(
                google_id=user_info['id'],
                email=user_info['email'].lower(),
                name=user_info.get('name', 'User'),
                role='candidate'
            )
            db.session.add(user)
            db.session.commit()
            flash(f'Welcome {user.name}! Your account has been created.', 'success')
        else:
            flash(f'Welcome back, {user.name}!', 'success')

        # Log in the user
        login_user(user, remember=True)
        
        return redirect(url_for('dashboard.dashboard'))
        
    except Exception as e:
        flash(f'Login failed: {str(e)}', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
