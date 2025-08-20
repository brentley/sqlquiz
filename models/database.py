"""
Database connection and initialization module.
Handles database setup, schema creation, and connection management.
"""

import sqlite3
import os
import time
from datetime import datetime

# Database configuration
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
    
    # Initialize user database
    init_user_database()


def init_healthcare_database():
    """Initialize the healthcare database (read from existing file)"""
    print(f"Healthcare database: {DATABASE}")
    
    # Check if database exists and has tables
    if os.path.exists(DATABASE):
        conn = get_db_connection()
        try:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [table['name'] for table in tables]
            print(f"Healthcare database already exists with {len(table_names)} tables: {table_names}")
        finally:
            conn.close()
    else:
        print("Healthcare database does not exist. Please upload CSV data or load sample data.")


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
        from models.challenges import seed_healthcare_challenges
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
            password_hash TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Create user sessions table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_token TEXT UNIQUE NOT NULL,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create query logs table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            query_text TEXT NOT NULL,
            execution_time_ms REAL,
            row_count INTEGER,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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


def get_version_info():
    """Get version info from build files or environment variables"""
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


def health_check():
    """Perform database health check"""
    health_status = {
        'status': 'healthy',
        'service': 'data-explorer',
        'checks': {}
    }
    
    # Check main database connectivity
    try:
        conn = get_db_connection()
        cursor = conn.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="table"')
        table_count = cursor.fetchone()[0]
        conn.close()
        health_status['checks']['main_database'] = 'healthy'
        health_status['checks']['table_count'] = table_count
    except Exception as e:
        health_status['checks']['main_database'] = f'database issue: {str(e)}'
    
    # Check user database connectivity
    try:
        conn = get_user_db_connection()
        cursor = conn.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="table"')
        user_table_count = cursor.fetchone()[0]
        conn.close()
        health_status['checks']['user_database'] = 'healthy'
        health_status['checks']['user_table_count'] = user_table_count
    except Exception as e:
        health_status['checks']['user_database'] = f'user database issue: {str(e)}'
    
    return health_status