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

            # Convert the extracted data (WTD and MTD DataFrames) to HTML tables
            wtd_html = dfs['WTD'].to_html(classes='table table-striped', index=False)
            mtd_html = dfs['MTD'].to_html(classes='table table-striped', index=False)
            pivot_html = pivot_df.to_html(classes='table table-striped', index=False)

            # Combine the HTML tables into a single response
            return render(request, 'dataextract/result.html', {
                'wtd_html': wtd_html,
                'mtd_html': mtd_html,
                'pivot_html': pivot_html
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
            'track',
            'billing',
            'status',
            'comments',
            'spoc',
            'spoc_comments'
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

