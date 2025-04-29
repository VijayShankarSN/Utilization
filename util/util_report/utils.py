import pandas as pd
import os
from datetime import datetime
from django.conf import settings
from .models.utilrepo import UtilizationReport

def process_excel_file(file):
    # Your existing process_excel_file function
    pass

def get_available_dates():
    # Get unique dates from the UtilizationReport model
    dates = UtilizationReport.objects.values_list('date', flat=True).distinct()
    # Convert dates to strings and sort in descending order
    date_strings = [date.strftime('%Y-%m-%d') for date in dates if date is not None]
    return sorted(date_strings, reverse=True)

def get_report_for_date(date):
    try:
        # Get all reports for the selected date
        reports = UtilizationReport.objects.filter(date=date)
        
        if not reports.exists():
            return None
            
        # Convert to DataFrame
        data = []
        for report in reports:
            data.append({
                'Resource Email Address': report.name,
                'Administrative': report.administrative,
                'Billable Hours': report.billable_days,
                'Training': report.training,
                'Unassigned': report.unassigned,
                'Vacation': report.vacation,
                'Grand Total': report.grand_total,
                'Last Week': report.last_week,
                'Status': report.status,
                'Additional Days': report.addtnl_days,
                'WTD Actual': report.wtd_actual,
                'Track': report.track,
                'Billing': report.billing
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