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
        
        challenges = [
            # VisiQuate Evaluation Scenarios - Data Integrity Focus
            
            # Level 1: Basic Data Exploration
            {
                'title': 'Account Balance Validation',
                'description': '''**Data Integrity Scenario: Balance Validity**

**Rule/Constraint**: Total Balance must equal Total Charges less Total Payments and Total Adjustments

**Task**: Test this rule and provide analysis:
1. Calculate the expected balance for each account using the formula
2. Compare to the actual balance field
3. Identify any accounts where the rule is violated
4. Summarize your findings with counts and examples

**Expected Approach**: Write SQL to validate this business rule across all accounts and identify discrepancies.''',
                'difficulty_level': 1,
                'category': 'data-integrity',
                'expected_query': 'SELECT invoice_id, balance, total_charges, total_payments, total_adjustments, (total_charges - total_payments - total_adjustments) as calculated_balance, (balance - (total_charges - total_payments - total_adjustments)) as variance FROM hw_accounts WHERE (balance - (total_charges - total_payments - total_adjustments)) != 0;',
                'expected_result_count': None,
                'hints': '["Focus on the formula: Balance = Charges - Payments - Adjustments", "Look for records where actual balance differs from calculated balance", "Consider using a variance calculation", "Provide specific examples in your summary"]',
                'time_limit_minutes': 30
            },
            
            {
                'title': 'Claim Date Pattern Analysis',
                'description': '''**Data Integrity Scenario: Claim Date Patterns**

**Rule/Constraint**: By default, first_claim_bill_date should be before last_claim_bill_date

**Task**: Analyze date patterns and identify violations:
1. Test the date sequence rule
2. Summarize data patterns (volumes, date ranges, etc.)
3. Provide examples where the rule is violated
4. Look for any interesting patterns in the violations

**Expected Approach**: Query the date fields and identify logical inconsistencies.''',
                'difficulty_level': 1,
                'category': 'data-integrity',
                'expected_query': "SELECT COUNT(*) as total_accounts, COUNT(CASE WHEN first_claim_bill_date > last_claim_bill_date THEN 1 END) as violations FROM hw_accounts WHERE first_claim_bill_date IS NOT NULL AND last_claim_bill_date IS NOT NULL;",
                'expected_result_count': None,
                'hints': '["Compare first_claim_bill_date with last_claim_bill_date", "Handle NULL values appropriately", "Count both total records and violations", "Look for patterns in date violations"]',
                'time_limit_minutes': 25
            },

            # Level 2: Cross-Table Validation
            {
                'title': 'Account vs Transaction Adjustments Reconciliation',
                'description': '''**Data Integrity Scenario: Account-Transaction Reconciliation**

**Rule/Constraint**: Total Adjustments in Accounts must equal the sum of Adjustments from Transactions

**Task**: Validate this rollup relationship:
1. Sum adjustments by invoice from the transactions table
2. Compare to total_adjustments in the accounts table
3. Identify discrepancies with specific examples
4. Calculate variance amounts and provide summary statistics

**Expected Approach**: JOIN accounts and transactions tables to validate the adjustment rollups.''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.total_adjustments as account_adjustments, COALESCE(SUM(t.total_adjustments), 0) as transaction_adjustments, (a.total_adjustments - COALESCE(SUM(t.total_adjustments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.total_adjustments HAVING variance != 0;',
                'expected_result_count': None,
                'hints': '["JOIN accounts and transactions on invoice_id", "Use SUM to aggregate transaction adjustments", "Handle cases where no transactions exist", "Focus on accounts with discrepancies"]',
                'time_limit_minutes': 35
            },

            {
                'title': 'Insurance vs Patient Payment Validation',
                'description': '''**Data Integrity Scenario: Payment Rollup Validation**

**Task**: Validate multiple payment rollup rules:
1. **Insurance Payments**: Total Insurance Payments in Accounts = sum of Ins Payments from Transactions
2. **Patient Payments**: Total Patient Payments in Accounts = sum of Patient Payments from Transactions  
3. **Overall Payments**: Total Payments in Accounts = sum of all Payments from Transactions

Identify which rule has the most violations and provide detailed analysis.

**Expected Approach**: Create comprehensive payment reconciliation analysis.''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.ins_payments, COALESCE(SUM(t.total_ins_payments), 0) as trans_ins_payments, a.pt_payments, COALESCE(SUM(t.total_pt_payments), 0) as trans_pt_payments, a.total_payments, COALESCE(SUM(t.total_payments), 0) as trans_total_payments FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id;',
                'expected_result_count': None,
                'hints': '["Validate multiple payment types in one query", "Compare account-level totals with transaction-level sums", "Look for patterns across different payment types", "Summarize which validation rules have the most issues"]',
                'time_limit_minutes': 40
            },

            # Level 3: Advanced Analysis
            {
                'title': 'AR Status and Balance Distribution Analysis',
                'description': '''**Analysis Scenario: Balance Summary Patterns**

**Task**: Analyze balance distribution by AR status:
1. **Rule Validation**: Account Balance = Insurance Balance + Patient Balance
2. **Pattern Analysis**: 
   - How many open vs closed accounts by service date year/month?
   - Which cur_payors have the lowest percentage of open accounts?
   - What are the balance patterns by billing center and service line?

**Expected Approach**: Multi-faceted analysis combining rule validation with business intelligence.''',
                'difficulty_level': 3,
                'category': 'business-analysis',
                'expected_query': "SELECT ar_status, COUNT(*) as account_count, COUNT(CASE WHEN (balance - (ins_balance + patient_balance)) != 0 THEN 1 END) as balance_rule_violations, strftime('%Y-%m', service_start_date) as service_month FROM hw_accounts WHERE service_start_date IS NOT NULL GROUP BY ar_status, service_month ORDER BY service_month DESC;",
                'expected_result_count': None,
                'hints': '["Validate the balance rule: Account Balance = Insurance Balance + Patient Balance", "Group by AR status and time periods", "Calculate percentages and identify trends", "Look for cur_payors with interesting patterns"]',
                'time_limit_minutes': 45
            },

            {
                'title': 'Primary Payor Analysis',
                'description': '''**Analysis Scenario: Payor Performance Patterns**

**Task**: Comprehensive payor analysis:
1. **Payment Performance**: For each iplan_1_payor, calculate the ratio of payment amounts to total charges
2. **Account Status Patterns**: Open vs closed accounts by service month per cur_payor
3. **Payor Hierarchy**: Analyze relationships between cur_payor, iplan_1_payor, iplan_2_payor, iplan_3_payor
4. **Reimbursement Efficiency**: Which payors have the best payment-to-charge ratios?

**Expected Approach**: Multi-dimensional payor performance analysis with business insights.''',
                'difficulty_level': 3,
                'category': 'business-analysis',
                'expected_query': "SELECT cur_payor, iplan_1_payor, COUNT(*) as total_accounts, COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) as open_accounts, ROUND(100.0 * COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) / COUNT(*), 2) as open_percentage, ROUND(AVG(CASE WHEN total_charges > 0 THEN 100.0 * ins_payments / total_charges END), 2) as payment_ratio FROM hw_accounts WHERE cur_payor IS NOT NULL GROUP BY cur_payor, iplan_1_payor ORDER BY payment_ratio DESC;",
                'expected_result_count': None,
                'hints': '["Analyze payment ratios and account status patterns", "Consider payor hierarchy relationships", "Look for efficiency metrics", "Provide business insights about payor performance"]',
                'time_limit_minutes': 50
            },

            # Level 4: Expert Cross-Walk and Data Quality
            {
                'title': 'Transaction Crosswalk Integrity Analysis',
                'description': '''**Data Integrity Scenario: Transaction Code Crosswalk**

**Rule/Constraint**: hw_trn_codes should uniquely map to transactions via txn_type_code and txn_sub_type_code

**Task**: Comprehensive crosswalk analysis:
1. **Uniqueness Validation**: Verify hw_trn_codes provides unique mappings
2. **Orphan Detection**: Find transactions with codes not in the crosswalk table
3. **Unused Codes**: Find crosswalk codes never used in transactions  
4. **Data Quality**: Analyze code usage patterns and identify potential issues

**Expected Approach**: Full data integrity audit of the crosswalk relationship.''',
                'difficulty_level': 4,
                'category': 'data-integrity',
                'expected_query': "SELECT 'Crosswalk Duplicates' as issue_type, COUNT(*) as count FROM (SELECT txn_type_code, txn_sub_type_code, COUNT(*) FROM hw_trn_codes GROUP BY txn_type_code, txn_sub_type_code HAVING COUNT(*) > 1) UNION SELECT 'Orphan Transactions' as issue_type, COUNT(DISTINCT t.txn_sub_type_code) FROM hw_transactions t LEFT JOIN hw_trn_codes c ON t.txn_sub_type_code = c.txn_sub_type_code WHERE c.txn_sub_type_code IS NULL;",
                'expected_result_count': None,
                'hints': '["Check for duplicate codes in the crosswalk table", "Find transactions that cannot be joined to crosswalk", "Identify unused crosswalk entries", "Provide comprehensive data quality summary"]',
                'time_limit_minutes': 60
            },

            # Original basic challenges for reference
            {
                'title': 'Data Overview - Table Exploration',
                'description': '''**Getting Started**: Explore the healthcare dataset structure.

**Task**: 
1. Count the total number of records in each table (hw_accounts, hw_charges, hw_transactions, hw_trn_codes)
2. Identify the date range of the data by finding min/max service dates
3. List the distinct billing offices and source systems

**Expected Approach**: Basic exploratory queries to understand the dataset scope.''',
                'difficulty_level': 1,
                'category': 'exploration',
                'expected_query': 'SELECT COUNT(*) as account_count FROM hw_accounts;',
                'expected_result_count': 1,
                'hints': '["Start with COUNT(*) queries for each table", "Use MIN/MAX for date ranges", "Use DISTINCT for categorical values", "This is your foundation for understanding the data"]',
                'time_limit_minutes': 20
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