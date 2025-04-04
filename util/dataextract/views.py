from django.shortcuts import render
from django.http import HttpResponse
from .data_extraction import main  # Import the main function from data_extraction.py

def home_view(request):
    return HttpResponse("Welcome to the Utilization App!")

def extract_data_view(request):
    # Path to the Excel file (you can make this dynamic if needed)
    file_path = 'new Utilization Report 14Mar2025.xlsb'

    try:
        # Call the main function to extract data
        dfs = main(file_path)

        # Debugging: Print the shape of the DataFrames
        print("WTD DataFrame shape:", dfs['WTD'].shape)
        print("MTD DataFrame shape:", dfs['MTD'].shape)

        # Convert the extracted data (WTD and MTD DataFrames) to HTML tables
        wtd_html = dfs['WTD'].to_html(classes='table table-striped', index=False)
        mtd_html = dfs['MTD'].to_html(classes='table table-striped', index=False)

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
                </div>
            </body>
        </html>
        """
        return HttpResponse(html_content)

    except Exception as e:
        # Handle errors and display them in the response
        error_message = f"An error occurred while extracting data: {str(e)}"
        return HttpResponse(f"<h1>Error</h1><p>{error_message}</p>")