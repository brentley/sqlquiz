"""
CSV processing and data utilities.
Handles CSV upload, processing, schema detection, and sample query generation.
"""

import csv
import io
import tempfile
import zipfile
import os
import re
from datetime import datetime
from werkzeug.utils import secure_filename
from models.database import get_db_connection


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
        'amount', 'total', 'cost', 'price', 'charge', 'payment', 'balance', 
        'revenue', 'income', 'expense', 'fee', 'copay', 'deductible'
    ]
    
    return any(indicator in column_lower for indicator in money_indicators)


def is_date_column(column_name):
    """Detect if a column contains date values based on name"""
    column_lower = column_name.lower()
    date_indicators = ['date', 'time', 'created', 'updated', 'start', 'end', 'birth']
    return any(indicator in column_lower for indicator in date_indicators)


def determine_column_type(sample_rows, column_name):
    """Determine the best SQLite type for a column based on sample data"""
    values = []
    for row in sample_rows:
        if column_name in row and row[column_name] is not None:
            values.append(row[column_name])
    
    if len(values) == 0:
        return 'TEXT'
    
    # Check if it's a date column
    if is_date_column(column_name):
        return 'TEXT'  # Store dates as TEXT in ISO format
    
    # Check if it's a money column
    if is_money_column(column_name):
        return 'INTEGER'  # Store money as cents (integer)
    
    # Analyze numeric patterns
    int_count = 0
    float_count = 0
    
    for value in values:
        try:
            int_val = int(float(value))
            if float(value) == int_val:
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


def clean_column_name(column_name):
    """Clean column names for database usage"""
    # Remove BOM character if present
    if column_name.startswith('\ufeff'):
        column_name = column_name[1:]
    
    # Remove any other problematic characters
    cleaned = re.sub(r'[^\w\s-]', '', column_name)
    cleaned = re.sub(r'\s+', '_', cleaned.strip())
    
    return cleaned


def deduplicate_column_names(column_names):
    """Ensure all column names are unique by adding suffixes to duplicates"""
    seen = {}
    result = []
    
    for name in column_names:
        if name in seen:
            # This is a duplicate, add a suffix
            seen[name] += 1
            unique_name = f"{name}_{seen[name]}"
        else:
            # First occurrence
            seen[name] = 0
            unique_name = name
        
        result.append(unique_name)
    
    return result


def process_csv_upload(file, clear_existing=False):
    """Process uploaded CSV file and import into database"""
    if clear_existing:
        clear_database()
    
    filename = secure_filename(file.filename)
    
    # Handle ZIP files
    if filename.lower().endswith('.zip'):
        return process_zip_upload(file)
    
    # Handle single CSV file
    elif filename.lower().endswith('.csv'):
        return process_single_csv(file, filename)
    
    else:
        return {'success': False, 'error': 'Unsupported file type. Please upload CSV or ZIP files.'}


def process_zip_upload(zip_file):
    """Process ZIP file containing CSV files"""
    results = []
    
    try:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.lower().endswith('.csv') and not file_info.filename.startswith('__MACOSX/'):
                    with zip_ref.open(file_info) as csv_file:
                        # Read CSV content
                        content = csv_file.read().decode('utf-8-sig')  # Handle BOM
                        
                        # Create a file-like object
                        csv_io = io.StringIO(content)
                        
                        # Process this CSV
                        result = process_single_csv(csv_io, file_info.filename)
                        results.append(result)
        
        successful = sum(1 for r in results if r.get('success', False))
        total = len(results)
        
        return {
            'success': successful > 0,
            'message': f'Processed {successful}/{total} CSV files successfully',
            'results': results
        }
    
    except Exception as e:
        return {'success': False, 'error': f'Error processing ZIP file: {str(e)}'}


def process_single_csv(file_obj, filename):
    """Process a single CSV file"""
    try:
        # Reset file pointer if it's a file object
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        
        # Read CSV content
        if hasattr(file_obj, 'read'):
            if hasattr(file_obj, 'filename'):
                # It's a FileStorage object
                content = file_obj.read().decode('utf-8-sig')
            else:
                # It's already a StringIO object
                content = file_obj.read()
        else:
            content = file_obj
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(content))
        
        # Clean column names and handle duplicates
        cleaned_fieldnames = [clean_column_name(name) for name in csv_reader.fieldnames]
        cleaned_fieldnames = deduplicate_column_names(cleaned_fieldnames)
        
        # Read sample rows for type detection
        sample_rows = []
        csv_reader = csv.DictReader(io.StringIO(content))
        for i, row in enumerate(csv_reader):
            if i >= 100:  # Sample first 100 rows
                break
            cleaned_row = {}
            for old_name, new_name in zip(csv_reader.fieldnames, cleaned_fieldnames):
                cleaned_row[new_name] = clean_value(row[old_name])
            sample_rows.append(cleaned_row)
        
        # Determine table name from filename
        table_name = os.path.splitext(filename)[0].lower()
        table_name = re.sub(r'[^\w]', '_', table_name)
        
        # Create table schema
        conn = get_db_connection()
        try:
            # Drop existing table if it exists
            conn.execute(f'DROP TABLE IF EXISTS {table_name}')
            
            # Create table
            columns_sql = []
            for col_name in cleaned_fieldnames:
                col_type = determine_column_type(sample_rows, col_name)
                columns_sql.append(f'`{col_name}` {col_type}')
            
            create_sql = f'CREATE TABLE {table_name} ({", ".join(columns_sql)})'
            conn.execute(create_sql)
            
            # Insert data
            csv_reader = csv.DictReader(io.StringIO(content))
            insert_sql = f'INSERT INTO {table_name} ({", ".join([f"`{name}`" for name in cleaned_fieldnames])}) VALUES ({", ".join(["?" for _ in cleaned_fieldnames])})'
            
            row_count = 0
            for row in csv_reader:
                values = []
                for old_name, new_name in zip(csv_reader.fieldnames, cleaned_fieldnames):
                    value = clean_value(row[old_name])
                    
                    # Process based on column type
                    col_type = determine_column_type(sample_rows, new_name)
                    if col_type == 'INTEGER' and is_money_column(new_name):
                        value = parse_money_to_cents(value) if value else None
                    elif col_type == 'REAL':
                        value = parse_decimal(value) if value else None
                    elif is_date_column(new_name) and value:
                        # Convert date to ISO format
                        date_obj = parse_date(value)
                        value = date_obj.isoformat() if date_obj else value
                    
                    values.append(value)
                
                conn.execute(insert_sql, values)
                row_count += 1
            
            conn.commit()
            
            return {
                'success': True,
                'table_name': table_name,
                'rows_imported': row_count,
                'columns': len(cleaned_fieldnames)
            }
        
        finally:
            conn.close()
    
    except Exception as e:
        return {'success': False, 'error': f'Error processing {filename}: {str(e)}'}


def clear_database():
    """Clear all user tables from the database"""
    conn = get_db_connection()
    try:
        # Get all table names except system tables
        tables = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
        
        # Drop each table
        for table in tables:
            conn.execute(f'DROP TABLE IF EXISTS `{table["name"]}`')
        
        conn.commit()
    finally:
        conn.close()


def get_database_schema():
    """Get the database schema information"""
    conn = get_db_connection()
    try:
        # Get all tables
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        
        schema = {}
        for table in tables:
            table_name = table['name']
            
            # Get column information
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            schema[table_name] = [
                {
                    'name': col['name'],
                    'type': col['type'],
                    'nullable': not col['notnull'],
                    'pk': bool(col['pk'])
                }
                for col in columns
            ]
        
        return schema
    finally:
        conn.close()


def get_table_names():
    """Get list of available table names"""
    conn = get_db_connection()
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return [table['name'] for table in tables]
    finally:
        conn.close()


def get_sample_data(table_name, limit=5):
    """Get sample rows from a table"""
    conn = get_db_connection()
    try:
        # Validate table name to prevent SQL injection
        tables = get_table_names()
        if table_name not in tables:
            return {'error': 'Invalid table name'}
        
        # Get sample rows
        query = f"SELECT * FROM `{table_name}` LIMIT {limit}"
        rows = conn.execute(query).fetchall()
        
        # Convert to list of dictionaries
        return [dict(row) for row in rows]
    finally:
        conn.close()


def generate_sample_queries():
    """Generate intelligent sample queries based on current schema"""
    conn = get_db_connection()
    try:
        # Get table names and their schemas
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        table_names = [table['name'] for table in tables]
        
        if not table_names:
            return {
                'basic': '-- No tables available\n-- Upload some CSV files first!',
                'join': '-- No tables available\n-- Upload some CSV files first!',
                'aggregate': '-- No tables available\n-- Upload some CSV files first!'
            }
        
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
            
            # Find potential join columns
            join_column = None
            
            # Look for ID-like columns that might have actual relationships
            id_candidates = []
            for col in t1_columns:
                if col in t2_columns:
                    clean_col = clean_column_name(col)
                    if any(pattern in clean_col.lower() for pattern in ['_id', 'id', 'invoice', 'patient', 'billing']):
                        id_candidates.append(clean_col)
            
            # Test ID candidates first
            for candidate in id_candidates:
                try:
                    # Check if this join would actually return results
                    test_join = f"SELECT COUNT(*) FROM `{table1}` t1 JOIN `{table2}` t2 ON t1.`{candidate}` = t2.`{candidate}` LIMIT 1"
                    result = conn.execute(test_join).fetchone()
                    if result and result[0] > 0:
                        join_column = candidate
                        break
                except Exception:
                    continue
            
            # Generate JOIN query
            if join_column:
                queries['join'] = f"""-- Join {table1} and {table2} on {join_column}
SELECT t1.*, t2.*
FROM `{table1}` t1
JOIN `{table2}` t2 ON t1.`{join_column}` = t2.`{join_column}`
LIMIT 10;"""
            else:
                queries['join'] = f"""-- Example join (adjust column names as needed)
SELECT t1.*, t2.*
FROM `{table1}` t1
JOIN `{table2}` t2 ON t1.id = t2.id
LIMIT 10;"""
        
        # Aggregation query
        first_table = table_names[0]
        columns = schema_info[first_table]
        
        # Find a good grouping column (text/categorical)
        group_column = None
        for col in columns:
            if col['type'] in ['TEXT', ''] and not col['pk']:
                group_column = col['name']
                break
        
        if group_column:
            queries['aggregate'] = f"""-- Aggregate data by {group_column}
SELECT `{group_column}`, COUNT(*) as record_count
FROM `{first_table}`
GROUP BY `{group_column}`
ORDER BY record_count DESC;"""
        else:
            queries['aggregate'] = f"""-- Count all records
SELECT COUNT(*) as total_records
FROM `{first_table}`;"""
        
        return queries
    finally:
        conn.close()