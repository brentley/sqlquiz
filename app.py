from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import json
import hashlib
from datetime import datetime
import os
import re
import time

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

DATABASE = 'healthcare_quiz.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_user_tables():
    """Initialize user tracking tables"""
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
    finally:
        conn.close()

# Initialize user tables on startup
init_user_tables()

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
    # Validate table name to prevent SQL injection
    valid_tables = ['patients', 'insurance_plans', 'service_lines', 'invoices', 'invoice_details']
    if table_name not in valid_tables:
        return jsonify({'error': 'Invalid table name'}), 400
    
    conn = get_db_connection()
    try:
        # Get sample rows
        query = f"SELECT * FROM {table_name} LIMIT 5"
        rows = conn.execute(query).fetchall()
        
        # Convert to list of dictionaries
        data = [dict(row) for row in rows]
        
        return jsonify(data)
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