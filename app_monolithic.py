from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import sqlite3
import json
import hashlib
from datetime import datetime
import os
import re
import time
import zipfile
import csv
import io
import tempfile
from werkzeug.utils import secure_filename

# Get version info from build files or environment variables
def get_version_info():
    # Try to read commit from build file first, fallback to environment
    git_commit = 'unknown'
    try:
        with open('/app/BUILD_INFO', 'r') as f:
            lines = f.read().strip().split('\n')
            for line in lines:
                if line.startswith('GIT_COMMIT='):
                    git_commit = line.split('=', 1)[1][:7]
                    break
    except FileNotFoundError:
        # Fallback to environment variable
        git_commit = os.getenv('GIT_COMMIT', 'unknown')[:7]
    
    # Also try to read build date from file
    build_date = 'unknown'
    version = '1.0.0'
    try:
        with open('/app/BUILD_INFO', 'r') as f:
            lines = f.read().strip().split('\n')
            for line in lines:
                if line.startswith('BUILD_DATE='):
                    build_date = line.split('=', 1)[1]
                elif line.startswith('VERSION='):
                    version = line.split('=', 1)[1]
    except FileNotFoundError:
        pass
    
    return {
        'git_commit': git_commit,
        'build_date': build_date,
        'version': version,
        'environment': os.getenv('FLASK_ENV', 'development')
    }

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')

# Use local path in development, container path in production
if os.path.exists('/app/data'):
    DATABASE = '/app/data/healthcare_quiz.db'
    USER_DATABASE = '/app/data/user_data.db'
else:
    DATABASE = 'healthcare_quiz.db'
    USER_DATABASE = 'user_data.db'

def get_db_connection():
    """Get connection to healthcare database (accessible via web UI)"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_db_connection():
    """Get connection to user tracking database (internal only)"""
    conn = sqlite3.connect(USER_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize both healthcare and user databases"""
    print("Initializing databases...")
    
    # Initialize healthcare database
    init_healthcare_database()
    
    # Initialize user tracking database (separate)
    init_user_database()

def init_healthcare_database():
    """Initialize healthcare database (accessible via web UI)"""
    import os
    import csv
    from datetime import datetime
    
    # Check if database already exists and has any tables
    if os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        try:
            # Check if any tables exist (uploaded data takes precedence)
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            if table_count > 0:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                existing_tables = [row[0] for row in cursor.fetchall()]
                print(f"Healthcare database already exists with {table_count} tables: {existing_tables}")
                conn.close()
                return
        except:
            pass
        finally:
            conn.close()
    
    print(f"Creating healthcare database: {DATABASE}")
    
    # Create fresh healthcare database
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    
    conn = sqlite3.connect(DATABASE)
    try:
        # Create healthcare schema
        if os.path.exists('schema.sql'):
            print("Creating healthcare tables from schema.sql...")
            with open('schema.sql', 'r') as f:
                schema = f.read()
            conn.executescript(schema)
            
            # Load healthcare data if CSV files exist
            if os.path.exists('HW_INVOICE.csv') and os.path.exists('HW_CHARGES.csv'):
                print("Loading healthcare data from CSV files...")
                load_healthcare_data(conn)
            else:
                print("CSV files not found - creating empty healthcare tables")
        
        conn.commit()
        print(f"Healthcare database initialized successfully: {DATABASE}")
    except Exception as e:
        print(f"Error initializing healthcare database: {e}")
        raise
    finally:
        conn.close()

def init_user_database():
    """Initialize user tracking database (internal only)"""
    print(f"Initializing user database: {USER_DATABASE}")
    
    # Create user database directory if needed
    import os
    db_dir = os.path.dirname(USER_DATABASE)
    if db_dir:  # Only create directory if there is a directory path
        os.makedirs(db_dir, exist_ok=True)
    
    conn = get_user_db_connection()
    try:
        create_user_tables(conn)
        conn.commit()
        print(f"User database initialized successfully: {USER_DATABASE}")
        
        # Seed challenges after database creation
        seed_healthcare_challenges()
        
    except Exception as e:
        print(f"Error initializing user database: {e}")
        raise
    finally:
        conn.close()

def create_user_tables(conn):
    """Create user tracking tables"""
    print("Creating user tracking tables...")
    
    # Create users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            first_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_sessions INTEGER DEFAULT 0
        )
    ''')
    
    # Create user_sessions table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT UNIQUE NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create query_logs table  
    conn.execute('''
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            query_text TEXT NOT NULL,
            execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            results_count INTEGER,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create challenges table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            difficulty_level INTEGER NOT NULL, -- 1=Basic, 2=Intermediate, 3=Advanced, 4=Expert
            category TEXT NOT NULL, -- 'financial', 'operational', 'temporal', 'quality'
            expected_query TEXT,
            expected_result_count INTEGER,
            expected_result_sample TEXT, -- JSON sample of expected results
            hints TEXT, -- JSON array of progressive hints
            max_score INTEGER DEFAULT 100,
            time_limit_minutes INTEGER DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Create challenge attempts table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS challenge_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            challenge_id INTEGER,
            query_text TEXT NOT NULL,
            result_count INTEGER,
            is_correct BOOLEAN NOT NULL,
            score INTEGER DEFAULT 0,
            hints_used INTEGER DEFAULT 0,
            execution_time_ms REAL,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (challenge_id) REFERENCES challenges (id)
        )
    ''')
    
    # Create user challenge progress table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_challenge_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            challenge_id INTEGER,
            best_score INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            is_completed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (challenge_id) REFERENCES challenges (id),
            UNIQUE(user_id, challenge_id)
        )
    ''')

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

def clean_value(value):
    """Clean and convert CSV values"""
    if not value or value.strip() == '' or value.upper() == 'N/A':
        return None
    
    # Remove BOM if present
    if value.startswith('﻿'):
        value = value[1:]
    
    return value.strip()

def parse_date(date_str):
    """Parse date strings from CSV"""
    if not date_str or date_str.strip() == '' or date_str.upper() == 'N/A':
        return None
    
    date_str = clean_value(date_str)
    if not date_str:
        return None
    
    try:
        # Try parsing YYYY-MM-DD format
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        try:
            # Try parsing MM/DD/YYYY format
            return datetime.strptime(date_str, '%m/%d/%Y').date()
        except ValueError:
            return None

def parse_decimal(decimal_str):
    """Parse decimal values from CSV"""
    if not decimal_str or decimal_str.strip() == '' or decimal_str.upper() == 'N/A':
        return None
    
    decimal_str = clean_value(decimal_str)
    if not decimal_str:
        return None
    
    try:
        return float(decimal_str)
    except ValueError:
        return None

def parse_money_to_cents(money_str):
    """Parse monetary values from CSV and convert to cents (integer)"""
    if not money_str or money_str.strip() == '' or money_str.upper() == 'N/A':
        return None
    
    money_str = clean_value(money_str)
    if not money_str:
        return None
    
    # Remove dollar signs and commas
    money_str = money_str.replace('$', '').replace(',', '')
    
    try:
        # Parse as float then convert to cents
        dollars = float(money_str)
        cents = int(round(dollars * 100))
        return cents
    except ValueError:
        return None

def is_money_column(column_name):
    """Detect if a column contains monetary values based on name"""
    column_lower = column_name.lower()
    
    # First check if it's clearly NOT a money column
    non_money_indicators = [
        'date', 'time', 'status', 'code', 'desc', 'description', 'id', 'number',
        'category', 'type', 'flag', 'name', 'office', 'center', 'system'
    ]
    
    # If it contains non-money indicators, it's not a money column
    if any(indicator in column_lower for indicator in non_money_indicators):
        return False
    
    # Now check for money indicators
    money_indicators = [
        'charge', 'amount', 'amt', 'cost', 'price', 'revenue', 'reimbursement', 
        'adjustment', 'debt', 'refund'
    ]
    
    # More specific patterns for money - avoid false positives
    specific_money_patterns = [
        '_amt', '_amount', '_charge', '_cost', '_price', '_revenue', 
        '_reimbursement', '_adjustment', '_debt', '_refund',
        'total_', '_total', '_paid_amt', '_payment_amt'
    ]
    
    # Check for specific money patterns first (more precise)
    if any(pattern in column_lower for pattern in specific_money_patterns):
        return True
        
    # Check for general money indicators (but we already filtered out dates/categories)
    return any(indicator in column_lower for indicator in money_indicators)

def format_cents_to_dollars(cents):
    """Convert cents (integer) back to dollar format for display"""
    if cents is None:
        return None
    
    # Handle different input types
    try:
        # If it's already a string that looks like a dollar amount, return as-is
        if isinstance(cents, str):
            # Check if it already looks like a dollar amount
            if '$' in cents or '.' in cents:
                return cents
            # Try to convert string to integer
            cents = int(float(cents))
        
        # If it's a float, convert to int first
        if isinstance(cents, float):
            cents = int(cents)
        
        # Convert cents to dollars
        return cents / 100.0
    except (ValueError, TypeError):
        # If conversion fails, return original value
        return cents

def load_healthcare_data(conn):
    """Load healthcare data from CSV files"""
    # Load lookup tables first
    load_lookup_tables(conn)
    
    # Load main tables
    load_patients(conn)
    load_invoices(conn)
    load_invoice_details(conn)
    
    # Print summary
    cursor = conn.execute("SELECT COUNT(*) FROM patients")
    patient_count = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM invoices")
    invoice_count = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM invoice_details")
    detail_count = cursor.fetchone()[0]
    
    print(f"Loaded {patient_count} patients, {invoice_count} invoices, {detail_count} invoice details")

def load_lookup_tables(conn):
    """Load lookup tables first"""
    # Service lines - extract from invoice data
    service_lines = set()
    
    # Read service lines from invoice CSV
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            service_line = clean_value(row.get('SERVICE_LINE'))
            if service_line:
                service_lines.add(service_line)
    
    # Insert service lines
    for service_line in service_lines:
        conn.execute("""
            INSERT OR IGNORE INTO service_lines (service_line_code, service_line_name)
            VALUES (?, ?)
        """, (service_line, service_line))
    
    # Insurance plans - extract from both CSV files
    insurance_plans = set()
    
    # From invoice CSV
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Current plan
            plan_code = clean_value(row.get('CUR_IPLAN_CODE'))
            plan_desc = clean_value(row.get('CUR_IPLAN_DESC'))
            payor = clean_value(row.get('CUR_PAYOR'))
            if plan_code:
                insurance_plans.add((plan_code, plan_desc, payor))
            
            # Primary plan
            plan_code = clean_value(row.get('IPLAN_1_CODE'))
            plan_desc = clean_value(row.get('IPLAN_1_DESC'))
            payor = clean_value(row.get('IPLAN_1_PAYOR'))
            if plan_code:
                insurance_plans.add((plan_code, plan_desc, payor))
    
    # Insert insurance plans
    for plan_code, plan_desc, payor in insurance_plans:
        conn.execute("""
            INSERT OR IGNORE INTO insurance_plans (plan_code, plan_description, payor_name)
            VALUES (?, ?, ?)
        """, (plan_code, plan_desc, payor))

def load_patients(conn):
    """Load patient data"""
    patients = set()
    
    # Extract unique patients from invoice CSV
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            patient_id = clean_value(row.get('NEW_PT_ID'))
            dob = parse_date(row.get('PAT_DOB'))
            billing_office = clean_value(row.get('BILLING_OFFICE'))
            
            if patient_id:
                patients.add((patient_id, dob, billing_office))
    
    # Insert patients
    for patient_id, dob, billing_office in patients:
        conn.execute("""
            INSERT OR IGNORE INTO patients (patient_id, date_of_birth, billing_office)
            VALUES (?, ?, ?)
        """, (patient_id, dob, billing_office))

def load_invoices(conn):
    """Load invoice header data"""
    count = 0
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            invoice_id = clean_value(row.get('NEW_INVOICE_ID'))
            if not invoice_id:
                continue
            
            # Extract and clean data (simplified version)
            patient_id = clean_value(row.get('NEW_PT_ID'))
            service_line_code = clean_value(row.get('SERVICE_LINE'))
            invoice_total_charges = parse_money_to_cents(row.get('INVOICE_TOTAL_CHARGES'))
            invoice_total_payments = parse_money_to_cents(row.get('INVOICE_TOTAL_PAYMENTS'))
            ar_status = clean_value(row.get('AR_STATUS'))
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO invoices (
                        invoice_id, patient_id, service_line_code, 
                        invoice_total_charges, invoice_total_payments, ar_status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (invoice_id, patient_id, service_line_code, 
                      invoice_total_charges, invoice_total_payments, ar_status))
                count += 1
                    
            except Exception as e:
                continue

def load_invoice_details(conn):
    """Load invoice detail data (simplified)"""
    count = 0
    with open('HW_CHARGES.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            invoice_detail_id = clean_value(row.get('NEW_INVOICE_DETAIL_ID'))
            if not invoice_detail_id:
                continue
            
            # Extract key fields only
            invoice_id = clean_value(row.get('NEW_INVOICE_ID'))
            patient_id = clean_value(row.get('NEW_PT_ID'))
            cpt_code = clean_value(row.get('CPT_CODE'))
            invoice_total_charges = parse_money_to_cents(row.get('INVOICE_TOTAL_CHARGES'))
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO invoice_details (
                        invoice_detail_id, invoice_id, patient_id, cpt_code, invoice_total_charges
                    ) VALUES (?, ?, ?, ?, ?)
                """, (invoice_detail_id, invoice_id, patient_id, cpt_code, invoice_total_charges))
                count += 1
                    
            except Exception as e:
                continue

# Initialize database on startup
init_database()

def get_or_create_user(username, email=None):
    """Get existing user or create new one"""
    conn = get_user_db_connection()
    try:
        # Try to find existing user
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user:
            # Update last seen
            conn.execute('UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            return dict(user)
        else:
            # Create new user
            cursor = conn.execute(
                'INSERT INTO users (username, email, total_sessions) VALUES (?, ?, 1)',
                (username, email or '')
            )
            user_id = cursor.lastrowid
            conn.commit()
            
            # Return new user
            new_user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            return dict(new_user)
    finally:
        conn.close()

def create_user_session(user_id, ip_address, user_agent):
    """Create a new user session"""
    import uuid
    session_id = str(uuid.uuid4())
    
    conn = get_user_db_connection()
    try:
        conn.execute(
            '''INSERT INTO user_sessions (user_id, session_id, ip_address, user_agent)
               VALUES (?, ?, ?, ?)''',
            (user_id, session_id, ip_address, user_agent)
        )
        
        # Update user total sessions count
        conn.execute(
            'UPDATE users SET total_sessions = total_sessions + 1 WHERE id = ?',
            (user_id,)
        )
        
        conn.commit()
        return session_id
    finally:
        conn.close()

def update_session_activity(session_id):
    """Update last activity for session"""
    conn = get_user_db_connection()
    try:
        conn.execute(
            'UPDATE user_sessions SET last_activity = CURRENT_TIMESTAMP WHERE session_id = ?',
            (session_id,)
        )
        conn.commit()
    finally:
        conn.close()

def log_query_execution(user_id, session_id, query_text, success, error_message=None, results_count=0, ip_address=None):
    """Log a query execution"""
    conn = get_user_db_connection()
    try:
        conn.execute(
            '''INSERT INTO query_logs (user_id, session_id, query_text, success, error_message, results_count, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, session_id, query_text, success, error_message, results_count, ip_address)
        )
        conn.commit()
    finally:
        conn.close()

def require_login(f):
    """Decorator to require user login"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Update session activity
        if 'session_id' in session:
            update_session_activity(session['session_id'])
            
        return f(*args, **kwargs)
    return decorated_function

# Make version info available to all templates
@app.context_processor
def inject_version_info():
    context = get_version_info()
    context['time'] = time  # Make time module available to templates
    return context

def format_query_results(results, columns):
    """Format query results, converting cents back to dollars for money columns"""
    if not results:
        return results
    
    # Detect money columns by name - temporarily disabled to prevent formatting errors
    money_columns = []  # [col for col in columns if is_money_column(col)]
    
    formatted_results = []
    for row in results:
        formatted_row = {}
        for column, value in row.items():
            if column in money_columns and value is not None:
                try:
                    # Convert cents back to dollars for display
                    formatted_row[column] = format_cents_to_dollars(value)
                except Exception as e:
                    print(f"Error formatting money column '{column}' with value '{value}' (type: {type(value)}): {e}")
                    # If formatting fails, return the original value
                    formatted_row[column] = value
            else:
                formatted_row[column] = value
        formatted_results.append(formatted_row)
    
    return formatted_results

def execute_user_query(query):
    """Execute user-provided SQL query safely (read-only)"""
    conn = get_db_connection()
    try:
        # Clean query by removing comments and normalizing
        query_lines = []
        for line in query.split('\n'):
            # Remove SQL comments (-- style)
            if '--' in line:
                line = line[:line.index('--')]
            line = line.strip()
            if line:  # Only add non-empty lines
                query_lines.append(line)
        
        query_clean = ' '.join(query_lines).strip().upper()
        
        # Basic security: only allow SELECT queries
        if not query_clean.startswith('SELECT'):
            return {
                'success': False,
                'error': 'Only SELECT queries are allowed',
                'results': [],
                'columns': []
            }
        
        # Prevent certain dangerous operations even in SELECT
        dangerous_patterns = ['DELETE', 'DROP', 'ALTER', 'INSERT', 'UPDATE', 'CREATE', ';DELETE', ';DROP', ';ALTER', ';INSERT', ';UPDATE']
        for pattern in dangerous_patterns:
            if pattern in query_clean:
                return {
                    'success': False,
                    'error': f'Query contains prohibited operation: {pattern}',
                    'results': [],
                    'columns': []
                }
        
        cursor = conn.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # Convert Row objects to dictionaries for JSON serialization
        results_list = [dict(row) for row in results]
        
        # Format money columns for display
        formatted_results = format_query_results(results_list, columns)
        
        return {
            'success': True,
            'error': None,
            'results': formatted_results,
            'columns': columns
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'results': [],
            'columns': []
        }
    finally:
        conn.close()

def check_query_answer(user_query, expected_query):
    """Compare user query results with expected results"""
    user_result = execute_user_query(user_query)
    expected_result = execute_user_query(expected_query)
    
    if not user_result['success']:
        return {
            'correct': False,
            'message': f"Query error: {user_result['error']}"
        }
    
    if not expected_result['success']:
        return {
            'correct': False,
            'message': "System error with expected query"
        }
    
    # Compare results
    if user_result['results'] == expected_result['results']:
        return {
            'correct': True,
            'message': "Correct! Your query returned the expected results."
        }
    else:
        return {
            'correct': False,
            'message': f"Incorrect. Your query returned {len(user_result['results'])} rows, expected {len(expected_result['results'])} rows."
        }

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login/registration"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        
        if not username:
            return render_template('login.html', error='Username is required')
        
        # Get or create user
        user = get_or_create_user(username, email)
        
        # Create session
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        session_id = create_user_session(user['id'], ip_address, user_agent)
        
        # Set session variables
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['session_id'] = session_id
        session['login_time'] = time.time()
        
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@require_login
def index():
    return render_template('index.html')

@app.route('/explore')
@app.route('/practice')  # Keep old route for compatibility
@require_login
def data_explorer():
    """Data Explorer - execute any SELECT query"""
    return render_template('explore.html')

@app.route('/api/execute', methods=['POST'])
@require_login
def api_execute():
    """Execute SQL query and return results"""
    data = request.get_json()
    query = data.get('query', '')
    
    if not query.strip():
        return jsonify({
            'success': False,
            'error': 'Empty query',
            'results': [],
            'columns': []
        })
    
    # Execute query
    result = execute_user_query(query)
    
    # Log the query execution
    user_id = session.get('user_id')
    session_id = session.get('session_id')
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    
    log_query_execution(
        user_id=user_id,
        session_id=session_id,
        query_text=query,
        success=result['success'],
        error_message=result.get('error'),
        results_count=len(result.get('results', [])),
        ip_address=ip_address
    )
    
    return jsonify(result)

# Quiz endpoints removed - app now focuses on data exploration

@app.route('/schema')
@require_login
def schema_reference():
    """Schema reference page - opens in separate window"""
    return render_template('schema.html')

@app.route('/api/schema')
@require_login
def api_schema():
    """Get database schema information"""
    conn = get_db_connection()
    try:
        # Get table names
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        
        schema_info = {}
        for table in tables:
            table_name = table['name']
            # Get column information
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            schema_info[table_name] = [
                {
                    'name': col['name'],
                    'type': col['type'],
                    'notnull': bool(col['notnull']),
                    'pk': bool(col['pk'])
                }
                for col in columns
            ]
        
        return jsonify(schema_info)
    finally:
        conn.close()

@app.route('/api/tables')
@require_login
def api_tables():
    """Get list of table names in the database"""
    conn = get_db_connection()
    try:
        # Get table names
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        table_names = [table['name'] for table in tables]
        
        return jsonify(table_names)
    finally:
        conn.close()

@app.route('/api/sample-data/<table_name>')
@require_login
def api_sample_data(table_name):
    """Get sample data from a table"""
    conn = get_db_connection()
    try:
        # Get all table names to validate
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        valid_tables = [table['name'] for table in tables]
        
        # Validate table name to prevent SQL injection
        if table_name not in valid_tables:
            return jsonify({'error': 'Invalid table name'}), 400
        
        # Get sample rows - using parameterized query would be ideal but table names can't be parameterized
        # Since we've validated the table name exists, this is safe
        query = f"SELECT * FROM `{table_name}` LIMIT 5"
        rows = conn.execute(query).fetchall()
        
        # Convert to list of dictionaries
        data = [dict(row) for row in rows]
        
        return jsonify(data)
    finally:
        conn.close()

@app.route('/api/sample-queries')
@require_login
def api_sample_queries():
    """Generate smart sample queries based on current schema"""
    conn = get_db_connection()
    try:
        # Get table names and their schemas
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        table_names = [table['name'] for table in tables]
        
        if not table_names:
            return jsonify({
                'basic': '-- No tables available\n-- Upload some CSV files first!',
                'join': '-- No tables available\n-- Upload some CSV files first!',
                'aggregate': '-- No tables available\n-- Upload some CSV files first!'
            })
        
        schema_info = {}
        for table_name in table_names:
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            schema_info[table_name] = [
                {'name': col['name'], 'type': col['type'], 'pk': bool(col['pk'])}
                for col in columns
            ]
        
        # Generate sample queries
        queries = {}
        
        # Basic query
        first_table = table_names[0]
        queries['basic'] = f"-- Browse {first_table} data\nSELECT * FROM {first_table} LIMIT 10;"
        
        # JOIN query - try to find tables with potential relationships
        if len(table_names) >= 2:
            table1 = table_names[0]
            table2 = table_names[1]
            
            # Look for common column names that might be join keys
            t1_columns = [col['name'] for col in schema_info[table1]]
            t2_columns = [col['name'] for col in schema_info[table2]]
            
            print(f"Table {table1} columns: {t1_columns}")
            print(f"Table {table2} columns: {t2_columns}")
            
            # Find potential join columns - prioritize meaningful relationships over just common names
            join_column = None
            
            # First, look for ID-like columns that might have actual relationships
            id_candidates = []
            for col in t1_columns:
                if col in t2_columns:
                    clean_col = col.strip()
                    for char in ['•', '\x00', '\r', '\n', '\t', '\x0b', '\x0c', '\ufeff']:
                        clean_col = clean_col.replace(char, '')
                    
                    if not clean_col:
                        continue
                        
                    # Prioritize ID-like columns for joins
                    col_lower = clean_col.lower()
                    if any(pattern in col_lower for pattern in ['_id', 'id', 'invoice', 'patient', 'billing']):
                        id_candidates.append(clean_col)
                    
            # Test ID candidates first
            for candidate in id_candidates:
                try:
                    # Check if this join would actually return results
                    test_join = f"SELECT COUNT(*) FROM `{table1}` t1 JOIN `{table2}` t2 ON t1.`{candidate}` = t2.`{candidate}` LIMIT 1"
                    result = conn.execute(test_join).fetchone()
                    if result and result[0] > 0:
                        join_column = candidate
                        print(f"Found meaningful join column: {repr(candidate)} (would return {result[0]} rows)")
                        break
                except Exception as e:
                    print(f"Join test failed for {candidate}: {e}")
                    continue
            
            # If no meaningful ID joins found, fall back to any common column that returns results
            if not join_column:
                for col in t1_columns:
                    if col in t2_columns:
                        clean_col = col.strip()
                        for char in ['•', '\x00', '\r', '\n', '\t', '\x0b', '\x0c', '\ufeff']:
                            clean_col = clean_col.replace(char, '')
                        
                        if not clean_col:
                            continue
                            
                        try:
                            # Test if this join returns any results
                            test_join = f"SELECT COUNT(*) FROM `{table1}` t1 JOIN `{table2}` t2 ON t1.`{clean_col}` = t2.`{clean_col}` LIMIT 1"
                            result = conn.execute(test_join).fetchone()
                            if result and result[0] > 0:
                                join_column = clean_col
                                print(f"Found working join column: {repr(clean_col)} (would return {result[0]} rows)")
                                break
                        except Exception as e:
                            continue
            
            # If no exact match, look for ID patterns
            if not join_column:
                for col1 in t1_columns:
                    for col2 in t2_columns:
                        if ('id' in col1.lower() and 'id' in col2.lower()) or \
                           (col1.lower().endswith('_id') and col2.lower().endswith('_id')):
                            join_column = f"{col1} = {col2}"
                            break
                    if join_column:
                        break
            
            if join_column:
                if '=' in join_column:
                    queries['join'] = f"""-- JOIN example using related tables
SELECT *
FROM {table1} t1
JOIN {table2} t2 ON t1.{join_column.split(' = ')[0]} = t2.{join_column.split(' = ')[1]}
LIMIT 15;"""
                else:
                    queries['join'] = f"""-- JOIN example using common column
SELECT *
FROM {table1} t1
JOIN {table2} t2 ON t1.{join_column} = t2.{join_column}
LIMIT 15;"""
            else:
                # No common columns found - provide a generic example with first columns of each table
                t1_first = t1_columns[0].strip().replace('•', '').replace('\x00', '').replace('\r', '').replace('\n', '') if t1_columns else 'id'
                t2_first = t2_columns[0].strip().replace('•', '').replace('\x00', '').replace('\r', '').replace('\n', '') if t2_columns else 'id'
                queries['join'] = f"""-- Example JOIN query (adjust column names as needed)
-- No common columns detected, showing example with first columns
SELECT *
FROM {table1} t1
JOIN {table2} t2 ON t1.{t1_first} = t2.{t2_first}
LIMIT 15;"""
        else:
            queries['join'] = f"""-- JOIN example (need 2+ tables)
SELECT *
FROM {first_table} t1
JOIN another_table t2 ON t1.id = t2.id
LIMIT 15;"""
        
        # Aggregation query - find good grouping columns
        first_table = table_names[0]
        columns = schema_info[first_table]
        
        # Look for good grouping columns (text columns, not IDs)
        group_column = None
        count_column = None
        
        print(f"Columns in {first_table}: {[col['name'] for col in columns]}")
        
        # Look for columns with diverse values for meaningful grouping
        good_grouping_candidates = []
        
        for col in columns:
            clean_name = col['name'].strip()
            for char in ['•', '\x00', '\r', '\n', '\t', '\x0b', '\x0c', '\ufeff']:
                clean_name = clean_name.replace(char, '')
            
            if not clean_name:
                continue
                
            col_name = clean_name.lower()
            
            # Skip obvious ID and date columns for grouping
            if any(skip in col_name for skip in ['_id', 'date', 'time', 'number']):
                continue
                
            if col['type'] == 'TEXT':
                try:
                    # Test how many distinct values this column has
                    distinct_query = f"SELECT COUNT(DISTINCT `{clean_name}`) as distinct_count FROM `{first_table}`"
                    distinct_result = conn.execute(distinct_query).fetchone()
                    distinct_count = distinct_result[0] if distinct_result else 0
                    
                    # Good grouping columns have multiple but not too many distinct values
                    if 2 <= distinct_count <= 100:  # Sweet spot for meaningful grouping
                        good_grouping_candidates.append((clean_name, distinct_count))
                        print(f"Found potential group column: {repr(clean_name)} with {distinct_count} distinct values")
                        
                except Exception as e:
                    print(f"Could not test distinct values for {clean_name}: {e}")
                    continue
        
        # Sort by number of distinct values (prefer moderate diversity)
        good_grouping_candidates.sort(key=lambda x: x[1])
        
        # Pick the best candidate
        if good_grouping_candidates:
            group_column = good_grouping_candidates[0][0]
            print(f"Selected group column: {repr(group_column)} ({good_grouping_candidates[0][1]} distinct values)")
        else:
            print("No good grouping columns found, will use fallback")
        
        # Look for ID or countable columns
        for col in columns:
            clean_name = col['name'].strip()
            for char in ['•', '\x00', '\r', '\n', '\t', '\x0b', '\x0c', '\ufeff']:
                clean_name = clean_name.replace(char, '')
                
            if not clean_name:
                continue
                
            col_name = clean_name.lower()
            
            if col_name.endswith('_id') or col_name == 'id' or col['pk']:
                # Validate with multiple quote styles
                test_queries = [
                    f"SELECT `{clean_name}` FROM `{first_table}` LIMIT 1",
                    f"SELECT [{clean_name}] FROM `{first_table}` LIMIT 1",
                    f"SELECT \"{clean_name}\" FROM `{first_table}` LIMIT 1",
                    f"SELECT {clean_name} FROM `{first_table}` LIMIT 1"
                ]
                
                query_worked = False
                for test_query in test_queries:
                    try:
                        conn.execute(test_query).fetchone()
                        count_column = clean_name
                        print(f"Found valid count column: {repr(clean_name)} using query: {test_query}")
                        query_worked = True
                        break
                    except:
                        continue
                        
                if query_worked:
                    break
        
        if not group_column:
            # Use first available column as fallback
            if columns:
                group_column = columns[0]['name'].strip()
                for char in ['•', '\x00', '\r', '\n', '\t', '\x0b', '\x0c', '\ufeff']:
                    group_column = group_column.replace(char, '')
            else:
                group_column = 'column_name'
        if not count_column:
            if columns:
                count_column = columns[0]['name'].strip()
                for char in ['•', '\x00', '\r', '\n', '\t', '\x0b', '\x0c', '\ufeff']:
                    count_column = count_column.replace(char, '')
            else:
                count_column = 'id'
        
        queries['aggregate'] = f"""-- Aggregation example for {first_table}
SELECT 
    {group_column},
    COUNT(*) as record_count,
    COUNT(DISTINCT {count_column}) as unique_count
FROM {first_table}
GROUP BY {group_column}
ORDER BY record_count DESC;"""
        
        return jsonify(queries)
        
    finally:
        conn.close()

@app.route('/api/debug-columns')
@require_login  
def api_debug_columns():
    """Debug endpoint to see what columns are actually detected"""
    conn = get_db_connection()
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        debug_info = {}
        
        for table in tables:
            table_name = table['name']
            
            # Get column info from PRAGMA
            columns_pragma = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            
            # Try to get actual column names from a sample query
            try:
                sample_query = conn.execute(f"SELECT * FROM `{table_name}` LIMIT 1").fetchone()
                actual_columns = list(sample_query.keys()) if sample_query else []
            except Exception as e:
                actual_columns = f"Error: {str(e)}"
            
            debug_info[table_name] = {
                'pragma_columns': [
                    {
                        'name': repr(col['name']),  # Use repr to show hidden characters
                        'clean_name': col['name'].strip().replace('•', '').replace('\x00', ''),
                        'type': col['type']
                    }
                    for col in columns_pragma
                ],
                'actual_query_columns': actual_columns,
                'column_count': len(columns_pragma)
            }
        
        return jsonify(debug_info)
        
    finally:
        conn.close()

@app.route('/upload', methods=['GET', 'POST'])
@require_login
def data_upload():
    """Upload and import CSV data from ZIP files"""
    if request.method == 'POST':
        if 'zip_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['zip_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and file.filename.lower().endswith('.zip'):
            try:
                result = process_zip_upload(file)
                if result['success']:
                    if result.get('errors'):
                        flash(result['message'], 'warning')
                    else:
                        flash(f'Successfully imported {result["tables_created"]} tables from {result["files_processed"]} CSV files. Data Explorer updated with new schema.', 'success')
                    # Redirect to Data Explorer after successful upload
                    return redirect(url_for('data_explorer'))
                else:
                    flash(f'Upload failed: {result["error"]}', 'error')
            except Exception as e:
                flash(f'Upload failed: {str(e)}', 'error')
        else:
            flash('Please upload a ZIP file', 'error')
        
        return redirect(request.url)
    
    return render_template('upload.html')

def clear_healthcare_database(conn):
    """Clear all data from healthcare database, keeping only the structure"""
    print("Clearing existing healthcare database data...")
    
    # Get all table names from the healthcare database
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    
    for table in tables:
        table_name = table['name']
        try:
            # Drop the table completely
            conn.execute(f'DROP TABLE IF EXISTS `{table_name}`')
            print(f"Dropped table: {table_name}")
        except Exception as e:
            print(f"Error dropping table {table_name}: {e}")
    
    conn.commit()
    print("Healthcare database cleared successfully")

def process_zip_upload(zip_file):
    """Process uploaded ZIP file and create tables from CSV files"""
    conn = get_db_connection()
    try:
        # Clear existing data from healthcare database before importing new data
        clear_healthcare_database(conn)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            zip_path = os.path.join(temp_dir, secure_filename(zip_file.filename))
            zip_file.save(zip_path)
            
            # Extract ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find CSV files (exclude macOS metadata files)
            csv_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if (file.lower().endswith('.csv') and 
                        not file.startswith('._') and 
                        not file.startswith('.DS_Store')):
                        csv_files.append(os.path.join(root, file))
            
            if not csv_files:
                return {'success': False, 'error': 'No CSV files found in ZIP archive'}
            
            tables_created = 0
            files_processed = 0
            errors = []
            
            for csv_file_path in csv_files:
                files_processed += 1  # Count all files found
                try:
                    # Get table name from filename (without extension)
                    table_name = os.path.splitext(os.path.basename(csv_file_path))[0]
                    # Sanitize table name
                    table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name).lower()
                    
                    print(f"Processing CSV file: {os.path.basename(csv_file_path)} -> table: {table_name}")
                    
                    # Read CSV and create table
                    if create_table_from_csv(conn, csv_file_path, table_name):
                        tables_created += 1
                        print(f"Successfully created table: {table_name}")
                    else:
                        error_msg = f"Failed to create table from {os.path.basename(csv_file_path)}"
                        print(error_msg)
                        errors.append(error_msg)
                    
                except Exception as e:
                    error_msg = f"Error processing {os.path.basename(csv_file_path)}: {str(e)}"
                    print(f"Detailed error for {csv_file_path}: {repr(e)}")
                    print(f"Error type: {type(e).__name__}")
                    errors.append(error_msg)
            
            conn.commit()
            
            success_msg = f"Processed {files_processed} CSV files, successfully created {tables_created} tables"
            if errors:
                success_msg += f". Errors: {'; '.join(errors)}"
            
            return {
                'success': True,
                'tables_created': tables_created,
                'files_processed': files_processed,
                'errors': errors,
                'message': success_msg
            }
            
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def create_table_from_csv(conn, csv_file_path, table_name):
    """Create SQLite table from CSV file with 1:1 mapping - preserving original data"""
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            # Detect delimiter with fallback options
            sample = csvfile.read(1024)
            csvfile.seek(0)
            
            delimiter = ','  # Default to comma
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample, delimiters=',\t;|')
                delimiter = dialect.delimiter
                print(f"Detected delimiter for {os.path.basename(csv_file_path)}: {repr(delimiter)}")
            except Exception as e:
                print(f"Could not detect delimiter for {os.path.basename(csv_file_path)}: {e}")
                # Try common delimiters manually
                delimiters = [',', '\t', ';', '|']
                for test_delim in delimiters:
                    test_line = sample.split('\n')[0] if '\n' in sample else sample
                    if test_delim in test_line and test_line.count(test_delim) > 0:
                        delimiter = test_delim
                        print(f"Manually detected delimiter: {repr(delimiter)}")
                        break
                else:
                    print(f"Using default delimiter: {repr(delimiter)}")
                    print(f"Sample content: {repr(sample[:200])}")  # Show first 200 chars for debugging
            
            reader = csv.reader(csvfile, delimiter=delimiter)
            headers = next(reader)
            
            if not headers:
                print(f"No headers found in {csv_file_path}")
                return False
            
            print(f"Found {len(headers)} columns: {headers[:5]}...")  # Show first 5 headers
            
            # Keep original column names but quote them for SQL safety
            # Clean problematic characters including UTF-8 BOM
            sql_safe_headers = []
            for header in headers:
                # Clean problematic characters first, then replace spaces with underscores
                safe_header = header.strip()
                # Remove problematic characters including UTF-8 BOM
                for char in ['•', '\x00', '\r', '\n', '\t', '\x0b', '\x0c', '\ufeff']:
                    safe_header = safe_header.replace(char, '')
                # Replace spaces with underscores for SQL compatibility  
                safe_header = safe_header.replace(' ', '_')
                sql_safe_headers.append(safe_header)
                
                if header != safe_header:
                    print(f"Cleaned column name: '{repr(header)}' -> '{repr(safe_header)}'")
            
            # Peek at first few rows to determine column types
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            sample_rows = []
            for i, row in enumerate(reader):
                if i >= 10:  # Sample first 10 rows
                    break
                sample_rows.append(row)
            
            if not sample_rows:
                print(f"No data rows found in {csv_file_path}")
                return False
            
            # Determine column types (simplified - mostly TEXT to preserve data)
            column_types = {}
            for header, safe_header in zip(headers, sql_safe_headers):
                # For most columns, just use TEXT to preserve original data
                # Only use INTEGER for clearly numeric money columns
                if is_money_column(header):
                    column_types[safe_header] = 'INTEGER'  # Store as cents
                    print(f"Detected money column: {header} -> {safe_header}")
                else:
                    column_types[safe_header] = 'TEXT'  # Preserve everything else as text
            
            # Drop table if exists (for reimport)
            conn.execute(f'DROP TABLE IF EXISTS `{table_name}`')
            
            # Create table with quoted column names
            columns_sql = ', '.join([f'`{col}` {col_type}' for col, col_type in column_types.items()])
            create_sql = f'CREATE TABLE `{table_name}` ({columns_sql})'
            conn.execute(create_sql)
            
            # Insert data
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            placeholders = ', '.join(['?' for _ in sql_safe_headers])
            quoted_headers = ', '.join([f'`{h}`' for h in sql_safe_headers])
            insert_sql = f'INSERT INTO `{table_name}` ({quoted_headers}) VALUES ({placeholders})'
            
            rows_inserted = 0
            for row in reader:
                values = []
                for header, safe_header in zip(headers, sql_safe_headers):
                    value = row.get(header, '')  # Keep original value including empty strings
                    
                    # Only convert money columns to cents, keep everything else as-is
                    if is_money_column(header) and value and value.strip():
                        # Convert dollars to cents for money columns
                        cents_value = parse_money_to_cents(value)
                        if cents_value is not None:
                            values.append(cents_value)
                        else:
                            # If money parsing failed, store as 0 or NULL
                            print(f"Warning: Could not parse money value '{value}' in column '{header}', storing as NULL")
                            values.append(None)
                    else:
                        # Keep original value exactly as-is
                        values.append(value if value else None)
                
                conn.execute(insert_sql, values)
                rows_inserted += 1
        
        print(f"Created table '{table_name}' with {len(sql_safe_headers)} columns and {rows_inserted} rows")
        return True
        
    except Exception as e:
        print(f"Error creating table from {csv_file_path}: {str(e)}")
        return False

def determine_column_type(sample_rows, column_name):
    """Determine SQLite column type based on sample data"""
    values = [row.get(column_name, '').strip() for row in sample_rows if row.get(column_name, '').strip()]
    
    if not values:
        return 'TEXT'
    
    # Check if this is a money column first
    if is_money_column(column_name):
        # Money columns should be INTEGER (stored as cents)
        return 'INTEGER'
    
    # Check if all values are integers
    int_count = 0
    float_count = 0
    
    for value in values:
        if value.lower() in ['null', 'none', 'n/a', '']:
            continue
            
        # Remove $ and commas for numeric detection
        clean_value_for_test = value.replace('$', '').replace(',', '')
        
        try:
            float_val = float(clean_value_for_test)
            if float_val.is_integer():
                int_count += 1
            else:
                float_count += 1
        except (ValueError, TypeError):
            # Not numeric
            return 'TEXT'
    
    # If more than 80% are numeric
    total_numeric = int_count + float_count
    if total_numeric > 0 and total_numeric / len(values) > 0.8:
        # If all numeric values are integers, use INTEGER type
        if float_count == 0:
            return 'INTEGER'
        else:
            return 'REAL'
    
    return 'TEXT'

# Challenge system routes
@app.route('/challenges')
@require_login  
def challenges():
    """Challenge mode - data analysis problems for candidates"""
    return render_template('challenges.html')

@app.route('/api/challenges')
@require_login
def api_challenges():
    """Get all available challenges grouped by difficulty level"""
    conn = get_db_connection()
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
        
        return jsonify(levels)
    finally:
        conn.close()

@app.route('/api/challenge/<int:challenge_id>')
@require_login
def api_challenge_detail(challenge_id):
    """Get detailed information about a specific challenge"""
    conn = get_db_connection()
    try:
        challenge = conn.execute('''
            SELECT id, title, description, difficulty_level, category, hints, 
                   max_score, time_limit_minutes, expected_result_count
            FROM challenges 
            WHERE id = ? AND is_active = 1
        ''', (challenge_id,)).fetchone()
        
        if not challenge:
            return jsonify({'error': 'Challenge not found'}), 404
        
        challenge_data = dict(challenge)
        # Parse hints from JSON
        try:
            challenge_data['hints'] = json.loads(challenge_data['hints'])
        except:
            challenge_data['hints'] = []
            
        # Get user's progress on this challenge
        attempts = conn.execute('''
            SELECT id, query_text, is_correct, score, hints_used, execution_time_ms,
                   created_at
            FROM challenge_attempts 
            WHERE user_id = ? AND challenge_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        ''', (session.get('user_id'), challenge_id)).fetchall()
        
        challenge_data['recent_attempts'] = [dict(attempt) for attempt in attempts]
        
        return jsonify(challenge_data)
    finally:
        conn.close()

@app.route('/api/challenge/<int:challenge_id>/attempt', methods=['POST'])
@require_login
def api_challenge_attempt(challenge_id):
    """Submit an attempt for a challenge"""
    data = request.get_json()
    query = data.get('query', '').strip()
    hints_used = data.get('hints_used', 0)
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    conn = get_db_connection()
    try:
        # Get challenge details
        challenge = conn.execute('''
            SELECT id, title, expected_result_count, expected_query, max_score
            FROM challenges 
            WHERE id = ? AND is_active = 1
        ''', (challenge_id,)).fetchone()
        
        if not challenge:
            return jsonify({'error': 'Challenge not found'}), 404
        
        # Execute the query and measure performance
        start_time = time.time()
        try:
            # Execute the user's query against the database
            user_conn = get_db_connection()
            result = user_conn.execute(query).fetchall()
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Evaluate the result
            result_count = len(result)
            expected_count = challenge['expected_result_count'] or 0
            
            # Basic correctness check - more sophisticated evaluation could be added
            is_correct = False
            score = 0
            
            if expected_count > 0:
                # Check if result count is close to expected (within 10% tolerance)
                tolerance = max(1, int(expected_count * 0.1))
                if abs(result_count - expected_count) <= tolerance:
                    is_correct = True
                    
                    # Calculate score based on multiple factors
                    base_score = challenge['max_score'] or 100
                    
                    # Penalty for hints used (10 points per hint)
                    hint_penalty = hints_used * 10
                    
                    # Bonus for efficiency (faster queries get higher scores)
                    efficiency_bonus = max(0, 20 - (execution_time_ms // 100))
                    
                    score = max(0, base_score - hint_penalty + efficiency_bonus)
            
            # Record the attempt
            conn.execute('''
                INSERT INTO challenge_attempts 
                (user_id, challenge_id, query_text, result_count, is_correct, 
                 score, hints_used, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session.get('user_id'), challenge_id, query, result_count, 
                  is_correct, score, hints_used, execution_time_ms))
            
            # Update user progress
            conn.execute('''
                INSERT OR REPLACE INTO user_challenge_progress 
                (user_id, challenge_id, best_score, total_attempts, is_completed)
                VALUES (?, ?, 
                        COALESCE(MAX(best_score, ?), ?),
                        COALESCE((SELECT total_attempts FROM user_challenge_progress 
                                 WHERE user_id = ? AND challenge_id = ?), 0) + 1,
                        ?)
            ''', (session.get('user_id'), challenge_id, score, score, 
                  session.get('user_id'), challenge_id, is_correct))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'is_correct': is_correct,
                'score': score,
                'result_count': result_count,
                'expected_count': expected_count,
                'execution_time_ms': execution_time_ms,
                'hints_used': hints_used,
                'feedback': 'Correct! Well done!' if is_correct else 
                           f'Not quite right. Your query returned {result_count} rows, but we expected around {expected_count}.'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Query execution error: {str(e)}',
                'is_correct': False,
                'score': 0
            })
        finally:
            if 'user_conn' in locals():
                user_conn.close()
                
    finally:
        conn.close()

@app.route('/api/user/progress')
@require_login
def api_user_progress():
    """Get user's overall progress across all challenges"""
    conn = get_db_connection()
    try:
        progress = conn.execute('''
            SELECT c.difficulty_level, c.title, c.category, c.max_score,
                   p.best_score, p.total_attempts, p.is_completed
            FROM challenges c
            LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id 
                AND p.user_id = ?
            WHERE c.is_active = 1
            ORDER BY c.difficulty_level, c.id
        ''', (session.get('user_id'),)).fetchall()
        
        # Calculate overall statistics
        total_challenges = len(progress)
        completed_challenges = sum(1 for p in progress if p['is_completed'])
        total_score = sum(p['best_score'] or 0 for p in progress)
        max_possible_score = sum(p['max_score'] or 100 for p in progress)
        
        return jsonify({
            'challenges': [dict(p) for p in progress],
            'stats': {
                'total_challenges': total_challenges,
                'completed_challenges': completed_challenges,
                'completion_rate': round(completed_challenges / total_challenges * 100, 1) if total_challenges > 0 else 0,
                'total_score': total_score,
                'max_possible_score': max_possible_score,
                'score_percentage': round(total_score / max_possible_score * 100, 1) if max_possible_score > 0 else 0
            }
        })
    finally:
        conn.close()

# Admin interface routes
@app.route('/admin')
@require_login
def admin_dashboard():
    """Admin dashboard - view all candidate assessments"""
    return render_template('admin/dashboard.html')

@app.route('/admin/candidates')
@require_login
def admin_candidates():
    """View detailed candidate list"""
    return render_template('admin/candidates.html')

@app.route('/admin/candidate/<username>')
@require_login
def admin_candidate_detail(username):
    """View detailed candidate assessment"""
    return render_template('admin/candidate_detail.html', username=username)

@app.route('/api/admin/candidates')
@require_login
def api_admin_candidates():
    """Get all candidates and their assessment summary"""
    conn = get_user_db_connection()
    try:
        # Get all users who have made challenge attempts
        candidates = conn.execute('''
            SELECT DISTINCT u.username, u.created_at as registration_date,
                   COUNT(DISTINCT ca.challenge_id) as challenges_attempted,
                   COUNT(DISTINCT CASE WHEN ca.is_correct = 1 THEN ca.challenge_id END) as challenges_completed,
                   MAX(ca.score) as best_score,
                   SUM(ca.score) as total_score,
                   COUNT(ca.id) as total_attempts,
                   AVG(ca.execution_time_ms) as avg_execution_time,
                   SUM(ca.hints_used) as total_hints_used,
                   MAX(ca.created_at) as last_activity
            FROM users u
            LEFT JOIN challenge_attempts ca ON u.id = ca.user_id
            WHERE u.username != 'admin'
            GROUP BY u.id, u.username, u.created_at
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
        
        return jsonify(candidate_list)
    finally:
        conn.close()

@app.route('/api/admin/candidate/<username>/detail')
@require_login
def api_admin_candidate_detail(username):
    """Get detailed candidate assessment data"""
    conn = get_user_db_connection()
    try:
        # Get user ID
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            return jsonify({'error': 'Candidate not found'}), 404
        
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
        
        # Calculate overall statistics
        total_challenges = len([p for p in challenge_progress if p['attempts'] > 0])
        completed_challenges = len([p for p in challenge_progress if p['completed']])
        total_score = sum(p['best_score'] or 0 for p in challenge_progress)
        max_possible_score = sum(p['max_score'] for p in challenge_progress)
        
        return jsonify({
            'username': username,
            'challenge_progress': [dict(p) for p in challenge_progress],
            'attempt_history': [dict(a) for a in attempt_history],
            'summary': {
                'total_challenges_attempted': total_challenges,
                'completed_challenges': completed_challenges,
                'completion_rate': round(completed_challenges / total_challenges * 100, 1) if total_challenges > 0 else 0,
                'total_score': total_score,
                'max_possible_score': max_possible_score,
                'score_percentage': round(total_score / max_possible_score * 100, 1) if max_possible_score > 0 else 0,
                'total_attempts': len(attempt_history),
                'avg_execution_time': round(sum(a['execution_time_ms'] for a in attempt_history) / len(attempt_history), 1) if attempt_history else 0,
                'total_hints_used': sum(a['hints_used'] for a in attempt_history)
            }
        })
    finally:
        conn.close()

@app.route('/api/admin/analytics')
@require_login
def api_admin_analytics():
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
        
        return jsonify({
            'overall': dict(overall_stats),
            'difficulty_breakdown': [dict(stat) for stat in difficulty_stats],
            'challenge_difficulty_ranking': [dict(stat) for stat in challenge_stats]
        })
    finally:
        conn.close()

@app.route('/api/admin/export/candidate/<username>')
@require_login
def api_admin_export_candidate(username):
    """Export candidate assessment report"""
    conn = get_user_db_connection()
    try:
        # Get detailed data (reuse existing endpoint logic)
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if not user:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Generate assessment report
        report = {
            'candidate': username,
            'assessment_date': datetime.now().isoformat(),
            'challenges': [],
            'summary': {}
        }
        
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
        
        return jsonify(report)
    finally:
        conn.close()

@app.route('/health')
def health():
    """Standardized health check endpoint."""
    import time
    
    start_time = getattr(app, 'start_time', time.time())
    if not hasattr(app, 'start_time'):
        app.start_time = start_time
    
    version_info = get_version_info()
    health_status = {
        'status': 'healthy',
        'service': 'sqlquiz',
        'version': version_info['version'],
        'commit': version_info['git_commit'],
        'build_date': version_info['build_date'],
        'uptime': int(time.time() - start_time),
        'environment': version_info['environment'],
        'checks': {}
    }
    
    # Check database connectivity (database-agnostic)
    try:
        conn = get_db_connection()
        # Just check that we can connect and query sqlite_master (always exists)
        cursor = conn.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="table"')
        table_count = cursor.fetchone()[0]
        conn.close()
        health_status['checks']['database'] = 'healthy'
        health_status['checks']['table_count'] = table_count
    except Exception as e:
        # Still mark as healthy since database issues shouldn't fail health checks
        health_status['checks']['database'] = f'database issue: {str(e)}'
        # Don't set status to unhealthy - keep app running regardless
    
    # Optional check for quiz questions file (not required for Data Explorer)
    try:
        with open('quiz_questions.json', 'r') as f:
            import json
            questions = json.load(f)
            health_status['checks']['quiz_questions'] = f'available: {len(questions)} questions loaded'
    except Exception as e:
        health_status['checks']['quiz_questions'] = f'not available: {str(e)}'
        # Don't mark as unhealthy - quiz mode is optional
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)