import pandas as pd
from datetime import datetime
import os

def read_data_from_excel(file_path):
    """
    Read data from Excel file using appropriate engine based on file extension.
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        tuple: (ExcelFile object, engine name)
    """
    # Determine the correct engine based on file extension
    file_ext = os.path.splitext(file_path)[-1].lower()
    engine_map = {".xlsb": "pyxlsb", ".xlsx": "openpyxl", ".xlsm": "openpyxl", ".xls": "xlrd"}

    if file_ext not in engine_map:
        raise ValueError(f"Unsupported file format: {file_ext}")

    engine = engine_map[file_ext]

    # Open the workbook using the correct engine
    xls = pd.ExcelFile(file_path, engine=engine)
    return xls, engine

def get_current_month():
    """
    Get the current month name.
    
    Returns:
        str: Current month name (e.g., "March")
    """
    return f"{datetime.now().strftime('%B')}"

def find_header_row(xls, sheet_name, target_column):
    """
    Find the header row in an Excel sheet by searching for a specific column.
    
    Args:
        xls (ExcelFile): ExcelFile object
        sheet_name (str): Name of the sheet to search
        target_column (str): Column name to search for
        
    Returns:
        int: Index of the header row
    """
    raw_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

    # Identify the header row by searching for a specific column name
    for idx, row in raw_df.iterrows():
        if target_column in row.values:
            return idx

    raise ValueError(f"Header containing '{target_column}' not found in {sheet_name}.")

def create_dataframes(xls, sheet_column_mapping, wtd_header_row, mtd_header_row):
    """
    Create DataFrames from Excel sheets with specific column mappings.
    
    Args:
        xls (ExcelFile): ExcelFile object
        sheet_column_mapping (dict): Dictionary containing column mappings for each sheet
        wtd_header_row (int): Header row index for WTD sheet
        mtd_header_row (int): Header row index for MTD sheet
        
    Returns:
        dict: Dictionary containing DataFrames for each sheet
    """
    current_month = get_current_month()
    
    # Read and filter data by 'CC' value (504686) from each sheet
    dfs = {
        'WTD': pd.read_excel(xls, sheet_name='WTD', 
                           usecols=sheet_column_mapping['WTD']['columns'], 
                           skiprows=wtd_header_row)
              .query(f"`{sheet_column_mapping['WTD']['cc_column']}` == 504686"),

        'MTD': pd.read_excel(xls, sheet_name='Consultant Summary', 
                           usecols=sheet_column_mapping['MTD']['base_columns'], 
                           skiprows=mtd_header_row)
              .query(f"`{sheet_column_mapping['MTD']['cc_column']}` == 504686")
    }
    return dfs

def main(file_path):
    """
    Main function to process the Excel file and extract data.
    
    Args:
        file_path (str): Path to the Excel file
    """
    # Read the Excel file
    xls, xl_engine = read_data_from_excel(file_path)
    
    # Get current month
    current_month = get_current_month()
    
    # Define sheets and columns
    sheet_column_mapping = {
        'WTD': {
            'columns': ['Consultant Name', 'Manager Name', 'WTD Capacity', 'Billable Hours', 'Utl %', 'CC'],
            'cc_column': 'CC'
        },
        'MTD': {
            'base_columns': ['Resource Email Address', 'Project Number', 'Project Name', 
                           'Work Type Description-OPS', current_month, 'Cost Center - OPS'],
            'cc_column': 'Cost Center - OPS'
        }
    }
    
    # Find header rows
    mtd_header_row = find_header_row(xls, 'Consultant Summary', 'Resource Email Address')
    wtd_header_row = find_header_row(xls, 'WTD', 'Consultant Name')
    
    # Create DataFrames
    dfs = create_dataframes(xls, sheet_column_mapping, wtd_header_row, mtd_header_row)
    
    return dfs

if __name__ == "__main__":
    # Example usage
    file_path = 'Latest Utilization Report 14Mar2025.xlsb'
    try:
        dfs = main(file_path)
        print("\n=== Data Extraction Results ===")
        print("\nWTD (Week-to-Date) Data:")
        print("-" * 80)
        print(dfs['WTD'].to_string())
        print("\nMTD (Month-to-Date) Data:")
        print("-" * 80)
        print(dfs['MTD'].to_string())
    except Exception as e:
        print(f"Error occurred: {str(e)}") 