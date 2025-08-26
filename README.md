# Data Explorer - VisiQuate Healthcare Analysis Assessment Platform

A comprehensive web-based healthcare data analysis assessment platform designed for evaluating analytical thinking and problem-solving approaches. Features secure candidate invitation system, comprehensive activity tracking, and professional evaluation scenarios based on real-world healthcare data integrity challenges.

## 🎯 Purpose & Use Cases

**Perfect for:**
- **Healthcare Data Analysis Assessment** - Evaluate analytical thinking with real-world data integrity scenarios
- **Professional Candidate Evaluation** - Secure invitation-based assessment system with comprehensive tracking
- **Data Analysis Interview Process** - Focus on problem-solving approach rather than SQL proficiency
- **Business Intelligence Evaluation** - Test data validation, reconciliation, and pattern analysis skills
- **Healthcare Data Consulting** - Assess experience with accounts receivable, claims processing, and payor analysis

## 🌟 Key Features

### 🔐 **Secure Candidate Invitation System**
- **Unique URL Generation** - Create secure, time-limited candidate assessment links
- **Email-Based Invitations** - Professional invitation management with expiration tracking
- **Usage Monitoring** - Track when links are accessed and prevent unauthorized sharing
- **Admin Impersonation** - Admin can view assessment as candidates with full audit trail
- **Access Control** - Remove public access, candidates only access via secure invitation URLs

### 📊 **Comprehensive Activity Tracking**
- **Complete Query Logging** - Every SQL query captured including syntax errors and performance metrics
- **Think Time Analysis** - Calculate time between candidate activities to measure analysis approach
- **Tab Switching Detection** - Track when candidates navigate away (potential external consultation)
- **Page Visibility Monitoring** - Detect minimization, tab switching with return duration tracking
- **Session Activity** - Login events, page views, impersonation activities with IP and user agent

### 🏥 **VisiQuate Healthcare Evaluation Scenarios**
- **Data Integrity Challenges** - Real-world healthcare data validation scenarios
- **Account Balance Validation** - Test business rule: Balance = Charges - Payments - Adjustments
- **Cross-Table Reconciliation** - Validate rollups between accounts and transactions tables  
- **Payment Analysis** - Insurance vs patient payment patterns and reconciliation
- **AR Status Distribution** - Analyze account receivable patterns by service date and payor
- **Transaction Crosswalk Integrity** - Comprehensive data quality audits

### 👥 **Professional Admin Dashboard**
- **Candidate Invitation Management** - Create, track, and manage candidate assessment URLs
- **Activity Timeline View** - Complete chronological view of candidate behavior with think times
- **Query History Analysis** - Review all queries including failed attempts and error patterns
- **Performance Analytics** - Success rates, execution times, and analytical approach insights
- **Evaluation Reports** - Export comprehensive candidate assessments for interview review

### 🎨 **Evaluation-Focused UI/UX**
- **Professional Assessment Interface** - Clean, distraction-free evaluation environment
- **Embedded Schema Reference** - Healthcare data structure and business rules built into challenges
- **SQLite Constraint Documentation** - Clear notes about CTE limitations and date function differences
- **Activity Visibility Indicators** - Visual cues for page visibility changes and think time patterns
- **Mobile-Responsive Design** - Seamless experience across devices for flexible assessment locations
- **Impersonation Mode** - Admin can experience assessment exactly as candidates do

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

### 3. Admin Setup
1. Navigate to **Admin Login** and enter your authorized email
2. Go to **Admin Dashboard** → "Candidate Invitations"
3. Create secure assessment URLs for candidates
4. Use "Reseed Evaluation Challenges" to load VisiQuate healthcare scenarios

### 4. Candidate Assessment Process
1. **Send Invitation**: Provide unique URL to candidate
2. **Monitor Progress**: Watch real-time activity in admin dashboard
3. **Review Analysis**: Examine query history, think times, and approach
4. **Export Report**: Generate comprehensive assessment for interview discussion

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

### 🏥 **Analysis Evaluation Mode** (Candidate Assessment)
- **10 healthcare data integrity scenarios** - VisiQuate evaluation challenges with professional formatting
- **Data validation focus** - Account balance, payment reconciliation, crosswalk integrity
- **Approach evaluation** - Analytical thinking assessment rather than SQL proficiency testing
- **Complete activity tracking** - Every query, error, and navigation event captured
- **Think time measurement** - Time between activities shows analytical process
- **UTC timezone handling** - All timestamps stored in UTC, displayed in user's local time

### 👨‍💼 **Admin Dashboard**
- **Candidate invitation management** - Generate secure time-limited assessment URLs
- **Real-time activity monitoring** - Watch candidate progress with live activity feeds
- **Comprehensive analytics** - Query success rates, think times, tab switching patterns
- **Detailed candidate reports** - Complete assessment timeline with query history
- **Admin impersonation** - Experience assessment exactly as candidates do

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
│   ├── challenges.py        # VisiQuate evaluation scenarios
│   ├── users.py             # User management and candidate tracking
│   ├── candidates.py        # Invitation system and activity logging
│   └── admin_auth.py        # Admin authentication and authorization
├── routes/                   # Route handlers (future expansion)
│   └── __init__.py          # Package initialization
├── utils/                    # Utility functions and helpers
│   ├── __init__.py          # Package initialization
│   ├── data_processing.py   # CSV processing and schema detection
│   ├── query_validation.py  # SQL security and validation
│   └── timezone.py          # UTC timestamp utilities and browser timezone handling
├── templates/
│   ├── base.html             # Base layout with activity tracking
│   ├── index.html            # Candidate landing page (invitation-only)
│   ├── explore.html          # Data explorer interface
│   ├── upload.html           # Data upload interface (admin-only)
│   ├── challenges.html       # VisiQuate evaluation scenarios
│   └── admin/                # Admin interface templates
│       ├── dashboard.html    # Admin dashboard with invitation management
│       ├── candidates.html   # Candidate activity tracking
│       ├── candidate_detail.html # Detailed assessment view
│       └── candidate_invitations.html # Invitation URL management
├── static/
│   ├── css/style.css         # Custom styles with challenge formatting
│   ├── js/
│   │   ├── app.js           # JavaScript utilities
│   │   └── timezone.js      # Browser timezone conversion utilities
│   └── ...
└── deploy/                   # Docker deployment configs
```

### 🔗 **API Endpoints**

#### Candidate Assessment
- `GET /api/schema` - Get database schema information
- `GET /api/tables` - List available tables
- `POST /api/execute` - Execute SQL queries with comprehensive activity logging
- `GET /api/sample-queries` - Get sample queries for data exploration
- `POST /api/log-activity` - Log candidate page visibility and navigation events

#### VisiQuate Evaluation System  
- `GET /api/challenges` - Get healthcare data integrity evaluation scenarios
- `GET /api/challenge/<id>` - Get specific evaluation scenario details
- `POST /api/challenge/<id>/attempt` - Submit evaluation scenario attempt
- `GET /api/user/progress` - Get candidate progress across evaluation scenarios

#### Admin Dashboard
- `GET /api/admin/candidates` - Get all candidates with activity summaries
- `GET /api/admin/candidate/<username>/detail` - Complete candidate activity timeline
- `GET /api/admin/analytics` - System-wide evaluation performance analytics
- `GET /api/admin/export/candidate/<username>` - Export comprehensive assessment report

#### Candidate Invitation Management
- `GET /api/admin/candidates/invitations` - List all candidate invitation URLs
- `POST /api/admin/candidates/invitations` - Create new secure candidate invitation
- `POST /api/admin/candidates/invitations/<id>/deactivate` - Deactivate invitation URL
- `GET /api/admin/candidates/<user_id>/activity` - Get detailed candidate activity log

#### Admin Tools & Impersonation
- `POST /api/admin/impersonate/<user_id>` - Start admin impersonation of candidate
- `POST /api/admin/end-impersonation` - End active impersonation session
- `POST /api/admin/challenges/reseed` - Update evaluation scenarios with latest content

## 🎯 VisiQuate Healthcare Evaluation Scenarios

### **Evaluation Focus Areas**

#### 🌱 **Level 1: Data Integrity Basics**
- **Account Balance Validation** - Test core business rule: Balance = Charges - Payments - Adjustments
- **Claim Date Pattern Analysis** - Validate first_claim_bill_date ≤ last_claim_bill_date logic
- **Data Overview & Exploration** - Understand table structures and record counts

#### 🔥 **Level 2: Cross-Table Validation** 
- **Account vs Transaction Reconciliation** - Validate adjustment rollups between tables
- **Payment Reconciliation Analysis** - Insurance vs patient payment validation across tables
- **Multi-dimensional Validation** - Test multiple business rules simultaneously

#### ⚡ **Level 3: Advanced Business Analysis**
- **AR Status & Balance Distribution** - Multi-faceted analysis combining rule validation with BI
- **Primary Payor Performance Analysis** - Payment ratios, account status patterns, and efficiency metrics
- **Temporal Pattern Analysis** - Service date trends and payor performance over time

#### 👑 **Level 4: Expert Data Quality**
- **Transaction Crosswalk Integrity** - Comprehensive data quality audit with orphan detection
- **Advanced Data Quality** - Uniqueness validation, unused code identification, pattern analysis
- **Complete System Validation** - Full end-to-end data integrity assessment

### **Assessment Approach**
- **Analytical Thinking Focus** - Evaluates problem-solving approach, not SQL syntax proficiency
- **Business Context Understanding** - Tests real-world healthcare data integrity scenarios
- **Documentation Emphasis** - Candidates document findings as they would for clients
- **Methodology Assessment** - Process and reasoning more important than perfect queries

## 🎨 VisiQuate Healthcare Evaluation Examples

### Level 1: Account Balance Validation
```sql
-- Test business rule: Balance = Charges - Payments - Adjustments
SELECT invoice_id, 
       balance, 
       total_charges, 
       total_payments, 
       total_adjustments,
       (total_charges - total_payments - total_adjustments) as calculated_balance,
       (balance - (total_charges - total_payments - total_adjustments)) as variance
FROM hw_accounts 
WHERE (balance - (total_charges - total_payments - total_adjustments)) != 0;
```

### Level 2: Cross-Table Payment Reconciliation  
```sql
-- Validate account-level payments match transaction-level rollups
SELECT a.invoice_id, 
       a.ins_payments, 
       COALESCE(SUM(t.total_ins_payments), 0) as trans_ins_payments,
       a.pt_payments, 
       COALESCE(SUM(t.total_pt_payments), 0) as trans_pt_payments
FROM hw_accounts a 
LEFT JOIN hw_transactions t ON a.invoice_id = t.invoice_id 
GROUP BY a.invoice_id
HAVING a.ins_payments != COALESCE(SUM(t.total_ins_payments), 0)
    OR a.pt_payments != COALESCE(SUM(t.total_pt_payments), 0);
```

### Level 3: AR Status Pattern Analysis
```sql
-- Analyze open vs closed account patterns by payor and service month
SELECT cur_payor, 
       strftime('%Y-%m', service_start_date) as service_month,
       COUNT(*) as total_accounts,
       COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) as open_accounts,
       ROUND(100.0 * COUNT(CASE WHEN ar_status = 'Open' THEN 1 END) / COUNT(*), 2) as open_percentage
FROM hw_accounts 
WHERE cur_payor IS NOT NULL AND service_start_date IS NOT NULL
GROUP BY cur_payor, service_month
ORDER BY open_percentage DESC;
```

### Level 4: Transaction Crosswalk Data Quality
```sql
-- Comprehensive crosswalk integrity analysis with orphan detection
SELECT 'Crosswalk Duplicates' as issue_type, 
       COUNT(*) as count 
FROM (SELECT txn_type_code, txn_sub_type_code, COUNT(*) 
      FROM hw_trn_codes 
      GROUP BY txn_type_code, txn_sub_type_code 
      HAVING COUNT(*) > 1)
UNION
SELECT 'Orphan Transactions' as issue_type, 
       COUNT(DISTINCT t.txn_sub_type_code) 
FROM hw_transactions t 
LEFT JOIN hw_trn_codes c ON t.txn_sub_type_code = c.txn_sub_type_code 
WHERE c.txn_sub_type_code IS NULL;
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

### **v3.1.0 - Enhanced Timezone & Admin Experience** 🔄
- **UTC Timezone Handling** - All timestamps stored in UTC, displayed in user's browser timezone
- **Enhanced Challenge Formatting** - Professional HTML presentation with clear section labels
- **Admin Session Improvements** - Fixed 500 errors, enhanced impersonation and candidate detail access
- **Browser Timezone Display** - Automatic conversion of UTC times to local timezone preferences
- **Professional Assessment Layout** - Clear separation of Data Set, Scenario, Rule/Constraint, and Task sections

### **v3.0.0 - VisiQuate Healthcare Evaluation Platform** 🏥
- **Secure Candidate Invitation System** - Time-limited unique URLs with usage tracking and admin impersonation
- **Comprehensive Activity Tracking** - Every query, error, navigation event with think time analysis
- **Tab Switching Detection** - Monitor when candidates navigate away (potential external consultation)
- **VisiQuate Healthcare Scenarios** - 10 real-world data integrity evaluation challenges
- **Professional Assessment Interface** - Focus on analytical approach over SQL proficiency
- **Admin Activity Dashboard** - Complete candidate timeline with query history and performance analytics

### **v2.1.0 - Production Stability & Performance** 🚀
- **High-performance CSV processing** - Optimized for 150K+ row datasets with column type caching
- **Resilient authentication system** - Graceful degradation when user database unavailable  
- **Query validation improvements** - Proper support for SQL comments in SELECT statements
- **Duplicate column handling** - Automatic renaming of duplicate CSV column headers
- **Database schema migrations** - Robust handling of existing database upgrades
- **Production deployment fixes** - Resolved container permissions and initialization issues
- **UI visibility enhancements** - Fixed dark theme code examples and error templates

### **v2.2.0 - Smart Pagination & Enhanced UX** 📊
- **Smart server-side pagination** - Navigate through millions of rows efficiently
- **SQL semantics compliance** - Respects user LIMIT clauses (≤5000) exactly as written
- **Configurable page sizes** - Choose 100, 250, 500, or 1000 rows per page with persistent preferences
- **Font size controls** - 5 adjustable levels (XS to XL) for optimal data viewing

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

### **Timezone & Data Display**
- **UTC Storage**: All timestamps stored consistently in UTC using `utils/timezone.py`
- **Browser Display**: Automatic conversion to user's local timezone via `static/js/timezone.js`
- **Activity Tracking**: Precise timing with timezone-aware calculations
- **Professional Timestamps**: Clear date/time formatting with timezone indicators
- **Think Time Accuracy**: UTC-based calculations ensure accurate time measurements across timezones

### **Browser Compatibility**
- **Modern Browsers**: Chrome, Firefox, Safari, Edge (latest versions)
- **Mobile Support**: Touch-friendly responsive design
- **Accessibility**: WCAG 2.1 AA compliance
- **Progressive Web App**: Offline capability and installable

## 🎯 VisiQuate Assessment Usage Guide

### **For VisiQuate Interviewers**
1. **Admin Setup**: Login with authorized email (brent.langston@visiquate.com, peyton.meroney@visiquate.com, jean-claire.chamian@visiquate.com)
   - All admins have full access to impersonation and candidate detail functions
   - Enhanced error handling prevents 500 errors during admin operations
2. **Create Invitation**: Generate secure candidate URL with expiration date via Admin Dashboard → Candidate Invitations
3. **Send to Candidate**: Provide unique assessment URL (expires automatically to prevent sharing)
4. **Real-time Monitoring**: Watch candidate progress, query attempts, and think times through admin dashboard
5. **Review Analysis**: Examine complete activity timeline including tab switching and analytical approach
6. **Export Report**: Generate comprehensive assessment for interview discussion

### **For Candidates**
1. **Access Assessment**: Use provided unique URL (no registration required)
2. **Understand Context**: This evaluates analytical thinking, not SQL proficiency
3. **Document Approach**: Save queries and document findings for interview discussion
4. **Focus on Method**: Emphasis on problem-solving process and business insights
5. **Use Resources**: Schema reference and business rules provided within assessment

### **Key Evaluation Areas**
- **Data Integrity Validation**: Testing business rules and identifying violations
- **Cross-Table Reconciliation**: Validating rollups between related tables
- **Pattern Recognition**: Identifying trends in AR status, payor performance, and date patterns
- **Data Quality Assessment**: Finding orphan records, duplicates, and data inconsistencies
- **Business Analysis**: Understanding healthcare finance concepts (AR, claims, payments)
- **Analytical Documentation**: Summarizing findings as you would for clients

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
- [x] **UTC Timezone System**: All timestamps stored in UTC with browser-local display ✅
- [x] **Enhanced Admin Access**: Fixed 500 errors for impersonation and candidate details ✅
- [x] **Challenge Formatting**: Professional HTML presentation with clear section labels ✅
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