import numpy as np
import pandas as pd
import os
from datetime import datetime

def extract_data():
    # Path to your Excel file
    file_path = 'C:/Users/Thrivikram Bhat V/Desktop/Utilization-Thrivikram/Utilization/util/new Utilization Report 14Mar2025.xlsb'

    # Function to read data from Excel
    def read_data_from_excel(file_path):
        file_ext = os.path.splitext(file_path)[-1].lower()
        engine_map = {".xlsb": "pyxlsb", ".xlsx": "openpyxl", ".xlsm": "openpyxl", ".xls": "xlrd"}
        if file_ext not in engine_map:
            raise ValueError(f"Unsupported file format: {file_ext}")
        engine = engine_map[file_ext]
        xls = pd.ExcelFile(file_path, engine=engine)
        return xls, engine

    # Read the Excel file
    xls, xl_engine = read_data_from_excel(file_path)

    # Get the current month name
    current_month = datetime.now().strftime('%B')

    # Define sheets and columns
    sheet_column_mapping = {
        'WTD': {
            'columns': ['Consultant Name', 'Manager Name', 'WTD Capacity', 'Billable Hours', 'Utl %', 'CC'],
            'cc_column': 'CC'
        },
        'MTD': {
            'base_columns': ['Resource Email Address', 'Project Number', 'Project Name', 'Work Type Description-OPS', current_month, 'Cost Center - OPS'],
            'cc_column': 'Cost Center - OPS'
        }
    }

    # Function to find the header row dynamically
    def find_header_row(sheet_name, target_column):
        raw_df = pd.read_excel(xls, sheet_name=sheet_name, engine=xl_engine, header=None)
        for idx, row in raw_df.iterrows():
            if target_column in row.values:
                return idx
        raise ValueError(f"Header containing '{target_column}' not found in {sheet_name}.")

    # Detect header rows
    mtd_header_row = find_header_row('Consultant Summary', 'Resource Email Address')
    wtd_header_row = find_header_row('WTD', 'Consultant Name')

    # Create DataFrames
    def create_dataframes(xls, sheet_column_mapping, wtd_header_row, mtd_header_row):
        dfs = {
            'WTD': pd.read_excel(xls, sheet_name='WTD', usecols=sheet_column_mapping['WTD']['columns'], skiprows=wtd_header_row)
                  .query(f"`{sheet_column_mapping['WTD']['cc_column']}` == 504686"),
            'MTD': pd.read_excel(xls, sheet_name='Consultant Summary', usecols=sheet_column_mapping['MTD']['base_columns'], skiprows=mtd_header_row)
                  .query(f"`{sheet_column_mapping['MTD']['cc_column']}` == 504686")
        }
        return dfs

    dfs = create_dataframes(xls, sheet_column_mapping, wtd_header_row, mtd_header_row)

    # Print extracted data to the console
    print("WTD DataFrame:")
    print(dfs['WTD'].head())
    print("MTD DataFrame:")
    print(dfs['MTD'].head())

    return dfs