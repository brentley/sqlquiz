"""
Challenge system models and database operations.
Handles challenge creation, seeding, and tracking.
"""

import json
from models.database import get_user_db_connection


def seed_healthcare_challenges(force_reseed=False):
    """Seed database with healthcare data analysis challenges"""
    conn = get_user_db_connection()
    try:
        # Check if challenges already exist
        existing = conn.execute('SELECT COUNT(*) FROM challenges').fetchone()[0]
        if existing > 0 and not force_reseed:
            print(f"Challenges already seeded ({existing} challenges exist)")
            return
        
        # Clear existing challenges if force reseeding
        if force_reseed and existing > 0:
            conn.execute('DELETE FROM challenge_attempts')
            conn.execute('DELETE FROM user_challenge_progress') 
            conn.execute('DELETE FROM challenges')
            conn.commit()
            print(f"Cleared {existing} existing challenges for reseeding")
            
        print("Seeding healthcare data analysis challenges...")
        
        # VisiQuate Healthcare Data Integrity Scenarios - Exact match to evaluation document
        challenges = [
            # Level 1: Basic Data Integrity
            {
                'title': 'Balance Validity',
                'description': '''**Data Integrity Scenario: Balance Validity**

**Rule/Constraint**: Total Balance must equal Total Charges less Total Payments and Total Adjustments

**Task for Applicant**:
- Test rule/constraint
- Summarize rule adherence (volumes, amounts, etc.)
- Provide detailed record examples where rule is not valid

**Expected Approach**: Validate the fundamental balance equation across all accounts.''',
                'difficulty_level': 1,
                'category': 'data-integrity',
                'expected_query': 'SELECT invoice_id, balance, total_charges, total_payments, total_adjustments, (total_charges - total_payments - total_adjustments) as calculated_balance, (balance - (total_charges - total_payments - total_adjustments)) as variance FROM hw_accounts WHERE (balance - (total_charges - total_payments - total_adjustments)) != 0;',
                'expected_result_count': None,
                'hints': '["Check the balance formula: Balance = Charges - Payments - Adjustments", "Look for accounts where the calculated balance differs from the recorded balance", "Calculate variance amounts and provide examples", "Consider NULL value handling"]',
                'time_limit_minutes': 25
            },

            # Level 2: Cross-Table Rollup Validation
            {
                'title': 'Adjustment Rollup Validation',
                'description': '''**Data Integrity Scenario: Amounts in accounts rolled up from transactions**

**Rule/Constraint**: Total Adjustments in Accounts must equal the sum of Adjustments from Transactions

**Task for Applicant**:
- Test rule/constraint  
- Summarize rule adherence (volumes, amounts, etc.)
- Provide detailed record examples where rule is not valid

**Expected Approach**: Cross-reference account totals with transaction detail sums.''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.total_adjustments as account_adjustments, COALESCE(SUM(t.total_adjustments), 0) as transaction_adjustments, (a.total_adjustments - COALESCE(SUM(t.total_adjustments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.total_adjustments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["JOIN accounts and transactions on invoice_id", "Sum transaction adjustments by account", "Compare with account-level totals", "Handle accounts with no transactions using LEFT JOIN"]',
                'time_limit_minutes': 30
            },

            {
                'title': 'Payment Rollup Validation',
                'description': '''**Data Integrity Scenario: Amounts in accounts rolled up from transactions**

**Rule/Constraint**: Total Payments in Accounts must equal the sum of Payments from Transactions

**Task for Applicant**:
- Test rule/constraint
- Summarize rule adherence (volumes, amounts, etc.)  
- Provide detailed record examples where rule is not valid

**Expected Approach**: Validate payment rollup accuracy between accounts and transactions.''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.total_payments as account_payments, COALESCE(SUM(t.total_payments), 0) as transaction_payments, (a.total_payments - COALESCE(SUM(t.total_payments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.total_payments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["Compare total_payments between accounts and transactions", "Use SUM to aggregate transaction payments by invoice", "Look for discrepancies between the two sources", "Provide summary statistics on adherence"]',
                'time_limit_minutes': 30
            },

            {
                'title': 'Insurance Payment Rollup Validation',
                'description': '''**Data Integrity Scenario: Amounts in accounts rolled up from transactions**

**Rule/Constraint**: Total Insurance Payments in Accounts must equal the sum of Ins Payments from Transactions

**Task for Applicant**:
- Test rule/constraint
- Summarize rule adherence (volumes, amounts, etc.)
- Provide detailed record examples where rule is not valid

**Expected Approach**: Validate insurance payment rollup integrity.''',
                'difficulty_level': 2,
                'category': 'data-integrity', 
                'expected_query': 'SELECT a.invoice_id, a.ins_payments as account_ins_payments, COALESCE(SUM(t.total_ins_payments), 0) as transaction_ins_payments, (a.ins_payments - COALESCE(SUM(t.total_ins_payments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.ins_payments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["Focus on insurance payment amounts specifically", "Compare ins_payments in accounts with total_ins_payments in transactions", "Identify patterns in discrepancies", "Calculate volume and amount summaries"]',
                'time_limit_minutes': 30
            },

            {
                'title': 'Patient Payment Rollup Validation',
                'description': '''**Data Integrity Scenario: Amounts in accounts rolled up from transactions**

**Rule/Constraint**: Total Patient Payments in Accounts must equal the sum of Patient Payments from Transactions

**Task for Applicant**:
- Test rule/constraint
- Summarize rule adherence (volumes, amounts, etc.)
- Provide detailed record examples where rule is not valid

**Expected Approach**: Validate patient payment rollup accuracy.''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.pt_payments as account_pt_payments, COALESCE(SUM(t.total_pt_payments), 0) as transaction_pt_payments, (a.pt_payments - COALESCE(SUM(t.total_pt_payments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.pt_payments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["Compare patient payment totals between accounts and transactions", "Use pt_payments and total_pt_payments fields", "Look for systematic vs random discrepancies", "Provide variance analysis"]',
                'time_limit_minutes': 30
            },

            {
                'title': 'Claim Date Patterns',
                'description': '''**Data Integrity Scenario: Claim Date Patterns**

**Rule/Constraint**: By default first_claim_bill_date is supposed to be before last_claim_bill_date

**Task for Applicant**:
- Test rule/constraint
- Summarize data patterns and/or rule adherence (showing volumes, amounts, etc.)
- Provide detailed record examples where rule is not valid

**Expected Approach**: Analyze claim billing date logic and identify anomalies.''',
                'difficulty_level': 1,
                'category': 'data-quality',
                'expected_query': "SELECT invoice_id, first_claim_bill_date, last_claim_bill_date, julianday(last_claim_bill_date) - julianday(first_claim_bill_date) as days_diff FROM hw_accounts WHERE first_claim_bill_date IS NOT NULL AND last_claim_bill_date IS NOT NULL AND first_claim_bill_date > last_claim_bill_date;",
                'expected_result_count': None,
                'hints': '["Compare first_claim_bill_date with last_claim_bill_date", "Look for cases where first date is after last date", "Calculate time differences where appropriate", "Consider NULL handling"]',
                'time_limit_minutes': 25
            },

            # Level 3: Balance Summary Analysis
            {
                'title': 'Balance Summary Validation',
                'description': '''**Data Integrity Scenario: Balance Summary**

**Rule/Constraint**: Account Balance must equal the sum of Insurance Balance + Patient Balance

**Task for Applicant**:
- Test rule/constraint
- Summarize data patterns and/or rule adherence (showing volumes, amounts, etc.) 
- Provide detailed record examples where rule is not valid

**Expected Approach**: Validate balance component relationships.''',
                'difficulty_level': 3,
                'category': 'data-integrity',
                'expected_query': 'SELECT invoice_id, balance, ins_balance, patient_balance, (ins_balance + patient_balance) as calculated_balance, (balance - (ins_balance + patient_balance)) as variance FROM hw_accounts WHERE ABS(balance - (ins_balance + patient_balance)) > 0.01;',
                'expected_result_count': None,
                'hints': '["Test if Account Balance = Insurance Balance + Patient Balance", "Calculate variances between recorded and calculated balances", "Look for patterns in the discrepancies", "Provide summary statistics on rule adherence"]',
                'time_limit_minutes': 35
            },

            {
                'title': 'AR Status Distribution Analysis',
                'description': '''**Analysis Scenario: Balance Summary**

**Data Context**: The account data has both open and closed accounts (ar_status)

**Task for Applicant**:
- Analyze balance (ar_status) distribution by various attributes
- Summarize data patterns
- Call attention to any interesting data patterns
- How many open accounts were there by service date year and month?
- For example: what are the top 10 cur_payors with the lowest percentage of open accounts

**Expected Approach**: Multi-dimensional AR status analysis with business insights.''',
                'difficulty_level': 3,
                'category': 'business-analysis',
                'expected_query': "SELECT ar_status, COUNT(*) as account_count, ROUND(AVG(balance), 2) as avg_balance, strftime('%Y-%m', service_start_date) as service_month FROM hw_accounts WHERE service_start_date IS NOT NULL GROUP BY ar_status, service_month ORDER BY service_month DESC;",
                'expected_result_count': None,
                'hints': '["Group accounts by AR status and analyze patterns", "Look at distribution by time periods (service dates)", "Calculate percentages for different attributes", "Identify payors with interesting open/closed patterns", "Provide business insights about the findings"]',
                'time_limit_minutes': 40
            },

            {
                'title': 'Primary Payor Patterns',
                'description': '''**Analysis Scenario: Primary Payor Patterns**

**Review Payor Attributes**: cur_iplan_code, cur_payor, iplan_1_code, iplan_1_payor, iplan_2_code, iplan_2_payor, iplan_3_code, iplan_3_payor

**Task for Applicant**:
- Analyze payor patterns and provide findings
- Examples could include:
  - For Iplan_1 who are the payors with the highest average of payment amounts to total charges?
  - How many closed accounts vs open accounts by service month per cur_payor?
- Note: these are just suggestions - please use your own thoughts and analysis and provide a summary description of any findings/analysis

**Expected Approach**: Comprehensive payor performance and pattern analysis.''',
                'difficulty_level': 3,
                'category': 'business-analysis',
                'expected_query': "SELECT cur_payor, iplan_1_payor, COUNT(*) as total_accounts, COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) as open_accounts, ROUND(100.0 * COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) / COUNT(*), 2) as open_percentage, ROUND(AVG(CASE WHEN total_charges > 0 THEN 100.0 * total_payments / total_charges END), 2) as payment_percentage FROM hw_accounts WHERE cur_payor IS NOT NULL AND total_charges > 0 GROUP BY cur_payor, iplan_1_payor ORDER BY payment_percentage DESC;",
                'expected_result_count': None,
                'hints': '["Analyze relationships between different payor fields", "Calculate payment ratios and performance metrics", "Look at open/closed account patterns by payor", "Consider service date trends", "Provide business insights about payor performance"]',
                'time_limit_minutes': 45
            },

            # Level 4: Expert Crosswalk Analysis  
            {
                'title': 'Transaction Crosswalk Uniqueness',
                'description': '''**Data Integrity Scenario: Transaction Crosswalk**

**Rule/Constraint**: hw_trn_codes is joined to hw_transactions on txn_type_code and txn_sub_type_code

**Task for Applicant**:
- Review data as it relates to transactions and provide analysis on any issues with the crosswalk table as it relates to transactions
- Validate uniqueness and referential integrity
- Identify orphaned records and unused codes
- Provide comprehensive data quality assessment

**Expected Approach**: Full integrity audit of transaction code crosswalk relationships.''',
                'difficulty_level': 4,
                'category': 'data-integrity',
                'expected_query': "SELECT 'Transaction codes not in crosswalk' as issue_type, COUNT(*) as count FROM hw_transactions t LEFT JOIN hw_trn_codes c ON t.txn_type_code = c.txn_type_code AND t.txn_sub_type_code = c.txn_sub_type_code WHERE c.txn_type_code IS NULL UNION ALL SELECT 'Duplicate crosswalk entries' as issue_type, COUNT(*) FROM (SELECT txn_type_code, txn_sub_type_code FROM hw_trn_codes GROUP BY txn_type_code, txn_sub_type_code HAVING COUNT(*) > 1);",
                'expected_result_count': None,
                'hints': '["Test the join relationship between transactions and crosswalk tables", "Look for transactions that cannot be matched to crosswalk codes", "Check for duplicate entries in the crosswalk table", "Identify unused crosswalk codes", "Provide comprehensive data quality summary"]',
                'time_limit_minutes': 50
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