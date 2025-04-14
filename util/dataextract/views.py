from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import FileSystemStorage
from .data_extraction import main  # Import the main function from data_extraction.py
from .forms import UploadFileForm
from .utils import process_excel_file
from .utils import get_available_dates, get_report_for_date
from django.urls import reverse
from django.shortcuts import redirect
from .models import UtilizationReport
from django.views.decorators.http import require_http_methods
import json
import pandas as pd
from io import BytesIO

def home_view(request):
    """
    Home view for the Utilization App.
    """
    return HttpResponse("Welcome to the Utilization App!")

def extract_data_view(request):
    """
    View to handle file uploads and extract data from the uploaded Excel files.
    """
    if request.method == 'POST' and request.FILES.get('file'):
        # Handle file uploads
        file = request.FILES['file']

        # Save the uploaded file to a temporary location
        fs = FileSystemStorage()
        file_path = fs.save(file.name, file)

        try:
            # Call the main function to extract data
            dfs, pivot_df = main(fs.path(file_path), None)  # Pass None for extracted_columns_path

            # Store DataFrames as JSON in the session
            request.session['wtd_data'] = dfs['WTD'].to_json(orient='records')
            request.session['mtd_data'] = dfs['MTD'].to_json(orient='records')
            request.session['pivot_data'] = pivot_df.to_json(orient='records')

            # Get the latest date from the database
            latest_report = UtilizationReport.objects.order_by('-date').first()
            report_date = latest_report.date.strftime('%Y-%m-%d') if latest_report else None

            # Convert the extracted data (WTD and MTD DataFrames) to HTML tables
            wtd_html = dfs['WTD'].to_html(classes='table table-striped', index=False)
            mtd_html = dfs['MTD'].to_html(classes='table table-striped', index=False)
            pivot_html = pivot_df.to_html(classes='table table-striped', index=False)

            # Combine the HTML tables into a single response
            return render(request, 'dataextract/result.html', {
                'wtd_html': wtd_html,
                'mtd_html': mtd_html,
                'pivot_html': pivot_html,
                'has_data': True,
                'current_date': report_date
            })

        except Exception as e:
            # Handle errors and display them in the response
            error_message = f"An error occurred while extracting data: {str(e)}"
            return render(request, 'dataextract/upload.html', {'error_message': error_message})

    return render(request, 'dataextract/upload.html')

def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            result = process_excel_file(file)
            return render(request, 'dataextract/result.html', {'pivot_html': result})
    else:
        form = UploadFileForm()
    return render(request, 'dataextract/upload.html', {'form': form})

def view_reports(request):
    available_dates = get_available_dates()
    selected_date = request.GET.get('date')
    report_data = None

    if selected_date:
        report_data = get_report_for_date(selected_date)

    context = {
        'available_dates': available_dates,
        'selected_date': selected_date,
        'report_data': report_data
    }
    return render(request, 'dataextract/view_reports.html', context)

def util_leakage(request):
    dates = get_available_dates()
    selected_date = request.GET.get('date')
    
    if selected_date:
        # Get report data and filter for open status only
        report_data = UtilizationReport.objects.filter(
            date=selected_date,
            status='Open'  # Filter only open cases
        ).values(
            'id',  # Include the id field
            'name',
            'administrative',
            'billable_days',
            'training',
            'unassigned',
            'vacation',
            'grand_total',
            'last_week',
            'status',
            'addtnl_days',
            'wtd_actual',
            'spoc',
            'comments',
            'spoc_comments',
            'rdm',
            'track',
            'billing'
        )
    else:
        report_data = None

    context = {
        'dates': dates,
        'selected_date': selected_date,
        'report_data': report_data,
    }
    
    return render(request, 'dataextract/util_leakage.html', context)

@require_http_methods(["POST"])
def update_comments(request):
    try:
        data = json.loads(request.body)
        report_id = data.get('id')
        field = data.get('field')
        value = data.get('value')

        if field not in ['comments', 'spoc_comments']:
            return JsonResponse({'success': False, 'error': 'Invalid field'})

        report = UtilizationReport.objects.get(id=report_id)
        setattr(report, field, value)
        report.save()

        return JsonResponse({'success': True})
    except UtilizationReport.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Report not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def download_report(request):
    date = request.GET.get('date')
    if not date:
        return HttpResponse("No date selected", status=400)

    # Get the report data for the selected date
    reports = UtilizationReport.objects.filter(date=date)
    
    # Convert to DataFrame
    data = []
    for report in reports:
        data.append({
            'Name': report.name,
            'Administrative': report.administrative,
            'Billable Days': report.billable_days,
            'Training': report.training,
            'Unassigned': report.unassigned,
            'Vacation': report.vacation,
            'Grand Total': report.grand_total,
            'Last Week': report.last_week,
            'Status': report.status,
            'Additional Days': report.addtnl_days,
            'WTD Actual': report.wtd_actual,
            'SPOC': report.spoc,
            'Comments': report.comments,
            'SPOC Comments': report.spoc_comments,
            'RDM': report.rdm,
            'Track': report.track,
            'Billing': report.billing
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Utilization Report', index=False)
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=utilization_report_{date}.xlsx'
    
    return response

def download_result(request):
    """
    Download the extraction results as an Excel file.
    """
    try:
        # Create a BytesIO buffer to save the Excel file
        output = BytesIO()
        
        # Create Excel writer object
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if 'wtd_data' in request.session:
                wtd_df = pd.read_json(request.session['wtd_data'])
                wtd_df.to_excel(writer, sheet_name='WTD Data', index=False)
            if 'mtd_data' in request.session:
                mtd_df = pd.read_json(request.session['mtd_data'])
                mtd_df.to_excel(writer, sheet_name='MTD Data', index=False)
            if 'pivot_data' in request.session:
                pivot_df = pd.read_json(request.session['pivot_data'])
                pivot_df.to_excel(writer, sheet_name='Pivot Data', index=False)
        
        # Prepare the response
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename=extraction_results_{timestamp}.xlsx'
        
        return response
    except Exception as e:
        return HttpResponse(f"Error generating Excel file: {str(e)}", status=500)

def download_util_leakage(request):
    """
    Download the util leakage data as an Excel file.
    """
    date = request.GET.get('date')
    if not date:
        return HttpResponse("No date selected", status=400)

    # Get report data and filter for open status only
    reports = UtilizationReport.objects.filter(
        date=date,
        status='Open'
    ).values(
        'name',
        'administrative',
        'billable_days',
        'training',
        'unassigned',
        'vacation',
        'grand_total',
        'last_week',
        'status',
        'addtnl_days',
        'wtd_actual',
        'spoc',
        'comments',
        'spoc_comments',
        'rdm',
        'track',
        'billing'
    )
    
    # Convert to DataFrame
    data = []
    for report in reports:
        data.append({
            'Name': report['name'],
            'Administrative': report['administrative'],
            'Billable Days': report['billable_days'],
            'Training': report['training'],
            'Unassigned': report['unassigned'],
            'Vacation': report['vacation'],
            'Grand Total': report['grand_total'],
            'Last Week': report['last_week'],
            'Status': report['status'],
            'Additional Days': report['addtnl_days'],
            'WTD Actual': report['wtd_actual'],
            'SPOC': report['spoc'],
            'Comments': report['comments'],
            'SPOC Comments': report['spoc_comments'],
            'RDM': report['rdm'],
            'Track': report['track'],
            'Billing': report['billing']
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Util Leakage Report', index=False)
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=util_leakage_report_{date}.xlsx'
    
    return response

