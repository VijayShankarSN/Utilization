from django.shortcuts import render
from django.http import HttpResponse
from .data_extraction import extract_data

def home_view(request):
    return HttpResponse("Welcome to the Utilization App!")
def extract_data_view(request):
    # Call the data extraction function
    dfs = extract_data()

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
