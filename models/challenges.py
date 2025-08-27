"""
Challenge system models and database operations.
Handles challenge creation, seeding, and tracking.
Updated with internal scenarios from TSV file.
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
            
        print("Seeding healthcare data analysis challenges from internal scenarios...")
        
        # VisiQuate Healthcare Data Integrity Scenarios - From internal_scenarios.tsv
        challenges = [
            {
                'title': 'Balance Validity',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Balance Validity
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> Total Balance must equal Total Charges less Total Payments and Total Adjustments
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Test rule/constraint</li>
                            <li>Summarize rule adherence (volumes, amounts, etc.)</li>
                            <li>Provide detailed record examples where rule is not valid</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 1,
                'category': 'data-integrity',
                'expected_query': 'SELECT invoice_id, balance, total_charges, total_payments, total_adjustments, (total_charges - total_payments - total_adjustments) as calculated_balance, (balance - (total_charges - total_payments - total_adjustments)) as variance FROM hw_accounts WHERE (balance - (total_charges - total_payments - total_adjustments)) != 0;',
                'expected_result_count': None,
                'hints': '["Check the balance formula: Balance = Charges - Payments - Adjustments", "Look for accounts where the calculated balance differs from the recorded balance", "Calculate variance amounts and provide examples", "Consider NULL value handling"]',
                'time_limit_minutes': 30,
                'admin_sql_example': '''/* 61416 */ 
select count(*) from hw_accounts where balance = total_charges + total_adjustments - total_payments;

select count(*) from hw_accounts where balance <> total_charges + total_adjustments - total_payments; -- 5 records

select * from hw_accounts where balance <> total_charges + total_adjustments - total_payments;''',
                'admin_notes': '''- Adjustments are negative values and payments are positive.
- We expect applicant to discover this and make SQL adjustments
- There are 5 invoices where this math is incorrect
- We expect them to summarize the volumes and amounts ideally showing variance
- We expect them to show the 5 invoices with errors'''
            },

            {
                'title': 'Amounts in accounts rolled up from transactions - Adjustments',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts + Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Amounts in accounts rolled up from transactions
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> Total Adjustments in Accounts must equal the sum of Adjustments from Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Test rule/constraint</li>
                            <li>Summarize rule adherence (volumes, amounts, etc.)</li>
                            <li>Provide detailed record examples where rule is not valid</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.total_adjustments as account_adjustments, COALESCE(SUM(t.total_adjustments), 0) as transaction_adjustments, (a.total_adjustments - COALESCE(SUM(t.total_adjustments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.total_adjustments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["JOIN accounts and transactions on invoice_id", "Sum transaction adjustments by account", "Compare with account-level totals", "Handle accounts with no transactions using LEFT JOIN"]',
                'time_limit_minutes': 35,
                'admin_sql_example': '''SELECT 
  COUNT(a.invoice_id) AS invoice_cnt,
  SUM(t.adjustments) AS Txn_Adjs,
  SUM(a.total_adjustments) AS Act_Adjs,
  SUM((t.adjustments * -1) - a.total_adjustments) AS Variance
FROM hw_accounts a 
LEFT JOIN (
  SELECT 
    invoice_id,
    SUM(total_adjustments) AS adjustments,
    SUM(total_payments) AS payments,
    SUM(total_ins_payments) AS ins_payments,
    SUM(total_pt_payments) AS pt_payments
  FROM hw_transactions
  GROUP BY invoice_id
) t ON a.invoice_id = t.invoice_id
WHERE a.total_adjustments <> t.adjustments * -1;''',
                'admin_notes': '''- There are a number of ways to identify this scenario.
- An efficient approach is to use CTE from transactions that can then be joined to accounts to identify variances.
- We expect the applicant to be able to identify correct fields based on schema, correct joins, etc.
- There are 1,013 invoices where adjustments are not equal to rolled up value.
- Applicant should be able to provide summary of vol and amount
- Applicant should be able to show examples of where amounts are incorrect
- Important for applicant to recognize that transaction adjustments are not negative but accounts are'''
            },

            {
                'title': 'Amounts in accounts rolled up from transactions - Payments',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts + Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Amounts in accounts rolled up from transactions
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> Total Payments in Accounts must equal the sum of Payments from Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Test rule/constraint</li>
                            <li>Summarize rule adherence (volumes, amounts, etc.)</li>
                            <li>Provide detailed record examples where rule is not valid</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.total_payments as account_payments, COALESCE(SUM(t.total_payments), 0) as transaction_payments, (a.total_payments - COALESCE(SUM(t.total_payments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.total_payments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["Compare total_payments between accounts and transactions", "Use SUM to aggregate transaction payments by invoice", "Look for discrepancies between the two sources", "Provide summary statistics on adherence"]',
                'time_limit_minutes': 35,
                'admin_sql_example': '''SELECT 
  COUNT(a.invoice_id) AS invoice_cnt,
  SUM(t.payments) AS Txn_Pmts,
  SUM(a.total_payments) AS Act_Pmts,
  SUM(t.payments - a.total_payments) AS Variance
FROM hw_accounts a 
LEFT JOIN (
  SELECT 
    invoice_id,
    SUM(total_adjustments) AS adjustments,
    SUM(total_payments) AS payments,
    SUM(total_ins_payments) AS ins_payments,
    SUM(total_pt_payments) AS pt_payments
  FROM hw_transactions
  GROUP BY invoice_id
) t ON a.invoice_id = t.invoice_id
WHERE a.total_payments <> t.payments''',
                'admin_notes': '''- There are a number of ways to identify this scenario.
- An efficient approach is to use CTE from transactions that can then be joined to accounts to identify variances.
- We expect the applicant to be able to identify correct fields based on schema, correct joins, etc.
- There are 748 invoices where total payments are not equal to rolled up value.
- Applicant should be able to provide summary of vol and amount
- Applicant should be able to show examples of where amounts are incorrect'''
            },

            {
                'title': 'Amounts in accounts rolled up from transactions - Insurance Payments',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts + Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Amounts in accounts rolled up from transactions
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> Total Insurance Payments in Accounts must equal the sum of Ins Payments from Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Test rule/constraint</li>
                            <li>Summarize rule adherence (volumes, amounts, etc.)</li>
                            <li>Provide detailed record examples where rule is not valid</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.ins_payments as account_ins_payments, COALESCE(SUM(t.total_ins_payments), 0) as transaction_ins_payments, (a.ins_payments - COALESCE(SUM(t.total_ins_payments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.ins_payments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["Focus on insurance payment amounts specifically", "Compare ins_payments in accounts with total_ins_payments in transactions", "Identify patterns in discrepancies", "Calculate volume and amount summaries"]',
                'time_limit_minutes': 35,
                'admin_sql_example': '''SELECT 
  COUNT(a.invoice_id) AS invoice_cnt,
  SUM(t.ins_payments) AS Txn_insPmts,
  SUM(a.ins_payments) AS Act_insPmts,
  SUM((t.ins_payments) - a.ins_payments) AS Variance
FROM hw_accounts a 
LEFT JOIN (
  SELECT 
    invoice_id,
    SUM(total_adjustments) AS adjustments,
    SUM(total_payments) AS payments,
    SUM(total_ins_payments) AS ins_payments,
    SUM(total_pt_payments) AS pt_payments
  FROM hw_transactions
  GROUP BY invoice_id
) t ON a.invoice_id = t.invoice_id
WHERE a.ins_payments <> t.ins_payments -- 626''',
                'admin_notes': '''- There are a number of ways to identify this scenario.
- An efficient approach is to use CTE from transactions that can then be joined to accounts to identify variances.
- We expect the applicant to be able to identify correct fields based on schema, correct joins, etc.
- There are 626 invoices where insurance payments are not equal to rolled up value.
- Applicant should be able to provide summary of vol and amount
- Applicant should be able to show examples of where amounts are incorrect'''
            },

            {
                'title': 'Amounts in accounts rolled up from transactions - Patient Payments',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts + Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Amounts in accounts rolled up from transactions
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> Total Patient Payments in Accounts must equal the sum of Patient Payments from Transactions
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Test rule/constraint</li>
                            <li>Summarize rule adherence (volumes, amounts, etc.)</li>
                            <li>Provide detailed record examples where rule is not valid</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 2,
                'category': 'data-integrity',
                'expected_query': 'SELECT a.invoice_id, a.pt_payments as account_pt_payments, COALESCE(SUM(t.total_pt_payments), 0) as transaction_pt_payments, (a.pt_payments - COALESCE(SUM(t.total_pt_payments), 0)) as variance FROM hw_accounts a LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id GROUP BY a.invoice_id, a.pt_payments HAVING ABS(variance) > 0.01;',
                'expected_result_count': None,
                'hints': '["Compare patient payment totals between accounts and transactions", "Use pt_payments and total_pt_payments fields", "Look for systematic vs random discrepancies", "Provide variance analysis"]',
                'time_limit_minutes': 35,
                'admin_sql_example': '''SELECT 
  COUNT(a.invoice_id) AS invoice_cnt,
  SUM(t.pt_payments) AS Txn_ptPmts,
  SUM(a.pt_payments) AS Act_ptPmts,
  SUM((t.pt_payments) - a.pt_payments) AS Variance
FROM hw_accounts a 
LEFT JOIN (
  SELECT 
    invoice_id,
    SUM(total_adjustments) AS adjustments,
    SUM(total_payments) AS payments,
    SUM(total_ins_payments) AS ins_payments,
    SUM(total_pt_payments) AS pt_payments
  FROM hw_transactions
  GROUP BY invoice_id
) t ON a.invoice_id = t.invoice_id
WHERE a.pt_payments <> t.pt_payments -- 123''',
                'admin_notes': '''- There are a number of ways to identify this scenario.
- An efficient approach is to use CTE from transactions that can then be joined to accounts to identify variances.
- We expect the applicant to be able to identify correct fields based on schema, correct joins, etc.
- There are 123 invoices where patient payments are not equal to rolled up value.
- Applicant should be able to provide summary of vol and amount
- Applicant should be able to show examples of where amounts are incorrect'''
            },

            {
                'title': 'Claim Date Patterns',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Claim Date Patterns
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> By default first_claim_bill_date is supposed to be before last_claim_bill_date
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Test rule/constraint</li>
                            <li>Summarize data patterns and/or rule adherence (showing volumes, amounts, etc.)</li>
                            <li>Provide detailed record examples where rule is not valid</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 2,
                'category': 'data-quality',
                'expected_query': "SELECT invoice_id, first_claim_bill_date, last_claim_bill_date, julianday(last_claim_bill_date) - julianday(first_claim_bill_date) as days_diff FROM hw_accounts WHERE first_claim_bill_date IS NOT NULL AND last_claim_bill_date IS NOT NULL AND first_claim_bill_date > last_claim_bill_date;",
                'expected_result_count': None,
                'hints': '["Compare first_claim_bill_date with last_claim_bill_date", "Look for cases where first date is after last date", "Calculate time differences where appropriate", "Consider NULL handling"]',
                'time_limit_minutes': 30,
                'admin_sql_example': '''select count(*) from hw_accounts where first_claim_bill_date is null and last_claim_bill_date is not null -- 411

select first_claim_bill_date,last_claim_bill_date from hw_accounts where first_claim_bill_date is null and last_claim_bill_date is not null -- shows dates summary

select count(*) from hw_accounts where first_claim_bill_date is not null and first_claim_bill_date > last_claim_bill_date -- 21''',
                'admin_notes': '''- Introduced 21 errors where first claim date > last claim date - expect applicant to identify that there are 21 errors.
- Also expect them to identify the 411 cases where the first bill date is NULL and final bill date is not null
- Ideally we would like to also see some distribution analysis etc.'''
            },

            {
                'title': 'Balance Summary',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Balance Summary
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> Account Balance must equal the sum of Insurance Balance + Patient Balance
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Test rule/constraint</li>
                            <li>Summarize data patterns and/or rule adherence (showing volumes, amounts, etc.)</li>
                            <li>Provide detailed record examples where rule is not valid</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 3,
                'category': 'data-integrity',
                'expected_query': 'SELECT invoice_id, balance, ins_balance, patient_balance, (ins_balance + patient_balance) as calculated_balance, (balance - (ins_balance + patient_balance)) as variance FROM hw_accounts WHERE ABS(balance - (ins_balance + patient_balance)) > 0.01;',
                'expected_result_count': None,
                'hints': '["Test if Account Balance = Insurance Balance + Patient Balance", "Calculate variances between recorded and calculated balances", "Look for patterns in the discrepancies", "Provide summary statistics on rule adherence"]',
                'time_limit_minutes': 40,
                'admin_sql_example': '''select count(*) from hw_accounts where balance <> ins_balance + patient_balance -- 140

-- UPDATE THE ERROR 
update hw_accounts set ins_balance = ins_balance + ins_payments 
where total_payments <> ins_payments 
  and ins_payments > 0 
  and ins_plan_1_total_payments > 0 
  and iplan_1_payor = 'Parkridge Underwriters' ''',
                'admin_notes': '''NOTE: There are 140 records where the balance <> ins_balance + patient_balance
This is due to errors for 140 records where iplan_1_payor = 'Parkridge Underwriters'
- Applicant is expected to find the 140 count and records and if they explore they should be able to determine that the error is due to 140 records where the insurance payment for Parkridge was not reflected in the insurance balance.
- The variance bw Balance - ( ins + pat balance ) = the ins_payments for these 140 examples'''
            },

            {
                'title': 'Balance Summary - AR Status Distribution',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Balance Summary
                    </div>
                    <div class="detail-row">
                        <strong>Data Context:</strong> The account data has both open and closed accounts (ar_status)
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Analyze balance (ar_status) distribution by various attributes</li>
                            <li>Summarize data patterns</li>
                            <li>Call attention to any interesting data patterns</li>
                            <li>How many open accounts were there by service date year and month?</li>
                            <li>For example: what are the top 10 cur_payors with the lowest percentage of open accounts</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 3,
                'category': 'business-analysis',
                'expected_query': "SELECT ar_status, COUNT(*) as account_count, ROUND(AVG(balance), 2) as avg_balance, strftime('%Y-%m', service_start_date) as service_month FROM hw_accounts WHERE service_start_date IS NOT NULL GROUP BY ar_status, service_month ORDER BY service_month DESC;",
                'expected_result_count': None,
                'hints': '["Group accounts by AR status and analyze patterns", "Look at distribution by time periods (service dates)", "Calculate percentages for different attributes", "Identify payors with interesting open/closed patterns", "Provide business insights about the findings"]',
                'time_limit_minutes': 45,
                'admin_sql_example': '''select 
  i.cur_payor,
  sum(i.VOL) as total_vol,
  sum(i.open_volume) as openvol,
  cast(sum(cast(i.open_volume as real) / cast(vol as real)) as real) as pct
from (
  select 
    cur_payor as cur_payor,
    count(*) as VOL,
    SUM(case when ar_status = 'Closed' then 1 else 0 end) as closed_volume,
    SUM(case when ar_status = 'Open' then 1 else 0 end) as open_volume
  from hw_accounts
  group by cur_payor
) i
group by i.cur_payor
order by pct ASC''',
                'admin_notes': '''- This is more of an exercise to see how they review data
- We want to see their patterns of analysis. How they present information etc.'''
            },

            {
                'title': 'Primary Payor Patterns',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Accounts
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Primary Payor Patterns
                    </div>
                    <div class="detail-row">
                        <strong>Review Payor Attributes:</strong>
                        <ul class="payor-list">
                            <li>cur_iplan_code</li>
                            <li>cur_payor</li>
                            <li>iplan_1_code</li>
                            <li>iplan_1_payor</li>
                            <li>iplan_2_code</li>
                            <li>iplan_2_payor</li>
                            <li>iplan_3_code</li>
                            <li>iplan_3_payor</li>
                        </ul>
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Analyze payor patterns and provide findings</li>
                            <li><strong>Examples could include:</strong>
                                <ul>
                                    <li>For Iplan_1 who are the payors with the highest average of payment amounts to total charges?</li>
                                    <li>How many closed accounts vs open accounts by service month per cur_payor?</li>
                                </ul>
                            </li>
                            <li><em>Note: these are just suggestions - please use your own thoughts and analysis and provide a summary description of any findings/analysis</em></li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 3,
                'category': 'business-analysis',
                'expected_query': "SELECT cur_payor, iplan_1_payor, COUNT(*) as total_accounts, COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) as open_accounts, ROUND(100.0 * COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) / COUNT(*), 2) as open_percentage, ROUND(AVG(CASE WHEN total_charges > 0 THEN 100.0 * total_payments / total_charges END), 2) as payment_percentage FROM hw_accounts WHERE cur_payor IS NOT NULL AND total_charges > 0 GROUP BY cur_payor, iplan_1_payor ORDER BY payment_percentage DESC;",
                'expected_result_count': None,
                'hints': '["Analyze relationships between different payor fields", "Calculate payment ratios and performance metrics", "Look at open/closed account patterns by payor", "Consider service date trends", "Provide business insights about payor performance"]',
                'time_limit_minutes': 50,
                'admin_sql_example': '''-- No set SQL here just looking for their approach to this question''',
                'admin_notes': '''- This is an open-ended analysis exercise
- We want to see their approach to exploring payor patterns
- Look for creativity in their analysis and business insights
- Should demonstrate understanding of healthcare payment dynamics'''
            },

            {
                'title': 'Transaction Crosswalk Uniqueness',
                'description': '''<div class="challenge-details">
                    <div class="detail-row">
                        <strong>Data Set(s):</strong> Transaction Crosswalk
                    </div>
                    <div class="detail-row">
                        <strong>Scenario:</strong> Uniqueness
                    </div>
                    <div class="detail-row">
                        <strong>Rule/Constraint:</strong> hw_trn_codes is joined to hw_transactions on txn_type_code and txn_sub_type_code
                    </div>
                    <div class="detail-row">
                        <strong>Task for Applicant:</strong>
                        <ul>
                            <li>Review data as it relates to transactions and provide analysis on any issues with the crosswalk table as it relates to transactions</li>
                        </ul>
                    </div>
                </div>''',
                'difficulty_level': 4,
                'category': 'data-integrity',
                'expected_query': "SELECT 'Transaction codes not in crosswalk' as issue_type, COUNT(*) as count FROM hw_transactions t LEFT JOIN hw_trn_codes c ON t.txn_type_code = c.txn_type_code AND t.txn_sub_type_code = c.txn_sub_type_code WHERE c.txn_type_code IS NULL UNION ALL SELECT 'Duplicate crosswalk entries' as issue_type, COUNT(*) FROM (SELECT txn_type_code, txn_sub_type_code FROM hw_trn_codes GROUP BY txn_type_code, txn_sub_type_code HAVING COUNT(*) > 1);",
                'expected_result_count': None,
                'hints': '["Test the join relationship between transactions and crosswalk tables", "Look for transactions that cannot be matched to crosswalk codes", "Check for duplicate entries in the crosswalk table", "Identify unused crosswalk codes", "Provide comprehensive data quality summary"]',
                'time_limit_minutes': 60,
                'admin_sql_example': '''-- There are 2 duplicate entries in the crosswalk table
select * from hw_trn_codes where txn_sub_type_code in ('A11NP','A19RT')

select count(t.txn_id) as vol,
       t.txn_type_code,
       t.txn_sub_type_code,
       x.txn_sub_type_desc
from hw_transactions t 
left join hw_trn_codes x on t.txn_type_code = x.txn_type_code and t.txn_sub_type_code = x.txn_sub_type_code
where t.txn_sub_type_code in ('A11NP','A19RT')
group by t.txn_type_code, t.txn_sub_type_code, x.txn_sub_type_desc

-- Also we deleted record from crosswalk: A17 PAST TIMELY FILING limit
select count(t.txn_id) as vol,
       t.txn_type_code,
       t.txn_sub_type_code,
       x.txn_sub_type_desc
from hw_transactions t 
left join hw_trn_codes x on t.txn_type_code = x.txn_type_code and t.txn_sub_type_code = x.txn_sub_type_code
where x.txn_type_code is null
group by t.txn_type_code, t.txn_sub_type_code, x.txn_sub_type_desc''',
                'admin_notes': '''- Applicant is expected to identify 2 duplicate keys in the crosswalk table
- Applicant should be able to identify that there is no crosswalk value for code A17 using the join logic
- This tests their ability to perform comprehensive data quality audits'''
            }
        ]
        
        for challenge in challenges:
            conn.execute('''
                INSERT INTO challenges (title, description, difficulty_level, category, expected_query, 
                                      expected_result_count, hints, time_limit_minutes, admin_sql_example, admin_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (challenge['title'], challenge['description'], challenge['difficulty_level'], 
                  challenge['category'], challenge['expected_query'], challenge['expected_result_count'],
                  challenge['hints'], challenge['time_limit_minutes'], 
                  challenge.get('admin_sql_example', ''), challenge.get('admin_notes', '')))
        
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
                   max_score, time_limit_minutes, is_active, admin_sql_example, admin_notes
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
                   max_score, time_limit_minutes, expected_result_count, admin_sql_example, admin_notes
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