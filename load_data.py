#!/usr/bin/env python3
"""
Data loader for SQLQuiz - Healthcare Database
Loads CSV data into SQLite database
"""

import sqlite3
import csv
import os
import sys
from datetime import datetime

DATABASE = 'healthcare_quiz.db'

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
            print(f"Warning: Could not parse date '{date_str}', skipping...")
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
        print(f"Warning: Could not parse decimal '{decimal_str}', using NULL")
        return None

def create_database():
    """Create database and tables from schema"""
    print("Creating database and tables...")
    
    # Remove existing database
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    
    # Create new database
    conn = sqlite3.connect(DATABASE)
    
    # Read and execute schema
    with open('schema.sql', 'r') as f:
        schema = f.read()
    
    conn.executescript(schema)
    conn.commit()
    
    print("Database created successfully!")
    return conn

def load_lookup_tables(conn):
    """Load lookup tables first"""
    print("Loading lookup tables...")
    
    # Service lines - extract from invoice data
    service_lines = set()
    
    # Read service lines from invoice CSV
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            service_line = clean_value(row.get('SERVICE_LINE'))
            if service_line:
                service_lines.add(service_line)
    
    # Insert service lines
    for service_line in service_lines:
        conn.execute("""
            INSERT OR IGNORE INTO service_lines (service_line_code, service_line_name)
            VALUES (?, ?)
        """, (service_line, service_line))
    
    # Insurance plans - extract from both CSV files
    insurance_plans = set()
    
    # From invoice CSV
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Current plan
            plan_code = clean_value(row.get('CUR_IPLAN_CODE'))
            plan_desc = clean_value(row.get('CUR_IPLAN_DESC'))
            payor = clean_value(row.get('CUR_PAYOR'))
            if plan_code:
                insurance_plans.add((plan_code, plan_desc, payor))
            
            # Primary plan
            plan_code = clean_value(row.get('IPLAN_1_CODE'))
            plan_desc = clean_value(row.get('IPLAN_1_DESC'))
            payor = clean_value(row.get('IPLAN_1_PAYOR'))
            if plan_code:
                insurance_plans.add((plan_code, plan_desc, payor))
    
    # From charges CSV
    with open('HW_CHARGES.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Current plan
            plan_code = clean_value(row.get('CUR_IPLAN_CODE'))
            plan_desc = clean_value(row.get('CUR_IPLAN_DESC'))
            payor = clean_value(row.get('CUR_PAYOR'))
            if plan_code:
                insurance_plans.add((plan_code, plan_desc, payor))
            
            # Primary plan
            plan_code = clean_value(row.get('IPLAN_1_CODE'))
            plan_desc = clean_value(row.get('IPLAN_1_DESC'))
            payor = clean_value(row.get('IPLAN_1_PAYOR'))
            if plan_code:
                insurance_plans.add((plan_code, plan_desc, payor))
            
            # Invoice plan
            plan_code = clean_value(row.get('INV_IPLAN_CODE'))
            plan_desc = clean_value(row.get('INV_IPLAN_DESC'))
            payor = clean_value(row.get('INV_IPLAN_PAYOR'))
            if plan_code:
                insurance_plans.add((plan_code, plan_desc, payor))
    
    # Insert insurance plans
    for plan_code, plan_desc, payor in insurance_plans:
        conn.execute("""
            INSERT OR IGNORE INTO insurance_plans (plan_code, plan_description, payor_name)
            VALUES (?, ?, ?)
        """, (plan_code, plan_desc, payor))
    
    conn.commit()
    print(f"Loaded {len(service_lines)} service lines and {len(insurance_plans)} insurance plans")

def load_patients(conn):
    """Load patient data"""
    print("Loading patient data...")
    
    patients = set()
    
    # Extract unique patients from invoice CSV
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            patient_id = clean_value(row.get('NEW_PT_ID'))
            dob = parse_date(row.get('PAT_DOB'))
            billing_office = clean_value(row.get('BILLING_OFFICE'))
            
            if patient_id:
                patients.add((patient_id, dob, billing_office))
    
    # Insert patients
    for patient_id, dob, billing_office in patients:
        conn.execute("""
            INSERT OR IGNORE INTO patients (patient_id, date_of_birth, billing_office)
            VALUES (?, ?, ?)
        """, (patient_id, dob, billing_office))
    
    conn.commit()
    print(f"Loaded {len(patients)} patients")

def load_invoices(conn):
    """Load invoice header data"""
    print("Loading invoice data...")
    
    count = 0
    with open('HW_INVOICE.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            invoice_id = clean_value(row.get('NEW_INVOICE_ID'))
            if not invoice_id:
                continue
            
            # Extract and clean data
            patient_id = clean_value(row.get('NEW_PT_ID'))
            billing_center = clean_value(row.get('NEW_BILLING_CENTER'))
            source_system = clean_value(row.get('NEW_SOURCE_SYSTEM'))
            ar_status = clean_value(row.get('AR_STATUS'))
            
            # Dates
            invoice_post_date = parse_date(row.get('INVOICE_POST_DATE'))
            invoice_open_date = parse_date(row.get('INVOICE_OPEN_DATE'))
            service_start_date = parse_date(row.get('SERVICE_START_DATE'))
            service_end_date = parse_date(row.get('SERVICE_END_DATE'))
            zero_balance_date = parse_date(row.get('ZERO_BALANCE_DATE'))
            bad_debt_transfer_date = parse_date(row.get('BAD_DEBT_TRANSFER_DATE'))
            first_bill_date = parse_date(row.get('FIRST_BILL_DATE'))
            last_payment_date = parse_date(row.get('INVOICE_LAST_PAYMENT_DATE'))
            
            # Financial amounts
            invoice_total_charges = parse_decimal(row.get('INVOICE_TOTAL_CHARGES'))
            invoice_total_balance = parse_decimal(row.get('TOTAL_CURRENT_BALANCE'))
            invoice_ins_balance = parse_decimal(row.get('INVOICE_INS_BALANCE'))
            invoice_bad_debt_balance = parse_decimal(row.get('TOTAL_BAD_DEBT_BALANCE'))
            invoice_total_payments = parse_decimal(row.get('INVOICE_TOTAL_PAYMENTS'))
            invoice_total_ins_payments = parse_decimal(row.get('INVOICE_TOTAL_INS_PAYMENTS'))
            invoice_total_pt_payments = parse_decimal(row.get('INVOICE_TOTAL_PT_PAYMENTS'))
            invoice_total_adjustments = parse_decimal(row.get('INVOICE_TOTAL_ADJUSTMENTS'))
            invoice_total_expected_reimbursement = parse_decimal(row.get('INVOICE_TOTAL_EXPECTED_REIMBURSEMENT'))
            
            # Service line
            service_line_code = clean_value(row.get('SERVICE_LINE'))
            
            # Insurance plans
            current_plan_code = clean_value(row.get('CUR_IPLAN_CODE'))
            primary_plan_code = clean_value(row.get('IPLAN_1_CODE'))
            secondary_plan_code = clean_value(row.get('IPLAN_2_CODE'))
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO invoices (
                        invoice_id, patient_id, billing_center, source_system, ar_status,
                        invoice_post_date, invoice_open_date, service_start_date, service_end_date,
                        service_line_code, invoice_total_charges, invoice_total_balance,
                        invoice_ins_balance, invoice_bad_debt_balance, invoice_total_payments,
                        invoice_total_ins_payments, invoice_total_pt_payments, invoice_total_adjustments,
                        invoice_total_expected_reimbursement, current_plan_code, primary_plan_code,
                        secondary_plan_code, zero_balance_date, bad_debt_transfer_date,
                        first_bill_date, last_payment_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    invoice_id, patient_id, billing_center, source_system, ar_status,
                    invoice_post_date, invoice_open_date, service_start_date, service_end_date,
                    service_line_code, invoice_total_charges, invoice_total_balance,
                    invoice_ins_balance, invoice_bad_debt_balance, invoice_total_payments,
                    invoice_total_ins_payments, invoice_total_pt_payments, invoice_total_adjustments,
                    invoice_total_expected_reimbursement, current_plan_code, primary_plan_code,
                    secondary_plan_code, zero_balance_date, bad_debt_transfer_date,
                    first_bill_date, last_payment_date
                ))
                count += 1
                
                if count % 100 == 0:
                    print(f"  Processed {count} invoices...")
                    
            except Exception as e:
                print(f"Error inserting invoice {invoice_id}: {e}")
                continue
    
    conn.commit()
    print(f"Loaded {count} invoices")

def load_invoice_details(conn):
    """Load invoice detail data"""
    print("Loading invoice detail data...")
    
    count = 0
    with open('HW_CHARGES.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            invoice_detail_id = clean_value(row.get('NEW_INVOICE_DETAIL_ID'))
            if not invoice_detail_id:
                continue
            
            # Extract and clean data
            invoice_id = clean_value(row.get('NEW_INVOICE_ID'))
            patient_id = clean_value(row.get('NEW_PT_ID'))
            billing_center = clean_value(row.get('NEW_BILLING_CENTER'))
            billing_office = clean_value(row.get('BILLING_OFFICE'))
            order_id = clean_value(row.get('ORDER_ID'))
            
            # Service codes
            cpt_code = clean_value(row.get('CPT_CODE'))
            catalog_code = clean_value(row.get('CATALOG_CODE'))
            
            # Dates
            service_start_date = parse_date(row.get('SERVICE_START_DATE'))
            service_end_date = parse_date(row.get('SERVICE_END_DATE'))
            claim_bill_date = parse_date(row.get('CLAIM_BILL_DATE'))
            last_bill_date = parse_date(row.get('LAST_BILL_DATE'))
            first_bill_date = parse_date(row.get('FIRST_BILL_DATE'))
            invoice_open_date = parse_date(row.get('INVOICE_OPEN_DATE'))
            invoice_detail_post_date = parse_date(row.get('INVOICE_DETAIL_POST_DATE'))
            
            # Financial amounts
            invoice_total_charges = parse_decimal(row.get('INVOICE_TOTAL_CHARGES'))
            charge_quantity = parse_decimal(row.get('CHARGE_QUANTITY'))
            invoice_total_expected_reimbursement = parse_decimal(row.get('INVOICE_TOTAL_EXPECTED_REIMBURSEMENT'))
            
            # Insurance information
            current_plan_code = clean_value(row.get('CUR_IPLAN_CODE'))
            current_plan_desc = clean_value(row.get('CUR_IPLAN_DESC'))
            current_payor = clean_value(row.get('CUR_PAYOR'))
            primary_plan_code = clean_value(row.get('IPLAN_1_CODE'))
            primary_plan_desc = clean_value(row.get('IPLAN_1_DESC'))
            primary_payor = clean_value(row.get('IPLAN_1_PAYOR'))
            invoice_plan_code = clean_value(row.get('INV_IPLAN_CODE'))
            invoice_plan_desc = clean_value(row.get('INV_IPLAN_DESC'))
            invoice_payor = clean_value(row.get('INV_IPLAN_PAYOR'))
            
            # Other fields
            payer_order = clean_value(row.get('PAYER_ORDER'))
            physician_ordering_id = clean_value(row.get('PHYSICIAN_ORDERING_ID'))
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO invoice_details (
                        invoice_detail_id, invoice_id, patient_id, billing_center, billing_office,
                        order_id, cpt_code, catalog_code, service_start_date, service_end_date,
                        invoice_total_charges, charge_quantity, invoice_total_expected_reimbursement,
                        current_plan_code, current_plan_desc, current_payor, primary_plan_code,
                        primary_plan_desc, primary_payor, invoice_plan_code, invoice_plan_desc,
                        invoice_payor, claim_bill_date, last_bill_date, first_bill_date,
                        invoice_open_date, invoice_detail_post_date, payer_order, physician_ordering_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    invoice_detail_id, invoice_id, patient_id, billing_center, billing_office,
                    order_id, cpt_code, catalog_code, service_start_date, service_end_date,
                    invoice_total_charges, charge_quantity, invoice_total_expected_reimbursement,
                    current_plan_code, current_plan_desc, current_payor, primary_plan_code,
                    primary_plan_desc, primary_payor, invoice_plan_code, invoice_plan_desc,
                    invoice_payor, claim_bill_date, last_bill_date, first_bill_date,
                    invoice_open_date, invoice_detail_post_date, payer_order, physician_ordering_id
                ))
                count += 1
                
                if count % 100 == 0:
                    print(f"  Processed {count} invoice details...")
                    
            except Exception as e:
                print(f"Error inserting invoice detail {invoice_detail_id}: {e}")
                continue
    
    conn.commit()
    print(f"Loaded {count} invoice details")

def create_summary_stats(conn):
    """Create some summary statistics"""
    print("Creating summary statistics...")
    
    stats = {}
    
    # Count records
    cursor = conn.execute("SELECT COUNT(*) FROM patients")
    stats['patients'] = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM invoices")
    stats['invoices'] = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM invoice_details")
    stats['invoice_details'] = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM insurance_plans")
    stats['insurance_plans'] = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM service_lines")
    stats['service_lines'] = cursor.fetchone()[0]
    
    # Financial totals
    cursor = conn.execute("SELECT SUM(invoice_total_charges) FROM invoices WHERE invoice_total_charges IS NOT NULL")
    total_charges = cursor.fetchone()[0] or 0
    stats['total_charges'] = total_charges
    
    cursor = conn.execute("SELECT SUM(invoice_total_payments) FROM invoices WHERE invoice_total_payments IS NOT NULL")
    total_payments = cursor.fetchone()[0] or 0
    stats['total_payments'] = total_payments
    
    print("\n=== DATABASE SUMMARY ===")
    print(f"Patients: {stats['patients']:,}")
    print(f"Invoices: {stats['invoices']:,}")
    print(f"Invoice Details: {stats['invoice_details']:,}")
    print(f"Insurance Plans: {stats['insurance_plans']:,}")
    print(f"Service Lines: {stats['service_lines']:,}")
    print(f"Total Charges: ${total_charges:,.2f}")
    print(f"Total Payments: ${total_payments:,.2f}")
    
    if total_charges > 0:
        collection_rate = (total_payments / total_charges) * 100
        print(f"Collection Rate: {collection_rate:.1f}%")
    
    print("========================\n")

def main():
    """Main data loading function"""
    print("SQLQuiz Data Loader - Healthcare Database")
    print("=========================================")
    
    # Check if CSV files exist
    if not os.path.exists('HW_INVOICE.csv'):
        print("Error: HW_INVOICE.csv not found!")
        sys.exit(1)
    
    if not os.path.exists('HW_CHARGES.csv'):
        print("Error: HW_CHARGES.csv not found!")
        sys.exit(1)
    
    if not os.path.exists('schema.sql'):
        print("Error: schema.sql not found!")
        sys.exit(1)
    
    try:
        # Create database
        conn = create_database()
        
        # Load data in order
        load_lookup_tables(conn)
        load_patients(conn)
        load_invoices(conn)
        load_invoice_details(conn)
        
        # Create summary
        create_summary_stats(conn)
        
        conn.close()
        
        print("Data loading completed successfully!")
        print(f"Database created: {DATABASE}")
        
    except Exception as e:
        print(f"Error during data loading: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()