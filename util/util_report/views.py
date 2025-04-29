from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_date
from .new_main import UtilizationReportGenerator
from .forms import UploadFileForm
from .utils import process_excel_file, get_available_dates, get_report_for_date
from django.urls import reverse
from .models import UtilizationReportModel, UtilizationHistoryModel
from django.views.decorators.http import require_http_methods
import json
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import os
from django.contrib import messages
from bs4 import BeautifulSoup
import threading
import time
import shutil
from django.conf import settings
import logging
from django.db import models
import random

# Configure logger
logger = logging.getLogger(__name__)

# Global dictionary to keep track of files that need to be deleted
files_to_cleanup = {}

def cleanup_files():
    """
    Cleanup function to delete files safely with retries.
    """
    files_to_remove = dict(files_to_cleanup)
    
    for file_path, timestamp in files_to_remove.items():
        # Only attempt to delete files that were created more than 60 seconds ago
        if time.time() - timestamp > 60:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Successfully deleted: {file_path}")
                    del files_to_cleanup[file_path]
            except PermissionError:
                print(f"File still in use, will retry later: {file_path}")
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
                del files_to_cleanup[file_path]

def upload_file(request):
    """
    Main landing page with file upload form.
    """
    dates = get_available_dates()
    return render(request, 'util_report/upload.html', {
        'dates': dates,
        'upload_form': UploadFileForm()
    })

def save_to_database_background(file_path, report_date=None, request=None):
    """
    Save the extracted data to the database in the background.
    This function is called asynchronously to avoid blocking the user interface.
    Now also accepts a request parameter to update the session when save is complete.
    """
    try:
        # Delete existing data for this date if specified
        if report_date:
            deleted_count, _ = UtilizationReportModel.objects.filter(date=report_date).delete()
            print(f"Deleted {deleted_count} existing records for date {report_date}")
        
        # Generate and save report
        report_generator = UtilizationReportGenerator(file_path)
        report_generator.generate_final_report()
        report_generator.save_to_model()
        
        # Mark file for cleanup instead of immediate deletion
        files_to_cleanup[file_path] = time.time()
        print(f"Background database save completed for date: {report_date}")
        
        # Run cleanup routine to safely delete files when possible
        cleanup_files()
        
        # After all saving operations are complete, set a flag in the session if request is provided
        if request and report_date:
            # Check if report_date is already a string or datetime object
            date_str = report_date
            if hasattr(report_date, 'strftime'):  # It's a datetime object
                date_str = report_date.strftime('%Y-%m-%d')
                
            # Store the date in session to indicate this date's data has been saved
            request.session['background_save_complete'] = date_str
            request.session.modified = True
            
        print("Data saved to database successfully in background.")
        return True
    except Exception as e:
        print(f"Error saving to database in background: {e}")
        # Still mark file for cleanup even if there's an error
        files_to_cleanup[file_path] = time.time()
        return False

def extract_data_view(request):
    """
    Handle file uploads and extract data from Excel files.
    """
    # Run cleanup routine at the start of request
    cleanup_files()
    
    # Check if we're processing an update confirmation
    if request.method == 'POST' and request.POST.get('confirm_update') == 'true':
        # Get the file path from session
        file_path = request.session.get('temp_file_path')
        if not file_path:
            return render(request, 'util_report/upload.html', {
                'error_message': "File session expired. Please upload again.",
                'upload_form': UploadFileForm(),
                'dates': get_available_dates()
            })
        
        try:
            # Make a copy of the file to avoid file locking issues
            file_name = os.path.basename(file_path)
            temp_copy_path = os.path.join(os.path.dirname(file_path), f"temp_copy_{file_name}")
            
            try:
                shutil.copy2(file_path, temp_copy_path)
            except Exception as e:
                return render(request, 'util_report/upload.html', {
                    'error_message': f"Error creating file copy: {str(e)}",
                    'upload_form': UploadFileForm(),
                    'dates': get_available_dates()
                })
            
            # Get the date to clean existing data
            report_date = request.session.get('report_date')
            
            # Generate report first without saving to database
            report_generator = UtilizationReportGenerator(temp_copy_path)
            final_df = report_generator.generate_final_report()
            
            # Store the current date in session for navigation purposes
            request.session['current_report_date'] = report_generator.file_date
            
            # Store DataFrame as JSON in session
            request.session['report_data'] = final_df.to_json(orient='records')
            
            # Clean up temp file path session variable
            if 'temp_file_path' in request.session:
                del request.session['temp_file_path']
            
            # Format numeric columns to limit decimal places
            for col in final_df.select_dtypes(include=['float', 'float32', 'float64']).columns:
                final_df[col] = final_df[col].round(2)
            
            # Convert data to HTML table with improved styling
            report_html = final_df.to_html(classes='table table-striped table-bordered', index=False)
            
            # Process the HTML to add better column formatting
            soup = BeautifulSoup(report_html, 'html.parser')
            
            # Add data-type attributes to cells for proper formatting
            for i, col in enumerate(final_df.columns):
                # Find all header cells
                th = soup.find('thead').find_all('th')[i]
                th['class'] = th.get('class', []) + ['py-2']
                
                # Check column data type and apply appropriate classes
                if pd.api.types.is_numeric_dtype(final_df[col].dtype):
                    th['class'] = th.get('class', []) + ['text-end', 'px-3']
                    # Apply to all cells in this column
                    for td in soup.find('tbody').find_all('tr'):
                        cells = td.find_all('td')
                        if i < len(cells):
                            cells[i]['class'] = cells[i].get('class', []) + ['text-end', 'px-3']
                else:
                    th['class'] = th.get('class', []) + ['text-start', 'px-3']
                    # Apply to all cells in this column
                    for td in soup.find('tbody').find_all('tr'):
                        cells = td.find_all('td')
                        if i < len(cells):
                            cells[i]['class'] = cells[i].get('class', []) + ['text-start', 'px-3']
            
            report_html = str(soup)
            
            # Start background thread to save to database
            bg_thread = threading.Thread(
                target=save_to_database_background,
                args=(temp_copy_path, report_date, request)
            )
            bg_thread.daemon = True
            bg_thread.start()
            
            messages.success(request, f'Report generated for {report_generator.file_date}. Data is being saved in the background.')
            
            return render(request, 'util_report/result.html', {
                'report_html': report_html,
                'has_data': True,
                'current_date': report_generator.file_date,
                'saving_in_background': True
            })
        except Exception as e:
            # Mark file for cleanup
            if file_path and os.path.exists(file_path):
                files_to_cleanup[file_path] = time.time()
            
            error_message = f"An error occurred while extracting data: {str(e)}"
            return render(request, 'util_report/upload.html', {
                'error_message': error_message,
                'upload_form': UploadFileForm(),
                'dates': get_available_dates()
            })
    
    # Normal file upload flow
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        fs = FileSystemStorage()
        file_path = fs.save(file.name, file)
        full_file_path = fs.path(file_path)

        try:
            # Make a copy of the file to avoid file locking issues
            file_name = os.path.basename(full_file_path)
            temp_copy_path = os.path.join(os.path.dirname(full_file_path), f"temp_copy_{file_name}")
            
            try:
                shutil.copy2(full_file_path, temp_copy_path)
            except Exception as e:
                # Mark original file for cleanup
                files_to_cleanup[full_file_path] = time.time()
                
                return render(request, 'util_report/upload.html', {
                    'error_message': f"Error creating file copy: {str(e)}",
                    'upload_form': UploadFileForm(),
                    'dates': get_available_dates()
                })
            
            # First process the file to determine its date without saving to DB
            report_generator = UtilizationReportGenerator(temp_copy_path)
            
            # Parse the date from the file to check for existing data
            report_generator.parse_date_from_filename()
            report_date = report_generator.file_date
            
            # Store the current date in session for navigation purposes
            request.session['current_report_date'] = report_date
            
            # Check if data for this date already exists
            existing_data = UtilizationReportModel.objects.filter(date=report_date).exists()
            
            # If data exists, ask for confirmation
            if existing_data:
                # Store file path and date in session for the confirmation flow
                request.session['temp_file_path'] = full_file_path
                request.session['report_date'] = report_date
                
                # Mark temp copy for cleanup
                files_to_cleanup[temp_copy_path] = time.time()
                
                return render(request, 'util_report/confirm_update.html', {
                    'report_date': report_date,
                    'dates': get_available_dates()
                })
            
            # If no existing data, proceed to generate the report first
            final_df = report_generator.generate_final_report()
            
            # Store DataFrame as JSON in session
            request.session['report_data'] = final_df.to_json(orient='records')

            # Format numeric columns to limit decimal places
            for col in final_df.select_dtypes(include=['float', 'float32', 'float64']).columns:
                final_df[col] = final_df[col].round(2)
            
            # Convert data to HTML table with improved styling
            report_html = final_df.to_html(classes='table table-striped table-bordered', index=False)
            
            # Process the HTML to add better column formatting
            soup = BeautifulSoup(report_html, 'html.parser')
            
            # Add data-type attributes to cells for proper formatting
            for i, col in enumerate(final_df.columns):
                # Find all header cells
                th = soup.find('thead').find_all('th')[i]
                th['class'] = th.get('class', []) + ['py-2']
                
                # Check column data type and apply appropriate classes
                if pd.api.types.is_numeric_dtype(final_df[col].dtype):
                    th['class'] = th.get('class', []) + ['text-end', 'px-3']
                    # Apply to all cells in this column
                    for td in soup.find('tbody').find_all('tr'):
                        cells = td.find_all('td')
                        if i < len(cells):
                            cells[i]['class'] = cells[i].get('class', []) + ['text-end', 'px-3']
                else:
                    th['class'] = th.get('class', []) + ['text-start', 'px-3']
                    # Apply to all cells in this column
                    for td in soup.find('tbody').find_all('tr'):
                        cells = td.find_all('td')
                        if i < len(cells):
                            cells[i]['class'] = cells[i].get('class', []) + ['text-start', 'px-3']
            
            report_html = str(soup)
            
            # Start background thread to save to database
            bg_thread = threading.Thread(
                target=save_to_database_background,
                args=(temp_copy_path, report_date, request)
            )
            bg_thread.daemon = True
            bg_thread.start()
            
            # Mark original file for cleanup
            files_to_cleanup[full_file_path] = time.time()

            messages.success(request, f'Report generated for {report_date}. Data is being saved in the background.')

            return render(request, 'util_report/result.html', {
                'report_html': report_html,
                'has_data': True,
                'current_date': report_date,
                'saving_in_background': True
            })

        except Exception as e:
            # Mark files for cleanup
            if os.path.exists(full_file_path):
                files_to_cleanup[full_file_path] = time.time()
            
            error_message = f"An error occurred while extracting data: {str(e)}"
            return render(request, 'util_report/upload.html', {
                'error_message': error_message,
                'upload_form': UploadFileForm(),
                'dates': get_available_dates()
            })

    return render(request, 'util_report/upload.html', {
        'upload_form': UploadFileForm(),
        'dates': get_available_dates()
    })

def view_reports(request):
    """
    View all reports for a given date.
    """
    # Try to get the date from request query parameters
    query_date = request.GET.get('date')
    
    # If no date in query parameters, try to get from session
    if not query_date:
        query_date = request.session.get('current_report_date')
    
    # If still no date, use current date
    selected_date = query_date or datetime.now().strftime('%Y-%m-%d')
    
    # Store the selected date in session
    request.session['current_report_date'] = selected_date
    
    # Get list of available dates for the dropdown
    available_dates = list(UtilizationReportModel.objects.values_list('date', flat=True).distinct().order_by('-date'))
    
    try:
        # Get all fields that we want to retrieve
        fields_to_retrieve = [
            'resource_email_address', 'administrative', 'billable_hours',
            'department_mgmt', 'training', 'unassigned', 'vacation', 'grand_total',
            'status', 'addtnl_days', 'wtd_actuals', 'comments',
            'spoc_comments', 'rdm', 'track', 'billing', 'dams_utilization', 
            'capable_utilization', 'individual_utilization'
        ]
        
        # Retrieve records for the selected date
        reports = UtilizationReportModel.objects.filter(date=selected_date)
        
        # Get unique values for filters
        rdms = list(UtilizationReportModel.objects.filter(date=selected_date).exclude(rdm='').values_list('rdm', flat=True).distinct().order_by('rdm'))
        tracks = list(UtilizationReportModel.objects.filter(date=selected_date).exclude(track='').values_list('track', flat=True).distinct().order_by('track'))
        
        # Get DAMS utilization, capable utilization, and individual utilization for the selected date
        first_report = reports.first()
        dams_utilization = first_report.dams_utilization if first_report else 0
        capable_utilization = first_report.capable_utilization if first_report else 0
        
        # Calculate average individual utilization
        individual_utilization = reports.aggregate(avg_individual=models.Avg('individual_utilization'))['avg_individual'] or 0
        
        # If no reports found, show the no data template
        if not reports.exists():
            context = {
                'date': selected_date,
                'selected_date': selected_date,
                'available_dates': available_dates,
                'rdms': rdms,
                'tracks': tracks,
                'dams_utilization': dams_utilization,
                'capable_utilization': capable_utilization,
                'individual_utilization': individual_utilization,
                'debug_info': {
                    'total_records': UtilizationReportModel.objects.count(),
                    'all_dates': available_dates,
                    'db_table': UtilizationReportModel._meta.db_table,
                    'available_fields': [f.name for f in UtilizationReportModel._meta.get_fields()]
                }
            }
            return render(request, 'util_report/no_data.html', context)
        
        # Convert queryset to list of dictionaries
        data = []
        for report in reports:
            report_data = {
                'Resource Email Address': report.resource_email_address,
                'Administrative': report.administrative or 0,
                'Billable Hours': report.billable_hours or 0,
                'Department Mgmt': report.department_mgmt or 0,
                'Training': report.training or 0,
                'Unassigned': report.unassigned or 0,
                'Vacation': report.vacation or 0,
                'Grand Total': report.grand_total or 0,
                'Status': report.status or 'open',
                'Additional Days': report.addtnl_days or 0,
                'WTD Actuals': report.wtd_actuals or 0,
                'Comments': report.comments or '',
                'SPOC Comments': report.spoc_comments or '',
                'RDM': report.rdm or '',
                'Track': report.track or '',
                'Billing': report.billing or 'TBD',
                'Individual Utilization': report.individual_utilization or 0
            }
            data.append(report_data)
        
        # Convert to DataFrame for HTML rendering
        df = pd.DataFrame(data)
        
        # Format numeric columns
        numeric_columns = ['Administrative', 'Billable Hours', 'Department Mgmt', 'Training',
                         'Unassigned', 'Vacation', 'Grand Total', 'Additional Days',
                         'WTD Actuals', 'Individual Utilization']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].round(2)
        
        # Convert DataFrame to HTML
        table_html = df.to_html(
            classes='table table-hover table-striped',
            index=False,
            float_format=lambda x: '{:.2f}'.format(x) if pd.notnull(x) else ''
        )
        
        # Add data attributes for filtering
        soup = BeautifulSoup(table_html, 'html.parser')
        
        # Add ID to table
        table = soup.find('table')
        if table:
            table['id'] = 'reportTable'
        
        # Add data attributes to cells
        for row in soup.find_all('tr')[1:]:  # Skip header row
            cells = row.find_all('td')
            if len(cells) >= 14:  # Make sure we have enough cells
                cells[11]['data-rdm'] = cells[11].text  # RDM column
                cells[12]['data-track'] = cells[12].text  # Track column
                cells[13]['data-billing'] = cells[13].text  # Billing column
        
        report_html = str(soup)
        
        # Prepare context for template
        context = {
            'reports': data,
            'report_data': report_html,
            'date': selected_date,
            'selected_date': selected_date,
            'available_dates': available_dates,
            'rdms': rdms,
            'tracks': tracks,
            'dams_utilization': dams_utilization,
            'capable_utilization': capable_utilization,
            'individual_utilization': individual_utilization
        }
        
        return render(request, 'util_report/view_reports.html', context)
    
    except Exception as e:
        error_msg = str(e)
        messages.error(request, f'Error viewing reports: {error_msg}')
        context = {
            'error': error_msg,
            'date': selected_date,
            'selected_date': selected_date,
            'available_dates': available_dates,
            'rdms': [],
            'tracks': [],
            'dams_utilization': 0,
            'capable_utilization': 0,
            'individual_utilization': 0,
            'debug_info': {
                'total_records': UtilizationReportModel.objects.count(),
                'all_dates': available_dates,
                'db_table': UtilizationReportModel._meta.db_table,
                'available_fields': [f.name for f in UtilizationReportModel._meta.get_fields()]
            }
        }
        return render(request, 'util_report/error.html', context)

@require_http_methods(["POST"])
def close_cases(request):
    """
    Close one or more open cases and add a closing reason.
    """
    try:
        # Check if it's a JSON request
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            case_ids = data.get('case_ids', [])
            reason = data.get('reason', '')
            date = data.get('date')
        else:
            # Handle regular form submission
            case_ids = request.POST.getlist('case_ids', [])
            reason = request.POST.get('reason', '')
            date = request.POST.get('date')
        
        if not case_ids:
            return JsonResponse({'success': False, 'error': 'No cases selected'})
            
        # Update all selected cases
        updated_count = 0
        for case_id in case_ids:
            try:
                case = UtilizationReportModel.objects.get(id=case_id)
                # Only update if case is open
                if case.status == 'open':
                    # Record history before making changes
                    UtilizationHistoryModel.objects.create(
                        report_date=case.date,
                        resource_email=case.resource_email_address,
                        action='closed',
                        details=f"Case closed with reason: {reason}",
                        field_name='status',
                        previous_value=case.status,
                        new_value='close'
                    )
                    
                    case.status = 'close'
                    case.comments = f"{case.comments or ''}{' ' if case.comments else ''}[Closed: {reason}]".strip()
                    case.save()
                    updated_count += 1
            except UtilizationReportModel.DoesNotExist:
                continue
        
        # Return success response
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'closed_count': updated_count,
                'message': f'Successfully closed {updated_count} cases'
            })
        else:
            messages.success(request, f'Successfully closed {updated_count} cases')
            return redirect(f'/util-leakage/?date={date}')
            
    except Exception as e:
        error_msg = f"Error closing cases: {str(e)}"
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': error_msg})
        else:
            messages.error(request, error_msg)
            return redirect(f'/util-leakage/?date={date}')

@require_http_methods(["POST"])
def update_comments(request):
    """
    Update comments for a specific report entry.
    """
    try:
        data = json.loads(request.body)
        report_id = data.get('id')
        field = data.get('field')
        value = data.get('value')

        if field not in ['comments', 'spoc_comments']:
            return JsonResponse({'success': False, 'error': 'Invalid field'})

        report = UtilizationReportModel.objects.get(id=report_id)
        
        # Record history before making changes
        previous_value = getattr(report, field, '')
        UtilizationHistoryModel.objects.create(
            report_date=report.date,
            resource_email=report.resource_email_address,
            action='edited',
            details=f"{field.replace('_', ' ').title()} updated",
            field_name=field,
            previous_value=previous_value,
            new_value=value
        )
        
        setattr(report, field, value)
        report.save()

        return JsonResponse({'success': True})
    except UtilizationReportModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Report not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def download_result(request):
    """
    Download current session's report as Excel.
    """
    try:
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if 'report_data' in request.session:
                report_df = pd.read_json(request.session['report_data'])
                columns = [
                    'resource_email_address', 'administrative', 'billable_hours',
                    'department_mgmt', 'investment', 'presales', 'training',
                    'unassigned', 'vacation', 'grand_total', 'last_week',
                    'total_logged', 'addtnl_days', 'rdm', 'track', 'billing',
                    'status', 'date'
                ]
                report_df = report_df[columns]
                report_df.to_excel(writer, sheet_name='Utilization Report', index=False)
        
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename=utilization_report_{timestamp}.xlsx'
        
        return response
    except Exception as e:
        return HttpResponse(f"Error generating Excel file: {str(e)}", status=500)

def download_report(request):
    """
    Download specific date's report as Excel.
    """
    date = request.GET.get('date')
    if not date:
        return HttpResponse("No date selected", status=400)

    try:
        # Get all records for the date
        reports = UtilizationReportModel.objects.filter(date=date)
        
        if not reports.exists():
            return HttpResponse("No data found for selected date", status=404)
        
        data = []
        for report in reports:
            data.append({
                'Resource Email Address': report.resource_email_address,
                'Administrative': report.administrative or 0,
                'Billable Hours': report.billable_hours or 0,
                'Department Mgmt': report.department_mgmt or 0,
                'Training': report.training or 0,
                'Unassigned': report.unassigned or 0,
                'Vacation': report.vacation or 0,
                'Grand Total': report.grand_total or 0,
                'Last Week': report.last_week or 0,
                'Total Logged': report.total_logged or 0,
                'Additional Days': report.addtnl_days or 0,
                'WTD Actuals': report.wtd_actuals or 0,
                'RDM': report.rdm or '',
                'Track': report.track or '',
                'Billing': report.billing or 'TBD',
                'Status': report.status or 'open',
                'Comments': report.comments or '',
                'SPOC Comments': report.spoc_comments or ''
            })
        
        # Create DataFrame and format numeric columns
        df = pd.DataFrame(data)
        numeric_columns = ['Administrative', 'Billable Hours', 'Department Mgmt', 'Training',
                         'Unassigned', 'Vacation', 'Grand Total', 'Last Week', 'Total Logged',
                         'Additional Days', 'WTD Actuals']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].round(2)
        
        # Create Excel file
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Report')
        
        # Prepare response
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=utilization_report_{date}.xlsx'
        
        return response
        
    except Exception as e:
        return HttpResponse(f"Error generating report: {str(e)}", status=500)

def util_leakage(request):
    """
    Display utilization leakage data.
    """
    # Try to get the date from request query parameters
    query_date = request.GET.get('date')
    
    # If no date in query parameters, try to get from session
    if not query_date:
        query_date = request.session.get('current_report_date')
    
    # Get all available dates for the dropdown
    dates = get_available_dates()
    
    # If still no date and dates are available, use the latest date
    if not query_date and dates:
        query_date = dates[0] if isinstance(dates, list) and dates else None
    
    # If we have a date, store it in session
    if query_date:
        request.session['current_report_date'] = query_date
        
    date = query_date
        
    if not date:
        return render(request, 'util_report/util_leakage.html', {
            'dates': dates,
            'dams_utilization': 0,
            'capable_utilization': 0,
            'debug_info': {
                'message': 'No date selected and no dates available',
                'available_dates': dates
            }
        })

    try:
        # Calculate previous week date
        current_date = datetime.strptime(date, '%Y-%m-%d')
        prev_week_date = (current_date - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Get current open cases
        current_open_count = UtilizationReportModel.objects.filter(
            date=date,
            status='open'
        ).count()
        
        # Get previous week's open cases
        last_week_open_count = UtilizationReportModel.objects.filter(
            date=prev_week_date,
            status='open'
        ).count()
        
        # Get handled cases this week (cases that were closed this week from util leakage)
        current_handled_count = UtilizationReportModel.objects.filter(
            date=date,
            status='close',
            comments__contains='[Closed:'  # This indicates it was closed from util leakage tab
        ).count()
        
        # Get handled cases last week (cases that were closed from util leakage last week)
        last_week_handled_count = UtilizationReportModel.objects.filter(
            date=prev_week_date,
            status='close',
            comments__contains='[Closed:'  # This indicates it was closed from util leakage tab
        ).count()

        # Get DAMS utilization for the selected date
        first_report = UtilizationReportModel.objects.filter(date=date).first()
        dams_utilization = first_report.dams_utilization if first_report else 0
        capable_utilization = first_report.capable_utilization if first_report else 0

        # Get the field names from the model to check what fields exist
        model_fields = [f.name for f in UtilizationReportModel._meta.get_fields()]
        
        # Create a list of fields that exist in the model
        fields_to_retrieve = ['id', 'resource_email_address']
        for field in ['administrative', 'billable_hours', 'department_mgmt', 'training', 'unassigned', 
                    'vacation', 'grand_total', 'status', 'addtnl_days', 
                    'wtd_actuals', 'rdm', 'track', 'billing']:
            if field in model_fields:
                fields_to_retrieve.append(field)
        
        # Query open cases for current date
        reports = UtilizationReportModel.objects.filter(
            date=date,
            status='open'
        ).values(*fields_to_retrieve)
        
        data = []
        for report in reports:
            entry = {
                'ID': report['id'],
                'Resource': report['resource_email_address'],
                'Administrative': report.get('administrative', 0),
                'Billable Hours': report.get('billable_hours', 0),
                'Department Mgmt': report.get('department_mgmt', 0),
                'Training': report.get('training', 0),
                'Unassigned': report.get('unassigned', 0),
                'Vacation': report.get('vacation', 0),
                'Grand Total': report.get('grand_total', 0),
                'Status': report.get('status', 'open'),
                'Additional Days': report.get('addtnl_days', 0),
                'WTD Actuals': report.get('wtd_actuals', 0),
                'RDM': report.get('rdm', ''),
                'Track': report.get('track', ''),
                'Billing': report.get('billing', '')
            }
            data.append(entry)
        
        report_html = ""
        if data:
            df = pd.DataFrame(data)
            display_columns = [col for col in df.columns if col != 'ID']
            df_display = df[display_columns]
            html_table = df_display.to_html(classes='table table-hover table-striped', index=False)
            
            soup = BeautifulSoup(html_table, 'html.parser')
            
            for i, row in enumerate(soup.find('tbody').find_all('tr')):
                if i < len(data):
                    row_id = data[i]['ID']
                    row['data-id'] = str(row_id)
            
            report_html = str(soup)
    
        return render(request, 'util_report/util_leakage.html', {
            'report_html': report_html,
            'selected_date': date,
            'dates': dates,
            'current_open_count': current_open_count,
            'last_week_open_count': last_week_open_count,
            'current_handled_count': current_handled_count,
            'last_week_handled_count': last_week_handled_count,
            'dams_utilization': dams_utilization,
            'capable_utilization': capable_utilization
        })
    except Exception as e:
        return render(request, 'util_report/util_leakage.html', {
            'error_message': f"SError retrieving data: {str(e)}",
            'dates': get_available_dates(),
            'dams_utilization': 0,
            'capable_utilization': 0
        })

def download_util_leakage(request):
    """
    Download utilization leakage report as Excel.
    """
    date = request.GET.get('date')
    if not date:
        return HttpResponse("No date selected", status=400)

    try:
        # Get the field names from the model to check what fields exist
        model_fields = [f.name for f in UtilizationReportModel._meta.get_fields()]
        
        # Create a list of fields that exist in the model - exclude specified fields
        fields_to_retrieve = ['resource_email_address']
        for field in ['administrative', 'billable_hours', 'department_mgmt', 'training', 'unassigned', 
                    'vacation', 'grand_total', 'status', 'addtnl_days', 
                    'wtd_actuals', 'rdm', 'track', 'billing']:
            if field in model_fields:
                fields_to_retrieve.append(field)
        
        # Query with only the fields that exist
        reports = UtilizationReportModel.objects.filter(
            date=date,
            status='open'
        ).values(*fields_to_retrieve)
        
        data = []
        for report in reports:
            entry = {
                'Name': report['resource_email_address'],
                'Administrative': report.get('administrative', 0),
                'Billable Days': report.get('billable_hours', 0),
                'Department Mgmt': report.get('department_mgmt', 0),
                'Training': report.get('training', 0),
                'Unassigned': report.get('unassigned', 0),
                'Vacation': report.get('vacation', 0),
                'Grand Total': report.get('grand_total', 0),
                'Status': report.get('status', 'open'),
                'Additional Days': report.get('addtnl_days', 0),
                'WTD Actual': report.get('wtd_actuals', 0),
                'RDM': report.get('rdm', ''),
                'Track': report.get('track', ''),
                'Billing': report.get('billing', '')
            }
            data.append(entry)
        
        if not data:
            return HttpResponse("No utilization leakage data found for the selected date", status=404)
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Util Leakage Report', index=False)
        
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=util_leakage_report_{date}.xlsx'
        
        return response
    except Exception as e:
        return HttpResponse(f"Error generating Excel file: {str(e)}", status=500)

def date_extraction(request, extraction_date=None):
    """
    Extract data from Excel file for each date.
    """
    # If extraction_date is passed in the URL
    if extraction_date:
        selected_date = extraction_date
    else:
        # Otherwise get from POST or use today's date as default
        selected_date = request.POST.get('date') or datetime.now().strftime('%Y-%m-%d')
    
    # Get file path for the selected date
    file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', f'util_report_{selected_date}.xlsx')
    
    # Check if file exists
    if not os.path.exists(file_path):
        messages.error(request, f"No file found for date {selected_date}")
        # Redirect to upload page if file not found
        return redirect('upload')
    
    try:
        # Check if data already exists for this date
        existing_data = UtilizationReportModel.objects.filter(date=selected_date).exists()
        
        if existing_data and request.method != 'POST':
            # If data exists and not a POST request, show confirmation page
            return render(request, 'util_report/confirm_update.html', {'date': selected_date})
        
        if existing_data and 'view_only' in request.POST:
            # User chose to view existing data
            return redirect(f'/view-reports/?date={selected_date}')
        
        if existing_data and 'update' in request.POST:
            # User confirmed to update, so delete old data
            UtilizationReportModel.objects.filter(date=selected_date).delete()
        
        # Read Excel file using pandas
        df = pd.read_excel(file_path)
        
        # Get a list of available fields in the model
        model_fields = [f.name for f in UtilizationReportModel._meta.get_fields()]
        field_defaults = {
            'resource_email_address': '',
            'administrative': 0,
            'billable_hours': 0, 
            'department_mgmt': 0,
            'training': 0,
            'unassigned': 0,
            'vacation': 0,
            'grand_total': 0,
            'last_week': 0,
            'status': 'open',
            'addtnl_days': 0,
            'wtd_actuals': 0,
            'spoc': '',
            'comments': '',
            'spoc_comments': '',
            'rdm': '',
            'track': '',
            'billing': '',
            'total_logged': 0
        }
        
        # Extract and save data
        for _, row in df.iterrows():
            record_data = {'date': selected_date}
            
            # Map DataFrame columns to model fields with defaults for missing fields
            for field, default in field_defaults.items():
                if field in model_fields:
                    # Handle case sensitivity in column names
                    col_matches = [col for col in df.columns if col.lower().replace(' ', '_') == field.lower()]
                    if col_matches:
                        value = row.get(col_matches[0], default)
                        # Convert NaN to appropriate default value
                        if pd.isna(value):
                            value = default
                        record_data[field] = value
                    else:
                        record_data[field] = default
            
            # Create record
            UtilizationReportModel.objects.create(**record_data)
        
        messages.success(request, f'Data for {selected_date} extracted and saved successfully!')
        return redirect(f'/view-reports/?date={selected_date}')
    
    except Exception as e:
        error_msg = str(e)
        messages.error(request, f'Error extracting data: {error_msg}')
        return redirect('upload')

@require_http_methods(["GET"])
def get_history_data(request):
    # Check if this is a save status check
    if request.GET.get('check_save_status'):
        date_str = request.GET.get('date')
        save_complete = False
        
        if date_str:
            # Check if the save is complete by looking for records with this date
            try:
                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                # Fix: Use the correct model name that's used throughout the code (from UtilizationReportModel)
                report_count = UtilizationReportModel.objects.filter(date=report_date).count()
                
                # If we have records, consider the save complete
                save_complete = report_count > 0
                
                # Check if background task is complete by looking at the session
                if request.session.get('background_save_complete') == date_str:
                    save_complete = True
                    # Clear the session flag
                    del request.session['background_save_complete']
                    request.session.modified = True
            except Exception as e:
                print(f"Error checking save status: {e}")
        
        return JsonResponse({'save_complete': save_complete})
    
    try:
        date_filter = request.GET.get('date', '')
        resource_filter = request.GET.get('resource', '')
        action_filter = request.GET.get('action', '')
            
        # Start with all history records
        history_query = UtilizationHistoryModel.objects.all()
            
        # Apply filters if provided
        if date_filter:
            history_query = history_query.filter(report_date=date_filter)
        
        if resource_filter:
            history_query = history_query.filter(resource_email__icontains=resource_filter)
                
        if action_filter:
            history_query = history_query.filter(action=action_filter)
        
        # Limit to the most recent 100 records to avoid performance issues
        history_query = history_query.order_by('-timestamp')[:100]
        
        # Convert to list of dictionaries for JSON response
        history_data = []
        for record in history_query:
            history_data.append({
                'date': record.report_date.strftime('%Y-%m-%d'),
                'resource': record.resource_email,
                'action': record.action,
                'details': record.details,
                'previousValue': record.previous_value or '',
                'newValue': record.new_value or '',
                'timestamp': record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return JsonResponse({'data': history_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["POST"])
def update_billable_hours(request):
    """
    Update billable hours and recalculate related fields.
    """
    try:
        data = json.loads(request.body)
        report_id = data.get('id')
        new_billable_hours = float(data.get('billable_hours', 0))

        report = UtilizationReportModel.objects.get(id=report_id)
        
        # Store old values for comparison
        old_status = report.status
        old_billable_hours = report.billable_hours
        
        # Record history for billable hours update
        UtilizationHistoryModel.objects.create(
            report_date=report.date,
            resource_email=report.resource_email_address,
            action='edited',
            details="Billable hours updated",
            field_name='billable_hours',
            previous_value=str(old_billable_hours),
            new_value=str(new_billable_hours)
        )
        
        # Update billable hours
        report.billable_hours = new_billable_hours
        
        # Get the week number from the report date
        report_date = report.date
        week_number = (report_date.day - 1) // 7 + 1
        total_days = week_number * 5
        
        # Recalculate grand total
        report.grand_total = (
            report.administrative +
            new_billable_hours +
            report.training +
            report.unassigned +
            report.vacation
        )
        
        # Get last week's additional days
        last_week = 0
        if week_number > 1:
            prev_week_date = report_date - timedelta(days=7)
            prev_week_record = UtilizationReportModel.objects.filter(
                resource_email_address=report.resource_email_address,
                date=prev_week_date
            ).first()
            
            if prev_week_record:
                last_week = prev_week_record.addtnl_days
        
        # Calculate total logged days
        total_logged = new_billable_hours + report.vacation + last_week
        
        # Store old status for comparison
        was_open = report.status == 'open'
        
        # Apply business logic based on billing type
        if report.billing == 'Billing':
            if total_logged >= total_days:
                report.addtnl_days = 0
                report.status = 'close'
            else:
                report.addtnl_days = total_days - total_logged
                report.status = 'open'
        elif report.billing == 'Partial':
            half_total_days = total_days / 2
            if total_logged >= half_total_days:
                report.addtnl_days = 0
                report.status = 'close'
            else:
                report.addtnl_days = half_total_days - total_logged
                report.status = 'open'
        elif report.billing in ['On Bench', 'Non Billable', 'Next', 'Released']:
            report.addtnl_days = 0
            report.status = 'close'
        else:
            # Default case (TBD, etc.)
            if total_logged >= total_days:
                report.addtnl_days = 0
                report.status = 'close'
            else:
                report.addtnl_days = total_days - total_logged
                report.status = 'open'
        
        # Add closing comment if case is being closed
        if was_open and report.status == 'close':
            closing_comment = f"[Closed: Automatically closed - Required hours met]"
            report.comments = f"{report.comments or ''}{' ' if report.comments else ''}{closing_comment}".strip()
            
            # Record status change in history
            UtilizationHistoryModel.objects.create(
                report_date=report.date,
                resource_email=report.resource_email_address,
                action='closed',
                details="Automatically closed - Required hours met",
                field_name='status',
                previous_value='open',
                new_value='close'
            )
        
        report.save()

        # Calculate updated counts if status changed
        response_data = {
            'success': True,
            'grand_total': report.grand_total,
            'addtnl_days': report.addtnl_days,
            'status': report.status,
        }

        if old_status != report.status:
            # Get current date's counts
            current_open_count = UtilizationReportModel.objects.filter(
                date=report_date,
                status='open'
            ).count()
            
            current_handled_count = UtilizationReportModel.objects.filter(
                date=report_date,
                status='close',
                comments__contains='[Closed:'
            ).count()

            response_data.update({
                'status_changed': True,
                'current_open_count': current_open_count,
                'current_handled_count': current_handled_count
            })

        return JsonResponse(response_data)
        
    except UtilizationReportModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Report not found'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': 'Invalid billable hours value'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def util_summary(request):
    """
    Display utilization summary with charts showing monthly, quarterly, and yearly comparisons
    between DAMS and capable utilization.
    """
    # Get available dates for the dropdown
    dates = get_available_dates()

    context = {
        'dates': dates,
    }

    return render(request, 'util_report/util_summary.html', context)

@require_http_methods(["GET"])
def get_utilization_data(request):
    """
    API endpoint to get utilization data for charts.
    Returns data aggregated by month, quarter, and year.
    """
    try:
        # Get all utilization reports
        reports = UtilizationReportModel.objects.all().values('date', 'dams_utilization', 'capable_utilization')
        df = pd.DataFrame(list(reports))
        
        if df.empty:
            # Return dummy data if no actual data is available
            dummy_data = generate_dummy_utilization_data()
            return JsonResponse(dummy_data)
            
        # Convert date strings to datetime objects
        df['date'] = pd.to_datetime(df['date'])
        
        # Add year, month, and quarter columns
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        
        # Dictionary to store all result data
        result = {}
        
        # Monthly data - average by month and year
        monthly_data = df.groupby(['year', 'month']).agg({
            'dams_utilization': 'mean',
            'capable_utilization': 'mean'
        }).reset_index()
        
        # Format the monthly data for chart.js - convert all values to strings properly
        monthly_result = {
            'labels': [f"{int(row['year'])}-{int(row['month']):02d}" for _, row in monthly_data.iterrows()],
            'dams': [round(float(val), 2) for val in monthly_data['dams_utilization'].tolist()],
            'capable': [round(float(val), 2) for val in monthly_data['capable_utilization'].tolist()]
        }
        
        # Quarterly data - average by quarter and year
        quarterly_data = df.groupby(['year', 'quarter']).agg({
            'dams_utilization': 'mean',
            'capable_utilization': 'mean'
        }).reset_index()
        
        # Format the quarterly data for chart.js - convert all values to strings properly
        quarterly_result = {
            'labels': [f"{int(row['year'])} Q{int(row['quarter'])}" for _, row in quarterly_data.iterrows()],
            'dams': [round(float(val), 2) for val in quarterly_data['dams_utilization'].tolist()],
            'capable': [round(float(val), 2) for val in quarterly_data['capable_utilization'].tolist()]
        }
        
        # Yearly data - average by year
        yearly_data = df.groupby('year').agg({
            'dams_utilization': 'mean',
            'capable_utilization': 'mean'
        }).reset_index()
        
        # Format the yearly data for chart.js - convert all values to strings properly
        yearly_result = {
            'labels': [str(int(year)) for year in yearly_data['year'].tolist()],
            'dams': [round(float(val), 2) for val in yearly_data['dams_utilization'].tolist()],
            'capable': [round(float(val), 2) for val in yearly_data['capable_utilization'].tolist()]
        }
        
        # Combine all data
        result = {
            'monthly': monthly_result,
            'quarterly': quarterly_result,
            'yearly': yearly_result
        }
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error getting utilization data: {str(e)}")
        # Return dummy data in case of error
        dummy_data = generate_dummy_utilization_data()
        return JsonResponse(dummy_data)

def generate_dummy_utilization_data():
    """Generate dummy utilization data for charts when real data is not available."""
    # Current year
    current_year = datetime.now().year
    
    # Generate dummy monthly data
    monthly_labels = []
    monthly_dams = []
    monthly_capable = []
    
    for month in range(1, 13):
        monthly_labels.append(f"{current_year}-{month:02d}")
        monthly_dams.append(round(random.uniform(70, 85), 2))
        monthly_capable.append(round(random.uniform(75, 90), 2))
    
    # Generate dummy quarterly data
    quarterly_labels = [f"{current_year} Q1", f"{current_year} Q2", f"{current_year} Q3", f"{current_year} Q4"]
    quarterly_dams = [round(random.uniform(72, 82), 2) for _ in range(4)]
    quarterly_capable = [round(random.uniform(78, 88), 2) for _ in range(4)]
    
    # Generate dummy yearly data
    yearly_labels = [str(current_year-2), str(current_year-1), str(current_year)]
    yearly_dams = [round(random.uniform(70, 80), 2), round(random.uniform(75, 85), 2), round(random.uniform(80, 90), 2)]
    yearly_capable = [round(random.uniform(75, 85), 2), round(random.uniform(80, 90), 2), round(random.uniform(85, 95), 2)]
    
    return {
        'monthly': {
            'labels': monthly_labels,
            'dams': monthly_dams,
            'capable': monthly_capable
        },
        'quarterly': {
            'labels': quarterly_labels,
            'dams': quarterly_dams,
            'capable': quarterly_capable
        },
        'yearly': {
            'labels': yearly_labels,
            'dams': yearly_dams,
            'capable': yearly_capable
        }
    }

@require_http_methods(["GET"])
def get_low_utilization_resources(request):
    """
    API endpoint to get resources with low average individual utilization over the last 4 weeks of the month.
    Returns two lists: resources below 35% and resources below 50%.
    """
    try:
        # Get all dates and sort them in descending order
        all_dates = list(UtilizationReportModel.objects.values_list('date', flat=True).distinct().order_by('-date'))
        
        if not all_dates:
            # Return dummy data when no data is available
            return JsonResponse(generate_dummy_low_utilization_data())
        
        # Find the latest date for each month
        latest_month_ends = {}
        for date_obj in all_dates:
            # Convert to datetime.date if it's a string
            if isinstance(date_obj, str):
                date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
                
            # Create a key for year-month
            year_month = f"{date_obj.year}-{date_obj.month:02d}"
            
            # If this year-month isn't in our dict or has a later day, update it
            if year_month not in latest_month_ends or date_obj.day > latest_month_ends[year_month].day:
                latest_month_ends[year_month] = date_obj
        
        # Sort the month-end dates in descending order
        month_end_dates = sorted(latest_month_ends.values(), reverse=True)
        
        # Use the most recent month-end date
        most_recent_month_end = month_end_dates[0] if month_end_dates else None
        
        if not most_recent_month_end:
            # Return dummy data when no month-end data is available
            return JsonResponse(generate_dummy_low_utilization_data())
        
        # Determine the year and month of the most recent month end
        year = most_recent_month_end.year
        month = most_recent_month_end.month
        
        # Find all reports from the same month (last 4 weeks)
        month_reports = UtilizationReportModel.objects.filter(
            date__year=year,
            date__month=month
        ).values('resource_email_address', 'individual_utilization', 'date', 'billing', 'rdm')
        
        # Get total resources count for reference
        total_resources = len(set([report['resource_email_address'] for report in month_reports]))
        
        # Group by resource and calculate average utilization
        resource_averages = {}
        for report in month_reports:
            email = report['resource_email_address']
            if email not in resource_averages:
                resource_averages[email] = {
                    'utilization_sum': 0,
                    'count': 0,
                    'billing': report['billing'] or 'N/A',
                    'rdm': report['rdm'] or 'N/A'
                }
            
            resource_averages[email]['utilization_sum'] += report['individual_utilization'] if report['individual_utilization'] is not None else 0
            resource_averages[email]['count'] += 1
        
        # Calculate average and categorize by threshold
        below_35 = []
        below_50 = []
        all_resources = []
        
        # Track statistics for the charts
        billing_types = {}
        rdm_distribution = {}
        utilization_ranges = {
            "0-15%": 0,
            "15-25%": 0,
            "25-35%": 0,
            "35-50%": 0,
            "Above 50%": 0
        }
        
        for email, data in resource_averages.items():
            if data['count'] > 0:  # Ensure we have data points
                avg_util = data['utilization_sum'] / data['count']
                billing = data['billing']
                rdm = data['rdm']
                
                # Update billing type statistics
                billing_types[billing] = billing_types.get(billing, 0) + 1
                
                # Update RDM distribution
                rdm_distribution[rdm] = rdm_distribution.get(rdm, 0) + 1
                
                # Update utilization range counts
                if avg_util < 15:
                    utilization_ranges["0-15%"] += 1
                elif avg_util < 25:
                    utilization_ranges["15-25%"] += 1
                elif avg_util < 35:
                    utilization_ranges["25-35%"] += 1
                elif avg_util < 50:
                    utilization_ranges["35-50%"] += 1
                else:
                    utilization_ranges["Above 50%"] += 1
                
                resource_data = {
                    'resource_email': email,
                    'individual_utilization': avg_util,
                    'billing': billing,
                    'rdm': rdm
                }
                
                all_resources.append(resource_data)
                
                if avg_util < 35:
                    below_35.append(resource_data)
                elif avg_util < 50:
                    below_50.append(resource_data)
        
        # Sort by utilization (ascending)
        below_35.sort(key=lambda x: x['individual_utilization'])
        below_50.sort(key=lambda x: x['individual_utilization'])
        all_resources.sort(key=lambda x: x['individual_utilization'])
        
        # Prepare statistics in the format needed for charts
        billing_stats = [{"type": billing, "count": count} for billing, count in billing_types.items()]
        rdm_stats = [{"name": rdm, "count": count} for rdm, count in rdm_distribution.items()]
        range_stats = [{"range": range_name, "count": count} for range_name, count in utilization_ranges.items()]
        
        # Calculate average utilization for different groups
        avg_below_35 = sum(r['individual_utilization'] for r in below_35) / len(below_35) if below_35 else 0
        avg_below_50 = sum(r['individual_utilization'] for r in below_50) / len(below_50) if below_50 else 0
        avg_all = sum(r['individual_utilization'] for r in all_resources) / len(all_resources) if all_resources else 0
        
        return JsonResponse({
            'month_end_date': most_recent_month_end.strftime('%Y-%m-%d'),
            'below_35': below_35,
            'below_50': below_50,
            'total_resources': total_resources,
            'stats': {
                'billing_types': billing_stats,
                'rdm_distribution': rdm_stats,
                'utilization_ranges': range_stats,
                'averages': {
                    'below_35': avg_below_35,
                    'below_50': avg_below_50,
                    'all': avg_all
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting low utilization resources: {str(e)}")
        # Return dummy data in case of error
        return JsonResponse(generate_dummy_low_utilization_data())

def generate_dummy_low_utilization_data():
    """Generate dummy data for low utilization resources when real data is not available."""
    # Current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Generate dummy RDMs
    rdms = ["Adam", "Sarah", "Michael", "Jennifer", "David"]
    
    # Generate dummy billing types
    billing_types = ["Billing", "Partial", "Non Billable", "On Bench", "TBD", "Released"]
    
    # Create dummy resources below 35%
    below_35 = []
    for i in range(5):
        below_35.append({
            'resource_email': f"employee{i+1}@example.com",
            'individual_utilization': round(random.uniform(15, 34), 2),
            'billing': random.choice(billing_types),
            'rdm': random.choice(rdms)
        })
    
    # Create dummy resources below 50%
    below_50 = []
    for i in range(8):
        below_50.append({
            'resource_email': f"employee{i+6}@example.com",
            'individual_utilization': round(random.uniform(35, 49), 2),
            'billing': random.choice(billing_types),
            'rdm': random.choice(rdms)
        })
    
    # Create dummy statistics
    rdm_stats = [{"name": rdm, "count": random.randint(1, 8)} for rdm in rdms]
    billing_stats = [{"type": btype, "count": random.randint(1, 6)} for btype in billing_types]
    
    return {
        'month_end_date': current_date,
        'below_35': below_35,
        'below_50': below_50,
        'total_resources': 50,
        'stats': {
            'billing_types': billing_stats,
            'rdm_distribution': rdm_stats,
            'utilization_ranges': [
                {"range": "0-15%", "count": 2},
                {"range": "15-25%", "count": 3},
                {"range": "25-35%", "count": 5},
                {"range": "35-50%", "count": 8},
                {"range": "Above 50%", "count": 32}
            ],
            'averages': {
                'below_35': 27.5,
                'below_50': 42.8,
                'all': 68.3
            }
        }
    }

@require_http_methods(["POST"])
def update_additional_days(request):
    """
    Update additional days and recalculate status.
    """
    try:
        data = json.loads(request.body)
        report_id = data.get('id')
        new_additional_days = float(data.get('additional_days', 0))

        report = UtilizationReportModel.objects.get(id=report_id)
        
        # Store old values for comparison
        old_status = report.status
        old_additional_days = report.addtnl_days
        
        # Record history for additional days update
        UtilizationHistoryModel.objects.create(
            report_date=report.date,
            resource_email=report.resource_email_address,
            action='edited',
            details="Additional days updated",
            field_name='addtnl_days',
            previous_value=str(old_additional_days),
            new_value=str(new_additional_days)
        )
        
        # Update additional days
        report.addtnl_days = new_additional_days
        
        # Get the week number from the report date
        report_date = report.date
        week_number = (report_date.day - 1) // 7 + 1
        total_days = week_number * 5
        
        # Get last week's additional days
        last_week = 0
        if week_number > 1:
            prev_week_date = report_date - timedelta(days=7)
            prev_week_record = UtilizationReportModel.objects.filter(
                resource_email_address=report.resource_email_address,
                date=prev_week_date
            ).first()
            
            if prev_week_record:
                last_week = prev_week_record.addtnl_days
        
        # Calculate total logged days
        total_logged = report.billable_hours + report.vacation + last_week
        
        # Store old status for comparison
        was_open = report.status == 'open'
        
        # Apply business logic based on billing type and the manually set additional days
        if new_additional_days == 0:
            report.status = 'close'
        else:
            report.status = 'open'
        
        # Add closing comment if case is being closed
        if was_open and report.status == 'close':
            closing_comment = f"[Closed: Manually set additional days to 0]"
            report.comments = f"{report.comments or ''}{' ' if report.comments else ''}{closing_comment}".strip()
            
            # Record status change in history
            UtilizationHistoryModel.objects.create(
                report_date=report.date,
                resource_email=report.resource_email_address,
                action='closed',
                details="Manually set additional days to 0",
                field_name='status',
                previous_value='open',
                new_value='close'
            )
        
        # Save changes to this record
        report.save()
        
        # Calculate updated capable utilization
        # Get all records for this date to recalculate capable utilization
        date_records = UtilizationReportModel.objects.filter(date=report_date)

        # Fetch total_capacity and dams_utilization from any record for this date
        sample_record = date_records.first()
        total_capacity = sample_record.total_capacity if sample_record and sample_record.total_capacity else 0
        dams_utilization = sample_record.dams_utilization if sample_record and sample_record.dams_utilization else 0
        # Calculate total_utilization from dams_utilization and total_capacity
        total_utilization = (dams_utilization / 100) * total_capacity if total_capacity else 0
        total_additional_days = sum(record.addtnl_days for record in date_records if record.addtnl_days is not None)

        if total_capacity > 0:
            # Calculate capable utilization using the formula: ((total_utilization + (total_additional_days * 8)) / total_capacity * 100)
            capable_utilization = ((total_utilization + (total_additional_days * 8)) / total_capacity) * 100
            capable_utilization = round(capable_utilization, 2)
            # Update capable_utilization for all records with this date
            date_records.update(capable_utilization=capable_utilization)
        else:
            capable_utilization = 0

        # Calculate updated counts if status changed
        response_data = {
            'success': True,
            'additional_days': report.addtnl_days,
            'status': report.status,
            'capable_utilization': capable_utilization,
        }

        if old_status != report.status:
            # Get current date's counts
            current_open_count = UtilizationReportModel.objects.filter(
                date=report_date,
                status='open'
            ).count()
            
            current_handled_count = UtilizationReportModel.objects.filter(
                date=report_date,
                status='close',
                comments__contains='[Closed:'
            ).count()

            response_data.update({
                'status_changed': True,
                'current_open_count': current_open_count,
                'current_handled_count': current_handled_count
            })

        return JsonResponse(response_data)
        
    except UtilizationReportModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Report not found'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': 'Invalid additional days value'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

