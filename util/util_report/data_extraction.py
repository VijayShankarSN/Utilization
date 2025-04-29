import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np
from .models.exclusion_table import rdmname
from .models.utilrepo import UtilizationReport
from .models.trackbill import EmailTrack 


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

def extract_month_from_filename(file_path):
    """
    Extract the month name from the file name.
    
    Args:
        file_path (str): Path to the file (e.g., 'Latest Utilization Report 14Mar2025_dxRTy5wxlsb.xlsb')
    
    Returns:
        str: Month name (e.g., 'March')
    """
    try:
        # Extract the file name from the path
        file_name = os.path.basename(file_path)  # e.g., 'Latest Utilization Report 14Mar2025_dxRTy5wxlsb.xlsb'
        
        # Split the file name and find the part containing the date
        parts = file_name.split()
        for part in parts:
            # Check if the part matches the expected date format
            try:
                parsed_date = datetime.strptime(part[:9], "%d%b%Y")  # Try parsing the first 9 characters
                return parsed_date.strftime('%B')  # Return the full month name (e.g., 'March')
            except ValueError:
                continue  # Skip parts that don't match the format
        
        # If no valid date part is found, raise an error
        raise ValueError("No valid date part found in the file name.")
    except Exception as e:
        raise ValueError(f"Error extracting month from filename: {str(e)}")
    
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

# Replace the hardcoded 'March' with dynamic month extraction
def create_dataframes(xls, sheet_column_mapping, wtd_header_row, mtd_header_row, file_path):
    """
    Create DataFrames from Excel sheets with specific column mappings.
    
    Args:
        xls (ExcelFile): ExcelFile object
        sheet_column_mapping (dict): Dictionary containing column mappings for each sheet
        wtd_header_row (int): Header row index for WTD sheet
        mtd_header_row (int): Header row index for MTD sheet
        file_path (str): Path to the file to extract the month
    
    Returns:
        dict: Dictionary containing DataFrames for each sheet
    """
    current_month = extract_month_from_filename(file_path)  # Dynamically extract the month
    
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


def read_extracted_columns(file_path=None):
    """
    Read data from the EmailTrack model instead of an Excel file.
    
    Args:
        file_path (str): Path to the extracted_columns.xlsb file (not used anymore)
        
    Returns:
        DataFrame: DataFrame containing Track and Billing columns
    """
    try:
        # Query all records from the EmailTrack model
        email_tracks = EmailTrack.objects.all().values('row_labels', 'track', 'billing')
        
        # Convert the QuerySet to a DataFrame
        df = pd.DataFrame(email_tracks)
        
        # Ensure required columns exist
        required_cols = ['row_labels', 'track', 'billing']
        if not all(col in df.columns for col in required_cols):
            raise ValueError("Required columns 'row_labels', 'track', and 'billing' not found in EmailTrack model")
        
        return df.rename(columns={'row_labels': 'Resource Email Address', 'track': 'Track', 'billing': 'Billing'})
    except Exception as e:
        raise Exception(f"Error reading data from EmailTrack model: {str(e)}")


def create_pivot_table(dfs, extracted_df,file_path):
    """
    Create a pivot table from the MTD DataFrame showing work type breakdowns.
    
    Args:
        dfs (dict): Dictionary containing DataFrames for each sheet
        extracted_df (DataFrame): DataFrame containing Track and Billing columns
        
    Returns:
        DataFrame: Pivot table with work type breakdowns
    """
    # Calculate days from hours (8 hours per day)
    dfs['MTD']['Days'] = dfs['MTD'][extract_month_from_filename(file_path)] / 8
    
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
    
    # Calculate Additional Days based on Billing values
    def calculate_additional_days(row, file_path):
        """
        Calculate additional days based on billing status and resource information.
        
        Args:
            row (Series): Row from the pivot table
            file_path (str): Path to the file to extract the week number
            
        Returns:
            float: Additional days to be added
        """
        # Extract week number from file path
        file_name = os.path.basename(file_path)
        parts = file_name.split()
        week_number = None

        for part in parts:
            try:
                parsed_date = datetime.strptime(part[:9], "%d%b%Y")
            
                # Calculate the week number using the new formula
                week_number = (parsed_date.day - 1) // 7 + 1
                break
            except ValueError:
                continue

        billing = row['Billing']  # Use exact value without case conversion
        
        # Get WTD Actual and Vacation values
        wtd_actual_days = row['WTD Actual'] / 8  # Convert hours to days
        vacation = row.get('Vacation', 0)  # Get Vacation value, default to 0 if not present
        dept = row.get('Department Mgmt', 0)  # Get Department Mgmt value, default to 0 if not present
        billable_hours = row.get('Billable Hours', 0)  # Get Billable Hours value, default to 0 if not present
        grand_total = row.get('Grand Total', 0)  # Get Grand Total value, default to 0 if not present
        
        # Get last week's additional days
        last_week = 0
        if week_number > 1:
            prev_week_date = parsed_date - timedelta(days=7)
            prev_week_record = UtilizationReport.objects.filter(
                name=row['Resource Email Address'],
                date=prev_week_date.strftime('%Y-%m-%d')
            ).first()
            if prev_week_record:
                last_week = prev_week_record.addtnl_days
        
        
        # Calculate total days based on week number
        total_days = week_number * 5
        
        # Check if the name is in the exclusion list
        exclusive_names = row['Resource Email Address']
        all_entries = rdmname.objects.all()
        
        # Logic based on billing type
        if billing == 'Billing':
            # For Billing type, check if total logged hours (billable + vacation + last_week) >= total_days
            if (billable_hours + vacation + last_week) >= total_days:
                return 0
            else:
                # Calculate additional days needed
                additional = max(0, total_days - (billable_hours + vacation + last_week))
                return additional
            
        elif billing == 'Partial':
            # For Partial billing, check if total logged hours (billable + vacation + last_week) >= total_days/2
            if (billable_hours + vacation + last_week) >= total_days/2:
                return 0
            else:
                # Calculate additional days needed
                additional = max(0, total_days/2 - (billable_hours + vacation + last_week))
                return additional
            
        elif billing in ['On Bench', 'Non Billable', 'Next', 'Released']:
            # For these billing types, no additional days needed
            return 0
        
        else:
            # Default case - no additional days
            return 0
    
    # Add Additional Days column
    pivot_df['Additional Days'] = pivot_df.apply(lambda row: calculate_additional_days(row, file_path), axis=1)
    
    # Add Status column based on Billing values and Additional Days
    def determine_status(row, file_path):
        """
        Determine the status based on billing type and logged hours.
        
        Args:
            row (Series): Row from the pivot table
            file_path (str): Path to the file to extract the week number
            
        Returns:
            str: Status ('open' or 'close')
        """
        # Extract week number from file path
        file_name = os.path.basename(file_path)
        parts = file_name.split()
        week_number = None

        for part in parts:
            try:
                parsed_date = datetime.strptime(part[:9], "%d%b%Y")
            
                # Calculate the week number using the new formula
                week_number = (parsed_date.day - 1) // 7 + 1
                break
            except ValueError:
                continue
        
        # Calculate total days based on week number
        total_days = week_number * 5
        
        # Get billing type and other values
        billing_type = str(row.get('Billing', '')).strip()
        dept_mgmt = row.get('Department Mgmt', 0) or 0
        admin = row.get('Administrative', 0) or 0
        billable_hours = row.get('Billable Hours', 0) or 0
        vacation = row.get('Vacation', 0) or 0
        total_logged = billable_hours + vacation

        # Priority-based checks
        if dept_mgmt >= 1 or admin >= 1:
            return 'close'

        if billing_type == 'Billing':  # Full Billable
            return 'close' if total_logged >= total_days else 'open'

        if billing_type == 'Partial':
            return 'close' if total_logged >= total_days / 2 else 'open'

        if billing_type in {'Next', 'TBD'}:
            return 'close' if total_logged >= total_days else 'open'

        if billing_type in {'On Bench', 'Non Billable', 'Released'}:
            return 'close'

        # Fallback/default
        return 'open'
    
    pivot_df['Status'] = pivot_df.apply(lambda row: determine_status(row, file_path), axis=1)
    
    # Define the exact column order
    column_order = [
        'Resource Email Address',
        'WTD Actual',
        'Track',
        'Billing',
        'Status',
        'Additional Days',
        'Administrative',
        'Billable Hours',
        'Department Mgmt',
        'Internal Projects',
        'Investment',
        'Presales',
        'Training',
        'Unassigned',
        'Vacation',
        'Grand Total'
    ]
    # Reorder columns according to the specified order
    pivot_df = pivot_df[column_order]
    
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
    
    # Define sheets and columns
    sheet_column_mapping = {
        'WTD': {
            'columns': ['Consultant Name', 'Manager Name', 'WTD Capacity', 'Billable Hours', 'Utl %', 'CC'],
            'cc_column': 'CC'
        },
        'MTD': {
            'base_columns': ['Resource Email Address', 'Project Number', 'Project Name', 
                           'Work Type Description-OPS', extract_month_from_filename(file_path), 'Cost Center - OPS'],
            'cc_column': 'Cost Center - OPS'
        }
    }
    
    # Find header rows
    mtd_header_row = find_header_row(xls, 'Consultant Summary', 'Resource Email Address')
    wtd_header_row = find_header_row(xls, 'WTD', 'Consultant Name')
    
    # Create DataFrames
    dfs = create_dataframes(xls, sheet_column_mapping, wtd_header_row, mtd_header_row, file_path)
    
    # Read extracted columns data
    extracted_df = read_extracted_columns(extracted_columns_path)
    
    # Create pivot table
    pivot_df = create_pivot_table(dfs, extracted_df,file_path)
    
    # Save pivot table data to the UtilizationReport model
    pivot_df = pivot_df.replace({np.nan: None})

    # Extract the date from file path
    file_name = os.path.basename(file_path)
    # Find the date part in the filename (e.g., '10Apr2025' from 'Latest Utilization Report 10Apr2025_xzi8ffd.xlsb')
    date_part = None
    for part in file_name.split():
        try:
            # Try to parse the first 9 characters of each part as a date
            date_part = part[:9]
            parsed_date = datetime.strptime(date_part, "%d%b%Y")
            break
        except ValueError:
            continue
    
    if date_part:
        file_date = parsed_date.strftime('%Y-%m-%d')  # e.g., '2025-04-10'
    else:
        file_date = None

    # Calculate week number
    week_number = (parsed_date.day - 1) // 7 + 1

    # Get previous week's additional days for each resource
    previous_week_data = {}
    if week_number > 1:
        # Query the previous week's data
        prev_week_date = parsed_date - timedelta(days=7)
        prev_week_records = UtilizationReport.objects.filter(date=prev_week_date.strftime('%Y-%m-%d'))
        for record in prev_week_records:
            previous_week_data[record.name] = record.addtnl_days

    for _, row in pivot_df.iterrows():
        resource_name = row.get('Resource Email Address', '') or ''
        last_week_value = previous_week_data.get(resource_name, 0) if week_number > 1 else 0

        UtilizationReport.objects.create(
        name=resource_name,
        administrative=row.get('Administrative') or 0,
        billable_days=row.get('Billable Hours') or 0,
        training=row.get('Training') or 0,
        unassigned=row.get('Unassigned') or 0,
        vacation=row.get('Vacation') or 0,
        grand_total=row.get('Grand Total') or 0,
        last_week=last_week_value,
        status=row.get('Status') or '',
        addtnl_days=row.get('Additional Days') or 0,
        wtd_actual=row.get('WTD Actual') or 0,
        spoc=row.get('Track') or '',
        comments=None,
        spoc_comments=None,
        rdm='',
        track=row.get('Track') or '',
        billing=row.get('Billing') or '',
        date=file_date
    )
        
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