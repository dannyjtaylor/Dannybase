import pandas as pd
import logging
import os

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_username(first_name, last_name):
    """
    Generates a username from a first and last name.
    Format: first initial + last name, all lowercase.
    Spaces are removed from the last name (e.g., "Van Horn" -> "vanhorn").
    """
    if not first_name or not isinstance(first_name, str) or not isinstance(last_name, str):
        return None
    
    # Username format: first initial + last name (with spaces removed), all lowercase.
    username = (first_name[0] + last_name.replace(' ', '')).lower()
    return username

def main():
    """
    Generates usernames for employees in 'Final_Import.csv' based on their
    FirstName and LastName. The script updates the 'Username' column and flags
    potential issues like duplicates, hyphens, and multi-word last names.
    """
    # --- File Path Configuration ---
    # Build paths relative to the script's location for robustness
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_file = os.path.join(script_dir, 'Final', 'Final_Import.csv')

    logging.info("Starting username generation process...")

    if not os.path.exists(target_file):
        logging.error(f"Target file not found: {target_file}")
        return

    try:
        # Load the target file to be updated
        df_target = pd.read_csv(target_file)
        logging.info(f"Loaded {len(df_target)} records from {target_file}.")

        username_tracker = {}

        # Iterate over each row in the target file to update it
        for index, target_row in df_target.iterrows():
            emp_id = target_row.get('EmployeeID')
            first_name = str(target_row.get('FirstName', ''))
            last_name = str(target_row.get('LastName', ''))

            if not first_name or not last_name:
                logging.warning(f"Skipping EmployeeID {emp_id or 'N/A'} due to missing FirstName or LastName.")
                continue

            username = generate_username(first_name, last_name)
            df_target.at[index, 'Username'] = username
            logging.info(f"Generated username for EmployeeID {emp_id} ({first_name} {last_name}): {username}")

            # --- Debugging Flags ---
            if ' ' in last_name.strip():
                logging.warning(f"  [FLAG] EmployeeID {emp_id}: LastName '{last_name}' contains a space.")
            if '-' in username:
                logging.warning(f"  [FLAG] EmployeeID {emp_id}: Username '{username}' contains a hyphen.")

            # Track for duplicates
            if username in username_tracker:
                username_tracker[username].append(emp_id)
            else:
                username_tracker[username] = [emp_id]

        # --- Final Duplicate Check ---
        logging.info("--- Checking for duplicate usernames ---")
        has_duplicates = False
        for username, emp_ids in username_tracker.items():
            if len(emp_ids) > 1:
                logging.warning(f"  [FLAG] Duplicate username '{username}' found for EmployeeIDs: {emp_ids}")
                has_duplicates = True
        if not has_duplicates:
            logging.info("No duplicate usernames were found.")

        # --- Final Data Type Conversion ---
        # Only convert the key column to ensure data integrity.
        df_target['EmployeeID'] = pd.to_numeric(df_target['EmployeeID'], errors='coerce').astype('Int64').fillna(0).astype(int)

        # Save the updated dataframe back to the target CSV file
        df_target.to_csv(target_file, index=False)
        logging.info(f"Successfully generated usernames and saved data to {target_file}")

    except Exception as e:
        logging.error(f"A critical error occurred during the script execution: {e}")

if __name__ == "__main__":
    main()