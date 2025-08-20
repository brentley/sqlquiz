"""
SQL query validation and security utilities.
Handles query validation, SQL injection prevention, and safe query execution.
"""

import re
import time
from models.database import get_db_connection


# Dangerous SQL keywords and patterns
DANGEROUS_KEYWORDS = [
    'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE',
    'REPLACE', 'MERGE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'PRAGMA',
    'ATTACH', 'DETACH'
]

DANGEROUS_PATTERNS = [
    r';\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)',  # Multiple statements
    r'--.*?(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)',  # Comments with dangerous keywords
    r'/\*.*?(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE).*?\*/',  # Block comments
]


def validate_query(query):
    """
    Validate SQL query for safety and security.
    Returns (is_valid, error_message)
    """
    if not query or not query.strip():
        return False, "Query cannot be empty"
    
    query = query.strip()
    
    # Remove SQL comments for analysis (but keep original for execution)
    query_for_analysis = remove_sql_comments(query)
    
    # Check for dangerous keywords
    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf'\b{keyword}\b', query_for_analysis, re.IGNORECASE):
            return False, f"Dangerous operation '{keyword}' not allowed"
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, query_for_analysis, re.IGNORECASE | re.DOTALL):
            return False, "Multiple statements or dangerous patterns not allowed"
    
    # Check for semicolon-separated statements (except at the end)
    statements = [stmt.strip() for stmt in query.split(';') if stmt.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements not allowed"
    
    # Basic syntax validation - use cleaned query without comments
    if not re.match(r'^\s*SELECT\b', query_for_analysis.strip(), re.IGNORECASE):
        return False, "Only SELECT statements are allowed"
    
    # Check if query has a LIMIT clause for large result protection
    if not re.search(r'\bLIMIT\s+\d+\b', query_for_analysis, re.IGNORECASE):
        # Add a warning but don't block the query
        print(f"Warning: Query without LIMIT clause may return many rows")
    
    return True, None


def remove_sql_comments(query):
    """Remove SQL comments from query for analysis"""
    # Remove single-line comments
    query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
    
    # Remove block comments
    query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
    
    return query


def execute_safe_query(query, timeout_seconds=60, page=1, rows_per_page=1000):
    """
    Execute a SQL query safely with validation, timeout, and pagination.
    Returns (success, data, error_message, execution_time_ms, total_count, page_count)
    """
    # Validate query first
    is_valid, error_message = validate_query(query)
    if not is_valid:
        return False, None, error_message, 0, 0, 0
    
    start_time = time.time()
    
    try:
        conn = get_db_connection()
        
        # Set a timeout for the query
        conn.execute(f"PRAGMA busy_timeout = {timeout_seconds * 1000}")
        
        # First, get the total count by wrapping the query
        count_query = f"SELECT COUNT(*) as total_count FROM ({query}) as subquery"
        count_cursor = conn.execute(count_query)
        total_count = count_cursor.fetchone()[0]
        
        # Calculate pagination
        offset = (page - 1) * rows_per_page
        
        # Execute the paginated query
        paginated_query = f"{query} LIMIT {rows_per_page} OFFSET {offset}"
        cursor = conn.execute(paginated_query)
        results = cursor.fetchall()
        
        # Get column names
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # Convert to list of dictionaries
        data = []
        for row in results:
            data.append(dict(zip(columns, row)))
        
        execution_time_ms = (time.time() - start_time) * 1000
        page_count = len(data)
        
        conn.close()
        
        return True, {'results': data, 'columns': columns, 'total_count': total_count, 'page': page, 'rows_per_page': rows_per_page}, None, execution_time_ms, total_count, page_count
    
    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        error_message = str(e)
        
        # Sanitize error message to avoid information disclosure
        if "no such table" in error_message.lower():
            error_message = "Table not found. Check the schema for available tables."
        elif "no such column" in error_message.lower():
            error_message = "Column not found. Check the table schema for available columns."
        elif "syntax error" in error_message.lower():
            error_message = "SQL syntax error. Please check your query syntax."
        
        return False, None, error_message, execution_time_ms, 0, 0


def sanitize_table_name(table_name):
    """Sanitize table name to prevent SQL injection"""
    # Remove any characters that aren't alphanumeric or underscore
    sanitized = re.sub(r'[^\w]', '', table_name)
    
    # Ensure it starts with a letter or underscore
    if not re.match(r'^[a-zA-Z_]', sanitized):
        return None
    
    return sanitized


def validate_table_exists(table_name):
    """Check if a table exists in the database"""
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        conn.close()
        
        return result is not None
    except Exception:
        return False


def get_query_complexity_score(query):
    """
    Calculate a complexity score for a query (for challenge evaluation).
    Returns a score from 1-10 based on query features.
    """
    query_lower = query.lower()
    score = 1
    
    # Basic SELECT gets base score
    if 'select' in query_lower:
        score += 1
    
    # JOINs add complexity
    join_count = len(re.findall(r'\bjoin\b', query_lower))
    score += join_count * 2
    
    # Subqueries add complexity
    subquery_count = query_lower.count('select') - 1  # Subtract main SELECT
    score += subquery_count * 2
    
    # Aggregation functions
    agg_functions = ['count', 'sum', 'avg', 'min', 'max', 'group_concat']
    for func in agg_functions:
        if func in query_lower:
            score += 1
    
    # GROUP BY and HAVING
    if 'group by' in query_lower:
        score += 1
    if 'having' in query_lower:
        score += 1
    
    # ORDER BY
    if 'order by' in query_lower:
        score += 1
    
    # Window functions
    window_functions = ['over', 'partition by', 'row_number', 'rank', 'dense_rank']
    for func in window_functions:
        if func in query_lower:
            score += 2
    
    # CTEs (Common Table Expressions)
    if 'with' in query_lower and 'as' in query_lower:
        score += 2
    
    # CASE statements
    if 'case when' in query_lower:
        score += 1
    
    # Date functions
    date_functions = ['strftime', 'date', 'datetime', 'julianday']
    for func in date_functions:
        if func in query_lower:
            score += 1
    
    return min(score, 10)  # Cap at 10


def analyze_query_performance(query, execution_time_ms):
    """
    Analyze query performance and provide suggestions.
    Returns performance insights and optimization suggestions.
    """
    insights = {
        'execution_time_ms': execution_time_ms,
        'performance_level': 'good',
        'suggestions': []
    }
    
    # Classify performance
    if execution_time_ms > 5000:  # 5 seconds
        insights['performance_level'] = 'poor'
        insights['suggestions'].append("Query took over 5 seconds to execute. Consider optimizing.")
    elif execution_time_ms > 1000:  # 1 second
        insights['performance_level'] = 'fair'
        insights['suggestions'].append("Query took over 1 second. Could be optimized for better performance.")
    
    query_lower = query.lower()
    
    # Check for common performance issues
    if 'select *' in query_lower:
        insights['suggestions'].append("Consider selecting specific columns instead of using SELECT *")
    
    if 'like' in query_lower and '%' in query:
        insights['suggestions'].append("LIKE patterns starting with % can be slow on large tables")
    
    if query_lower.count('join') > 3:
        insights['suggestions'].append("Multiple JOINs detected. Ensure proper indexing for optimal performance")
    
    if 'order by' in query_lower and 'limit' not in query_lower:
        insights['suggestions'].append("ORDER BY without LIMIT may be inefficient on large result sets")
    
    return insights