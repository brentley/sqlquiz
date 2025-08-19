from flask import Flask, render_template, request, jsonify, session
import sqlite3
import json
import hashlib
from datetime import datetime
import os
import re

# Get version info from environment variables
def get_version_info():
    return {
        'git_commit': os.getenv('GIT_COMMIT', 'unknown')[:7],
        'build_date': os.getenv('BUILD_DATE', 'unknown'),
        'version': os.getenv('VERSION', '1.0.0'),
        'environment': os.getenv('FLASK_ENV', 'development')
    }

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

DATABASE = 'healthcare_quiz.db'

# Make version info available to all templates
@app.context_processor
def inject_version_info():
    return get_version_info()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/explore')
@app.route('/practice')  # Keep old route for compatibility
def data_explorer():
    """Data Explorer - execute any SELECT query"""
    return render_template('explore.html')

@app.route('/api/execute', methods=['POST'])
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
    
    result = execute_user_query(query)
    return jsonify(result)

# Quiz endpoints removed - app now focuses on data exploration

@app.route('/schema')
def schema_reference():
    """Schema reference page - opens in separate window"""
    return render_template('schema.html')

@app.route('/api/schema')
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
    app.run(debug=True, host='0.0.0.0', port=5000)