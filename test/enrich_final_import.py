import pandas as pd
import logging
import os

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def enrich_employee_data():
    """
    Enriches 'Final_ImportF.csv' with data from 'jostUsersMinus.csv'.

    This script updates the following fields in the target file:
    - OfficeLocation
    - Supervisor
    - OfficePhoneAndExtension
    - MobilePhone

    It uses 'EmployeeID' as the key for matching records between the two files.
    """
    # --- File Path Configuration ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.join(script_dir, 'Final', 'Final_ImportF.csv')
    source_path = os.path.join(script_dir, 'Final', 'BeforeFinal', 'jostUsersMinus.csv')

    logging.info("Starting data enrichment process...")

    # --- File Existence Check ---
    if not os.path.exists(target_path):
        logging.error(f"Target file not found: {target_path}")
        return
    if not os.path.exists(source_path):
        logging.error(f"Source file not found: {source_path}")
        return

    try:
        # --- Load and Prepare DataFrames ---
        df_target = pd.read_csv(target_path, dtype={'EmployeeID': str})
        logging.info(f"Loaded {len(df_target)} records from {os.path.basename(target_path)}.")

        df_source = pd.read_csv(source_path, dtype={'EmployeeID': str})
        logging.info(f"Loaded {len(df_source)} records from {os.path.basename(source_path)}.")

        # Handle potential duplicates in the source file before setting the index.
        if df_source['EmployeeID'].duplicated().any():
            logging.warning("Duplicate EmployeeIDs found in source file. Using the first occurrence of each.")
            df_source.drop_duplicates(subset='EmployeeID', keep='first', inplace=True)

        # For efficient lookup, set the index of the source df to the EmployeeID.
        df_source.set_index('EmployeeID', inplace=True)

        # --- Data Mapping ---
        columns_to_map = [
            'OfficeLocation',
            'Supervisor',
            'OfficePhoneAndExtension',
            'MobilePhone'
        ]

        logging.info("--- Updating records ---")
        for index, row in df_target.iterrows():
            emp_id = row['EmployeeID']
            if emp_id in df_source.index:
                source_row = df_source.loc[emp_id]
                logging.info(f"Processing EmployeeID: {emp_id}...")
                for col in columns_to_map:
                    source_value = source_row.get(col)
                    # Only update if the source value is not null/NaN to avoid overwriting with blanks
                    if pd.notna(source_value):
                        df_target.at[index, col] = source_value
                        logging.info(f"  -> Mapped '{col}': {source_value}")
            else:
                logging.warning(f"  EmployeeID {emp_id} not found in source file. Skipping.")

        # --- Save Results ---
        logging.debug(f"Data to be written to {target_path}:\n{df_target.head().to_string()}")
        df_target.to_csv(target_path, index=False)
        logging.info(f"Successfully enriched and saved data to {target_path}")

    except Exception as e:
        logging.error(f"A critical error occurred during the script execution: {e}")

if __name__ == "__main__":
    enrich_employee_data()