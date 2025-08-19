-- SQLQuiz Healthcare Database Schema
-- This schema represents a simplified healthcare billing system

-- Patients table
CREATE TABLE patients (
    patient_id TEXT PRIMARY KEY,
    date_of_birth DATE,
    billing_office TEXT
);

-- Insurance plans table
CREATE TABLE insurance_plans (
    plan_code TEXT PRIMARY KEY,
    plan_description TEXT,
    payor_name TEXT
);

-- Service lines table
CREATE TABLE service_lines (
    service_line_code TEXT PRIMARY KEY,
    service_line_name TEXT
);

-- Invoices table (header level)
CREATE TABLE invoices (
    invoice_id TEXT PRIMARY KEY,
    patient_id TEXT,
    billing_center TEXT,
    source_system TEXT,
    ar_status TEXT,
    invoice_post_date DATE,
    invoice_open_date DATE,
    service_start_date DATE,
    service_end_date DATE,
    service_line_code TEXT,
    
    -- Financial totals
    invoice_total_charges DECIMAL(12,2),
    invoice_total_balance DECIMAL(12,2),
    invoice_ins_balance DECIMAL(12,2),
    invoice_bad_debt_balance DECIMAL(12,2),
    invoice_total_payments DECIMAL(12,2),
    invoice_total_ins_payments DECIMAL(12,2),
    invoice_total_pt_payments DECIMAL(12,2),
    invoice_total_adjustments DECIMAL(12,2),
    invoice_total_expected_reimbursement DECIMAL(12,2),
    
    -- Current insurance plan
    current_plan_code TEXT,
    primary_plan_code TEXT,
    secondary_plan_code TEXT,
    
    -- Dates
    zero_balance_date DATE,
    bad_debt_transfer_date DATE,
    first_bill_date DATE,
    last_bill_date DATE,
    last_payment_date DATE,
    
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (current_plan_code) REFERENCES insurance_plans(plan_code),
    FOREIGN KEY (primary_plan_code) REFERENCES insurance_plans(plan_code),
    FOREIGN KEY (secondary_plan_code) REFERENCES insurance_plans(plan_code),
    FOREIGN KEY (service_line_code) REFERENCES service_lines(service_line_code)
);

-- Invoice details table (line item level)
CREATE TABLE invoice_details (
    invoice_detail_id TEXT PRIMARY KEY,
    invoice_id TEXT,
    patient_id TEXT,
    billing_center TEXT,
    billing_office TEXT,
    order_id TEXT,
    
    -- Service information
    cpt_code TEXT,
    catalog_code TEXT,
    service_start_date DATE,
    service_end_date DATE,
    
    -- Financial amounts
    invoice_total_charges DECIMAL(12,2),
    charge_quantity DECIMAL(10,4),
    invoice_total_expected_reimbursement DECIMAL(12,2),
    
    -- Insurance information
    current_plan_code TEXT,
    current_plan_desc TEXT,
    current_payor TEXT,
    primary_plan_code TEXT,
    primary_plan_desc TEXT,
    primary_payor TEXT,
    invoice_plan_code TEXT,
    invoice_plan_desc TEXT,
    invoice_payor TEXT,
    
    -- Billing dates
    claim_bill_date DATE,
    last_bill_date DATE,
    first_bill_date DATE,
    invoice_open_date DATE,
    invoice_detail_post_date DATE,
    
    -- Other
    payer_order INTEGER,
    physician_ordering_id TEXT,
    
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- Create indexes for better query performance
CREATE INDEX idx_invoices_patient_id ON invoices(patient_id);
CREATE INDEX idx_invoices_service_line ON invoices(service_line_code);
CREATE INDEX idx_invoices_ar_status ON invoices(ar_status);
CREATE INDEX idx_invoices_service_dates ON invoices(service_start_date, service_end_date);
CREATE INDEX idx_invoice_details_invoice_id ON invoice_details(invoice_id);
CREATE INDEX idx_invoice_details_patient_id ON invoice_details(patient_id);
CREATE INDEX idx_invoice_details_cpt_code ON invoice_details(cpt_code);
CREATE INDEX idx_invoice_details_service_dates ON invoice_details(service_start_date, service_end_date);