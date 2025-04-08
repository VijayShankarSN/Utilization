from django.shortcuts import render
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from .data_extraction import main  # Import the main function from data_extraction.py

def home_view(request):
    """
    Home view for the Utilization App.
    """
    return HttpResponse("Welcome to the Utilization App!")

def extract_data_view(request):
    """
    View to handle file uploads and extract data from the uploaded Excel files.
    """
    if request.method == 'POST' and request.FILES.get('file') and request.FILES.get('extracted_columns_file'):
        # Handle file uploads
        file = request.FILES['file']
        extracted_columns_file = request.FILES['extracted_columns_file']

        # Save the uploaded files to a temporary location
        fs = FileSystemStorage()
        file_path = fs.save(file.name, file)
        extracted_columns_path = fs.save(extracted_columns_file.name, extracted_columns_file)

        try:
            # Call the main function to extract data
            dfs, pivot_df = main(fs.path(file_path), fs.path(extracted_columns_path))  # Pass both file paths

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