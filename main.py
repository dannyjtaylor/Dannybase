"""
FastAPI backend for Winter Haven Database
- Serves static frontend (HTML/JS/CSS)
- Manages employee records in CSV (db.csv)
- Uses pandas for CSV I/O
- Uses Jinja2 for HTML templates
"""

# --- All Imports ---
import os
import io
import logging
import re
import asyncio
import base64
import datetime
from contextlib import asynccontextmanager
import aiosqlite
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)

# Use a lock to prevent race conditions when reading/writing the CSV file
DB_LOCK = asyncio.Lock()
DB_PATH = os.path.join(os.path.dirname(__file__), "dannybase.db")

CANONICAL_COLS = [
    'EmployeeID', 'Username', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
    'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
    'MobilePhone', 'EmploymentType', 'EmploymentStatus'
]

# --- FastAPI app and setup ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@asynccontextmanager
async def db_connection():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

@app.on_event("startup")
async def startup_db():
    async with db_connection() as db:
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS employees (
                {', '.join([f'{col} TEXT' for col in CANONICAL_COLS])},
                PRIMARY KEY (EmployeeID)
            )
        """)
        await db.commit()
    logging.info("Database connection established and table verified.")

# --- Database Helpers ---
async def load_employees():
    async with db_connection() as db:
        cursor = await db.execute("SELECT * FROM employees")
        rows = await cursor.fetchall()
        employees = [dict(row) for row in rows]
    
    enriched_employees = [enrich_employee_row(emp) for emp in employees]
    return enriched_employees

def normalize_for_db(employee_data):
    """Ensures a dictionary has all canonical columns before DB insertion."""
    return {col: employee_data.get(col, 'N/A') or 'N/A' for col in CANONICAL_COLS}

# --- Data Enrichment ---
def enrich_employee_row(row):
    # Make a copy to avoid modifying the original dict if it's a Row object
    row = dict(row)
    # WorkEmail: username@mywinterhaven.com if Username present
    if 'Username' in row and row.get('Username') and row['Username'] not in ['N/A', '']:
        row['WorkEmail'] = f"{str(row['Username']).lower()}@mywinterhaven.com"
    else:
        row['WorkEmail'] = 'N/A'

    # YearsOfService: calculate from JoinDate if possible
    join_date_str = row.get('JoinDate')
    if join_date_str and join_date_str not in ['N/A', '']:
        try:
            # Accommodate different date formats if necessary, but stick to MM/DD/YYYY
            join_date = datetime.datetime.strptime(join_date_str, '%m/%d/%Y')
            today = datetime.datetime.today()
            # This logic correctly calculates full years passed
            years = today.year - join_date.year - ((today.month, today.day) < (join_date.month, join_date.day))
            row['YearsOfService'] = str(years)
        except (ValueError, TypeError):
            row['YearsOfService'] = 'N/A' # Invalid date format
    else:
        row['YearsOfService'] = 'N/A' # No join date

    return row

# --- Import/Export (AJAX/JSON for modal) ---
@app.post("/import/preview")
async def import_preview(file: UploadFile = File(...)):
    """AJAX: Upload file, return preview and columns as JSON."""
    import pandas as pd
    try:
        if file.filename.endswith('.csv'):
            import io
            raw = file.file.read()
            df_new = pd.read_csv(io.BytesIO(raw))
        else:
            return JSONResponse({"error": "Only CSV import is supported."}, status_code=400)
        # Always strip spaces from all column names after reading
        df_new.columns = [c.strip() for c in df_new.columns]
        # Do NOT strip spaces from values; allow values to have spaces
        # Replace NaN/None with 'N/A' for preview
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
        # Enrich the preview data so the frontend doesn't have to
        if not df_new.empty:
            records = df_new.to_dict(orient='records')
            enriched_records = [enrich_employee_row(dict(row)) for row in records]
            df_new = pd.DataFrame(enriched_records)
        logging.info(f"[Import Preview] CSV Header: {list(df_new.columns)}")
        for idx, row in df_new.iterrows():
            logging.debug(f"[Import Preview] Row {idx+1}: {row.to_dict()}")
        logging.info(f"[Import Preview] Previewing {len(df_new)} employees.")
        csv_bytes = df_new.to_csv(index=False).encode('utf-8')
        csv_b64 = base64.b64encode(csv_bytes).decode('utf-8')
        return JSONResponse({
            "preview": df_new.to_dict(orient="records"),
            "columns": list(df_new.columns),
            "csv_b64": csv_b64
        })
    except Exception as e:
        logging.error(f"[Import] Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)

@app.post("/import/confirm")
async def import_confirm(request: Request):
    """AJAX: Confirm import from base64 encoded CSV, save data."""
    import pandas as pd
    try:
        data = await request.json()
        csv_b64 = data.get('csv_b64')

        if not csv_b64:
            raise HTTPException(status_code=400, detail="Missing csv_b64 data in request body.")

        csv_bytes = base64.b64decode(csv_b64)
        df_new = pd.read_csv(io.BytesIO(csv_bytes))
        # Always strip spaces from all column names after reading
        df_new.columns = [c.strip() for c in df_new.columns]
        # Do NOT strip spaces from values; allow values to have spaces
        # Replace NaN/None/empty with 'N/A' for import
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
        logging.info(f"[Import Confirm] CSV Header: {list(df_new.columns)}")
        
        employees_to_import = [normalize_for_db(row) for row in df_new.to_dict(orient='records')]

        async with db_connection() as db:
            for emp in employees_to_import:
                placeholders = ', '.join(['?'] * len(CANONICAL_COLS))
                cols = ', '.join(CANONICAL_COLS)
                sql = f"INSERT OR REPLACE INTO employees ({cols}) VALUES ({placeholders})"
                await db.execute(sql, tuple(emp.values()))
            await db.commit()

        logging.info(f"[Import Confirm] Confirmed import of {len(df_new)} employees.")
        return JSONResponse({"message": f"Imported {len(df_new)} employees."})
    except Exception as e:
        logging.error(f"[Import] Confirm error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)


# POST (create new employee)
@app.post("/api/employees")
async def api_create_employee(emp: dict):
    emp_id = emp.get("EmployeeID")
    if not emp_id:
        raise HTTPException(status_code=400, detail="EmployeeID is required.")

    normalized_emp = normalize_for_db(emp)
    
    async with db_connection() as db:
        placeholders = ', '.join(['?'] * len(CANONICAL_COLS))
        cols = ', '.join(CANONICAL_COLS)
        sql = f"INSERT INTO employees ({cols}) VALUES ({placeholders})"
        await db.execute(sql, tuple(normalized_emp.values()))
        await db.commit()

    logging.info(f"[API] Employee added: {emp}")
    return {"message": "Employee created"}

# --- PUT (upsert employee) ---
@app.put("/api/employees/{emp_id}")
async def api_update_employee(emp_id: str, emp: dict):
    """
    Upsert an employee by EmployeeID:
     - If exists, update fields.
     - If not, create new row.
    """
    logging.info(f"[Upsert Employee] Received PUT for EmployeeID={emp_id}")
    
    # Filter out derived fields from the incoming payload
    update_data = {k: v for k, v in emp.items() if k in CANONICAL_COLS}

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update.")

    set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(emp_id)

    sql = f"UPDATE employees SET {set_clause} WHERE EmployeeID = ?"

    async with db_connection() as db:
        cursor = await db.execute(sql, tuple(values))
        if cursor.rowcount == 0:
            # If no rows were updated, it means the employee doesn't exist. Let's create it.
            normalized_emp = normalize_for_db(emp)
            await api_create_employee(normalized_emp)
            return {"message": "Employee created via PUT"}
        await db.commit()

    return {"message": "Employee updated"}

# --- DELETE employee ---
@app.delete("/api/employees/{emp_id}")
async def api_delete_employee(emp_id: str):
    """
    Delete an employee by EmployeeID.
    """
    logging.info(f"[Delete Employee] Received DELETE for EmployeeID={emp_id}")
    async with db_connection() as db:
        cursor = await db.execute("DELETE FROM employees WHERE EmployeeID = ?", (emp_id,))
        await db.commit()
        if cursor.rowcount == 0:
            logging.warning(f"[Delete Employee] EmployeeID={emp_id} not found")
            raise HTTPException(status_code=404, detail="Employee not found")

    return JSONResponse({"message": "Employee deleted"}, status_code=200)

# --- Page-serving Routes (HTML out) ---
@app.get("/export")
async def export():
    """Export all employees as a CSV file (even if empty)."""
    df = await load_employees()
    # Ensure export matches canonical headers
    export_cols = [
        'EmployeeID', 'Username', 'WorkEmail', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
        'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
        'MobilePhone', 'EmploymentType', 'EmploymentStatus', 'YearsOfService'
    ]
    
    # Create a pandas DataFrame for easy CSV export
    import pandas as pd
    df_export = pd.DataFrame(df, columns=export_cols).fillna('N/A')

    stream = io.StringIO()
    df_export.to_csv(stream, index=False)
    logging.info(f"[Export] Exported {len(df_export)} employees as CSV.")
    for idx, row in df_export.iterrows():
        logging.debug(f"[Export] Row {idx+1}: {row.to_dict()}")
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=employees_export.csv"
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, q: str = ""):
    """
    Home page: View/search employee table
    """
    employees = await load_employees()
    if q:
        q_lower = q.lower()
        employees = [emp for emp in employees if any(str(val).lower().find(q_lower) != -1 for val in emp.values())]
    return templates.TemplateResponse("index.html", {"request": request, "employees": employees, "search": q})


# Step 1: Enter Employee ID
@app.get("/add", response_class=HTMLResponse)
async def add_employee_id_form(request: Request):
    """
    Step 1: Ask for Employee ID
    """
    return templates.TemplateResponse("addEmployee1.html", {"request": request})

# Step 2: Enter all other fields
@app.post("/add_id")
async def add_employee_id(
    request: Request, 
    emp_id: str = Form(...),
    work_email: str = Form(...)):
    """
    Step 2: Redirect to full form with Employee ID
    """
    if not emp_id:
        return templates.TemplateResponse("addEmployee1.html", {"request": request, "error": "Employee ID is required."})
    # pass username along - FIX: Correct indentation
    return templates.TemplateResponse("addEmployee2.html", {"request": request, "emp_id": emp_id, "work_email": work_email})

@app.post("/add_fields")
async def add_employee_fields(
    request: Request,
    emp_id: str = Form(...),
    work_email: str = Form(None),
    first_name: str = Form(None),
    last_name: str = Form(None),
    nickname: str = Form(None),
    dept_code: str = Form(None),
    dept_desc: str = Form(None),
    position: str = Form(None),
    join_date: str = Form(None),
    birthday: str = Form(None),
    office_location: str = Form(None),
    supervisor: str = Form(None),
    office_phone: str = Form(None),
    mobile_phone: str = Form(None),
    employment_type: str = Form(None),
    employment_status: str = Form(None),
    years_of_service: str = Form(None)
):
    """
    Add new employee with all fields
    """
    # logging.basicConfig(level=logging.INFO)  # Already set at module level
    errors = []
    # Validate required fields
    if not emp_id:
        errors.append("Employee ID is required.")
    if not work_email or not re.match(r'^[^@\s]+$', work_email):
        errors.append("Work Email is required and must not contain @ or spaces.")
    if not first_name:
        errors.append("First Name is required.")
    if not last_name:
        errors.append("Last Name is required.")
    if not dept_code or not dept_code.isdigit():
        errors.append("Department Code is required and must be numbers only.")
    if not dept_desc:
        errors.append("Department / Description is required.")
    if not position:
        errors.append("Position is required.")
    if not join_date:
        errors.append("Join Date is required.")
    if not birthday:
        errors.append("Birthday is required.")
    if not supervisor:
        errors.append("Supervisor is required.")
    if not employment_type:
        errors.append("Employment Type is required.")
    if not employment_status:
        errors.append("Employment Status is required.")
    # Validate Office Phone format if provided
    if office_phone:
        if not re.match(r'^\d{3}-\d{4}( x\d+)?$', office_phone):
            errors.append("Office Phone & Extension must be in the format 555-1234 x1234 or 555-1234.")
    # Validate Years of Service if provided
    if years_of_service:
        try:
            y = int(years_of_service)
            if y < 0:
                errors.append("Years of Service must be a positive number.")
        except Exception:
            errors.append("Years of Service must be a number.")
    # Set N/A for optional fields if empty
    if not nickname:
        nickname = "N/A"
    if not office_location:
        office_location = "N/A"
    if not mobile_phone:
        mobile_phone = "N/A"
    # If errors, re-render form with errors
    if errors:
        return templates.TemplateResponse("addEmployee2.html", {"request": request, "emp_id": emp_id, "error": errors[0]})
    try:
        # Compose full work email
        full_email = f"{work_email}@mywinterhaven.com"
        username = work_email.lower()
        # Auto-calculate YearsOfService from JoinDate (MM/DD/YYYY)
        from datetime import datetime
        try:
            join_year = int(str(join_date).split('/')[-1])
            years_of_service = str(datetime.now().year - join_year)
        except Exception:
            years_of_service = ''

        logging.info(f"Adding employee via form: ID={emp_id}")
        new_row = {
            "EmployeeID": emp_id,
            "Username": username,
            "WorkEmail": full_email,
            "FirstName": first_name,
            "LastName": last_name,
            "Nickname": nickname,
            "DepartmentCode": dept_code,
            "Department": dept_desc,
            "Position": position,
            "JoinDate": join_date,
            "Birthday": birthday,
            "OfficeLocation": office_location,
            "Supervisor": supervisor,
            "OfficePhoneAndExtension": office_phone or "",
            "MobilePhone": mobile_phone,
            "EmploymentType": employment_type,
            "EmploymentStatus": employment_status,
            "YearsOfService": years_of_service or ""
        }

        normalized_emp = normalize_for_db(new_row)
        async with db_connection() as db:
            placeholders = ', '.join(['?'] * len(CANONICAL_COLS))
            cols = ', '.join(CANONICAL_COLS)
            sql = f"INSERT INTO employees ({cols}) VALUES ({placeholders})"
            await db.execute(sql, tuple(normalized_emp.values()))
            await db.commit()

        # Redirect to home page to show updated database
        return RedirectResponse("/", status_code=303)
    except Exception as e:
        logging.error(f"[Add Employee] Unexpected error: {e}")
        # Fallback: redirect to home with error (could be improved to show error page)
        return RedirectResponse("/", status_code=303)


# Run with: uvicorn main:app --reload
