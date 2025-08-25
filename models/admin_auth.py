"""
Admin authentication module using OAuth/SSO.
Handles admin user authentication via OAuth providers like Google, Microsoft, etc.
"""

import os
import secrets
from urllib.parse import urlencode
from functools import wraps
from flask import session, request, redirect, url_for, flash, current_app
from authlib.integrations.flask_client import OAuth
from models.database import get_user_db_connection


def init_oauth(app):
    """Initialize OAuth client"""
    oauth = OAuth(app)
    
    # Check if OAuth is configured
    client_id = os.getenv('OAUTH_CLIENT_ID')
    client_secret = os.getenv('OAUTH_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("Warning: OAuth not configured. Admin authentication will not work.")
        print("Please set OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET environment variables.")
        return oauth, None
    
    # Configure OAuth client (Google by default, but configurable)
    oauth_client = oauth.register(
        name='oauth_provider',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=os.getenv('OAUTH_DISCOVERY_URL', 'https://accounts.google.com/.well-known/openid_configuration'),
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
    
    return oauth, oauth_client


def get_admin_emails():
    """Get list of admin emails from environment variable"""
    admin_emails_str = os.getenv('ADMIN_EMAILS', '')
    if not admin_emails_str:
        return []
    return [email.strip().lower() for email in admin_emails_str.split(',') if email.strip()]


def is_admin_email(email):
    """Check if email is in the admin whitelist"""
    if not email:
        return False
    admin_emails = get_admin_emails()
    return email.lower() in admin_emails


def create_admin_user(email, name=None):
    """Create or update admin user record"""
    try:
        conn = get_user_db_connection()
        try:
            # Check if admin user already exists
            existing_user = conn.execute(
                'SELECT id FROM users WHERE email = ? AND is_admin = 1', 
                (email,)
            ).fetchone()
            
            if existing_user:
                return existing_user['id']
            
            # Create new admin user
            cursor = conn.execute('''
                INSERT INTO users (username, email, is_admin, created_at)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ''', (name or email.split('@')[0], email))
            
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Could not create admin user (database unavailable): {e}")
        return None


def create_admin_session(user_id, email, name=None):
    """Create admin session with additional metadata"""
    try:
        conn = get_user_db_connection()
        try:
            # Generate session token
            session_token = secrets.token_urlsafe(32)
            
            # Create session with admin flag
            conn.execute('''
                INSERT INTO user_sessions (
                    user_id, session_token, login_time, last_activity,
                    ip_address, user_agent, is_admin
                )
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, 1)
            ''', (user_id, session_token, request.remote_addr, request.headers.get('User-Agent', '')))
            
            # Update user last login
            conn.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user_id,))
            
            conn.commit()
            return session_token
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Could not create admin session (database unavailable): {e}")
        return None


def get_admin_by_session(session_token):
    """Get admin user information from session token"""
    try:
        conn = get_user_db_connection()
        try:
            result = conn.execute('''
                SELECT u.id, u.username, u.email, u.is_admin, s.login_time
                FROM users u
                JOIN user_sessions s ON u.id = s.user_id
                WHERE s.session_token = ? AND s.is_active = 1 AND u.is_admin = 1
            ''', (session_token,)).fetchone()
            
            if result:
                # Update last activity
                conn.execute('''
                    UPDATE user_sessions 
                    SET last_activity = CURRENT_TIMESTAMP 
                    WHERE session_token = ?
                ''', (session_token,))
                conn.commit()
                
                return dict(result)
            return None
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Could not validate admin session (database unavailable): {e}")
        return None


def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated as admin
        if 'admin_session_token' not in session:
            # Store the intended destination
            session['admin_next'] = request.url
            return redirect(url_for('admin_login'))
        
        # Validate admin session
        admin_user = get_admin_by_session(session['admin_session_token'])
        if not admin_user:
            # Invalid session, redirect to login
            session.pop('admin_session_token', None)
            session.pop('admin_user', None)
            session['admin_next'] = request.url
            flash('Your admin session has expired. Please log in again.', 'warning')
            return redirect(url_for('admin_login'))
        
        # Store admin user info in session for templates
        session['admin_user'] = {
            'id': admin_user['id'],
            'username': admin_user['username'],
            'email': admin_user['email']
        }
        
        return f(*args, **kwargs)
    
    return decorated_function


def invalidate_admin_session(session_token):
    """Invalidate admin session"""
    try:
        conn = get_user_db_connection()
        try:
            conn.execute('''
                UPDATE user_sessions 
                SET is_active = 0 
                WHERE session_token = ? AND is_admin = 1
            ''', (session_token,))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Could not invalidate admin session (database unavailable): {e}")


def log_admin_action(user_id, action, details=None):
    """Log admin actions for audit trail"""
    try:
        conn = get_user_db_connection()
        try:
            conn.execute('''
                INSERT INTO admin_audit_log (
                    user_id, action, details, ip_address, user_agent, timestamp
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, action, details, request.remote_addr, request.headers.get('User-Agent', '')))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Could not log admin action (database unavailable): {e}")