"""
Candidate invitation and activity tracking module.
Handles unique URL generation, candidate authentication, and comprehensive activity logging.
"""

import sqlite3
import secrets
import string
from datetime import datetime, timedelta
from models.database import get_user_db_connection
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
        
        # Set expiration date
        expires_at = datetime.now() + timedelta(days=expires_days) if expires_days else None
        
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
            if datetime.now() > expires_at:
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
            # Create new user for this candidate
            cursor = conn.execute('''
                INSERT INTO users (username, email, is_admin, is_active)
                VALUES (?, ?, 0, 1)
            ''', (invitation['candidate_name'], invitation['email']))
            user_id = cursor.lastrowid
        
        # Generate session token
        session_token = generate_invitation_token()
        
        # Create session
        conn.execute('''
            INSERT INTO user_sessions 
            (user_id, session_token, ip_address, user_agent, is_admin, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
        ''', (user_id, session_token, request.remote_addr, request.headers.get('User-Agent')))
        
        # Mark invitation as used if not already
        if not invitation['is_used']:
            conn.execute('''
                UPDATE candidate_invitations 
                SET is_used = 1, used_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (invitation['id'],))
        
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
    conn = get_user_db_connection()
    try:
        conn.execute('''
            INSERT INTO candidate_activity_log 
            (user_id, invitation_token, activity_type, details, query_text, 
             execution_time_ms, success, error_message, ip_address, user_agent, 
             page_url, session_duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, invitation_token, activity_type, details, query_text,
              execution_time_ms, success, error_message, ip_address, user_agent,
              page_url, session_duration_ms))
        conn.commit()
    except Exception as e:
        print(f"Error logging candidate activity: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_all_candidate_invitations():
    """Get all candidate invitations for admin interface"""
    conn = get_user_db_connection()
    try:
        invitations = conn.execute('''
            SELECT ci.*, u.username as created_by_name
            FROM candidate_invitations ci
            JOIN users u ON ci.created_by = u.id
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