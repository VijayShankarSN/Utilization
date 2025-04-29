"""
Utilization Report Generator module
Reads Excel files and processes utilization data to generate reports
"""

# importing libraries
import os
from datetime import datetime, timedelta
import re
import io
import logging

import pandas as pd
from django.utils.dateparse import parse_date

from .models import ResourceDetailsFetch, ExclusionTableModel, UtilizationReportModel

# Set up logging
logger = logging.getLogger(__name__)


class UtilizationReportGenerator:
    """Processes Excel files to generate utilization reports."""

    def __init__(self, file_path):
        """Initialize the report generator with a file path."""
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
        self.total_capacity = None
        self.dams_utilization = None
        self.initial_report = None
        self.merged_report = None
        self.final_report = None
        self.exclusion_set = None

    def parse_date_from_filename(self):
        """Extract and parse date information from the filename."""
        # Extract only the part that looks like a date, e.g., 10Apr2025
        match = re.search(r'(\d{1,2}[A-Za-z]{3}\d{4})', os.path.basename(self.file_path))
        if not match:
            raise ValueError("Filename does not contain a valid date format like '10Apr2025'.")

        date_part = match.group(1)
        self.parsed_date = datetime.strptime(date_part, "%d%b%Y")

        self.file_date = self.parsed_date.strftime('%Y-%m-%d')
        self.prev_week_date = self.parsed_date - timedelta(days=7)
        self.week_number = (self.parsed_date.day - 1) // 7 + 1
        self.month_name = self.parsed_date.strftime('%B')
        self.total_days = self.week_number * 5

        return self.parsed_date, self.prev_week_date, self.file_date, self.month_name, self.week_number, self.total_days

    def read_excel_file(self):
        """Read and validate the Excel file from disk safely and close the handle."""
        # Determine the correct engine based on file extension
        file_ext = os.path.splitext(self.file_path)[-1].lower()
        engine_map = {".xlsb": "pyxlsb", ".xlsx": "openpyxl", ".xlsm": "openpyxl", ".xls": "xlrd"}

        if file_ext not in engine_map:
            raise ValueError(f"Unsupported file format: {file_ext}")

        self.engine = engine_map[file_ext]

        try:
            # Read into memory to avoid locking issues
            with open(self.file_path, 'rb') as f:
                file_bytes = io.BytesIO(f.read())

            # Read the Excel file from memory
            self.xls = pd.ExcelFile(file_bytes, engine=self.engine)
            return self.xls, self.engine
        except Exception as e:
            logger.error(f"Error reading Excel file {self.file_path}: {e}")
            raise ValueError(f"Could not read Excel file: {str(e)}")

    def find_header_row(self, sheet_name, target_column):
        """Find the header row in a specific sheet."""
        try:
            # Read only the first 20 rows to find the header - optimization
            raw_df = pd.read_excel(self.xls, sheet_name=sheet_name, engine=self.engine, header=None, nrows=20)

            for idx, row in raw_df.iterrows():
                if target_column in row.values:
                    return idx

            raise ValueError(f"Header containing '{target_column}' not found in {sheet_name}.")
        except Exception as e:
            logger.error(f"Error finding header row: {e}")
            raise

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
        try:
            wtd_header_row = self.find_header_row('WTD', 'Consultant Name')
            mtd_header_row = self.find_header_row('Consultant Summary', 'Resource Email Address')

            # Only read the specific columns we need - optimization
            # For WTD sheet, only read the rows we need (more efficient)
            self.dfs = {
                'WTD': pd.read_excel(
                    self.xls, 
                    sheet_name='WTD',
                    usecols=self.sheet_column_mapping['WTD']['columns'],
                    skiprows=wtd_header_row,
                    # Using dtype for performance improvement
                    dtype={
                        'WTD Capacity': 'float32',
                        'Billable Hours': 'float32',
                        'Utl %': 'float32',
                    },
                    # Apply filtering during read for optimization
                    converters={self.sheet_column_mapping['WTD']['cc_column']: lambda x: str(x).strip()}
                )
            }
            
            # Apply filter after reading (using vectorized operations for better performance)
            cc_column = self.sheet_column_mapping['WTD']['cc_column']
            self.dfs['WTD'] = self.dfs['WTD'][self.dfs['WTD'][cc_column] == '504686']
            
            # Calculate individual utilization using vectorized operations
            self.dfs['WTD']['Individual Utilization'] = (self.dfs['WTD']['Billable Hours'] / self.dfs['WTD']['WTD Capacity'] * 100).round(2)
            
            # Read MTD data with optimized dtypes
            self.dfs['MTD'] = pd.read_excel(
                self.xls, 
                sheet_name='Consultant Summary',
                usecols=self.sheet_column_mapping['MTD']['base_columns'],
                skiprows=mtd_header_row,
                # Using dtype for performance improvement
                dtype={self.month_name: 'float32'},
                # Apply filtering during read for optimization
                converters={self.sheet_column_mapping['MTD']['cc_column']: lambda x: str(x).strip()}
            )
            
            # Apply filter after reading (using vectorized operations for better performance)
            cc_column = self.sheet_column_mapping['MTD']['cc_column']
            self.dfs['MTD'] = self.dfs['MTD'][self.dfs['MTD'][cc_column] == '504686']

            # Calculate derived fields using vectorized operations
            self.dfs['WTD']['WTD Actuals'] = self.dfs['WTD']['Billable Hours'] / 8
            self.dfs['WTD']['Utl %'] = self.dfs['WTD']['Utl %'] * 100
            
            # Remove rows with NaN values in month column
            self.dfs['MTD'] = self.dfs['MTD'].dropna(subset=[self.month_name])
            
            # Calculate days
            self.dfs['MTD']['Days'] = self.dfs['MTD'][self.month_name] / 8
            
            return self.dfs
        except Exception as e:
            logger.error(f"Error creating dataframes: {e}")
            raise

    def process_report(self):
        """Main method to process the utilization report."""
        try:
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
        except Exception as e:
            logger.error(f"Error processing report: {e}")
            raise

    def calculate_dams_utilization(self):
        """Calculate the DAMS utilization percentage."""
        try:
            total_capacity = self.dfs['WTD']['WTD Capacity'].sum()
            total_utilization = self.dfs['WTD']['Billable Hours'].sum()
            self.total_capacity = total_capacity
            self.dams_utilization = round(total_utilization / total_capacity * 100, 2)
            return self.dams_utilization
        except Exception as e:
            logger.error(f"Error calculating DAMS utilization: {e}")
            self.dams_utilization = 0
            return 0

    def calculate_capable_utilization(self):
        """Calculate the capable utilization percentage using the formula: ((total utilization + (additional days * 8)) * 100)."""
        try:
            total_capacity = self.dfs['WTD']['WTD Capacity'].sum()
            total_utilization = self.dfs['WTD']['Billable Hours'].sum()
            total_additional_days = self.merged_report['Additional Days'].sum() if self.merged_report is not None else 0
            
            # Calculate capable utilization: ((total utilization + (additional days * 8)) * 100)
            capable_utilization = ((total_utilization + (total_additional_days * 8)) / total_capacity * 100) if total_capacity > 0 else 0
            self.capable_utilization = round(capable_utilization, 2)
            return self.capable_utilization
        except Exception as e:
            logger.error(f"Error calculating capable utilization: {e}")
            self.capable_utilization = 0
            return 0

    def generate_report(self):
        """Generate the initial report by pivoting and merging data."""
        try:
            # Use a more efficient pivot implementation
            # Pre-filter columns for pivot to avoid unnecessary processing
            pivot_data = self.dfs['MTD'][['Resource Email Address', 'Work Type Description-OPS', 'Days']]
            
            # Pivoting MTD data
            self.initial_report = pivot_data.pivot_table(
                index="Resource Email Address",
                columns="Work Type Description-OPS",
                values="Days",
                aggfunc="sum",
                fill_value=0
            ).reset_index()

            logger.info("Initial Report Generated")
            logger.debug(f"Initial report columns: {self.initial_report.columns.tolist()}")

            # Ensure required columns exist for grand total calculation
            required_cols = ['Administrative', 'Vacation']
            for col in required_cols:
                if col not in self.initial_report.columns:
                    logger.warning(f"Required column {col} not found in data. Adding empty column.")
                    self.initial_report[col] = 0

            # Calculate Grand Total across relevant work types more efficiently
            try:
                # Get numeric columns only for faster calculation
                numeric_cols = self.initial_report.select_dtypes(include=['number']).columns
                self.initial_report['Grand Total'] = self.initial_report[numeric_cols].sum(axis=1)
            except Exception as e:
                logger.error(f"Error calculating Grand Total: {e}")
                # Simplified fallback calculation
                numeric_cols = self.initial_report.select_dtypes(include=['number']).columns
                self.initial_report['Grand Total'] = self.initial_report[numeric_cols].sum(axis=1)

            # Optimize merge operation
            # Select only the columns we need from WTD data
            wtd_data = self.dfs['WTD'][['Consultant Name', 'WTD Actuals']]
            
            # Merge with initial report (optimize by pre-selecting columns)
            self.initial_report = pd.merge(
                self.initial_report,
                wtd_data,
                left_on='Resource Email Address',
                right_on='Consultant Name',
                how='left'
            ).drop(columns=['Consultant Name'])  # Remove duplicate column

            return self.initial_report
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise

    def add_additional_days_column(self):
        """Add additional days column based on previous week data."""
        try:
            if self.merged_report is None or self.merged_report.empty:
                logger.error("Merged report is empty or None")
                return None

            logger.info(f"Week number: {self.week_number}")
            logger.info(f"Previous week date: {self.prev_week_date}")

            # Get previous week data from database - only for week > 1
            last_week_map = {}
            if self.week_number > 1:
                prev_data = UtilizationReportModel.objects.filter(
                    date=self.prev_week_date.strftime('%Y-%m-%d')
                ).values('resource_email_address', 'addtnl_days')

                logger.info(f"Found {len(prev_data)} records from previous week")
                
                # Create a mapping with lowercase keys for case-insensitive matching
                last_week_map = {entry['resource_email_address'].lower(): float(entry['addtnl_days']) 
                                for entry in prev_data if entry['resource_email_address']}
                
                logger.info(f"Last week map: {last_week_map}")
            
            # Map last week values to current report - handle None values and case sensitivity
            self.merged_report['Last Week'] = self.merged_report['Resource Email Address'].apply(
                lambda email: last_week_map.get(email.lower(), 0) if isinstance(email, str) else 0
            )
            
            # Ensure Last Week values are numeric
            self.merged_report['Last Week'] = pd.to_numeric(self.merged_report['Last Week'], errors='coerce').fillna(0)

            # Calculate total logged days using vectorized operations
            billable_hours_col = 'Billable Hours' if 'Billable Hours' in self.merged_report.columns else 'WTD Actuals'
            
            # Ensure Vacation column exists or use zero
            if 'Vacation' not in self.merged_report.columns:
                self.merged_report['Vacation'] = 0
                
            # Calculate Total Logged with properly converted numeric values
            self.merged_report['Total Logged'] = (
                pd.to_numeric(self.merged_report[billable_hours_col], errors='coerce').fillna(0) +
                pd.to_numeric(self.merged_report['Vacation'], errors='coerce').fillna(0) +
                self.merged_report['Last Week']
            )

            logger.info("Billing types in report:")
            logger.info(self.merged_report['Billing'].value_counts().to_dict())

            # Calculate additional days
            self.merged_report['Additional Days'] = self._compute_additional_days()

            logger.info("Sample of final calculations:")
            logger.info(self.merged_report[['Resource Email Address', 'Billing', 'Total Logged', 'Additional Days']].head())

            return self.merged_report
        except Exception as e:
            logger.error(f"Error adding additional days column: {e}")
            raise

    def _compute_additional_days(self):
        """Calculate additional days based on billing type and shortfall using vectorized operations."""
        try:
            # Create a default series of zeros
            add_days = pd.Series(0, index=self.merged_report.index)

            # Handle Billing column - create if missing
            if 'Billing' not in self.merged_report.columns:
                self.merged_report['Billing'] = 'TBD'
            
            # Sanitize billing values - explicitly clean the column
            self.merged_report['Billing'] = self.merged_report['Billing'].fillna('TBD')
            
            # Convert to string and clean up values
            if hasattr(self.merged_report['Billing'], 'str'):
                self.merged_report['Billing'] = (self.merged_report['Billing']
                    .str.strip()
                    .replace({'None': 'TBD', '': 'TBD', None: 'TBD', pd.NA: 'TBD'})
                )
            
            # Ensure Total Logged is numeric
            total_logged = pd.to_numeric(self.merged_report['Total Logged'], errors='coerce').fillna(0)
            
            # Get exclusion list if not already fetched
            if not hasattr(self, 'exclusion_set') or self.exclusion_set is None:
                self.get_exclusion_list()
            
            # Create masks for different billing types and exclusions
            exclusion_mask = self.merged_report['Resource Email Address'].isin(self.exclusion_set)
            billing_mask = (self.merged_report['Billing'] == 'Billing') & (~exclusion_mask)
            partial_mask = (self.merged_report['Billing'] == 'Partial') & (~exclusion_mask)

            # Calculate shortfall for 'Billing' type using vectorized operations
            if billing_mask.any():
                shortfall = self.total_days - total_logged.loc[billing_mask]
                # Explicitly cast to int64 to avoid dtype compatibility warning
                add_days.loc[billing_mask] = shortfall.clip(lower=0).astype('int64')

            # Calculate shortfall for 'Partial' type using vectorized operations
            if partial_mask.any():
                partial_days = self.total_days / 2
                shortfall_partial = partial_days - total_logged.loc[partial_mask]
                # Explicitly cast to int64 to avoid dtype compatibility warning
                add_days.loc[partial_mask] = shortfall_partial.clip(lower=0).astype('int64')

            # Final check to replace any NaNs with 0
            add_days = add_days.fillna(0)
            return add_days
        except Exception as e:
            logger.error(f"Error computing additional days: {e}", exc_info=True)
            return pd.Series(0, index=self.merged_report.index)

    def merge_from_models(self):
        """Merge data from ResourceDetailsFetch Django model."""
        try:
            # Fetch required fields from Django model
            mysql_df = pd.DataFrame.from_records(
                ResourceDetailsFetch.objects.values('row_labels', 'rdm', 'track', 'billing')
            )

            if mysql_df.empty:
                logger.warning("No resource details found in database")
                # Create a merged report with just the initial report
                self.merged_report = self.initial_report.copy()
                # Add empty columns for the fields we expect from ResourceDetailsFetch
                for col in ['rdm', 'track', 'billing']:
                    self.merged_report[col] = ''
            else:
                # Merge with initial report
                self.merged_report = pd.merge(
                    self.initial_report,
                    mysql_df,
                    how='left',
                    left_on='Resource Email Address',
                    right_on='row_labels'
                )

            # Convert columns to string to avoid NaN issues
            self.merged_report['Resource Email Address'] = self.merged_report['Resource Email Address'].astype(str)
            
            # Safely convert columns that may not exist
            for col, default in [('track', ''), ('billing', 'TBD'), ('rdm', 'Adam')]:
                if col in self.merged_report.columns:
                    self.merged_report[col] = self.merged_report[col].fillna(default).astype(str)

            # Create standardized column names
            if 'track' in self.merged_report.columns:
                self.merged_report['Track'] = self.merged_report['track']
            if 'billing' in self.merged_report.columns:
                self.merged_report['Billing'] = self.merged_report['billing'].replace(to_replace='None', value='TBD')
            elif 'Billing' not in self.merged_report.columns:
                # If Billing doesn't exist, create it
                self.merged_report['Billing'] = 'TBD'
                
            if 'rdm' in self.merged_report.columns:
                self.merged_report['RDM'] = self.merged_report['rdm'].fillna('Adam')
            elif 'RDM' not in self.merged_report.columns:
                # If RDM doesn't exist, create it
                self.merged_report['RDM'] = 'Adam'

            # Drop redundant columns
            cols_to_drop = [col for col in ['row_labels'] if col in self.merged_report.columns]
            if cols_to_drop:
                self.merged_report.drop(columns=cols_to_drop, inplace=True)

            return self.merged_report
        except Exception as e:
            logger.error(f"Error merging from models: {e}")
            # In case of error, ensure we have a valid DataFrame
            if self.merged_report is None or not isinstance(self.merged_report, pd.DataFrame):
                logger.warning("Creating empty merged_report after error")
                self.merged_report = self.initial_report.copy() if self.initial_report is not None else pd.DataFrame()
                
                # Ensure required columns exist
                for col, default in [('Billing', 'TBD'), ('RDM', 'Adam'), ('Track', '')]:
                    if col not in self.merged_report.columns:
                        self.merged_report[col] = default
            raise

    def determine_status(self, row):
        """Determine the status based on billing type and hours logged."""
        try:
            # Helper function to safely get numeric values
            def safe_float(value, default=0.0):
                if pd.isna(value) or value is None or value == '':
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # Safely get values with appropriate fallbacks
            billing_type = str(row.get('Billing', row.get('billing', ''))).strip()
            dept_mgmt = safe_float(row.get('Department Mgmt', row.get('department_mgmt', 0)))
            admin = safe_float(row.get('Administrative', row.get('administrative', 0)))
            billable_hours = safe_float(row.get('Billable Hours', row.get('billable_hours', 0)))
            vacation = safe_float(row.get('Vacation', row.get('vacation', 0)))
            total_logged = billable_hours + vacation

            # Apply business rules to determine status
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
        except Exception as e:
            logger.error(f"Error determining status: {e}")
            return 'open'  # Default to open if there's an error

    def apply_status(self):
        """Apply status to each row in the final report."""
        try:
            self.merged_report['Status'] = self.merged_report.apply(self.determine_status, axis=1)
            return self.merged_report
        except Exception as e:
            logger.error(f"Error applying status: {e}")
            raise

    def get_exclusion_list(self):
        """Get exclusion list from ExclusionTableModel and convert to set."""
        try:
            exclusion_records = ExclusionTableModel.objects.values_list('exclusion_list', flat=True)
            self.exclusion_set = set(email.strip() for email in exclusion_records if email)
            return self.exclusion_set
        except Exception as e:
            logger.error(f"Error getting exclusion list: {e}")
            self.exclusion_set = set()
            return set()

    def filter_exclusions(self):
        """Update status to 'close' for excluded emails that are currently 'open'."""
        try:
            if not self.exclusion_set:
                return self.merged_report

            # Create a mask for open statuses where email is in exclusion set
            mask = (self.merged_report['Status'] == 'open') & (
                self.merged_report['Resource Email Address'].isin(self.exclusion_set)
            )
            
            # Update Status to 'close' for the masked rows
            if any(mask):
                self.merged_report.loc[mask, 'Status'] = 'close'

            return self.merged_report
        except Exception as e:
            logger.error(f"Error filtering exclusions: {e}")
            return self.merged_report

    def generate_final_report(self):
        """Generate the full utilization report by running all processing steps."""
        try:
            logger.info("Starting report generation")
            
            self.process_report()
            logger.info("Process report completed")
            
            self.generate_report()
            logger.info("Generate report completed")
            
            self.merge_from_models()
            logger.info("Merged from models completed")
            
            self.add_additional_days_column()
            logger.info("Additional days column added")
            
            self.apply_status()
            logger.info("Status applied")
            
            self.get_exclusion_list()
            logger.info("Exclusion list retrieved")
            
            self.filter_exclusions()
            logger.info("Exclusions filtered")
            
            # Create the final report
            self.final_report = self.merged_report.copy()
            
            # Ensure all required columns exist
            if 'comments' not in self.final_report.columns:
                self.final_report['comments'] = ''
            if 'spoc_comments' not in self.final_report.columns:
                self.final_report['spoc_comments'] = ''
            
            # Round all numeric columns to 2 decimal places for better display
            for col in self.final_report.select_dtypes(include=['float', 'float32', 'float64']).columns:
                self.final_report[col] = self.final_report[col].round(2)
                
            logger.info("Final report generated successfully")
            return self.final_report
        except Exception as e:
            logger.error(f"Error generating final report: {e}", exc_info=True)
            raise

    def save_to_model(self):
        """Save the final merged report to the Django model."""
        if self.merged_report is None or self.merged_report.empty:
            logger.error("Cannot save: merged_report is None or empty")
            return
            
        # Calculate DAMS utilization before saving
        dams_utilization = self.calculate_dams_utilization()
        
        # Calculate capable utilization before saving
        capable_utilization = self.calculate_capable_utilization()
            
        # Use bulk create for better performance
        records_to_save = []
        error_count = 0

        # Replace NaN values with None in the DataFrame to avoid MySQL errors - optimize by only processing necessary columns
        for column in self.merged_report.columns:
            if pd.api.types.is_numeric_dtype(self.merged_report[column]):
                # Use more efficient nan replacement
                self.merged_report[column] = self.merged_report[column].replace({pd.NA: None, float('nan'): None})
            elif pd.api.types.is_string_dtype(self.merged_report[column]):
                # Use more efficient fillna
                self.merged_report[column] = self.merged_report[column].fillna('')

        # Define safe_float helper function outside the loop for better performance
        def safe_float(value, default=0.0):
            if pd.isna(value) or value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
                
        # Prepare batch insertion
        # Create more efficient model creation by pre-processing common fields
        file_date_parsed = parse_date(self.file_date)
        
        # Get individual utilization from WTD dataframe
        individual_util_map = dict(zip(
            self.dfs['WTD']['Consultant Name'],
            self.dfs['WTD']['Individual Utilization']
        ))
        
        # Prepare batch creation with list comprehension instead of looping
        try:
            records_to_save = []
            
            for _, row in self.merged_report.iterrows():
                # Get resource email in a safe way
                resource_email = row.get('Resource Email Address', '')
                if not resource_email:
                    continue
                    
                # Use lowercase values for database lookups
                if isinstance(resource_email, str):
                    resource_email = resource_email.lower()
                
                # Calculate total_logged from billable hours and vacation
                billable_hours = safe_float(row.get('Billable Hours', row.get('billable_hours', 0)))
                vacation = safe_float(row.get('Vacation', row.get('vacation', 0)))
                last_week = safe_float(row.get('Last Week', row.get('last_week', 0)))
                total_logged = billable_hours + vacation + last_week
                
                # Get individual utilization for this resource
                individual_utilization = safe_float(individual_util_map.get(resource_email, 0))
                
                # Create the model instance with safe gets for all fields and NaN handling
                records_to_save.append(UtilizationReportModel(
                    resource_email_address=resource_email,
                    administrative=safe_float(row.get('Administrative', row.get('administrative', 0))),
                    billable_hours=billable_hours,
                    department_mgmt=safe_float(row.get('Department Mgmt', row.get('department_mgmt', 0))),
                    investment=safe_float(row.get('Investment', row.get('investment', 0))),
                    presales=safe_float(row.get('Presales', row.get('presales', 0))),
                    training=safe_float(row.get('Training', row.get('training', 0))),
                    unassigned=safe_float(row.get('Unassigned', row.get('unassigned', 0))),
                    vacation=vacation,
                    grand_total=safe_float(row.get('Grand Total', row.get('grand_total', 0))),
                    last_week=last_week,
                    total_logged=total_logged,  # Added total_logged field
                    status=row.get('Status', row.get('status', 'open')) or 'open',
                    addtnl_days=safe_float(row.get('Additional Days', row.get('addtnl_days', 0))),
                    wtd_actuals=safe_float(row.get('WTD Actuals', row.get('wtd_actuals', 0))),
                    rdm=row.get('RDM', row.get('rdm', 'Adam')) or 'Adam',
                    track=row.get('Track', row.get('track', '')) or '',
                    billing=row.get('Billing', row.get('billing', 'TBD')) or 'TBD',
                    spoc=row.get('RDM', row.get('rdm', 'Adam')) or 'Adam',  # SPOC is the same as RDM
                    comments=row.get('comments', '') or '',
                    spoc_comments=row.get('spoc_comments', '') or '',
                    date=file_date_parsed,
                    dams_utilization=dams_utilization,  # Add DAMS utilization
                    capable_utilization=capable_utilization,  # Add capable utilization
                    individual_utilization=individual_utilization,  # Add individual utilization
                    total_capacity=self.total_capacity  # Store total capacity for the date
                ))
            
        except Exception as e:
            logger.error(f"Error creating records: {e}")
            raise
            
        try:
            # Use batch size for better performance on large datasets
            if records_to_save:
                # Use a larger batch size for better performance
                UtilizationReportModel.objects.bulk_create(records_to_save, batch_size=500)
                logger.info(f"{len(records_to_save)} records saved successfully.")
            else:
                logger.warning("No records to save")
        except Exception as e:
            logger.error(f"Error during bulk_create: {e}")
            raise 