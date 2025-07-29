import pandas as pd
import sqlite3
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), "db.csv")
DB_PATH = os.path.join(os.path.dirname(__file__), "dannybase.db")

CANONICAL_COLS = [
    'EmployeeID', 'Username', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
    'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
    'MobilePhone', 'EmploymentType', 'EmploymentStatus'
]

def migrate():
    if not os.path.exists(CSV_PATH):
        print(f"Source file not found: {CSV_PATH}")
        return

    try:
        df = pd.read_csv(CSV_PATH)
        df = df.where(pd.notnull(df), 'N/A').replace('', 'N/A')

        # Ensure all canonical columns exist
        for col in CANONICAL_COLS:
            if col not in df.columns:
                df[col] = 'N/A'
        
        # Keep only canonical columns for the database
        df_to_db = df[CANONICAL_COLS]

        conn = sqlite3.connect(DB_PATH)
        df_to_db.to_sql('employees', conn, if_exists='replace', index=False)
        conn.close()

        print(f"Successfully migrated {len(df_to_db)} records from {CSV_PATH} to {DB_PATH}")

    except Exception as e:
        print(f"An error occurred during migration: {e}")

if __name__ == "__main__":
    migrate()