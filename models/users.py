"""
User management and session handling.
Handles user authentication, session management, and activity tracking.
"""

import hashlib
import secrets
import time
from datetime import datetime, timezone
from utils.timezone import utc_now, format_for_display
from models.database import get_user_db_connection


def create_user(username, password=None, email=None):
    """Create a new user"""
    conn = get_user_db_connection()
    try:
        # Check if user already exists
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing_user:
            return existing_user['id']
        
        # Hash password if provided
        password_hash = None
        if password:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Create user
        cursor = conn.execute('''
            INSERT INTO users (username, password_hash, email)
            VALUES (?, ?, ?)
        ''', (username, password_hash, email))
        
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    finally:
        conn.close()


def authenticate_user(username, password=None):
    """Authenticate user with username/password or create if not exists"""
    try:
        conn = get_user_db_connection()
        try:
            user = conn.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,)).fetchone()
            
            if user:
                # User exists - check password if provided
                if password and user['password_hash']:
                    password_hash = hashlib.sha256(password.encode()).hexdigest()
                    if password_hash != user['password_hash']:
                        return None
                return user['id']
            else:
                # User doesn't exist - create new user
                return create_user(username, password)
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Could not authenticate user (database unavailable): {e}")
        return None


def create_session(user_id, ip_address=None, user_agent=None):
    """Create a new user session"""
    try:
        conn = get_user_db_connection()
        try:
            # Generate session token
            session_token = secrets.token_urlsafe(32)
            
            # Create session
            conn.execute('''
                INSERT INTO user_sessions (user_id, session_token, ip_address, user_agent)
                VALUES (?, ?, ?, ?)
            ''', (user_id, session_token, ip_address, user_agent))
            
            # Update user last login
            conn.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user_id,))
            
            conn.commit()
            return session_token
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Could not create user session (database unavailable): {e}")
        return None


def get_user_by_session(session_token):
    """Get user information from session token"""
    try:
        conn = get_user_db_connection()
        try:
            result = conn.execute('''
                SELECT u.id, u.username, u.email, s.login_time
                FROM users u
                JOIN user_sessions s ON u.id = s.user_id
                WHERE s.session_token = ? AND s.is_active = 1
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
        print(f"Warning: Could not check user session (database unavailable): {e}")
        return None


def get_user_by_username(username):
    """Get user information by username"""
    conn = get_user_db_connection()
    try:
        user = conn.execute('''
            SELECT id, username, email, created_at, last_login
            FROM users 
            WHERE username = ?
        ''', (username,)).fetchone()
        
        return dict(user) if user else None
    finally:
        conn.close()


def invalidate_session(session_token):
    """Invalidate a user session"""
    conn = get_user_db_connection()
    try:
        conn.execute('''
            UPDATE user_sessions 
            SET is_active = 0 
            WHERE session_token = ?
        ''', (session_token,))
        conn.commit()
        return True
    finally:
        conn.close()


def log_query(user_id, session_id, query_text, execution_time_ms, row_count, success, error_message=None):
    """Log a query execution"""
    conn = get_user_db_connection()
    try:
        conn.execute('''
            INSERT INTO query_logs 
            (user_id, session_id, query_text, execution_time_ms, row_count, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, session_id, query_text, execution_time_ms, row_count, success, error_message))
        conn.commit()
    except Exception as e:
        print(f"Error logging query: {e}")
    finally:
        conn.close()


def get_all_candidates():
    """Get all candidates with their assessment summary"""
    conn = get_user_db_connection()
    try:
        candidates = conn.execute('''
            SELECT DISTINCT u.id, u.username, u.email, u.created_at as registration_date,
                   COUNT(DISTINCT ca.challenge_id) as challenges_attempted,
                   COUNT(DISTINCT CASE WHEN ca.is_correct = 1 THEN ca.challenge_id END) as challenges_completed,
                   MAX(ca.score) as best_score,
                   SUM(ca.score) as total_score,
                   COUNT(ca.id) as total_attempts,
                   AVG(ca.execution_time_ms) as avg_execution_time,
                   SUM(ca.hints_used) as total_hints_used,
                   MAX(COALESCE(cal.timestamp, ca.created_at)) as last_activity,
                   COUNT(cal.id) as total_activity_events,
                   COUNT(CASE WHEN cal.activity_type = 'query_executed' THEN 1 END) as query_attempts
            FROM users u
            LEFT JOIN challenge_attempts ca ON u.id = ca.user_id
            LEFT JOIN candidate_activity_log cal ON u.id = cal.user_id
            WHERE u.username != 'admin' AND u.is_admin != 1
            GROUP BY u.id, u.username, u.email, u.created_at
            ORDER BY last_activity DESC NULLS LAST
        ''').fetchall()
        
        candidate_list = []
        for candidate in candidates:
            # Calculate completion rate
            completion_rate = 0
            if candidate['challenges_attempted'] > 0:
                completion_rate = round((candidate['challenges_completed'] or 0) / candidate['challenges_attempted'] * 100, 1)
            
            # Get challenge difficulty breakdown
            difficulty_stats = conn.execute('''
                SELECT c.difficulty_level, 
                       COUNT(DISTINCT ca.challenge_id) as attempted,
                       COUNT(DISTINCT CASE WHEN ca.is_correct = 1 THEN ca.challenge_id END) as completed
                FROM challenge_attempts ca
                JOIN challenges c ON ca.challenge_id = c.id
                JOIN users u ON ca.user_id = u.id
                WHERE u.username = ?
                GROUP BY c.difficulty_level
                ORDER BY c.difficulty_level
            ''', (candidate['username'],)).fetchall()
            
            candidate_data = dict(candidate)
            candidate_data['completion_rate'] = completion_rate
            candidate_data['difficulty_breakdown'] = [dict(stat) for stat in difficulty_stats]
            
            candidate_list.append(candidate_data)
        
        return candidate_list
    finally:
        conn.close()


def get_candidate_detail(username):
    """Get detailed candidate assessment data"""
    conn = get_user_db_connection()
    try:
        # Get user ID
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            return None
        
        user_id = user['id']
        
        # Get challenge progress
        challenge_progress = conn.execute('''
            SELECT c.id, c.title, c.difficulty_level, c.category, c.max_score,
                   COUNT(ca.id) as attempts,
                   MAX(CASE WHEN ca.is_correct = 1 THEN ca.score ELSE 0 END) as best_score,
                   MAX(ca.is_correct) as completed,
                   MIN(ca.execution_time_ms) as best_time,
                   SUM(ca.hints_used) as total_hints,
                   MAX(ca.created_at) as last_attempt
            FROM challenges c
            LEFT JOIN challenge_attempts ca ON c.id = ca.challenge_id AND ca.user_id = ?
            WHERE c.is_active = 1
            GROUP BY c.id, c.title, c.difficulty_level, c.category, c.max_score
            ORDER BY c.difficulty_level, c.id
        ''', (user_id,)).fetchall()
        
        # Get detailed attempt history
        attempt_history = conn.execute('''
            SELECT ca.id, ca.challenge_id, c.title as challenge_title, 
                   ca.query_text, ca.is_correct, ca.score, ca.result_count,
                   ca.execution_time_ms, ca.hints_used, ca.created_at,
                   c.difficulty_level, c.expected_result_count
            FROM challenge_attempts ca
            JOIN challenges c ON ca.challenge_id = c.id
            WHERE ca.user_id = ?
            ORDER BY ca.created_at DESC
        ''', (user_id,)).fetchall()
        
        # Get candidate activity log (new system)
        activity_history = conn.execute('''
            SELECT id, activity_type, details, query_text, execution_time_ms,
                   success, error_message, timestamp, ip_address
            FROM candidate_activity_log
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (user_id,)).fetchall()
        
        # Calculate overall statistics
        total_challenges = len([p for p in challenge_progress if p['attempts'] > 0])
        completed_challenges = len([p for p in challenge_progress if p['completed']])
        total_score = sum(p['best_score'] or 0 for p in challenge_progress)
        max_possible_score = sum(p['max_score'] for p in challenge_progress)
        
        # Calculate activity statistics
        query_activities = [a for a in activity_history if a['activity_type'] == 'query_executed']
        successful_queries = [a for a in query_activities if a['success']]
        
        return {
            'username': username,
            'challenge_progress': [dict(p) for p in challenge_progress],
            'attempt_history': [dict(a) for a in attempt_history],
            'activity_history': [dict(a) for a in activity_history],  # NEW: Include activity log
            'summary': {
                'total_challenges_attempted': total_challenges,
                'completed_challenges': completed_challenges,
                'completion_rate': round(completed_challenges / total_challenges * 100, 1) if total_challenges > 0 else 0,
                'total_score': total_score,
                'max_possible_score': max_possible_score,
                'score_percentage': round(total_score / max_possible_score * 100, 1) if max_possible_score > 0 else 0,
                'total_attempts': len(attempt_history),
                'avg_execution_time': round(sum(a['execution_time_ms'] for a in attempt_history) / len(attempt_history), 1) if attempt_history else 0,
                'total_hints_used': sum(a['hints_used'] for a in attempt_history),
                # NEW: Activity-based statistics
                'total_activities': len(activity_history),
                'query_executions': len(query_activities),
                'successful_queries': len(successful_queries),
                'query_success_rate': round(len(successful_queries) / len(query_activities) * 100, 1) if query_activities else 0
            }
        }
    finally:
        conn.close()


def get_system_analytics():
    """Get overall assessment analytics"""
    conn = get_user_db_connection()
    try:
        # Overall statistics
        overall_stats = conn.execute('''
            SELECT 
                COUNT(DISTINCT u.id) as total_candidates,
                COUNT(DISTINCT ca.challenge_id) as challenges_attempted,
                COUNT(DISTINCT CASE WHEN ca.is_correct = 1 THEN ca.challenge_id END) as challenges_completed,
                AVG(ca.score) as avg_score,
                AVG(ca.execution_time_ms) as avg_execution_time,
                COUNT(ca.id) as total_attempts
            FROM users u
            LEFT JOIN challenge_attempts ca ON u.id = ca.user_id
            WHERE u.username != 'admin'
        ''').fetchone()
        
        # Challenge difficulty statistics
        difficulty_stats = conn.execute('''
            SELECT c.difficulty_level,
                   COUNT(DISTINCT ca.user_id) as candidates_attempted,
                   COUNT(DISTINCT CASE WHEN ca.is_correct = 1 THEN ca.user_id END) as candidates_completed,
                   AVG(ca.score) as avg_score,
                   COUNT(ca.id) as total_attempts
            FROM challenges c
            LEFT JOIN challenge_attempts ca ON c.id = ca.challenge_id
            GROUP BY c.difficulty_level
            ORDER BY c.difficulty_level
        ''').fetchall()
        
        # Most challenging problems
        challenge_stats = conn.execute('''
            SELECT c.title, c.difficulty_level,
                   COUNT(ca.id) as total_attempts,
                   COUNT(CASE WHEN ca.is_correct = 1 THEN 1 END) as successful_attempts,
                   AVG(ca.score) as avg_score,
                   AVG(ca.execution_time_ms) as avg_time,
                   AVG(ca.hints_used) as avg_hints
            FROM challenges c
            LEFT JOIN challenge_attempts ca ON c.id = ca.challenge_id
            WHERE c.is_active = 1
            GROUP BY c.id, c.title, c.difficulty_level
            ORDER BY (COUNT(CASE WHEN ca.is_correct = 1 THEN 1 END) * 1.0 / NULLIF(COUNT(ca.id), 0)) ASC
        ''').fetchall()
        
        return {
            'overall': dict(overall_stats),
            'difficulty_breakdown': [dict(stat) for stat in difficulty_stats],
            'challenge_difficulty_ranking': [dict(stat) for stat in challenge_stats]
        }
    finally:
        conn.close()


def export_candidate_report(username):
    """Export candidate assessment report"""
    conn = get_user_db_connection()
    try:
        # Get challenge attempts with full details
        attempts = conn.execute('''
            SELECT c.title, c.difficulty_level, c.category, ca.query_text, 
                   ca.is_correct, ca.score, ca.execution_time_ms, ca.hints_used,
                   ca.created_at, c.expected_result_count, ca.result_count
            FROM challenge_attempts ca
            JOIN challenges c ON ca.challenge_id = c.id
            JOIN users u ON ca.user_id = u.id
            WHERE u.username = ?
            ORDER BY ca.created_at
        ''', (username,)).fetchall()
        
        # Generate assessment report
        report = {
            'candidate': username,
            'assessment_date': utc_now().isoformat(),
            'challenges': [],
            'summary': {}
        }
        
        for attempt in attempts:
            report['challenges'].append({
                'challenge': attempt['title'],
                'difficulty': attempt['difficulty_level'],
                'category': attempt['category'],
                'query': attempt['query_text'],
                'correct': bool(attempt['is_correct']),
                'score': attempt['score'],
                'execution_time_ms': attempt['execution_time_ms'],
                'hints_used': attempt['hints_used'],
                'timestamp': attempt['created_at']
            })
        
        return report
    finally:
        conn.close()