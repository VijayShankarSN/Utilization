#!/usr/bin/env python
"""
Direct Data Import Script for Utilization Report

This script allows direct pushing of report data to the database
without requiring an Excel file as an intermediate step.

Usage:
    python manage.py shell < util/util_report/push_direct_report.py
"""

import logging
from datetime import datetime
from django.utils.dateparse import parse_date

# Import your models (adjust the import path if needed)
from util.util_report.models import UtilizationReportModel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Target date for the report data
TARGET_DATE = '2025-03-07'  # Format: YYYY-MM-DD for 7Mar2025

# Define the direct report data
# This is a list of dictionaries, each representing a record to insert
DIRECT_REPORT_DATA = [
    # Example of a record structure - replace with your actual data
    # {
    #     'resource_email_address': 'john.doe@example.com',
    #     'administrative': 0,
    #     'billable_hours': 40,
    #     'department_mgmt': 0,
    #     'investment': 0,
    #     'presales': 0,
    #     'training': 0,
    #     'unassigned': 0,
    #     'vacation': 0,
    #     'grand_total': 40,
    #     'last_week': 0,
    #     'total_logged': 40,
    #     'status': 'open',
    #     'addtnl_days': 0,
    #     'wtd_actuals': 5,
    #     'rdm': 'Adam',
    #     'track': '',
    #     'billing': 'Billing',
    #     'spoc': 'Adam',
    #     'comments': '',
    #     'spoc_comments': ''
    # },
    # Add more records here...
]

def safe_float(value, default=0.0):
    """Convert value to float, with fallback to default for invalid values."""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def push_direct_data():
    """Push the direct report data to the database."""
    try:
        if not DIRECT_REPORT_DATA:
            logger.error("No data provided in DIRECT_REPORT_DATA")
            return False
            
        # Delete existing data for this date
        deleted_count, _ = UtilizationReportModel.objects.filter(date=TARGET_DATE).delete()
        logger.info(f"Deleted {deleted_count} existing records for {TARGET_DATE}")
        
        # Prepare records for bulk insert
        records_to_save = []
        
        for record in DIRECT_REPORT_DATA:
            # Get resource email safely and ensure it's lowercase
            resource_email = record.get('resource_email_address', '')
            if not resource_email:
                logger.warning(f"Skipping record with missing email: {record}")
                continue
                
            # Use lowercase email for consistency
            if isinstance(resource_email, str):
                resource_email = resource_email.lower()
            
            # Create the model instance with all relevant fields
            records_to_save.append(UtilizationReportModel(
                resource_email_address=resource_email,
                administrative=safe_float(record.get('administrative', 0)),
                billable_hours=safe_float(record.get('billable_hours', 0)),
                department_mgmt=safe_float(record.get('department_mgmt', 0)),
                investment=safe_float(record.get('investment', 0)),
                presales=safe_float(record.get('presales', 0)),
                training=safe_float(record.get('training', 0)),
                unassigned=safe_float(record.get('unassigned', 0)),
                vacation=safe_float(record.get('vacation', 0)),
                grand_total=safe_float(record.get('grand_total', 0)),
                last_week=safe_float(record.get('last_week', 0)),
                total_logged=safe_float(record.get('total_logged', 0)),
                status=record.get('status', 'open'),
                addtnl_days=safe_float(record.get('addtnl_days', 0)),
                wtd_actuals=safe_float(record.get('wtd_actuals', 0)),
                rdm=record.get('rdm', 'Adam') or 'Adam',
                track=record.get('track', '') or '',
                billing=record.get('billing', 'TBD') or 'TBD',
                spoc=record.get('spoc', record.get('rdm', 'Adam')) or 'Adam',
                comments=record.get('comments', ''),
                spoc_comments=record.get('spoc_comments', ''),
                date=parse_date(TARGET_DATE)
            ))
        
        # Bulk insert the records
        if records_to_save:
            UtilizationReportModel.objects.bulk_create(records_to_save, batch_size=500)
            logger.info(f"Successfully imported {len(records_to_save)} records for {TARGET_DATE}")
        else:
            logger.warning("No records to import")
        
        return True
    
    except Exception as e:
        logger.error(f"Error pushing direct data: {str(e)}", exc_info=True)
        return False

def calculate_and_push_from_dataframe(df, week_number=1, total_days=5):
    """
    Alternative method to push data from a pandas DataFrame.
    This function can be called from an interactive shell.
    
    Args:
        df: pandas DataFrame with the report data
        week_number: week number (default: 1)
        total_days: total working days (default: 5)
    """
    import pandas as pd
    
    try:
        # Delete existing data for this date
        deleted_count, _ = UtilizationReportModel.objects.filter(date=TARGET_DATE).delete()
        logger.info(f"Deleted {deleted_count} existing records for {TARGET_DATE}")
        
        # Ensure required columns
        for col in ['Resource Email Address', 'Billing']:
            if col not in df.columns:
                if col == 'Billing':
                    df['Billing'] = 'TBD'
                else:
                    logger.error(f"Required column {col} missing from DataFrame")
                    return False
        
        # Set Last Week to 0 for week 1
        df['Last Week'] = 0
        
        # Calculate Total Logged (for week 1, just billable hours + vacation)
        billable_col = 'Billable Hours' if 'Billable Hours' in df.columns else 'WTD Actuals'
        if billable_col == 'WTD Actuals' and 'Billable Hours' not in df.columns:
            df['Billable Hours'] = df['WTD Actuals'] * 8
            
        if 'Vacation' not in df.columns:
            df['Vacation'] = 0
            
        df['Total Logged'] = df['Billable Hours'].fillna(0) + df['Vacation'].fillna(0)
        
        # Calculate Additional Days based on billing type
        df['Additional Days'] = 0
        df['Billing'] = df['Billing'].fillna('TBD').astype(str)
        
        # For Billing type
        billing_mask = df['Billing'] == 'Billing'
        if any(billing_mask):
            shortfall = total_days - df.loc[billing_mask, 'Total Logged']
            df.loc[billing_mask, 'Additional Days'] = shortfall.clip(lower=0).astype('int64')
        
        # For Partial type
        partial_mask = df['Billing'] == 'Partial'
        if any(partial_mask):
            partial_days = total_days / 2
            shortfall_partial = partial_days - df.loc[partial_mask, 'Total Logged']
            df.loc[partial_mask, 'Additional Days'] = shortfall_partial.clip(lower=0).astype('int64')
            
        # Prepare records for bulk insert
        records_to_save = []
        
        for _, row in df.iterrows():
            # Get resource email safely
            resource_email = row.get('Resource Email Address', '')
            if not resource_email or pd.isna(resource_email):
                continue
                
            # Use lowercase email for consistency
            if isinstance(resource_email, str):
                resource_email = resource_email.lower()
            
            # Get RDM value safely
            rdm_value = row.get('RDM', row.get('rdm', 'Adam'))
            if not rdm_value or pd.isna(rdm_value):
                rdm_value = 'Adam'
                
            # Get Track value safely
            track_value = row.get('Track', row.get('track', ''))
            if pd.isna(track_value):
                track_value = ''
                
            # Get Billing value safely
            billing_value = row.get('Billing', row.get('billing', 'TBD'))
            if not billing_value or pd.isna(billing_value):
                billing_value = 'TBD'
            
            # Create the model instance with all relevant fields
            records_to_save.append(UtilizationReportModel(
                resource_email_address=resource_email,
                administrative=safe_float(row.get('Administrative', 0)),
                billable_hours=safe_float(row.get('Billable Hours', 0)),
                department_mgmt=safe_float(row.get('Department Mgmt', 0)),
                investment=safe_float(row.get('Investment', 0)),
                presales=safe_float(row.get('Presales', 0)),
                training=safe_float(row.get('Training', 0)),
                unassigned=safe_float(row.get('Unassigned', 0)),
                vacation=safe_float(row.get('Vacation', 0)),
                grand_total=safe_float(row.get('Grand Total', 0)),
                last_week=0,  # For week 1, set to 0
                total_logged=safe_float(row.get('Total Logged', 0)),
                status='open',  # Default status
                addtnl_days=safe_float(row.get('Additional Days', 0)),
                wtd_actuals=safe_float(row.get('WTD Actuals', 0)),
                rdm=rdm_value,
                track=track_value,
                billing=billing_value,
                spoc=rdm_value,  # SPOC is the same as RDM
                comments='',
                spoc_comments='',
                date=parse_date(TARGET_DATE)
            ))
        
        # Bulk insert the records
        if records_to_save:
            UtilizationReportModel.objects.bulk_create(records_to_save, batch_size=500)
            logger.info(f"Successfully imported {len(records_to_save)} records for {TARGET_DATE}")
            return True
        else:
            logger.warning("No records to import")
            return False
            
    except Exception as e:
        logger.error(f"Error pushing DataFrame data: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # This will run when executed via Django shell
    logger.info("Starting direct data import...")
    success = push_direct_data()
    if success:
        logger.info("Direct data import completed successfully")
    else:
        logger.error("Direct data import failed") 