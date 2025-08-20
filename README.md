# Data Explorer - Advanced SQL Skills Assessment Platform

A comprehensive web-based SQL skills assessment and training platform designed for technical interviews, candidate evaluation, and data analysis training. Features dynamic CSV data import, progressive challenge modes, and comprehensive admin analytics.

## 🎯 Purpose & Use Cases

**Perfect for:**
- **Technical Interviews** - Assess SQL skills with real-world data scenarios
- **Candidate Evaluation** - Progressive challenge system with detailed tracking
- **Training Programs** - Learn SQL with dynamic data exploration
- **Skill Assessment** - Evaluate proficiency from basic queries to advanced analytics
- **Data Science Interviews** - Test data analysis and problem-solving skills

## 🌟 Key Features

### 🔄 **Dynamic Data Import**
- **Upload any CSV data** - Transform CSV files into interactive SQL databases
- **ZIP file support** - Upload multiple CSV files at once
- **Automatic schema detection** - Intelligent column type inference with duplicate column handling
- **UTF-8 BOM handling** - Clean data import from various sources
- **High-performance processing** - Optimized for large datasets (150K+ rows)
- **Smart query generation** - Automatic sample queries based on your data with relationship detection

### 🏆 **Challenge Mode Assessment System**
- **Progressive difficulty levels** - Basic → Intermediate → Advanced → Expert
- **Real-time scoring** - Performance-based evaluation with efficiency bonuses
- **Hint system** - Progressive disclosure with scoring penalties
- **Query tracking** - Complete audit trail of all candidate attempts
- **Performance metrics** - Execution time, accuracy, and approach analysis

### 👥 **Comprehensive Admin Interface**
- **Candidate management** - View all assessments with filtering and search
- **Detailed analytics** - Performance breakdowns by difficulty level
- **Query history** - See exact SQL queries attempted by each candidate
- **Export functionality** - Generate detailed assessment reports
- **System insights** - Identify challenging problems and success patterns

### 🎨 **Professional UI/UX**
- **Mobile-first design** - Responsive interface for all devices
- **CodeMirror integration** - Syntax highlighting with SQL comment support
- **Real-time feedback** - Immediate query results and error handling
- **Schema reference** - Interactive database structure viewer
- **Dark/light theme support** - User preference detection with proper contrast
- **Resilient authentication** - Graceful degradation when database unavailable

### 📊 **Smart Query Results & Pagination**
- **Server-side pagination** - Navigate through millions of rows efficiently
- **Smart pagination rules** - Respects user LIMIT clauses (≤5000 rows) exactly
- **Configurable page sizes** - Choose 100, 250, 500, or 1000 rows per page
- **Performance optimization** - Prevents browser freezing with large datasets
- **User preferences** - Persistent settings for font size and page size
- **Font size controls** - 5 levels from extra small to extra large for optimal viewing

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Run the Application
```bash
python3 app.py
```

The application will be available at: http://localhost:5002

### 3. Upload Your Data
1. Navigate to **Upload Data** page
2. Upload CSV files or ZIP archives
3. Data is automatically converted to SQLite tables
4. Start exploring with the **Data Explorer**

### 4. Set Up Assessments
1. Use **Challenge Mode** to test candidates
2. View results in **Admin Dashboard**
3. Export detailed reports for evaluation

## 📊 Application Modes

### 🔍 **Data Explorer Mode**
- **Free-form SQL practice** with any uploaded data
- **Intelligent sample queries** based on your schema
- **Real-time query execution** with results visualization and progress tracking
- **Schema browser** for table exploration with sample data preview
- **Smart pagination** - Navigate through large result sets efficiently
- **Configurable display** - Adjustable font sizes and rows per page (100-1000)
- **SQL semantics respect** - LIMIT clauses honored exactly as written
- **Query performance monitoring** - Execution time tracking with 60-second timeout

### 🏆 **Challenge Mode** (Assessment)
- **7 progressive challenges** from basic to expert level
- **Healthcare data scenarios** with realistic business problems
- **Scoring system** based on correctness, efficiency, and hints used
- **Progressive hint system** for guided problem-solving
- **Attempt tracking** with detailed performance metrics

### 👨‍💼 **Admin Dashboard**
- **Candidate overview** with completion rates and scores
- **Performance analytics** by difficulty level and challenge type
- **Query-by-query analysis** showing problem-solving approaches
- **Export capabilities** for detailed assessment reports
- **System-wide insights** for challenge optimization

## 🏗️ Architecture Overview

### 📁 **Modular Structure**
```
data-explorer/
├── app.py                     # Main Flask application (refactored & modular)
├── app_monolithic.py          # Original monolithic version (backup)
├── requirements.txt           # Python dependencies
├── healthcare_quiz.db         # Default sample database
├── user_data.db              # User tracking and challenges
├── models/                   # Data models and database operations
│   ├── __init__.py          # Package initialization
│   ├── database.py          # Database connections and initialization
│   ├── challenges.py        # Challenge system models
│   └── users.py             # User management and sessions
├── routes/                   # Route handlers (future expansion)
│   └── __init__.py          # Package initialization
├── utils/                    # Utility functions and helpers
│   ├── __init__.py          # Package initialization
│   ├── data_processing.py   # CSV processing and schema detection
│   └── query_validation.py  # SQL security and validation
├── templates/
│   ├── base.html             # Base layout template
│   ├── index.html            # Landing page
│   ├── explore.html          # Data explorer interface
│   ├── upload.html           # Data upload interface
│   ├── challenges.html       # Challenge mode interface
│   └── admin/                # Admin interface templates
│       ├── dashboard.html    # Admin dashboard
│       ├── candidates.html   # Candidate management
│       └── candidate_detail.html # Detailed candidate view
├── static/
│   ├── css/style.css         # Custom styles
│   └── js/app.js            # JavaScript utilities
└── deploy/                   # Docker deployment configs
```

### 🔗 **API Endpoints**

#### Data Management
- `GET /api/schema` - Get database schema information
- `GET /api/tables` - List available tables
- `POST /api/execute` - Execute SQL queries with pagination support
  - Parameters: `query`, `page` (default: 1), `rows_per_page` (default: 1000)
  - Smart pagination: Respects user LIMIT clauses ≤5000 rows exactly
- `GET /api/sample-queries` - Get intelligent sample queries
- `POST /api/upload` - Upload CSV/ZIP data files

#### Challenge System
- `GET /api/challenges` - Get all challenges by difficulty
- `GET /api/challenge/<id>` - Get specific challenge details
- `POST /api/challenge/<id>/attempt` - Submit challenge attempt
- `GET /api/user/progress` - Get user progress across challenges

#### Admin Interface
- `GET /api/admin/candidates` - Get all candidates with summaries
- `GET /api/admin/candidate/<username>/detail` - Detailed candidate data
- `GET /api/admin/analytics` - System-wide performance analytics
- `GET /api/admin/export/candidate/<username>` - Export assessment report

## 🎯 Challenge System Details

### **Challenge Difficulty Levels**

#### 🌱 **Level 1: Basic** (Green)
- Simple SELECT queries and filtering
- Basic aggregation (COUNT, SUM)
- Single table operations
- *Example: "How many unique patients are in the charges data?"*

#### 🔥 **Level 2: Intermediate** (Yellow)
- GROUP BY analysis and reporting
- Date/time functions and filtering
- Multiple aggregation functions
- *Example: "Which month had the highest total charges?"*

#### ⚡ **Level 3: Advanced** (Red)
- Complex JOINs across multiple tables
- Subqueries and analytical functions
- Business logic implementation
- *Example: "Find patients with invoices in multiple AR statuses"*

#### 👑 **Level 4: Expert** (Purple)
- Advanced business intelligence queries
- Performance optimization challenges
- Complex date arithmetic and analysis
- *Example: "Analyze revenue cycle efficiency by billing office"*

### **Scoring System**
- **Base Score**: 100 points per challenge
- **Correctness**: Based on result accuracy (±10% tolerance)
- **Efficiency Bonus**: Faster queries earn bonus points
- **Hint Penalty**: -10 points per hint used
- **Time Factor**: Completion time affects final score

## 🎨 Sample Challenge Problems

### Basic Level
```sql
-- Find Patient Count
SELECT COUNT(DISTINCT NEW_PT_ID) FROM hw_charges;
```

### Intermediate Level  
```sql
-- AR Status Distribution
SELECT AR_STATUS, COUNT(*) as invoice_count 
FROM hw_invoice 
GROUP BY AR_STATUS 
ORDER BY invoice_count DESC;
```

### Advanced Level
```sql
-- Insurance Reimbursement Analysis
SELECT IPLAN_1_PAYOR, 
       SUM(INVOICE_TOTAL_EXPECTED_REIMBURSEMENT) as expected,
       SUM(INVOICE_TOTAL_INS_PAYMENTS) as actual,
       ROUND(100.0 * SUM(INVOICE_TOTAL_INS_PAYMENTS) / 
             SUM(INVOICE_TOTAL_EXPECTED_REIMBURSEMENT), 2) as rate
FROM hw_invoice 
WHERE IPLAN_1_PAYOR IS NOT NULL 
GROUP BY IPLAN_1_PAYOR 
ORDER BY rate DESC;
```

### Expert Level
```sql
-- Revenue Cycle Efficiency
SELECT i.BILLING_OFFICE,
       AVG(JULIANDAY(i.INVOICE_LAST_PAYMENT_DATE) - 
           JULIANDAY(c.SERVICE_START_DATE)) as avg_days_to_payment
FROM hw_invoice i 
JOIN hw_charges c ON i.NEW_INVOICE_ID = c.NEW_INVOICE_ID
WHERE i.AR_STATUS = 'Paid' AND i.INVOICE_LAST_PAYMENT_DATE IS NOT NULL
GROUP BY i.BILLING_OFFICE
ORDER BY avg_days_to_payment ASC;
```

## 📊 Admin Analytics Features

### **Candidate Performance Tracking**
- ✅ Overall completion rates and progress visualization
- ✅ Score breakdowns by difficulty level and category
- ✅ Time-to-completion analysis across challenges
- ✅ Hint usage patterns and help-seeking behavior
- ✅ Query evolution and problem-solving approaches

### **System-Wide Analytics**
- ✅ Challenge difficulty rankings based on success rates
- ✅ Performance trends across candidate pool
- ✅ Most challenging problems identification
- ✅ Average execution times and optimization opportunities
- ✅ Candidate activity patterns and engagement metrics

### **Assessment Reports**
- ✅ **Individual Reports**: Complete candidate assessment with query history
- ✅ **Comparative Analysis**: Performance relative to candidate pool
- ✅ **Skill Mapping**: Strengths and weaknesses by SQL concept
- ✅ **Progression Tracking**: Improvement over time and attempts
- ✅ **Export Formats**: JSON reports for external analysis

## 🎯 Recent Updates

### **v2.2.0 - Smart Pagination & Enhanced UX** 📊
- **Smart server-side pagination** - Navigate through millions of rows efficiently
- **SQL semantics compliance** - Respects user LIMIT clauses (≤5000) exactly as written
- **Configurable page sizes** - Choose 100, 250, 500, or 1000 rows per page with persistent preferences
- **Font size controls** - 5 adjustable levels (XS to XL) for optimal data viewing
- **Performance optimization** - Prevents browser freezing with large result sets
- **User experience improvements** - Loading states, progress tracking, and intuitive controls

### **v2.1.0 - Production Stability & Performance** 🚀
- **High-performance CSV processing** - Optimized for 150K+ row datasets with column type caching
- **Resilient authentication system** - Graceful degradation when user database unavailable  
- **Query validation improvements** - Proper support for SQL comments in SELECT statements
- **Duplicate column handling** - Automatic renaming of duplicate CSV column headers
- **Database schema migrations** - Robust handling of existing database upgrades
- **Production deployment fixes** - Resolved container permissions and initialization issues
- **UI visibility enhancements** - Fixed dark theme code examples and error templates

### **v2.0.0 - Data Explorer Transformation** 🔄
- **Dynamic CSV import system** - Upload any data, get instant SQL interface
- **Challenge mode** - Progressive difficulty assessment system  
- **Admin dashboard** - Comprehensive candidate evaluation tools
- **Modular architecture** - Maintainable, scalable codebase
- **UI/UX overhaul** - Modern, responsive, mobile-first design

## 🐳 Docker Deployment

### Development
```bash
# Start development environment
make dev

# Run tests
make test

# View logs
make logs

# Access container shell
make shell
```

### Production
```bash
# Automated deployment via GitHub Actions
git push origin main

# Manual deployment
docker compose up -d

# Check status
docker compose ps
```

## 🔧 Technical Specifications

### **Performance**
- **Database Engine**: SQLite for fast, embedded operations
- **Query Performance**: Sub-second execution for most operations with 60-second timeout
- **Smart Pagination**: Server-side pagination for large result sets (up to millions of rows)
- **File Upload**: Handles large CSV files (150K+ rows) with streaming processing and column type caching
- **Browser Optimization**: Prevents freezing with configurable page sizes (100-1000 rows)
- **Concurrent Users**: Optimized for interview scenarios with efficient resource management

### **Security Features**
- **Read-only database access** for candidate queries
- **Query validation** blocks dangerous SQL operations
- **Input sanitization** prevents SQL injection attacks
- **UTF-8 BOM cleaning** prevents hidden character issues
- **Container security** with non-root user execution

### **Browser Compatibility**
- **Modern Browsers**: Chrome, Firefox, Safari, Edge (latest versions)
- **Mobile Support**: Touch-friendly responsive design
- **Accessibility**: WCAG 2.1 AA compliance
- **Progressive Web App**: Offline capability and installable

## 🎯 Interview Usage Guide

### **For Interviewers**
1. **Setup**: Upload relevant CSV data or use default healthcare dataset
2. **Challenge Selection**: Choose appropriate difficulty level for candidate
3. **Real-time Monitoring**: Watch candidate progress through admin dashboard
4. **Assessment**: Review detailed query history and problem-solving approach
5. **Export**: Generate comprehensive assessment report for evaluation

### **For Candidates**
1. **Familiarization**: Start with Data Explorer to understand the schema
2. **Challenge Mode**: Work through progressive difficulty levels
3. **Hint Usage**: Use hints strategically (impacts final score)
4. **SQL Best Practices**: Write clean, efficient queries with comments
5. **Problem-Solving**: Think through business requirements before coding

### **Key Assessment Areas**
- **Data Retrieval**: SELECT, WHERE, ORDER BY fundamentals
- **Aggregation**: GROUP BY, aggregate functions, HAVING clauses
- **Joins**: INNER/LEFT/RIGHT joins across multiple tables
- **Date Analysis**: Date functions and time-based filtering
- **Business Intelligence**: KPIs, ratios, and analytical queries
- **Advanced SQL**: Window functions, CTEs, complex subqueries

## 🔐 Data Privacy & Security

### **Data Handling**
- **User-uploaded data** stays local to your deployment
- **No external data transmission** except for application functionality
- **SQLite local storage** with configurable retention policies
- **Assessment data tracking** with anonymization options

### **Security Measures**
- **Container isolation** with minimal attack surface
- **Read-only query execution** prevents data modification
- **Input validation** at multiple application layers
- **Secure deployment** with Cloudflare tunnel integration

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- **Development setup** and coding standards
- **Pull request process** and review guidelines
- **Testing requirements** and security considerations
- **Feature development areas** and technical improvements
- **Bug reporting** and performance optimization

Key areas for enhancement:
- **Challenge Library**: Add more domain-specific problems
- **UI/UX Improvements**: Enhanced candidate experience
- **Analytics Features**: Advanced performance insights
- **Integration Capabilities**: HR system integrations
- **Security Enhancements**: Additional query validation
- **Performance Optimization**: Query execution improvements

## 📝 Roadmap

### **Planned Features**
- [x] **Module Refactoring**: Break app.py into focused modules ✅
- [ ] **Custom Challenge Creation**: Admin interface for creating new challenges
- [ ] **Team Assessment**: Multi-candidate comparison tools
- [ ] **API Integrations**: Connect with ATS/HR systems
- [ ] **Advanced Analytics**: Machine learning insights
- [ ] **Mobile App**: Native mobile assessment experience

### **Technical Improvements**
- [x] **Database Optimization**: CSV processing performance enhancements ✅
- [x] **Authentication System**: Resilient authentication with graceful degradation ✅
- [x] **Schema Migration**: Robust database schema updates ✅
- [x] **Query Validation**: Enhanced security with comment support ✅
- [ ] **Caching Layer**: Redis integration for better performance
- [ ] **Role-based Access Control**: Admin/candidate permission levels
- [ ] **Audit Logging**: Enhanced activity tracking
- [ ] **Backup Systems**: Automated data protection

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

**Professional SQL skills assessment made simple** 📊💼🚀

*Transform any CSV data into interactive SQL assessment experiences*