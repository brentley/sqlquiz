"""
Candidate invitation and activity tracking module.
Handles unique URL generation, candidate authentication, and comprehensive activity logging.
"""

import sqlite3
import secrets
import string
from datetime import datetime, timedelta, timezone
from models.database import get_user_db_connection
from utils.timezone import utc_now, format_for_display
from flask import request, session


def generate_invitation_token(length=32):
    """Generate a cryptographically secure invitation token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_candidate_invitation(email, candidate_name, created_by_user_id, expires_days=30):
    """Create a new candidate invitation with unique URL token"""
    conn = get_user_db_connection()
    try:
        # Generate unique token
        token = generate_invitation_token()
        
        # Check if token already exists (highly unlikely but good practice)
        while conn.execute("SELECT id FROM candidate_invitations WHERE invitation_token = ?", (token,)).fetchone():
            token = generate_invitation_token()
        
        # Set expiration date (UTC)
        expires_at = utc_now() + timedelta(days=expires_days) if expires_days else None
        
        # Create invitation
        cursor = conn.execute('''
            INSERT OR REPLACE INTO candidate_invitations 
            (email, candidate_name, invitation_token, created_by, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (email, candidate_name, token, created_by_user_id, expires_at))
        
        invitation_id = cursor.lastrowid
        conn.commit()
        
        return {
            'success': True,
            'invitation_id': invitation_id,
            'token': token,
            'expires_at': expires_at,
            'unique_url': f"/candidate/{token}"
        }
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def validate_invitation_token(token):
    """Validate an invitation token and return candidate info if valid"""
    conn = get_user_db_connection()
    try:
        invitation = conn.execute('''
            SELECT * FROM candidate_invitations 
            WHERE invitation_token = ? AND is_active = 1
        ''', (token,)).fetchone()
        
        if not invitation:
            return {'valid': False, 'error': 'Invalid or expired invitation'}
        
        # Check if expired
        if invitation['expires_at']:
            expires_at = datetime.fromisoformat(invitation['expires_at'])
            # Ensure expires_at is timezone-aware (UTC)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if utc_now() > expires_at:
                return {'valid': False, 'error': 'Invitation has expired'}
        
        return {
            'valid': True,
            'invitation': dict(invitation)
        }
    except Exception as e:
        return {'valid': False, 'error': str(e)}
    finally:
        conn.close()


def authenticate_candidate(token):
    """Authenticate candidate and create session"""
    validation = validate_invitation_token(token)
    if not validation['valid']:
        return validation
    
    invitation = validation['invitation']
    conn = get_user_db_connection()
    
    try:
        # Check if user already exists for this invitation
        user = conn.execute('''
            SELECT * FROM users WHERE email = ?
        ''', (invitation['email'],)).fetchone()
        
        if user:
            user_id = user['id']
        else:
            # Create new user for this candidate with unique username if needed
            base_username = invitation['candidate_name']
            username = base_username
            counter = 1
            
            # Ensure username is unique
            while conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
                username = f"{base_username}_{counter}"
                counter += 1
            
            cursor = conn.execute('''
                INSERT INTO users (username, email, is_admin, is_active)
                VALUES (?, ?, 0, 1)
            ''', (username, invitation['email']))
            user_id = cursor.lastrowid
        
        # Generate session token
        session_token = generate_invitation_token()
        
        # Create session
        conn.execute('''
            INSERT INTO user_sessions 
            (user_id, session_token, ip_address, user_agent, is_admin, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
        ''', (user_id, session_token, request.remote_addr, request.headers.get('User-Agent')))
        
        # Log candidate login activity
        log_candidate_activity(
            user_id=user_id,
            invitation_token=token,
            activity_type='candidate_login',
            details=f"Candidate {invitation['candidate_name']} logged in via invitation",
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            page_url=request.url
        )
        
        conn.commit()
        
        # Mark invitation as used only AFTER successful authentication and session creation
        if not invitation['is_used']:
            conn.execute('''
                UPDATE candidate_invitations 
                SET is_used = 1, used_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (invitation['id'],))
            conn.commit()
        
        return {
            'success': True,
            'user_id': user_id,
            'session_token': session_token,
            'candidate_name': invitation['candidate_name'],
            'email': invitation['email']
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def log_candidate_activity(user_id=None, invitation_token=None, activity_type=None, 
                         details=None, query_text=None, execution_time_ms=None, 
                         success=None, error_message=None, ip_address=None, 
                         user_agent=None, page_url=None, session_duration_ms=None):
    """Log comprehensive candidate activity"""
    print(f"DEBUG - log_candidate_activity called: user_id={user_id}, activity_type={activity_type}, details={details}")
    
    if not user_id:
        print("WARNING - log_candidate_activity: user_id is None, skipping logging")
        return
    
    conn = get_user_db_connection()
    try:
        cursor = conn.execute('''
            INSERT INTO candidate_activity_log 
            (user_id, invitation_token, activity_type, details, query_text, 
             execution_time_ms, success, error_message, ip_address, user_agent, 
             page_url, session_duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, invitation_token, activity_type, details, query_text,
              execution_time_ms, success, error_message, ip_address, user_agent,
              page_url, session_duration_ms))
        conn.commit()
        print(f"DEBUG - Successfully logged activity for user {user_id}, row_id={cursor.lastrowid}")
    except Exception as e:
        print(f"ERROR - Failed to log candidate activity: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_all_candidate_invitations():
    """Get all candidate invitations for admin interface"""
    conn = get_user_db_connection()
    try:
        invitations = conn.execute('''
            SELECT ci.*, u_creator.username as created_by_name, u_target.id as target_user_id
            FROM candidate_invitations ci
            JOIN users u_creator ON ci.created_by = u_creator.id
            LEFT JOIN users u_target ON ci.email = u_target.email
            ORDER BY ci.created_at DESC
        ''').fetchall()
        
        return [dict(invitation) for invitation in invitations]
    except Exception as e:
        print(f"Error getting invitations: {e}")
        return []
    finally:
        conn.close()


def get_candidate_activity_log(user_id=None, invitation_token=None, limit=100):
    """Get candidate activity log"""
    conn = get_user_db_connection()
    try:
        if user_id:
            activities = conn.execute('''
                SELECT * FROM candidate_activity_log 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (user_id, limit)).fetchall()
        elif invitation_token:
            activities = conn.execute('''
                SELECT * FROM candidate_activity_log 
                WHERE invitation_token = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (invitation_token, limit)).fetchall()
        else:
            activities = conn.execute('''
                SELECT * FROM candidate_activity_log 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,)).fetchall()
        
        return [dict(activity) for activity in activities]
    except Exception as e:
        print(f"Error getting activity log: {e}")
        return []
    finally:
        conn.close()


def deactivate_invitation(invitation_id):
    """Deactivate a candidate invitation"""
    conn = get_user_db_connection()
    try:
        conn.execute('''
            UPDATE candidate_invitations 
            SET is_active = 0 
            WHERE id = ?
        ''', (invitation_id,))
        conn.commit()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def get_candidate_summary(user_id):
    """Get comprehensive summary of candidate activity and performance"""
    conn = get_user_db_connection()
    try:
        # Get user info
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            return None
        
        # Get invitation info
        invitation = conn.execute('''
            SELECT * FROM candidate_invitations WHERE email = ?
        ''', (user['email'],)).fetchone()
        
        # Get activity summary
        activity_count = conn.execute('''
            SELECT COUNT(*) as total FROM candidate_activity_log WHERE user_id = ?
        ''', (user_id,)).fetchone()['total']
        
        # Get query attempts
        query_attempts = conn.execute('''
            SELECT COUNT(*) as total FROM candidate_activity_log 
            WHERE user_id = ? AND activity_type = 'query_executed'
        ''', (user_id,)).fetchone()['total']
        
        # Get challenge progress
        challenge_progress = conn.execute('''
            SELECT * FROM user_challenge_progress WHERE user_id = ?
        ''', (user_id,)).fetchall()
        
        # Get recent activity
        recent_activity = get_candidate_activity_log(user_id=user_id, limit=20)
        
        return {
            'user': dict(user),
            'invitation': dict(invitation) if invitation else None,
            'activity_count': activity_count,
            'query_attempts': query_attempts,
            'challenge_progress': [dict(cp) for cp in challenge_progress],
            'recent_activity': recent_activity
        }
        
    except Exception as e:
        print(f"Error getting candidate summary: {e}")
        return None
    finally:
        conn.close()


def start_impersonation(admin_user_id, target_user_id):
    """Start impersonating a candidate user (admin only)"""
    conn = get_user_db_connection()
    try:
        # Get target user info
        target_user = conn.execute('SELECT * FROM users WHERE id = ?', (target_user_id,)).fetchone()
        if not target_user:
            return {'success': False, 'error': 'Target user not found'}
        
        # Get admin user info
        admin_user = conn.execute('SELECT * FROM users WHERE id = ? AND is_admin = 1', (admin_user_id,)).fetchone()
        if not admin_user:
            return {'success': False, 'error': 'Only admins can impersonate users'}
        
        # Generate impersonation session token
        impersonation_token = generate_invitation_token()
        
        # Create impersonation session record
        conn.execute('''
            INSERT INTO user_sessions 
            (user_id, session_token, ip_address, user_agent, is_admin, is_active, 
             impersonated_by, impersonation_start_time)
            VALUES (?, ?, ?, ?, 0, 1, ?, CURRENT_TIMESTAMP)
        ''', (target_user_id, impersonation_token, request.remote_addr, 
              request.headers.get('User-Agent'), admin_user_id))
        
        # Log impersonation start
        log_candidate_activity(
            user_id=target_user_id,
            activity_type='impersonation_started',
            details=f"Admin {admin_user['username']} ({admin_user['email']}) started impersonating user",
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            page_url=request.url
        )
        
        conn.commit()
        
        return {
            'success': True,
            'impersonation_token': impersonation_token,
            'target_user': dict(target_user),
            'admin_user': dict(admin_user)
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def end_impersonation(session_token):
    """End impersonation session"""
    conn = get_user_db_connection()
    try:
        # Get impersonation session
        session = conn.execute('''
            SELECT * FROM user_sessions 
            WHERE session_token = ? AND impersonated_by IS NOT NULL
        ''', (session_token,)).fetchone()
        
        if not session:
            return {'success': False, 'error': 'No active impersonation session found'}
        
        # Get admin and target user info
        admin_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['impersonated_by'],)).fetchone()
        target_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        
        # Log impersonation end
        log_candidate_activity(
            user_id=session['user_id'],
            activity_type='impersonation_ended',
            details=f"Admin {admin_user['username']} ({admin_user['email']}) ended impersonation session",
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        # Deactivate impersonation session
        conn.execute('''
            UPDATE user_sessions 
            SET is_active = 0, impersonation_end_time = CURRENT_TIMESTAMP
            WHERE session_token = ?
        ''', (session_token,))
        
        conn.commit()
        
        return {
            'success': True,
            'admin_user': dict(admin_user),
            'target_user': dict(target_user)
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def get_impersonation_info(session_token):
    """Get information about current impersonation session"""
    conn = get_user_db_connection()
    try:
        session = conn.execute('''
            SELECT us.*, u_admin.username as admin_username, u_admin.email as admin_email,
                   u_target.username as target_username, u_target.email as target_email
            FROM user_sessions us
            LEFT JOIN users u_admin ON us.impersonated_by = u_admin.id
            LEFT JOIN users u_target ON us.user_id = u_target.id
            WHERE us.session_token = ? AND us.impersonated_by IS NOT NULL AND us.is_active = 1
        ''', (session_token,)).fetchone()
        
        if session:
            return dict(session)
        return None
        
    except Exception as e:
        print(f"Error getting impersonation info: {e}")
        return None
    finally:
        conn.close()