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
    
    try:
        # Initialize healthcare database
        init_healthcare_database()
    except Exception as e:
        print(f"Warning: Healthcare database initialization failed: {e}")
    
    try:
        # Initialize user database
        init_user_database()
    except Exception as e:
        print(f"Warning: User database initialization failed: {e}")
        print("Application will continue but user features may not work properly")


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
    import stat
    db_dir = os.path.dirname(USER_DATABASE)
    if db_dir:  # Only create directory if there is a directory path
        try:
            os.makedirs(db_dir, exist_ok=True)
            # Ensure directory is writable
            os.chmod(db_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)
            print(f"Created/verified database directory: {db_dir}")
        except Exception as e:
            print(f"Warning: Could not create database directory {db_dir}: {e}")
    
    # Check if we can write to the database location
    try:
        test_file = USER_DATABASE + '.test'
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"Database directory is writable: {db_dir}")
    except Exception as e:
        print(f"WARNING: Database directory is not writable: {e}")
        print(f"Database path: {USER_DATABASE}")
        print(f"Directory permissions might be an issue")
    
    # Check if we need to force regenerate the database due to schema issues
    force_regenerate = False
    if os.path.exists(USER_DATABASE):
        try:
            test_conn = get_user_db_connection()
            # Quick check for problematic schemas
            try:
                sessions_info = test_conn.execute("PRAGMA table_info(user_sessions)").fetchall()
                sessions_columns = [col['name'] for col in sessions_info]
                print(f"Found existing user_sessions columns: {sessions_columns}")
                
                # If we find the problematic session_id column, force regeneration
                if 'session_id' in sessions_columns and 'session_token' not in sessions_columns:
                    print("Detected incompatible schema in user database. Force regenerating...")
                    force_regenerate = True
                elif sessions_columns and 'session_token' not in sessions_columns:
                    print("User_sessions table missing session_token column. Force regenerating...")
                    force_regenerate = True
            except Exception as table_error:
                print(f"Error checking user_sessions table: {table_error}")
                # If table doesn't exist or has issues, that's fine - we'll create it
            
            test_conn.close()
        except Exception as e:
            print(f"Error checking existing database schema: {e}")
            force_regenerate = True
    
    # Remove force regeneration now that schema is correct
    # force_regenerate is only set if there are actual schema conflicts
    
    # Force regenerate database if needed
    if force_regenerate:
        print(f"Removing user database: {USER_DATABASE}")
        if os.path.exists(USER_DATABASE):
            try:
                os.remove(USER_DATABASE)
                print(f"Successfully removed old database: {USER_DATABASE}")
            except Exception as e:
                print(f"Error removing database: {e}")
        print("Creating fresh user database with correct schema...")
    
    conn = get_user_db_connection()
    try:
        # Check if database exists and what schema it has
        existing_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        existing_table_names = [table['name'] for table in existing_tables]
        print(f"Existing tables in user database: {existing_table_names}")
        
        # Create or update user tables
        create_user_tables(conn)
        
        # Verify the schema was created correctly
        verify_user_database_schema(conn)
        
        conn.commit()
        print(f"User database initialized successfully: {USER_DATABASE}")
        
        # Seed challenges after database creation
        from models.challenges import seed_healthcare_challenges
        seed_healthcare_challenges()
        
    except Exception as e:
        print(f"Error initializing user database: {e}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
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
            is_admin BOOLEAN DEFAULT 0,
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
            is_admin BOOLEAN DEFAULT 0,
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
    
    # Create admin audit log table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')


def verify_user_database_schema(conn):
    """Verify that all required columns exist in user tables"""
    print("Verifying user database schema...")
    
    # Check users table schema
    try:
        users_info = conn.execute("PRAGMA table_info(users)").fetchall()
        users_columns = [col['name'] for col in users_info]
        print(f"Users table columns: {users_columns}")
        
        required_users_columns = ['id', 'username', 'password_hash', 'email', 'is_admin', 'created_at', 'last_login', 'is_active']
        missing_columns = [col for col in required_users_columns if col not in users_columns]
        
        if missing_columns:
            print(f"Missing columns in users table: {missing_columns}")
            # Add missing columns
            for column in missing_columns:
                if column == 'password_hash':
                    conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                elif column == 'email':
                    conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
                elif column == 'created_at':
                    conn.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                elif column == 'last_login':
                    conn.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
                elif column == 'is_active':
                    conn.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
                elif column == 'is_admin':
                    conn.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
                print(f"Added missing column: {column}")
        else:
            print("Users table schema is complete")
            
    except Exception as e:
        print(f"Error verifying users table schema: {e}")
        # If users table doesn't exist, it will be created by create_user_tables
    
    # Check user_sessions table schema
    try:
        sessions_info = conn.execute("PRAGMA table_info(user_sessions)").fetchall()
        sessions_columns = [col['name'] for col in sessions_info]
        print(f"User_sessions table columns: {sessions_columns}")
        
        # Print detailed column info for debugging
        for col in sessions_info:
            print(f"  Column: {col['name']}, Type: {col['type']}, Not Null: {col['notnull']}, Default: {col['dflt_value']}")
        
        # Check if table has incompatible schema (old version with session_id instead of proper columns)
        if 'session_id' in sessions_columns and 'session_token' not in sessions_columns:
            print("Detected old user_sessions table schema with session_id column. Recreating table...")
            # Drop and recreate the table with correct schema
            conn.execute("DROP TABLE user_sessions")
            conn.execute('''
                CREATE TABLE user_sessions (
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
            print("Recreated user_sessions table with correct schema")
        else:
            # Check for missing columns in existing table
            required_sessions_columns = ['id', 'user_id', 'session_token', 'login_time', 'last_activity', 'ip_address', 'user_agent', 'is_admin', 'is_active']
            missing_columns = [col for col in required_sessions_columns if col not in sessions_columns]
            
            if missing_columns:
                print(f"Missing columns in user_sessions table: {missing_columns}")
                # Add missing columns
                for column in missing_columns:
                    if column == 'session_token':
                        conn.execute("ALTER TABLE user_sessions ADD COLUMN session_token TEXT")
                    elif column == 'login_time':
                        conn.execute("ALTER TABLE user_sessions ADD COLUMN login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    elif column == 'last_activity':
                        conn.execute("ALTER TABLE user_sessions ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    elif column == 'ip_address':
                        conn.execute("ALTER TABLE user_sessions ADD COLUMN ip_address TEXT")
                    elif column == 'user_agent':
                        conn.execute("ALTER TABLE user_sessions ADD COLUMN user_agent TEXT")
                    elif column == 'is_active':
                        conn.execute("ALTER TABLE user_sessions ADD COLUMN is_active BOOLEAN DEFAULT 1")
                    elif column == 'is_admin':
                        conn.execute("ALTER TABLE user_sessions ADD COLUMN is_admin BOOLEAN DEFAULT 0")
                    print(f"Added missing column: {column}")
            else:
                print("User_sessions table schema is complete")
            
    except Exception as e:
        print(f"Error verifying user_sessions table schema: {e}")
        # If table doesn't exist, it will be created by create_user_tables
    
    # Check query_logs table schema
    try:
        logs_info = conn.execute("PRAGMA table_info(query_logs)").fetchall()
        logs_columns = [col['name'] for col in logs_info]
        print(f"Query_logs table columns: {logs_columns}")
        
        required_logs_columns = ['id', 'user_id', 'session_id', 'query_text', 'execution_time_ms', 'row_count', 'success', 'error_message', 'timestamp']
        missing_columns = [col for col in required_logs_columns if col not in logs_columns]
        
        if missing_columns:
            print(f"Missing columns in query_logs table: {missing_columns}")
            # Add missing columns
            for column in missing_columns:
                if column == 'session_id':
                    conn.execute("ALTER TABLE query_logs ADD COLUMN session_id TEXT")
                elif column == 'execution_time_ms':
                    conn.execute("ALTER TABLE query_logs ADD COLUMN execution_time_ms REAL")
                elif column == 'row_count':
                    conn.execute("ALTER TABLE query_logs ADD COLUMN row_count INTEGER")
                elif column == 'success':
                    conn.execute("ALTER TABLE query_logs ADD COLUMN success BOOLEAN NOT NULL DEFAULT 0")
                elif column == 'error_message':
                    conn.execute("ALTER TABLE query_logs ADD COLUMN error_message TEXT")
                elif column == 'timestamp':
                    conn.execute("ALTER TABLE query_logs ADD COLUMN timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print(f"Added missing column: {column}")
        else:
            print("Query_logs table schema is complete")
            
    except Exception as e:
        print(f"Error verifying query_logs table schema: {e}")
    
    # Check challenge tables schema
    try:
        challenge_progress_info = conn.execute("PRAGMA table_info(user_challenge_progress)").fetchall()
        progress_columns = [col['name'] for col in challenge_progress_info]
        print(f"User_challenge_progress table columns: {progress_columns}")
        
        required_progress_columns = ['id', 'user_id', 'challenge_id', 'best_score', 'total_attempts', 'is_completed', 'created_at', 'updated_at']
        missing_columns = [col for col in required_progress_columns if col not in progress_columns]
        
        if missing_columns:
            print(f"Missing columns in user_challenge_progress table: {missing_columns}")
            # Add missing columns
            for column in missing_columns:
                if column == 'best_score':
                    conn.execute("ALTER TABLE user_challenge_progress ADD COLUMN best_score INTEGER DEFAULT 0")
                elif column == 'total_attempts':
                    conn.execute("ALTER TABLE user_challenge_progress ADD COLUMN total_attempts INTEGER DEFAULT 0")
                elif column == 'is_completed':
                    conn.execute("ALTER TABLE user_challenge_progress ADD COLUMN is_completed BOOLEAN DEFAULT 0")
                elif column == 'created_at':
                    conn.execute("ALTER TABLE user_challenge_progress ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                elif column == 'updated_at':
                    conn.execute("ALTER TABLE user_challenge_progress ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print(f"Added missing column: {column}")
        else:
            print("User_challenge_progress table schema is complete")
            
    except Exception as e:
        print(f"Error verifying user_challenge_progress table schema: {e}")
    
    # Verify other important tables exist
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [table['name'] for table in tables]
    
    required_tables = ['users', 'user_sessions', 'query_logs', 'challenges', 'challenge_attempts', 'user_challenge_progress', 'admin_audit_log']
    missing_tables = [table for table in required_tables if table not in table_names]
    
    if missing_tables:
        print(f"Missing tables: {missing_tables}")
    else:
        print("All required tables exist")


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