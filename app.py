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

DATABASE = '/app/data/healthcare_quiz.db'
USER_DATABASE = '/app/data/user_data.db'

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
    os.makedirs(os.path.dirname(USER_DATABASE), exist_ok=True)
    
    conn = get_user_db_connection()
    try:
        create_user_tables(conn)
        conn.commit()
        print(f"User database initialized successfully: {USER_DATABASE}")
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
    money_indicators = [
        'charge', 'payment', 'balance', 'amount', 'amt', 'cost', 'price', 
        'total', 'revenue', 'reimbursement', 'adjustment', 'debt', 'paid'
    ]
    
    column_lower = column_name.lower()
    return any(indicator in column_lower for indicator in money_indicators)

def format_cents_to_dollars(cents):
    """Convert cents (integer) back to dollar format for display"""
    if cents is None:
        return None
    return cents / 100.0

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
    
    # Detect money columns by name
    money_columns = [col for col in columns if is_money_column(col)]
    
    formatted_results = []
    for row in results:
        formatted_row = {}
        for column, value in row.items():
            if column in money_columns and value is not None:
                # Convert cents back to dollars for display
                formatted_row[column] = format_cents_to_dollars(value)
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
            
            # Find potential join columns (common names or ID-like columns)
            join_column = None
            for col in t1_columns:
                if col in t2_columns:
                    join_column = col
                    break
            
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
                queries['join'] = f"""-- Example JOIN query (adjust column names as needed)
SELECT *
FROM {table1} t1
JOIN {table2} t2 ON t1.column_name = t2.column_name
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
        
        for col in columns:
            col_name = col['name'].lower()
            if col['type'] == 'TEXT' and not col_name.endswith('_id') and not col_name == 'id':
                group_column = col['name']
                break
        
        # Look for ID or countable columns
        for col in columns:
            col_name = col['name'].lower()
            if col_name.endswith('_id') or col_name == 'id' or col['pk']:
                count_column = col['name']
                break
        
        if not group_column:
            group_column = columns[0]['name'] if columns else 'column_name'
        if not count_column:
            count_column = columns[0]['name'] if columns else 'id'
        
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
            # Only minimal sanitization - replace spaces with underscores for SQL compatibility
            sql_safe_headers = []
            for header in headers:
                # Only replace spaces with underscores, keep everything else
                safe_header = header.strip().replace(' ', '_')
                sql_safe_headers.append(safe_header)
            
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
                        values.append(cents_value)
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
    
    # Check database connectivity
    try:
        conn = get_db_connection()
        cursor = conn.execute('SELECT COUNT(*) FROM patients LIMIT 1')
        patient_count = cursor.fetchone()[0]
        conn.close()
        health_status['checks']['database'] = 'healthy'
        health_status['checks']['patient_count'] = patient_count
    except Exception as e:
        health_status['checks']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check if quiz questions file exists
    try:
        with open('quiz_questions.json', 'r') as f:
            import json
            questions = json.load(f)
            health_status['checks']['quiz_questions'] = f'healthy: {len(questions)} questions loaded'
    except Exception as e:
        health_status['checks']['quiz_questions'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)