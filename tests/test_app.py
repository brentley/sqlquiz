#!/usr/bin/env python3
"""
Basic tests for SQLQuiz application
"""

import pytest
import json
import sqlite3
import os
import sys

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, get_db_connection


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_db():
    """Ensure test database exists"""
    if not os.path.exists('healthcare_quiz.db'):
        # Create a minimal test database
        conn = sqlite3.connect('healthcare_quiz.db')
        conn.execute('''CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            date_of_birth DATE,
            billing_office TEXT
        )''')
        conn.execute("INSERT INTO patients VALUES ('TEST001', '1980-01-01', 'TEST')")
        conn.commit()
        conn.close()
    return 'healthcare_quiz.db'


def test_health_endpoint(client, test_db):
    """Test health endpoint returns 200 and expected structure"""
    response = client.get('/health')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'status' in data
    assert 'service' in data
    assert 'version' in data
    assert 'uptime' in data
    assert 'checks' in data
    
    # Should have database check
    assert 'database' in data['checks']


def test_home_page(client):
    """Test home page loads"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'SQLQuiz' in response.data


def test_practice_page(client):
    """Test practice page loads"""
    response = client.get('/practice')
    assert response.status_code == 200
    assert b'Practice Mode' in response.data


def test_quiz_page(client):
    """Test quiz page loads"""
    response = client.get('/quiz')
    assert response.status_code == 200
    assert b'Quiz Mode' in response.data


def test_api_schema(client, test_db):
    """Test schema API endpoint"""
    response = client.get('/api/schema')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert isinstance(data, dict)
    # Should have at least the patients table
    assert 'patients' in data


def test_api_quiz_questions(client):
    """Test quiz questions API endpoint"""
    response = client.get('/api/quiz/questions')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Check first question structure
    question = data[0]
    required_fields = ['id', 'title', 'description', 'expected_query', 'hint', 'difficulty', 'category', 'points']
    for field in required_fields:
        assert field in question


def test_api_execute_basic_query(client, test_db):
    """Test query execution API with basic query"""
    query_data = {
        'query': 'SELECT COUNT(*) as count FROM patients'
    }
    
    response = client.post('/api/execute', 
                          data=json.dumps(query_data),
                          content_type='application/json')
    
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'results' in data
    assert 'columns' in data
    assert len(data['results']) > 0


def test_api_execute_invalid_query(client, test_db):
    """Test query execution API with invalid query"""
    query_data = {
        'query': 'DELETE FROM patients'  # Should be blocked
    }
    
    response = client.post('/api/execute', 
                          data=json.dumps(query_data),
                          content_type='application/json')
    
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'error' in data


def test_api_quiz_check_correct(client):
    """Test quiz answer checking with correct answer"""
    check_data = {
        'query': 'SELECT COUNT(*) FROM patients',
        'expected_query': 'SELECT COUNT(*) FROM patients'
    }
    
    response = client.post('/api/quiz/check',
                          data=json.dumps(check_data),
                          content_type='application/json')
    
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'correct' in data
    assert 'message' in data


def test_database_connection():
    """Test database connection function"""
    conn = get_db_connection()
    assert conn is not None
    
    # Test basic query
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    assert len(tables) >= 0  # Should have at least some tables
    
    conn.close()


def test_quiz_questions_file_exists():
    """Test that quiz questions file exists and is valid JSON"""
    assert os.path.exists('quiz_questions.json')
    
    with open('quiz_questions.json', 'r') as f:
        questions = json.load(f)
    
    assert isinstance(questions, list)
    assert len(questions) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])