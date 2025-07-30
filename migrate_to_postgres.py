import pandas as pd
import asyncpg
import asyncio
import os

from config import settings

CSV_PATH = os.path.join(os.path.dirname(__file__), "test imports", "db.csv")

CANONICAL_COLS = [
    'EmployeeID', 'Username', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
    'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
    'MobilePhone', 'EmploymentType', 'EmploymentStatus'
]

async def migrate():
    if not os.path.exists(CSV_PATH):
        print(f"Source file not found: {CSV_PATH}")
        return

    conn = None
    try:
        # Read and prepare data with pandas
        print(f"Reading data from {CSV_PATH}...")
        df = pd.read_csv(CSV_PATH, dtype=str)
        df = df.where(pd.notnull(df), None) # Use None for DB NULL

        # Ensure all canonical columns exist
        for col in CANONICAL_COLS:
            if col not in df.columns:
                df[col] = None
        
        df_to_db = df[CANONICAL_COLS]
        records = [tuple(r) for r in df_to_db.to_numpy()]

        # Connect to PostgreSQL
        conn = await asyncpg.connect(settings.DATABASE_URL)
        print("Connected to PostgreSQL database.")

        # Create table (idempotent)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS employees (
                {', '.join([f'"{col}" TEXT' for col in CANONICAL_COLS])},
                PRIMARY KEY ("EmployeeID")
            )
        """)
        print("Table 'employees' verified.")

        # Clear existing data
        await conn.execute("TRUNCATE TABLE employees")
        print("Cleared existing data from 'employees' table.")

        # Insert new data using copy_records_to_table for high performance
        await conn.copy_records_to_table('employees', records=records, columns=CANONICAL_COLS)

        print(f"Successfully migrated {len(df_to_db)} records to PostgreSQL.")

    except Exception as e:
        print(f"An error occurred during migration: {e}")
    finally:
        if conn and not conn.is_closed():
            await conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    print("Starting PostgreSQL data migration...")
    print("NOTE: This script will TRUNCATE the 'employees' table before inserting data.")
    print("If using Docker, run 'docker-compose up -d' first.")
    print("Then, in your local terminal, set the DATABASE_URL environment variable to point to localhost:")
    print("e.g., $env:DATABASE_URL='postgresql://user:password@localhost:5432/dannybase' (PowerShell)")
    asyncio.run(migrate())