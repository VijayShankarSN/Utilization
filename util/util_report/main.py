
# importing libraries
import os
from datetime import datetime, timedelta

import pandas as pd
from django.utils.dateparse import parse_date

from Util_report.models import ReportReq, ExclusionTable, UtilizationReport


# importing packages


class UtilizationReportGenerator:

    def __init__(self, file_path):
        self.file_path = file_path
        self.parsed_date = None
        self.prev_week_date = None
        self.file_date = None
        self.month_name = None
        self.week_number = None
        self.total_days = None
        self.xls = None
        self.engine = None
        self.dfs = None
        self.sheet_column_mapping = None
        self.dams_utilization = None
        self.initial_report = None
        self.merged_report = None
        self.final_report = None
        self.exclusion_set = None

    def parse_date_from_filename(self):
        """Extract and parse date information from the filename."""
        date_part = os.path.splitext(self.file_path)[0].split()[-1]  # e.g., '10Apr2025'
        self.parsed_date = datetime.strptime(date_part, "%d%b%Y")  # datetime object

        # Get MySQL-compatible date string
        self.file_date = self.parsed_date.strftime('%Y-%m-%d')  # e.g., '2025-04-10'
        self.prev_week_date = self.parsed_date - timedelta(days=7)
        self.week_number = (self.parsed_date.day - 1) // 7 + 1
        self.month_name = self.parsed_date.strftime('%B')
        self.total_days = self.week_number * 5

        return self.parsed_date, self.prev_week_date, self.file_date, self.month_name, self.week_number, self.total_days

    def read_excel_file(self):
        """Read and validate the Excel file."""
        # Determine the correct engine based on file extension
        file_ext = os.path.splitext(self.file_path)[-1].lower()
        engine_map = {".xlsb": "pyxlsb", ".xlsx": "openpyxl", ".xlsm": "openpyxl", ".xls": "xlrd"}

        if file_ext not in engine_map:
            raise ValueError(f"Unsupported file format: {file_ext}")

        self.engine = engine_map[file_ext]
        self.xls = pd.ExcelFile(self.file_path, engine=self.engine)
        return self.xls, self.engine

    def find_header_row(self, sheet_name, target_column):
        """Find the header row in a specific sheet."""
        raw_df = pd.read_excel(self.xls, sheet_name=sheet_name, engine=self.engine, header=None)

        for idx, row in raw_df.iterrows():
            if target_column in row.values:
                return idx

        raise ValueError(f"Header containing '{target_column}' not found in {sheet_name}.")

    def initialize_column_mapping(self):
        """Initialize the column mapping for different sheets."""
        self.sheet_column_mapping = {
            'WTD': {
                'columns': ['Consultant Name', 'Manager Name', 'WTD Capacity', 'Billable Hours', 'Utl %', 'CC'],
                'cc_column': 'CC'
            },
            'MTD': {
                'base_columns': ['Resource Email Address', 'Project Number', 'Project Name',
                                 'Work Type Description-OPS', self.month_name, 'Cost Center - OPS'],
                'cc_column': 'Cost Center - OPS'
            }
        }
        return self.sheet_column_mapping

    def create_dataframes(self):
        """Create and filter dataframes from the Excel sheets."""
        wtd_header_row = self.find_header_row('WTD', 'Consultant Name')
        mtd_header_row = self.find_header_row('Consultant Summary', 'Resource Email Address')

        self.dfs = {
            'WTD': pd.read_excel(self.xls, sheet_name='WTD',
                                 usecols=self.sheet_column_mapping['WTD']['columns'],
                                 skiprows=wtd_header_row)
            .query(f"`{self.sheet_column_mapping['WTD']['cc_column']}` == 504686"),

            'MTD': pd.read_excel(self.xls, sheet_name='Consultant Summary',
                                 usecols=self.sheet_column_mapping['MTD']['base_columns'],
                                 skiprows=mtd_header_row)
            .query(f"`{self.sheet_column_mapping['MTD']['cc_column']}` == 504686")
        }

        self.dfs['WTD']['WTD Actuals'] = self.dfs['WTD']['Billable Hours'] / 8
        self.dfs['WTD']['Utl %'] = self.dfs['WTD']['Utl %'] * 100
        self.dfs['MTD'] = self.dfs['MTD'].dropna(subset=[self.month_name])
        self.dfs['MTD']['Days'] = self.dfs['MTD'][self.month_name] / 8
        return self.dfs

    def process_report(self):
        """Main method to process the utilization report."""
        # Parse date information
        self.parse_date_from_filename()

        # Read Excel file
        self.read_excel_file()

        # Initialize column mapping
        self.initialize_column_mapping()

        # Create dataframes
        self.create_dataframes()

        return {
            'file_date': self.file_date,
            'month_name': self.month_name,
            'week_number': self.week_number,
            'dataframes': self.dfs
        }

    def calculate_dams_utilization(self):
        total_capacity = self.dfs['WTD']['WTD Capacity'].sum()
        total_utilization = self.dfs['WTD']['Billable Hours'].sum()
        self.dams_utilization = round(total_utilization / total_capacity * 100, 3)
        return self.dams_utilization

    def generate_report(self):
        self.initial_report = self.dfs['MTD'].pivot_table(
            index="Resource Email Address",
            columns="Work Type Description-OPS",
            values="Days",
            aggfunc="sum",  # Summing up the days if multiple rows exist for the same combination
            fill_value=0  # Filling NaNs with 0
        ).reset_index()

        start_col = 'Administrative'
        end_col = 'Vacation'

        # Get the position of these columns
        start_idx = self.initial_report.columns.get_loc(start_col)
        end_idx = self.initial_report.columns.get_loc(end_col)

        # Create the sum across the selected columns range
        self.initial_report['Grand Total'] = self.initial_report.iloc[:, start_idx:end_idx + 1].sum(axis=1)
        self.initial_report = self.initial_report.merge(
            self.dfs['WTD'][['Consultant Name', 'WTD Actuals']],
            on="Resource Email Address",
            how='left'  # Use 'left' join to keep all rows in initial_report
        )

        return self.initial_report

    # Add NaN handling to the relevant columns before aggregation
    def add_additional_days_column(self):

        if self.week_number > 1:
            prev_data = UtilizationReport.objects.filter(
                date=self.prev_week_date.strftime('%Y-%m-%d')
            ).values('resource_email_address', 'addtnl_days')

            last_week_map = {entry['resource_email_address']: entry['addtnl_days'] for entry in prev_data}
        else:
            last_week_map = {}

        self.initial_report['Last Week'] = self.initial_report['Resource Email Address'].map(last_week_map).fillna(0)

        # Step 3: Calculate total logged days
        self.initial_report['Total Logged'] = (
                self.initial_report.get('Billable Hours', 0) +
                self.initial_report.get('Vacation', 0) +
                self.initial_report['Last Week']
        ).fillna(0)  # Ensuring no NaN in total logged

        def compute_additional_days_vec(df):
            # Sanitize the 'Billing' column to handle unexpected values
            df['Billing'] = df['Billing'].str.strip().replace({'None': 'TBD', '': 'TBD'})

            add_days = pd.Series(0, index=df.index)

            billing_mask = df['Billing'] == 'Billing'
            partial_mask = df['Billing'] == 'Partial'

            # For Billing
            shortfall = self.total_days - df.loc[billing_mask, 'Total Logged']
            add_days.loc[billing_mask] = shortfall.clip(lower=0)

            # For Partial
            partial_days = self.total_days / 2
            shortfall_partial = partial_days - df.loc[partial_mask, 'Total Logged']
            add_days.loc[partial_mask] = shortfall_partial.clip(lower=0)

            return add_days

        # Add the computed additional days column
        self.initial_report['Additional Days'] = compute_additional_days_vec(self.initial_report)

        return self.initial_report

    def merge_from_models(self):
        # Fetch required fields from Django model
        mysql_df = pd.DataFrame.from_records(
            ReportReq.objects.values('row_labels', 'rdm', 'track', 'billing')
        )
        self.merged_report = pd.merge(
            self.initial_report,
            mysql_df,
            how='left',
            left_on='Resource Email Address',
            right_on='row_labels'
        )
        self.merged_report['Resource Email Address'] = self.merged_report['Resource Email Address'].astype(str)
        self.merged_report['Track'] = self.merged_report['track'].astype(str)
        self.merged_report['Billing'] = self.merged_report['billing'].astype(str)
        self.merged_report['RDM'] = self.merged_report['RDM'].fillna('Adam')
        self.merged_report['Billing'] = self.merged_report['Billing'].replace(to_replace='None', value='TBD')

        # Drop the redundant column if needed
        self.merged_report.drop(columns=['row_labels'], inplace=True)
        return self.merged_report

    def determine_status(self, row):
        """Determine the status based on billing type and hours logged."""
        # Safely get and clean values
        billing_type = str(row.get('Billing', '')).strip()
        dept_mgmt = row.get('Department Mgmt', 0) or 0
        admin = row.get('Administrative', 0) or 0
        billable_hours = row.get('Billable Hours', 0) or 0
        vacation = row.get('Vacation', 0) or 0
        total_logged = billable_hours + vacation
        # Priority-based checks
        # if dept_mgmt >= 1 or admin >= 1:
        #     return 'close'
        if billing_type == 'Billing':  # Full Billable
            return 'close' if total_logged >= self.total_days else 'open'
        if billing_type == 'Partial':
            return 'close' if total_logged >= self.total_days / 2 else 'open'
        if billing_type in {'Next', 'TBD'}:
            return 'close' if total_logged >= self.total_days else 'open'
        if billing_type in {'On Bench', 'Non Billable', 'Released'}:
            return 'close'
        # Fallback/default
        return 'open'

    def apply_status(self):
        """Apply status to the final report."""
        self.merged_report['Status'] = self.merged_report.apply(self.determine_status, axis=1)
        return self.merged_report

    def get_exclusion_list(self):
        """Get exclusion list from ExclusionTable model and convert to set."""
        exclusion_records = ExclusionTable.objects.values_list('exclusion_list', flat=True)
        self.exclusion_set = set(email.strip() for email in exclusion_records if email)
        return self.exclusion_set

    def filter_exclusions(self):
        """Update status to 'close' for excluded emails that are currently 'open'."""
        # Create a mask for open statuses where email is in exclusion set
        mask = (self.merged_report['Status'] == 'open') & (
            self.merged_report['Resource Email Address'].isin(self.exclusion_set)
        )
        # Update Status to 'close' for the masked rows
        self.merged_report.loc[mask, 'Status'] = 'close'

        return self.merged_report

    def generate_final_report(self):
        self.process_report()
        self.generate_report()
        self.add_additional_days_column()
        self.merge_from_models()
        self.apply_status()
        self.get_exclusion_list()
        self.filter_exclusions()
        self.final_report = self.merged_report
        return self.final_report

    def save_to_model(self):
        """Save the final merged report to the Django model."""
        records_to_save = []

        for _, row in self.merged_report.iterrows():
            try:
                record = UtilizationReport(
                    resource_email_address=row.get('Resource Email Address'),
                    administrative=row.get('Administrative', 0),
                    billable_hours=row.get('Billable Hours', 0),
                    department_mgmt=row.get('Department Mgmt', 0),
                    investment=row.get('Investment', 0),
                    presales=row.get('Presales', 0),
                    training=row.get('Training', 0),
                    unassigned=row.get('Unassigned', 0),
                    vacation=row.get('Vacation', 0),
                    grand_total=row.get('Grand Total', 0),
                    rdm=row.get('RDM'),
                    track=row.get('Track'),
                    billing=row.get('Billing'),
                    status=row.get('Status'),
                    date=parse_date(self.file_date)
                )
                records_to_save.append(record)
            except Exception as e:
                print(f"Error creating record for {row.get('Resource Email Address')}: {e}")

        try:
            # Bulk create for better performance
            UtilizationReport.objects.bulk_create(records_to_save)
            print(f"{len(records_to_save)} records saved successfully.")
        except Exception as e:
            print("Error during bulk_create:", e)


# File is taken as input and the file path is passed for report generation

# Instantiate and run the report
report = UtilizationReportGenerator(file_path)

# Generate the full report (runs all internal steps)
final_df = report.generate_final_report()

# (Optional) Save to database
report.save_to_model()

