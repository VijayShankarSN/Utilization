import pandas as pd
import os
from datetime import datetime
from django.conf import settings
from .models import UtilizationReportModel
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render
from django.http import JsonResponse

def process_excel_file(request, file):
    fs = FileSystemStorage()
    filename = fs.save(file.name, file)
    uploaded_file_url = fs.url(filename)
    return uploaded_file_url

def get_available_dates():
    """Get list of available report dates."""
    dates = UtilizationReportModel.objects.values_list('date', flat=True).distinct().order_by('-date')
    return [date.strftime('%Y-%m-%d') for date in dates]

def get_report_for_date(date):
    """
    Get reports for a specific date.
    
    Args:
        date: Date to retrieve reports for (YYYY-MM-DD format)
        
    Returns:
        QuerySet of UtilizationReportModel objects
    """
    try:
        # Make sure we're retrieving the ID field to enable edit functionality
        reports = UtilizationReportModel.objects.filter(date=date).order_by('resource_email_address')
        return reports
    except Exception:
        return None

def get_report_for_date_html(date):
    try:
        # Get all reports for the selected date
        reports = UtilizationReportModel.objects.filter(date=date)
        
        if not reports.exists():
            return None
            
        # Convert to DataFrame
        data = []
        for report in reports:
            data.append({
                'Resource Email Address': report.resource_email_address,
                'Administrative': report.administrative,
                'Billable Hours': report.billable_hours,
                'Department Mgmt': report.department_mgmt,
                'Investment': report.investment,
                'Presales': report.presales,
                'Training': report.training,
                'Unassigned': report.unassigned,
                'Vacation': report.vacation,
                'Grand Total': report.grand_total,
                'Last Week': report.last_week,
                'Total Logged': report.total_logged,
                'Additional Days': report.addtnl_days,
                'RDM': report.rdm,
                'Track': report.track,
                'Billing': report.billing,
                'Status': report.status
            })
        
        df = pd.DataFrame(data)
        
        # Convert to HTML table
        html_table = df.to_html(
            classes='table table-hover table-striped',
            index=False,
            border=0,
            justify='left'
        )
        
        return html_table
    except Exception as e:
        print(f"Error processing report: {e}")
        return None 