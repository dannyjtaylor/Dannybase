import pandas as pd
import logging
import os

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def validate_usernames():
    """
    Compares usernames between 'Final_Import.csv' and 'jostUsers.csv'
    using EmployeeID as the key.

    - Reads 'jostUsers.csv' (as a TSV) and 'Final_Import.csv'.
    - Cleans the email-style username from 'jostUsers.csv' for comparison.
    - Logs any mismatches or EmployeeIDs that are not found in both files.
    """
    # --- File Path Configuration ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # NOTE: The request mentioned 'FinalImportNOTES.csv', but based on the provided context,
    # 'Final_Import.csv' is the file being generated and is the logical target for validation.
    final_import_path = os.path.join(script_dir, 'Final', 'Final_Import.csv')
    jost_users_path = os.path.join(script_dir, 'Final', 'BeforeFinal', 'jostUsers.csv')

    logging.info("Starting username validation process...")

    # --- File Existence Check ---
    if not os.path.exists(final_import_path):
        logging.error(f"Target file not found: {final_import_path}")
        return
    if not os.path.exists(jost_users_path):
        logging.error(f"Source user file not found: {jost_users_path}")
        return

    try:
        # --- Load and Prepare DataFrames ---
        # Load the source of truth for usernames, ensuring EmployeeID is a string for accurate matching.
        df_jost = pd.read_csv(jost_users_path, sep='\t', dtype={'EmployeeID': str})
        df_jost['CleanUsername'] = df_jost['Username'].str.split('@').str[0]
        logging.info(f"Loaded {len(df_jost)} records from {os.path.basename(jost_users_path)}.")

        # Create a lookup map for efficient comparison: {EmployeeID: CleanUsername}
        jost_username_map = df_jost.set_index('EmployeeID')['CleanUsername'].to_dict()

        # Load the file to be validated, also treating EmployeeID as a string.
        df_final = pd.read_csv(final_import_path, dtype={'EmployeeID': str})
        logging.info(f"Loaded {len(df_final)} records from {os.path.basename(final_import_path)}.")

        mismatch_count = 0
        logging.info("--- Comparing Usernames ---")

        # --- Iterate and Compare ---
        for index, row in df_final.iterrows():
            emp_id = row.get('EmployeeID')
            final_username = row.get('Username')
            expected_username = jost_username_map.get(emp_id)

            if expected_username is None:
                logging.warning(f"Row {index + 2}: EmployeeID '{emp_id}' from '{os.path.basename(final_import_path)}' not found in '{os.path.basename(jost_users_path)}'.")
                mismatch_count += 1
            elif final_username != expected_username:
                logging.warning(f"Row {index + 2}: Mismatch for EmployeeID '{emp_id}'. Expected: '{expected_username}', Found: '{final_username}'.")
                mismatch_count += 1

        logging.info("--- Validation Complete ---")
        if mismatch_count == 0:
            logging.info("Success! All usernames match between the two files.")
        else:
            logging.error(f"Found {mismatch_count} total mismatches or missing IDs.")

    except Exception as e:
        logging.error(f"A critical error occurred during the script execution: {e}")

if __name__ == "__main__":
    validate_usernames()