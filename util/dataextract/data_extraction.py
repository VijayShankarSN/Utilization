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

def read_extracted_columns(file_path):
    """
    Read data from extracted_columns.xlsb file.
    
    Args:
        file_path (str): Path to the extracted_columns.xlsb file
        
    Returns:
        DataFrame: DataFrame containing Track and Billing columns
    """
    try:
        # Read the Excel file using pyxlsb engine
        xls = pd.ExcelFile(file_path, engine="pyxlsb")
        
        # Read the first sheet (assuming it's the only sheet)
        df = pd.read_excel(xls, sheet_name=0)
        
        # Ensure required columns exist
        required_cols = ['Track', 'Billing']
        if not all(col in df.columns for col in required_cols):
            raise ValueError("Required columns 'Track' and 'Billing' not found in extracted_columns.xlsb")
            
        return df
    except Exception as e:
        raise Exception(f"Error reading extracted_columns.xlsb: {str(e)}")

def create_pivot_table(dfs, extracted_df):
    """
    Create a pivot table from the MTD DataFrame showing work type breakdowns.
    
    Args:
        dfs (dict): Dictionary containing DataFrames for each sheet
        extracted_df (DataFrame): DataFrame containing Track and Billing columns
        
    Returns:
        DataFrame: Pivot table with work type breakdowns
    """
    # Calculate days from hours (8 hours per day)
    dfs['MTD']['Days'] = dfs['MTD']['March'] / 8
    
    # Create pivot table
    pivot_df = dfs['MTD'].pivot_table(
        index="Resource Email Address",
        columns="Work Type Description-OPS",
        values="Days",
        aggfunc="sum",
        fill_value=0
    ).reset_index()
    
    # Add Grand Total column
    pivot_df['Grand Total'] = pivot_df.iloc[:, 1:].sum(axis=1)
    
    # Extract Billable Hours data
    wtd_actual = dfs['WTD'][['Consultant Name', 'Billable Hours']].copy()
    wtd_actual['WTD Actual'] = wtd_actual['Billable Hours']  # Keep in hours, no conversion
    
    # Merge WTD Actual data with pivot table
    pivot_df = pivot_df.merge(
        wtd_actual[['Consultant Name', 'WTD Actual']],
        left_on='Resource Email Address',
        right_on='Consultant Name',
        how='left'
    )
    
    # Drop the duplicate Consultant Name column
    pivot_df = pivot_df.drop('Consultant Name', axis=1)
    
    # Fill NaN values with 0
    pivot_df['WTD Actual'] = pivot_df['WTD Actual'].fillna(0)
    
    # Merge with extracted columns data
    # Assuming the first column in extracted_df is the key for mapping
    key_column = extracted_df.columns[0]
    pivot_df = pivot_df.merge(
        extracted_df[[key_column, 'Track', 'Billing']],
        left_on='Resource Email Address',
        right_on=key_column,
        how='left'
    )
    
    # Reorder columns to put WTD Actual after Resource Email Address
    cols = ['Resource Email Address', 'WTD Actual', 'Track', 'Billing'] + [col for col in pivot_df.columns 
            if col not in ['Resource Email Address', 'WTD Actual', 'Track', 'Billing', 'Grand Total']] + ['Grand Total']
    pivot_df = pivot_df[cols]
    
    # Remove any 'Row Labels' column if it exists
    if 'Row Labels' in pivot_df.columns:
        pivot_df = pivot_df.drop('Row Labels', axis=1)
    
    return pivot_df

def main(file_path, extracted_columns_path):
    """
    Main function to process the Excel file and extract data.
    
    Args:
        file_path (str): Path to the Excel file
        extracted_columns_path (str): Path to the extracted_columns.xlsb file
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
                           'Work Type Description-OPS', 'March', 'Cost Center - OPS'],
            'cc_column': 'Cost Center - OPS'
        }
    }
    
    # Find header rows
    mtd_header_row = find_header_row(xls, 'Consultant Summary', 'Resource Email Address')
    wtd_header_row = find_header_row(xls, 'WTD', 'Consultant Name')
    
    # Create DataFrames
    dfs = create_dataframes(xls, sheet_column_mapping, wtd_header_row, mtd_header_row)
    
    # Read extracted columns data
    extracted_df = read_extracted_columns(extracted_columns_path)
    
    # Create pivot table
    pivot_df = create_pivot_table(dfs, extracted_df)
    
    return dfs, pivot_df

if __name__ == "__main__":
    # Example usage
    file_path = 'Latest Utilization Report 14Mar2025.xlsb'
    extracted_columns_path = 'extracted_columns.xlsb'  # Path to the extracted columns file
    
    try:
        dfs, pivot_df = main(file_path, extracted_columns_path)
        print("\n=== Data Extraction Results ===")
        print("\nWTD (Week-to-Date) Data:")
        print("-" * 80)
        print(dfs['WTD'].to_string())
        print("\nMTD (Month-to-Date) Data:")
        print("-" * 80)
        print(dfs['MTD'].to_string())
        print("\nWork Type Breakdown (Pivot Table):")
        print("-" * 80)
        print(pivot_df.to_string())
    except Exception as e:
        print(f"Error occurred: {str(e)}") 