"""
Challenge system models and database operations.
Handles challenge creation, seeding, and tracking.
"""

import json
from models.database import get_user_db_connection


def seed_healthcare_challenges():
    """Seed database with healthcare data analysis challenges"""
    conn = get_user_db_connection()
    try:
        # Check if challenges already exist
        existing = conn.execute('SELECT COUNT(*) FROM challenges').fetchone()[0]
        if existing > 0:
            print(f"Challenges already seeded ({existing} challenges exist)")
            return
            
        print("Seeding healthcare data analysis challenges...")
        
        challenges = [
            # Level 1: Basic queries
            {
                'title': 'Find Patient Count',
                'description': 'How many unique patients are in the charges data? Use the hw_charges table to count distinct patients.',
                'difficulty_level': 1,
                'category': 'basic',
                'expected_query': 'SELECT COUNT(DISTINCT NEW_PT_ID) FROM hw_charges;',
                'expected_result_count': 1,
                'hints': '["Look for patient ID columns", "Use COUNT with DISTINCT", "The patient ID column is NEW_PT_ID"]',
                'time_limit_minutes': 10
            },
            {
                'title': 'Billing Office Locations',
                'description': 'What are all the different billing offices in the invoice data? List them alphabetically.',
                'difficulty_level': 1,
                'category': 'basic',
                'expected_query': 'SELECT DISTINCT BILLING_OFFICE FROM hw_invoice ORDER BY BILLING_OFFICE;',
                'expected_result_count': None,
                'hints': '["Use DISTINCT to find unique values", "Sort results with ORDER BY", "Look in the hw_invoice table"]',
                'time_limit_minutes': 10
            },
            
            # Level 2: Intermediate analysis
            {
                'title': 'AR Status Distribution',
                'description': 'What is the distribution of accounts receivable (AR) status? Show the count of invoices for each AR status, ordered by count descending.',
                'difficulty_level': 2,
                'category': 'operational',
                'expected_query': 'SELECT AR_STATUS, COUNT(*) as invoice_count FROM hw_invoice GROUP BY AR_STATUS ORDER BY invoice_count DESC;',
                'expected_result_count': None,
                'hints': '["Use GROUP BY for aggregation", "COUNT(*) gives you totals", "AR_STATUS is in hw_invoice table", "Order by count in descending order"]',
                'time_limit_minutes': 15
            },
            {
                'title': 'Monthly Charge Volume',
                'description': 'Which month had the highest total charges? Analyze invoice charges by month and find the peak month.',
                'difficulty_level': 2,
                'category': 'temporal',
                'expected_query': "SELECT strftime('%Y-%m', INVOICE_DETAIL_POST_DATE) as month, SUM(INVOICE_TOTAL_CHARGES) as total_charges FROM hw_charges WHERE INVOICE_DETAIL_POST_DATE IS NOT NULL GROUP BY month ORDER BY total_charges DESC LIMIT 1;",
                'expected_result_count': 1,
                'hints': '["Use strftime to extract month from dates", "SUM the charge amounts", "GROUP BY month", "Use LIMIT to get the top result"]',
                'time_limit_minutes': 20
            },
            
            # Level 3: Advanced analysis
            {
                'title': 'Patient Payment Patterns',
                'description': 'Find patients with invoices in multiple AR statuses. This could indicate complex payment scenarios. Show patient ID, number of different statuses, and list the statuses.',
                'difficulty_level': 3,
                'category': 'financial',
                'expected_query': "SELECT NEW_PT_ID, COUNT(DISTINCT AR_STATUS) as status_count, GROUP_CONCAT(DISTINCT AR_STATUS) as statuses FROM hw_invoice GROUP BY NEW_PT_ID HAVING COUNT(DISTINCT AR_STATUS) > 1 ORDER BY status_count DESC;",
                'expected_result_count': None,
                'hints': '["Join invoice data with charges", "Look for patients with multiple AR statuses", "Use GROUP_CONCAT to list statuses", "HAVING clause filters groups"]',
                'time_limit_minutes': 25
            },
            {
                'title': 'Insurance Reimbursement Analysis',
                'description': 'Compare expected vs actual reimbursement by insurance plan. Calculate the reimbursement rate for each primary insurance plan (IPLAN_1_PAYOR).',
                'difficulty_level': 3,
                'category': 'financial',
                'expected_query': "SELECT IPLAN_1_PAYOR, SUM(INVOICE_TOTAL_EXPECTED_REIMBURSEMENT) as expected, SUM(INVOICE_TOTAL_INS_PAYMENTS) as actual, ROUND(100.0 * SUM(INVOICE_TOTAL_INS_PAYMENTS) / SUM(INVOICE_TOTAL_EXPECTED_REIMBURSEMENT), 2) as reimbursement_rate FROM hw_invoice WHERE IPLAN_1_PAYOR IS NOT NULL AND INVOICE_TOTAL_EXPECTED_REIMBURSEMENT > 0 GROUP BY IPLAN_1_PAYOR ORDER BY reimbursement_rate DESC;",
                'expected_result_count': None,
                'hints': '["Compare expected vs actual payments", "Calculate percentage rates", "Group by insurance payor", "Handle division by zero"]',
                'time_limit_minutes': 30
            },
            
            # Level 4: Expert business insights
            {
                'title': 'Revenue Cycle Efficiency',
                'description': 'Analyze the time from service to payment. Calculate average days between service start date and invoice payment date for completed accounts. Identify the most efficient billing offices.',
                'difficulty_level': 4,
                'category': 'operational',
                'expected_query': "SELECT i.BILLING_OFFICE, COUNT(*) as completed_invoices, AVG(JULIANDAY(i.INVOICE_LAST_PAYMENT_DATE) - JULIANDAY(c.SERVICE_START_DATE)) as avg_days_to_payment FROM hw_invoice i JOIN hw_charges c ON i.NEW_INVOICE_ID = c.NEW_INVOICE_ID WHERE i.INVOICE_LAST_PAYMENT_DATE IS NOT NULL AND c.SERVICE_START_DATE IS NOT NULL AND i.AR_STATUS = 'Paid' GROUP BY i.BILLING_OFFICE HAVING COUNT(*) >= 10 ORDER BY avg_days_to_payment ASC;",
                'expected_result_count': None,
                'hints': '["Join charges and invoice tables", "Calculate date differences", "Filter for paid invoices only", "Focus on billing office efficiency", "Use JULIANDAY for date arithmetic"]',
                'time_limit_minutes': 40
            }
        ]
        
        for challenge in challenges:
            conn.execute('''
                INSERT INTO challenges (title, description, difficulty_level, category, expected_query, 
                                      expected_result_count, hints, time_limit_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (challenge['title'], challenge['description'], challenge['difficulty_level'], 
                  challenge['category'], challenge['expected_query'], challenge['expected_result_count'],
                  challenge['hints'], challenge['time_limit_minutes']))
        
        conn.commit()
        print(f"Seeded {len(challenges)} healthcare data analysis challenges")
        
    except Exception as e:
        print(f"Error seeding challenges: {e}")
        raise
    finally:
        conn.close()


def get_all_challenges():
    """Get all active challenges grouped by difficulty level"""
    conn = get_user_db_connection()
    try:
        challenges = conn.execute('''
            SELECT id, title, description, difficulty_level, category, hints, 
                   max_score, time_limit_minutes, is_active
            FROM challenges 
            WHERE is_active = 1 
            ORDER BY difficulty_level, id
        ''').fetchall()
        
        # Group by difficulty level
        levels = {
            1: {'name': 'Basic', 'challenges': []},
            2: {'name': 'Intermediate', 'challenges': []},
            3: {'name': 'Advanced', 'challenges': []},
            4: {'name': 'Expert', 'challenges': []}
        }
        
        for challenge in challenges:
            level = challenge['difficulty_level']
            if level in levels:
                challenge_data = dict(challenge)
                # Parse hints from JSON
                try:
                    challenge_data['hints'] = json.loads(challenge_data['hints'])
                except:
                    challenge_data['hints'] = []
                levels[level]['challenges'].append(challenge_data)
        
        return levels
    finally:
        conn.close()


def get_challenge_by_id(challenge_id, user_id=None):
    """Get detailed information about a specific challenge"""
    conn = get_user_db_connection()
    try:
        challenge = conn.execute('''
            SELECT id, title, description, difficulty_level, category, hints, 
                   max_score, time_limit_minutes, expected_result_count
            FROM challenges 
            WHERE id = ? AND is_active = 1
        ''', (challenge_id,)).fetchone()
        
        if not challenge:
            return None
        
        challenge_data = dict(challenge)
        # Parse hints from JSON
        try:
            challenge_data['hints'] = json.loads(challenge_data['hints'])
        except:
            challenge_data['hints'] = []
            
        # Get user's progress on this challenge if user_id provided
        if user_id:
            attempts = conn.execute('''
                SELECT id, query_text, is_correct, score, hints_used, execution_time_ms,
                       created_at
                FROM challenge_attempts 
                WHERE user_id = ? AND challenge_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            ''', (user_id, challenge_id)).fetchall()
            
            challenge_data['recent_attempts'] = [dict(attempt) for attempt in attempts]
        
        return challenge_data
    finally:
        conn.close()


def record_challenge_attempt(user_id, challenge_id, query, result_count, is_correct, 
                           score, hints_used, execution_time_ms, error_message=None):
    """Record a challenge attempt"""
    conn = get_user_db_connection()
    try:
        # Record the attempt
        conn.execute('''
            INSERT INTO challenge_attempts 
            (user_id, challenge_id, query_text, result_count, is_correct, 
             score, hints_used, execution_time_ms, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, challenge_id, query, result_count, 
              is_correct, score, hints_used, execution_time_ms, error_message))
        
        # Update user progress
        conn.execute('''
            INSERT OR REPLACE INTO user_challenge_progress 
            (user_id, challenge_id, best_score, total_attempts, is_completed)
            VALUES (?, ?, 
                    COALESCE(MAX(best_score, ?), ?),
                    COALESCE((SELECT total_attempts FROM user_challenge_progress 
                             WHERE user_id = ? AND challenge_id = ?), 0) + 1,
                    ?)
        ''', (user_id, challenge_id, score, score, 
              user_id, challenge_id, is_correct))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error recording challenge attempt: {e}")
        return False
    finally:
        conn.close()


def get_user_progress(user_id):
    """Get user's overall progress across all challenges"""
    conn = get_user_db_connection()
    try:
        progress = conn.execute('''
            SELECT c.difficulty_level, c.title, c.category, c.max_score,
                   p.best_score, p.total_attempts, p.is_completed
            FROM challenges c
            LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id 
                AND p.user_id = ?
            WHERE c.is_active = 1
            ORDER BY c.difficulty_level, c.id
        ''', (user_id,)).fetchall()
        
        # Calculate overall statistics
        total_challenges = len(progress)
        completed_challenges = sum(1 for p in progress if p['is_completed'])
        total_score = sum(p['best_score'] or 0 for p in progress)
        max_possible_score = sum(p['max_score'] or 100 for p in progress)
        
        return {
            'challenges': [dict(p) for p in progress],
            'stats': {
                'total_challenges': total_challenges,
                'completed_challenges': completed_challenges,
                'completion_rate': round(completed_challenges / total_challenges * 100, 1) if total_challenges > 0 else 0,
                'total_score': total_score,
                'max_possible_score': max_possible_score,
                'score_percentage': round(total_score / max_possible_score * 100, 1) if max_possible_score > 0 else 0
            }
        }
    finally:
        conn.close()