# SQLQuiz - Healthcare Database Skills Assessment

A professional web-based SQL skills assessment application designed for technical interviews and training. Built with real healthcare invoicing data to provide authentic SQL learning experiences.

## 🎯 Purpose & Use Cases

**Perfect for:**
- **Technical Interviews** - Assess SQL skills with realistic healthcare scenarios
- **Training Programs** - Learn SQL with authentic business data
- **Skill Assessment** - Evaluate proficiency from basic queries to advanced analytics
- **Interview Preparation** - Practice SQL before job interviews

## 🏥 Database Overview

The application uses a realistic healthcare billing database with:

- **51,051 patients** with demographics and billing information
- **61,421 invoices** with financial totals and payment tracking  
- **217,654 invoice detail records** with CPT codes and line-item charges
- **762 insurance plans** from various payors
- **10 service lines** including diabetic supplies, wound care, ostomy, etc.
- **$65.7M in total charges** with $45M in payments (68.5% collection rate)

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Load the Database
```bash
python3 load_data.py
```

This will create `healthcare_quiz.db` and populate it with data from the CSV files.

### 3. Run the Application
```bash
python3 app.py
```

The application will be available at: http://localhost:5002

> **Note**: Port 5002 is used to avoid conflicts with macOS Control Center on port 5000

## 📊 Features

### 🎓 Practice Mode
- **Free-form SQL practice** with real healthcare data
- **SQL editor** with syntax highlighting and auto-completion
- **Real-time query execution** with results display
- **Schema browser** to explore table structures and relationships
- **Sample queries** to get started quickly
- **SQL comment support** for annotated queries

### 🧠 Quiz Mode (Interview-Ready)
- **15 progressive questions** from basic to advanced SQL
- **Points-based scoring** (10-45 points per question)
- **Multiple difficulty levels**: Easy, Medium, Hard
- **Schema reference** - View database structure during quizzes
- **Question categories**:
  - Basic Queries & Filtering
  - Aggregation & GROUP BY
  - Joins & Relationships
  - Date Functions & Time-based Analysis
  - Healthcare Analytics & Business Intelligence
  - Advanced Calculations & Window Functions
- **Interview-friendly features**:
  - Professional UI suitable for screen sharing
  - Schema visibility for candidates
  - Clear progress tracking
  - Immediate feedback with explanations

### Security Features
- **Read-only database access** prevents data modification
- **Query validation** blocks dangerous SQL operations
- **Sanitized inputs** prevent SQL injection attacks

## 🗃️ Database Schema

### Core Tables

**patients**
- `patient_id` (Primary Key)
- `date_of_birth`
- `billing_office`

**invoices** 
- `invoice_id` (Primary Key)
- `patient_id` (Foreign Key)
- Financial amounts (charges, payments, adjustments, balances)
- Service dates and billing information
- Insurance plan references
- AR status tracking

**invoice_details**
- `invoice_detail_id` (Primary Key)
- `invoice_id` (Foreign Key)
- CPT codes and catalog codes
- Quantity and unit charges
- Service date details

**insurance_plans**
- `plan_code` (Primary Key)
- `plan_description`
- `payor_name`

**service_lines**
- `service_line_code` (Primary Key)
- `service_line_name`

## 🎯 Sample Queries

### Basic Queries
```sql
-- Count total patients
SELECT COUNT(*) FROM patients;

-- List service lines
SELECT * FROM service_lines ORDER BY service_line_name;
```

### Intermediate Queries
```sql
-- Revenue by service line
SELECT 
    sl.service_line_name,
    SUM(i.invoice_total_charges) as total_revenue
FROM invoices i
JOIN service_lines sl ON i.service_line_code = sl.service_line_code
GROUP BY sl.service_line_code, sl.service_line_name
ORDER BY total_revenue DESC;
```

### Advanced Analytics
```sql
-- Collection rate by service line
SELECT 
    sl.service_line_name,
    SUM(i.invoice_total_charges) as total_charges,
    SUM(i.invoice_total_payments) as total_payments,
    ROUND((SUM(i.invoice_total_payments) * 100.0 / SUM(i.invoice_total_charges)), 2) as collection_rate_percent
FROM invoices i
JOIN service_lines sl ON i.service_line_code = sl.service_line_code
WHERE i.invoice_total_charges > 0
GROUP BY sl.service_line_code, sl.service_line_name
ORDER BY collection_rate_percent DESC;
```

## 🏗️ Technical Architecture

### Backend (Flask)
- **Python 3** web application
- **SQLite database** for fast, embedded data storage
- **RESTful API** for query execution and quiz functionality
- **Security middleware** for query validation

### Frontend
- **Bootstrap 5** for responsive UI design
- **CodeMirror** for SQL syntax highlighting
- **Vanilla JavaScript** for interactive quiz functionality
- **Mobile-first design** with touch-friendly interface

### File Structure
```
sqlquiz/
├── app.py                 # Flask application
├── schema.sql             # Database schema definition
├── load_data.py           # CSV data loader script
├── quiz_questions.json    # Quiz questions and answers
├── requirements.txt       # Python dependencies
├── healthcare_quiz.db     # SQLite database (generated)
├── templates/            
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── practice.html     # Practice mode
│   └── quiz.html         # Quiz interface
└── static/
    ├── css/style.css     # Custom styles
    └── js/app.js         # JavaScript utilities
```

## 🧪 Development & Testing

### Running Tests
```bash
# Test basic functionality
curl http://localhost:5002/api/schema

# Test query execution with comments (newly supported)
curl -X POST -H "Content-Type: application/json" \
  -d '{"query":"-- Get patient count\nSELECT COUNT(*) FROM patients"}' \
  http://localhost:5002/api/execute

# Test quiz questions
curl http://localhost:5002/api/quiz/questions

# Test health endpoint
curl http://localhost:5002/health
```

### Interview Testing Checklist
- [ ] Schema visibility works in quiz mode (click "View Schema")
- [ ] SQL comments work in practice mode (try "Load Basic Query")
- [ ] Query execution provides clear feedback
- [ ] Progress tracking works correctly
- [ ] Mobile responsiveness for different screen sizes

### Adding New Questions
Edit `quiz_questions.json` to add new quiz questions:

```json
{
  "id": 16,
  "title": "Question Title",
  "description": "Question description...",
  "expected_query": "SELECT ...",
  "hint": "Helpful hint for students",
  "difficulty": "Easy|Medium|Hard",
  "category": "Question Category", 
  "points": 15
}
```

## 🐳 Docker Deployment

### Development
```bash
# Start development environment
make dev
# Or directly:
docker compose -f docker-compose.dev.yml up

# Access at http://localhost:5001
```

### Production
```bash
# Production deployment is automated via GitHub Actions
# Manual deployment:
docker compose up -d

# View logs
make logs

# Check status
docker compose ps
```

### 🚀 Production-Ready DevOps
- **Automated Deployments**: GitHub Actions with Watchtower integration
- **Auto-healing**: Autoheal monitors and restarts unhealthy containers
- **Cloudflare Tunnel**: Secure external access without exposed ports
- **Health Monitoring**: Comprehensive health checks for all services
- **Security Scanning**: Multiple tools (Bandit, Safety, pip-audit, Trivy) in CI/CD
- **Multi-architecture**: Supports both amd64 and arm64 platforms
- **Container Orchestration**: Docker Compose with development and production configs

### 🔒 Security & Compliance
- **Read-only database access** prevents data modification
- **SQL injection protection** with query validation and sanitization
- **Container security** with non-root user and health checks
- **Automated security scanning** in CI/CD pipeline
- **Secrets management** with environment variables

### Available Commands
```bash
make dev          # Start development environment
make test         # Run test suite
make build        # Build Docker image
make logs         # View application logs
make shell        # Access container shell
make stop         # Stop all containers
make clean        # Clean up everything
make security-scan # Run security scans
```

## 🎯 Interview Usage Guide

### For Interviewers
1. **Preparation**: Start the application and navigate to Quiz Mode
2. **Screen Sharing**: Share your screen showing the quiz interface
3. **Schema Access**: Candidates can click "View Schema" to see database structure
4. **Question Flow**: Use the built-in question progression (Easy → Medium → Hard)
5. **Real-time Feedback**: Watch candidates work through problems with immediate validation

### For Candidates
1. **Practice First**: Use Practice Mode to familiarize yourself with the data
2. **Schema Reference**: In Quiz Mode, click "View Schema" to see table structures
3. **SQL Comments**: Use `-- comments` to explain your approach
4. **Time Management**: 15 questions with increasing difficulty
5. **Ask Questions**: Clarify business requirements when needed

### Key Interview Scenarios Covered
- **Data Retrieval**: Basic SELECT with filtering and sorting
- **Aggregation**: GROUP BY, COUNT, SUM, AVG for business metrics
- **Joins**: Multi-table queries for comprehensive reporting
- **Date Analysis**: Time-based filtering and date functions
- **Business Intelligence**: Healthcare KPIs, collection rates, patient analytics
- **Advanced SQL**: Window functions, subqueries, complex calculations

## 📊 Database Business Context

The healthcare billing database represents a realistic medical billing scenario:

- **Patient Demographics**: Age groups, billing offices, service utilization
- **Financial Metrics**: Charges, payments, adjustments, outstanding balances
- **Service Lines**: Diabetic supplies, wound care, ostomy products, etc.
- **Insurance**: Multiple payors with varying coverage and payment patterns
- **CPT Codes**: Medical procedure and supply codes for billing
- **Time Series**: Historical data for trend analysis and reporting

This provides authentic business scenarios for SQL assessment rather than artificial academic examples.

## 🔧 Technical Specifications

### Performance
- **Database Size**: ~200MB SQLite file with 217K+ records
- **Query Performance**: Optimized indexes for common query patterns
- **Response Time**: Sub-second query execution for most operations
- **Scalability**: Handles concurrent users for interview scenarios

### Browser Compatibility
- **Modern Browsers**: Chrome, Firefox, Safari, Edge (latest 2 versions)
- **Mobile Support**: Responsive design for tablets and phones
- **Accessibility**: WCAG 2.1 AA compliance for inclusive interviews

### Deployment Options
- **Local Development**: Direct Python execution for testing
- **Docker**: Containerized deployment for consistency
- **Cloud Ready**: Automated deployment via GitHub Actions
- **Secure Access**: Cloudflare Tunnel for remote interviewing

## 📝 License

This project is for educational and professional assessment purposes using synthetic healthcare data.

## 🤝 Contributing

Contributions welcome! Please feel free to:
- **Add Questions**: Expand the quiz with new SQL challenges
- **Improve UI/UX**: Enhance the interview experience
- **Security**: Strengthen query validation and safety
- **Documentation**: Add more examples and use cases
- **Performance**: Optimize query execution and response times

---

**Built with authentic healthcare data for professional SQL skills assessment** 🏥📊💼