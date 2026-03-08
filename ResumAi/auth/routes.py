from flask import Blueprint, redirect, url_for, render_template, session, current_app, flash
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

        # Find or create user
        user = User.query.filter_by(google_id=user_info['id']).first()
        
        if not user:
            # Create new user
            user = User(
                google_id=user_info['id'],
                email=user_info['email'],
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
