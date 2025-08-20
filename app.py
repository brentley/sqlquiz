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

# Get version info from environment variables
def get_version_info():
    return {
        'git_commit': os.getenv('GIT_COMMIT', 'unknown')[:7],
        'build_date': os.getenv('BUILD_DATE', 'unknown'),
        'version': os.getenv('VERSION', '1.0.0'),
        'environment': os.getenv('FLASK_ENV', 'development')
    }

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')

DATABASE = '/app/data/healthcare_quiz.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database and create all necessary tables"""
    import os
    
    # Ensure the database file exists by creating a minimal database first
    if not os.path.exists(DATABASE):
        print(f"Creating initial database: {DATABASE}")
        conn = sqlite3.connect(DATABASE)
        conn.execute('CREATE TABLE IF NOT EXISTS _init (id INTEGER)')
        conn.commit()
        conn.close()
    
    # Now initialize user tracking tables
    conn = get_db_connection()
    try:
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
        
        conn.commit()
        print(f"Database initialized successfully: {DATABASE}")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

# Initialize database on startup
init_database()

def get_or_create_user(username, email=None):
    """Get existing user or create new one"""
    conn = get_db_connection()
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
    
    conn = get_db_connection()
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
    conn = get_db_connection()
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
    conn = get_db_connection()
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
        
        return {
            'success': True,
            'error': None,
            'results': results_list,
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
                    flash(f'Successfully imported {result["tables_created"]} tables from {result["files_processed"]} CSV files', 'success')
                else:
                    flash(f'Upload failed: {result["error"]}', 'error')
            except Exception as e:
                flash(f'Upload failed: {str(e)}', 'error')
        else:
            flash('Please upload a ZIP file', 'error')
        
        return redirect(request.url)
    
    return render_template('upload.html')

def process_zip_upload(zip_file):
    """Process uploaded ZIP file and create tables from CSV files"""
    conn = get_db_connection()
    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            zip_path = os.path.join(temp_dir, secure_filename(zip_file.filename))
            zip_file.save(zip_path)
            
            # Extract ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find CSV files
            csv_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith('.csv'):
                        csv_files.append(os.path.join(root, file))
            
            if not csv_files:
                return {'success': False, 'error': 'No CSV files found in ZIP archive'}
            
            tables_created = 0
            files_processed = 0
            
            for csv_file_path in csv_files:
                try:
                    # Get table name from filename (without extension)
                    table_name = os.path.splitext(os.path.basename(csv_file_path))[0]
                    # Sanitize table name
                    table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name).lower()
                    
                    # Read CSV and create table
                    if create_table_from_csv(conn, csv_file_path, table_name):
                        tables_created += 1
                    files_processed += 1
                    
                except Exception as e:
                    print(f"Error processing {csv_file_path}: {e}")
                    continue
            
            conn.commit()
            return {
                'success': True,
                'tables_created': tables_created,
                'files_processed': files_processed
            }
            
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def create_table_from_csv(conn, csv_file_path, table_name):
    """Create SQLite table from CSV file with 1:1 mapping"""
    with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
        # Detect delimiter
        sample = csvfile.read(1024)
        csvfile.seek(0)
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample).delimiter
        
        reader = csv.reader(csvfile, delimiter=delimiter)
        headers = next(reader)
        
        # Sanitize column names
        sanitized_headers = []
        for header in headers:
            sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', header.strip()).lower()
            if not sanitized or sanitized[0].isdigit():
                sanitized = f'col_{sanitized}'
            sanitized_headers.append(sanitized)
        
        # Peek at first few rows to determine column types
        csvfile.seek(0)
        reader = csv.DictReader(csvfile, delimiter=delimiter)
        sample_rows = []
        for i, row in enumerate(reader):
            if i >= 10:  # Sample first 10 rows
                break
            sample_rows.append(row)
        
        # Determine column types
        column_types = {}
        for header, sanitized in zip(headers, sanitized_headers):
            column_types[sanitized] = determine_column_type(sample_rows, header)
        
        # Drop table if exists (for reimport)
        conn.execute(f'DROP TABLE IF EXISTS {table_name}')
        
        # Create table
        columns_sql = ', '.join([f'{col} {col_type}' for col, col_type in column_types.items()])
        create_sql = f'CREATE TABLE {table_name} ({columns_sql})'
        conn.execute(create_sql)
        
        # Insert data
        csvfile.seek(0)
        reader = csv.DictReader(csvfile, delimiter=delimiter)
        
        placeholders = ', '.join(['?' for _ in sanitized_headers])
        insert_sql = f'INSERT INTO {table_name} ({", ".join(sanitized_headers)}) VALUES ({placeholders})'
        
        rows_inserted = 0
        for row in reader:
            values = []
            for header, sanitized in zip(headers, sanitized_headers):
                value = row.get(header, '').strip()
                if value == '' or value.lower() in ['null', 'none', 'n/a']:
                    values.append(None)
                else:
                    # Convert value based on determined type
                    col_type = column_types[sanitized]
                    if col_type == 'INTEGER':
                        try:
                            values.append(int(float(value)))  # Handle integers stored as floats
                        except (ValueError, TypeError):
                            values.append(None)
                    elif col_type == 'REAL':
                        try:
                            values.append(float(value))
                        except (ValueError, TypeError):
                            values.append(None)
                    else:  # TEXT
                        values.append(value)
            
            conn.execute(insert_sql, values)
            rows_inserted += 1
        
        print(f"Created table '{table_name}' with {len(sanitized_headers)} columns and {rows_inserted} rows")
        return True

def determine_column_type(sample_rows, column_name):
    """Determine SQLite column type based on sample data"""
    values = [row.get(column_name, '').strip() for row in sample_rows if row.get(column_name, '').strip()]
    
    if not values:
        return 'TEXT'
    
    # Check if all values are integers
    int_count = 0
    float_count = 0
    
    for value in values:
        if value.lower() in ['null', 'none', 'n/a', '']:
            continue
            
        try:
            float_val = float(value)
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