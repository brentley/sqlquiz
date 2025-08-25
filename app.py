"""
Data Explorer - Main Flask Application
A comprehensive SQL skills assessment and training platform.

This is the refactored modular version of the application.
"""

import os
import time
import json
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash

# Import our modular components
from models.database import init_database, get_version_info, health_check
from models.users import (
    authenticate_user, create_session, get_user_by_session, 
    get_user_by_username, invalidate_session, log_query,
    get_all_candidates, get_candidate_detail, get_system_analytics, export_candidate_report
)
from models.challenges import (
    get_all_challenges, get_challenge_by_id, record_challenge_attempt, get_user_progress
)
from utils.data_processing import (
    process_csv_upload, get_database_schema, get_table_names, 
    get_sample_data, generate_sample_queries, delete_table,
    rename_table, modify_column_type, get_table_info
)
from utils.query_validation import execute_safe_query
from models.admin_auth import (
    init_oauth, require_admin, is_admin_email, create_admin_user, 
    create_admin_session, invalidate_admin_session, log_admin_action
)


# Flask app initialization
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')

# Initialize OAuth
oauth, oauth_client = init_oauth(app)

# Track app start time for health checks
app.start_time = time.time()


# Authentication decorator
def require_login(f):
    """Decorator to require user login"""
    def decorated_function(*args, **kwargs):
        # Check for basic session info (fallback when user database unavailable)
        if 'username' not in session:
            return redirect(url_for('login'))
        
        # Try to validate session if we have a session token
        if 'session_token' in session:
            user = get_user_by_session(session['session_token'])
            if user:
                # Store user info in session for easy access
                session['user_id'] = user['id']
                session['username'] = user['username']
            # If user database is unavailable, continue with basic session info
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# Template context processors
@app.context_processor
def inject_version():
    """Inject version info into templates"""
    version_info = get_version_info()
    return {
        'git_commit': version_info['git_commit'],
        'version': version_info['version'],
        'time': time  # For calculating session duration
    }


# Main routes
@app.route('/')
@require_login
def index():
    """Home page"""
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        
        if not username:
            flash('Username is required', 'error')
            return render_template('login.html')
        
        # Authenticate user (create if doesn't exist)
        user_id = authenticate_user(username)
        if user_id:
            # Create session
            session_token = create_session(
                user_id, 
                request.remote_addr, 
                request.headers.get('User-Agent', '')
            )
            
            if session_token:
                # Store in session
                session['session_token'] = session_token
                session['user_id'] = user_id
                session['username'] = username
                session['login_time'] = time.time()
                
                return redirect(url_for('index'))
            else:
                # Session creation failed, but allow basic access
                session['user_id'] = user_id
                session['username'] = username
                session['login_time'] = time.time()
                flash('Login successful (limited functionality - user database unavailable)', 'warning')
                return redirect(url_for('index'))
        else:
            flash('Authentication failed', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session"""
    if 'session_token' in session:
        invalidate_session(session['session_token'])
    session.clear()
    return redirect(url_for('login'))


@app.route('/explore')
@require_login
def data_explorer():
    """Data explorer interface"""
    return render_template('explore.html')


@app.route('/upload', methods=['GET', 'POST'])
@require_admin
def data_upload():
    """Data upload interface and processing"""
    if request.method == 'POST':
        # Handle file upload
        if 'zip_file' not in request.files:
            flash('No file uploaded', 'error')
            return render_template('upload.html')
        
        file = request.files['zip_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return render_template('upload.html')
        
        # Check if clear existing data was requested
        clear_existing = 'clear_existing' in request.form
        
        # Log admin action
        admin_user = session.get('admin_user', {})
        log_admin_action(admin_user.get('id'), 'data_upload', f'Uploaded file: {file.filename}, Clear existing: {clear_existing}')
        
        # Process the upload
        result = process_csv_upload(file, clear_existing)
        
        if result['success']:
            if isinstance(result, dict) and 'results' in result:
                # Multiple files processed
                flash(result['message'], 'success')
                for file_result in result['results']:
                    if file_result['success']:
                        flash(f"✓ {file_result.get('filename', 'File')}: {file_result.get('rows_imported', 0)} rows imported", 'success')
                    else:
                        flash(f"✗ {file_result.get('filename', 'File')}: {file_result.get('error', 'Unknown error')}", 'error')
            else:
                # Single file processed
                flash(f"File uploaded successfully! {result.get('rows_imported', 0)} rows imported into {result.get('table_name', 'table')}", 'success')
            
            # Redirect to index page to see the data
            return redirect(url_for('index'))
        else:
            flash(f"Upload failed: {result.get('error', 'Unknown error')}", 'error')
    
    return render_template('upload.html')


@app.route('/challenges')
@require_login  
def challenges():
    """Challenge mode interface"""
    return render_template('challenges.html')


# Admin authentication routes
@app.route('/admin/login')
def admin_login():
    """Admin login page"""
    return render_template('admin/login.html')


@app.route('/admin/simple-login', methods=['POST'])
def admin_simple_login():
    """Simple email-based admin login (temporary)"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400
    
    # Check if email is in the allowed list
    allowed_admins = ['brent.langston@visiquate.com', 'peyton.meroney@visiquate.com']
    if email not in allowed_admins:
        log_admin_action(None, 'unauthorized_simple_login_attempt', f'Email: {email}')
        return jsonify({'success': False, 'error': 'Access denied. You are not authorized as an admin.'}), 403
    
    try:
        # Extract name from email
        name = email.split('@')[0].replace('.', ' ').title()
        
        # Create or get admin user
        user_id = create_admin_user(email, name)
        if not user_id:
            return jsonify({'success': False, 'error': 'Failed to create admin user session'}), 500
        
        # Create admin session
        session_token = create_admin_session(user_id, email, name)
        if not session_token:
            return jsonify({'success': False, 'error': 'Failed to create admin session'}), 500
        
        # Store in session
        session['admin_session_token'] = session_token
        session['admin_user'] = {
            'id': user_id,
            'email': email,
            'name': name
        }
        
        # Log successful login
        log_admin_action(user_id, 'admin_simple_login', f'Simple login successful for {email}')
        
        return jsonify({
            'success': True, 
            'message': 'Admin login successful',
            'redirect': url_for('admin_dashboard')
        })
        
    except Exception as e:
        print(f"Simple login error: {e}")
        return jsonify({'success': False, 'error': 'Authentication failed. Please try again.'}), 500


@app.route('/admin/auth')
def admin_auth():
    """Initiate OAuth authentication for admin"""
    if not oauth_client:
        flash('OAuth not configured. Please contact administrator.', 'error')
        return redirect(url_for('admin_login'))
    
    redirect_uri = url_for('admin_auth_callback', _external=True)
    return oauth_client.authorize_redirect(redirect_uri)


@app.route('/admin/auth/callback')
def admin_auth_callback():
    """Handle OAuth callback for admin authentication"""
    if not oauth_client:
        flash('OAuth not configured. Please contact administrator.', 'error')
        return redirect(url_for('admin_login'))
    
    try:
        # Get token from OAuth provider
        token = oauth_client.authorize_access_token()
        
        # Get user info from OAuth provider
        user_info = oauth_client.parse_id_token(token)
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0] if email else 'Unknown')
        
        if not email:
            flash('Email not provided by OAuth provider', 'error')
            return redirect(url_for('admin_login'))
        
        # Check if email is in admin whitelist
        if not is_admin_email(email):
            flash('Access denied. You are not authorized as an admin.', 'error')
            log_admin_action(None, 'unauthorized_login_attempt', f'Email: {email}')
            return redirect(url_for('admin_login'))
        
        # Create or get admin user
        user_id = create_admin_user(email, name)
        if not user_id:
            flash('Failed to create admin user session', 'error')
            return redirect(url_for('admin_login'))
        
        # Create admin session
        session_token = create_admin_session(user_id, email, name)
        if not session_token:
            flash('Failed to create admin session', 'error')
            return redirect(url_for('admin_login'))
        
        # Store in session
        session['admin_session_token'] = session_token
        session['admin_user'] = {
            'id': user_id,
            'email': email,
            'name': name
        }
        
        # Log successful login
        log_admin_action(user_id, 'admin_login', f'OAuth login successful for {email}')
        
        flash('Admin login successful', 'success')
        
        # Redirect to intended page or admin dashboard
        next_url = session.pop('admin_next', None)
        return redirect(next_url or url_for('admin_dashboard'))
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('admin_login'))


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    if 'admin_session_token' in session:
        # Log logout action
        admin_user = session.get('admin_user', {})
        log_admin_action(admin_user.get('id'), 'admin_logout', 'Admin logged out')
        
        # Invalidate session
        invalidate_admin_session(session['admin_session_token'])
        
        # Clear session
        session.pop('admin_session_token', None)
        session.pop('admin_user', None)
    
    flash('Admin logout successful', 'success')
    return redirect(url_for('admin_login'))


# Admin routes (now protected)
@app.route('/admin')
@require_admin
def admin_dashboard():
    """Admin dashboard"""
    return render_template('admin/dashboard.html')


@app.route('/admin/candidates')
@require_admin
def admin_candidates():
    """Candidate management"""
    return render_template('admin/candidates.html')


@app.route('/admin/candidate/<username>')
@require_admin
def admin_candidate_detail(username):
    """Detailed candidate view"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'view_candidate_detail', f'Viewed details for candidate: {username}')
    return render_template('admin/candidate_detail.html', username=username)


@app.route('/admin/tables')
@require_admin
def admin_tables():
    """Table management interface"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'view_table_management', 'Accessed table management interface')
    return render_template('admin/tables.html')


# Schema reference page
@app.route('/schema')
@require_login
def schema():
    """Schema reference page"""
    return render_template('schema.html')


# API Routes - Data Management
@app.route('/api/schema')
@require_login
def api_schema():
    """Get database schema"""
    return jsonify(get_database_schema())


@app.route('/api/tables')
@require_login
def api_tables():
    """Get list of tables"""
    return jsonify(get_table_names())


@app.route('/api/execute', methods=['POST'])
@require_login
def api_execute():
    """Execute SQL query with pagination support"""
    data = request.get_json()
    query = data.get('query', '').strip()
    page = data.get('page', 1)
    rows_per_page = data.get('rows_per_page', 1000)
    
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'})
    
    # Execute query safely with pagination
    success, result_data, error_message, execution_time_ms, total_count, page_count = execute_safe_query(
        query, page=page, rows_per_page=rows_per_page
    )
    
    # Log the query (log the original query, not paginated version)
    log_query(
        session.get('user_id'),
        session.get('session_token'),
        query,
        execution_time_ms,
        page_count,  # Log the count of rows returned for this page
        success,
        error_message
    )
    
    if success:
        return jsonify({
            'success': True,
            'results': result_data['results'],
            'columns': result_data['columns'],
            'total_count': result_data['total_count'],
            'page': result_data['page'],
            'rows_per_page': result_data['rows_per_page'],
            'execution_time_ms': execution_time_ms,
            'page_count': page_count
        })
    else:
        return jsonify({
            'success': False,
            'error': error_message,
            'execution_time_ms': execution_time_ms
        })


@app.route('/api/sample-queries')
@require_login
def api_sample_queries():
    """Get intelligent sample queries"""
    return jsonify(generate_sample_queries())


@app.route('/api/sample-data/<table_name>')
@require_login
def api_sample_data(table_name):
    """Get sample data from a table"""
    return jsonify(get_sample_data(table_name))


@app.route('/api/upload', methods=['POST'])
@require_admin
def api_upload():
    """Upload CSV/ZIP files"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    clear_existing = request.form.get('clear_existing') == 'true'
    
    # Log admin action
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'api_data_upload', f'API upload: {file.filename}, Clear existing: {clear_existing}')
    
    result = process_csv_upload(file, clear_existing)
    
    return jsonify(result)


# API Routes - Challenge System
@app.route('/api/challenges')
@require_login
def api_challenges():
    """Get all challenges"""
    return jsonify(get_all_challenges())


@app.route('/api/challenge/<int:challenge_id>')
@require_login
def api_challenge_detail(challenge_id):
    """Get challenge details"""
    challenge = get_challenge_by_id(challenge_id, session.get('user_id'))
    if challenge:
        return jsonify(challenge)
    else:
        return jsonify({'error': 'Challenge not found'}), 404


@app.route('/api/challenge/<int:challenge_id>/attempt', methods=['POST'])
@require_login
def api_challenge_attempt(challenge_id):
    """Submit challenge attempt"""
    data = request.get_json()
    query = data.get('query', '').strip()
    hints_used = data.get('hints_used', 0)
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Get challenge details
    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        return jsonify({'error': 'Challenge not found'}), 404
    
    # Execute query and measure performance (for challenges, use old interface)
    start_time = time.time()
    success, result_data, error_message, execution_time_ms, total_count, result_count = execute_safe_query(query)
    
    if success:
        expected_count = challenge.get('expected_result_count', 0)
        
        # Basic correctness check
        is_correct = False
        score = 0
        
        if expected_count and expected_count > 0:
            # Check if result count is close to expected (within 10% tolerance)
            tolerance = max(1, int(expected_count * 0.1))
            if abs(total_count - expected_count) <= tolerance:
                is_correct = True
                
                # Calculate score
                base_score = challenge.get('max_score', 100)
                hint_penalty = hints_used * 10
                efficiency_bonus = max(0, 20 - (execution_time_ms // 100))
                score = max(0, base_score - hint_penalty + efficiency_bonus)
        
        # Record the attempt
        record_challenge_attempt(
            session.get('user_id'), challenge_id, query, total_count,
            is_correct, score, hints_used, execution_time_ms
        )
        
        return jsonify({
            'success': True,
            'is_correct': is_correct,
            'score': score,
            'result_count': total_count,
            'expected_count': expected_count,
            'execution_time_ms': execution_time_ms,
            'hints_used': hints_used,
            'feedback': 'Correct! Well done!' if is_correct else 
                       f'Not quite right. Your query returned {total_count} rows, but we expected around {expected_count}.'
        })
    else:
        # Record failed attempt
        record_challenge_attempt(
            session.get('user_id'), challenge_id, query, 0,
            False, 0, hints_used, execution_time_ms, error_message
        )
        
        return jsonify({
            'success': False,
            'error': f'Query execution error: {error_message}',
            'is_correct': False,
            'score': 0
        })


@app.route('/api/user/progress')
@require_login
def api_user_progress():
    """Get user progress"""
    return jsonify(get_user_progress(session.get('user_id')))


# API Routes - Admin Interface (now protected)
@app.route('/api/admin/candidates')
@require_admin
def api_admin_candidates():
    """Get all candidates"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'view_candidates_list', 'Accessed candidates list')
    return jsonify(get_all_candidates())


@app.route('/api/admin/candidate/<username>/detail')
@require_admin
def api_admin_candidate_detail(username):
    """Get detailed candidate data"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'view_candidate_data', f'Accessed data for candidate: {username}')
    
    candidate_data = get_candidate_detail(username)
    if candidate_data:
        return jsonify(candidate_data)
    else:
        return jsonify({'error': 'Candidate not found'}), 404


@app.route('/api/admin/analytics')
@require_admin
def api_admin_analytics():
    """Get system analytics"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'view_analytics', 'Accessed system analytics')
    return jsonify(get_system_analytics())


@app.route('/api/admin/export/candidate/<username>')
@require_admin
def api_admin_export_candidate(username):
    """Export candidate report"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'export_candidate_report', f'Exported report for candidate: {username}')
    
    report = export_candidate_report(username)
    if report:
        return jsonify(report)
    else:
        return jsonify({'error': 'Candidate not found'}), 404


# Health check endpoint
@app.route('/health')
def health():
    """Health check endpoint"""
    version_info = get_version_info()
    health_status = health_check()
    
    # Add version and uptime info
    health_status.update({
        'service': 'data-explorer',
        'version': version_info['version'],
        'commit': version_info['git_commit'],
        'build_date': version_info['build_date'],
        'uptime': int(time.time() - app.start_time),
        'environment': version_info['environment']
    })
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code


# Table Management API Routes (Admin Only)
@app.route('/api/admin/tables', methods=['GET'])
@require_admin
def api_admin_tables():
    """Get list of all tables with metadata"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'view_tables_list', 'Accessed tables list')
    
    try:
        table_names = get_table_names()
        tables_info = []
        
        for table_name in table_names:
            info = get_table_info(table_name)
            if info['success']:
                tables_info.append({
                    'name': table_name,
                    'columns': len(info['columns']),
                    'row_count': info['row_count'],
                    'is_system': table_name in ['users', 'user_sessions', 'query_logs', 'user_challenge_progress', 'challenges']
                })
        
        return jsonify({
            'success': True,
            'tables': tables_info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/table/<table_name>/info', methods=['GET'])
@require_admin
def api_admin_table_info(table_name):
    """Get detailed table information"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'view_table_info', f'Viewed info for table: {table_name}')
    
    result = get_table_info(table_name)
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 404


@app.route('/api/admin/table/<table_name>/delete', methods=['DELETE'])
@require_admin
def api_admin_delete_table(table_name):
    """Delete a table"""
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'delete_table', f'Attempted to delete table: {table_name}')
    
    result = delete_table(table_name)
    if result['success']:
        log_admin_action(admin_user.get('id'), 'delete_table_success', f'Successfully deleted table: {table_name}')
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/admin/table/<table_name>/rename', methods=['POST'])
@require_admin
def api_admin_rename_table(table_name):
    """Rename a table"""
    data = request.get_json()
    new_name = data.get('new_name', '').strip()
    
    if not new_name:
        return jsonify({'success': False, 'error': 'New table name is required'}), 400
    
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'rename_table', f'Attempted to rename table {table_name} to {new_name}')
    
    result = rename_table(table_name, new_name)
    if result['success']:
        log_admin_action(admin_user.get('id'), 'rename_table_success', f'Successfully renamed table {table_name} to {new_name}')
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/admin/table/<table_name>/column/<column_name>/modify', methods=['POST'])
@require_admin
def api_admin_modify_column(table_name, column_name):
    """Modify a column's data type"""
    data = request.get_json()
    new_type = data.get('new_type', '').strip().upper()
    
    if not new_type:
        return jsonify({'success': False, 'error': 'New data type is required'}), 400
    
    admin_user = session.get('admin_user', {})
    log_admin_action(admin_user.get('id'), 'modify_column_type', f'Attempted to change {table_name}.{column_name} to {new_type}')
    
    result = modify_column_type(table_name, column_name, new_type)
    if result['success']:
        log_admin_action(admin_user.get('id'), 'modify_column_success', f'Successfully changed {table_name}.{column_name} to {new_type}')
        return jsonify(result)
    else:
        return jsonify(result), 400


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500


# Initialize database on startup (for both direct run and Gunicorn)
print("=== Data Explorer - Modular Version ===")
init_database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)