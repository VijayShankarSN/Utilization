from django.shortcuts import render
from django.http import HttpResponse
from .data_extraction import main  # Import the main function from data_extraction.py

def home_view(request):
    """
    Home view for the Utilization App.
    """
    return HttpResponse("Welcome to the Utilization App!")

def extract_data_view(request):
    """
    View to extract data from the Excel file and display it as HTML tables.
    """
    # Paths to the Excel files
    file_path = 'new Utilization Report 14Mar2025.xlsb'  # Path to the main Excel file
    extracted_columns_path = 'extracted_columns.xlsb'  # Path to the extracted columns file

    try:
        # Call the main function to extract data
        dfs, pivot_df = main(file_path, extracted_columns_path)  # Pass both arguments

        # Debugging: Print the shape of the DataFrames
        print("WTD DataFrame shape:", dfs['WTD'].shape)
        print("MTD DataFrame shape:", dfs['MTD'].shape)

        # Convert the extracted data (WTD and MTD DataFrames) to HTML tables
        wtd_html = dfs['WTD'].to_html(classes='table table-striped', index=False)
        mtd_html = dfs['MTD'].to_html(classes='table table-striped', index=False)
        pivot_html = pivot_df.to_html(classes='table table-striped', index=False)

        # Combine the HTML tables into a single response
        html_content = f"""
        <html>
            <head>
                <title>Extracted Data</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
            </head>
            <body>
                <div class="container">
                    <h1>Extracted WTD Data</h1>
                    {wtd_html}
                    <h1>Extracted MTD Data</h1>
                    {mtd_html}
                    <h1>Work Type Breakdown (Pivot Table)</h1>
                    {pivot_html}
                </div>
            </body>
        </html>
        """
        return HttpResponse(html_content)

    except Exception as e:
        # Handle errors and display them in the response
        error_message = f"An error occurred while extracting data: {str(e)}"
        return HttpResponse(f"<h1>Error</h1><p>{error_message}</p>")