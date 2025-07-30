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
import base64
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncpg
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from userauth import create_access_token, get_current_user_from_cookie, verify_password

logging.basicConfig(level=logging.INFO)

CANONICAL_COLS = [
    'EmployeeID', 'Username', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
    'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
    'MobilePhone', 'EmploymentType', 'EmploymentStatus'
]

# --- FastAPI app and setup ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.state.pool = None # Placeholder for the connection pool

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    If a 401 Unauthorized error is raised, redirect the user to the login page.
    This provides blanket protection for all routes using the auth dependency.
    """
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # For API calls, return a proper JSON 401 response
        if request.url.path.startswith("/api/") or request.url.path.startswith("/import/"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": exc.detail},
            )
        # For page views, redirect to the login screen
        return RedirectResponse(url="/login")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@asynccontextmanager
async def db_connection(request: Request):
    """Acquires a connection from the pool."""
    pool = request.app.state.pool
    try:
        async with pool.acquire() as connection:
            yield connection
    finally:
        # The connection is automatically released back to the pool
        pass

@app.on_event("startup")
async def startup_event():
    """Create a database connection pool and ensure the table exists on startup."""
    try:
        app.state.pool = await asyncpg.create_pool(settings.DATABASE_URL)
        # Verify connection and ensure the table exists
        async with app.state.pool.acquire() as connection:
            await connection.execute(f"""
                CREATE TABLE IF NOT EXISTS employees (
                    {', '.join([f'"{col}" TEXT' for col in CANONICAL_COLS])},
                    PRIMARY KEY ("EmployeeID")
                )
            """)
        logging.info("Database connection pool created and 'employees' table verified.")
    except Exception as e:
        logging.critical(f"FATAL: Could not connect to database or create table: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Close the database connection pool on shutdown."""
    await app.state.pool.close()
    logging.info("Database connection pool closed.")
# --- Database Helpers ---
async def load_employees(request: Request):
    async with db_connection(request) as db:
        # Use db.fetch() for SELECT queries. It directly returns a list of records.
        rows = await db.fetch("SELECT * FROM employees")
        employees = [dict(row) for row in rows] # asyncpg.Record is already dict-like
    
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
            join_date = datetime.strptime(join_date_str, '%m/%d/%Y')
            today = datetime.today()
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
async def import_preview(file: UploadFile = File(...), user: str = Depends(get_current_user_from_cookie)):
    """AJAX: Upload file, return preview and columns as JSON."""
    import pandas as pd
    try:
        if file.filename.endswith('.csv'):
            import io
            raw = file.file.read()
            # Read all columns as strings to prevent pandas from inferring types (e.g., '918' as 918.0)
            df_new = pd.read_csv(io.BytesIO(raw), dtype=str)
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
async def import_confirm(request: Request, user: str = Depends(get_current_user_from_cookie)):
    """AJAX: Confirm import from base64 encoded CSV, save data."""
    import pandas as pd
    try:
        data = await request.json()
        csv_b64 = data.get('csv_b64')

        if not csv_b64:
            raise HTTPException(status_code=400, detail="Missing csv_b64 data in request body.")

        csv_bytes = base64.b64decode(csv_b64)

        # Read all columns as strings for consistency and to prevent type inference issues.
        df_new = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
        # Always strip spaces from all column names after reading
        df_new.columns = [c.strip() for c in df_new.columns]
        # Do NOT strip spaces from values; allow values to have spaces
        # Replace NaN/None/empty with 'N/A' for import
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
        logging.info(f"[Import Confirm] CSV Header: {list(df_new.columns)}")
        
        employees_to_import = [normalize_for_db(row) for row in df_new.to_dict(orient='records')]

        async with db_connection(request) as db:
            for emp in employees_to_import:
                # Use PostgreSQL's "UPSERT" functionality
                cols = ', '.join([f'"{c}"' for c in CANONICAL_COLS])
                placeholders = ', '.join([f'${i+1}' for i in range(len(CANONICAL_COLS))])
                # On conflict, update all columns except the primary key
                update_cols = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in CANONICAL_COLS if col != 'EmployeeID'])
                
                sql = f'INSERT INTO employees ({cols}) VALUES ({placeholders}) ON CONFLICT ("EmployeeID") DO UPDATE SET {update_cols}'
                
                await db.execute(sql, *emp.values())

        logging.info(f"[Import Confirm] Confirmed import of {len(df_new)} employees.")
        return JSONResponse({"message": f"Imported {len(df_new)} employees."})
    except Exception as e:
        logging.error(f"[Import] Confirm error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)


# POST (create new employee)
@app.post("/api/employees")
async def api_create_employee(request: Request, emp: dict, user: str = Depends(get_current_user_from_cookie)):
    emp_id = emp.get("EmployeeID")
    if not emp_id:
        raise HTTPException(status_code=400, detail="EmployeeID is required.")

    normalized_emp = normalize_for_db(emp)
    
    async with db_connection(request) as db:
        cols = ', '.join([f'"{c}"' for c in CANONICAL_COLS])
        placeholders = ', '.join([f'${i+1}' for i in range(len(CANONICAL_COLS))])
        sql = f"INSERT INTO employees ({cols}) VALUES ({placeholders})"
        await db.execute(sql, *normalized_emp.values())

    logging.info(f"[API] Employee added: {emp}")
    return {"message": "Employee created"}

# --- PUT (upsert employee) ---
@app.put("/api/employees/{emp_id}")
async def api_update_employee(request: Request, emp_id: str, emp: dict, user: str = Depends(get_current_user_from_cookie)):
    """
    Upsert an employee by EmployeeID:
    - If exists, update fields.
    - If not, create new row.
    """
    logging.info(f"[Upsert Employee] Received PUT for EmployeeID={emp_id}")
    
    # Prepare a full record for potential insertion
    normalized_emp = normalize_for_db(emp)
    normalized_emp['EmployeeID'] = emp_id # Ensure EmployeeID is set from the URL

    async with db_connection(request) as db:
        # Use PostgreSQL's "UPSERT" for a single, atomic operation
        cols = ', '.join([f'"{c}"' for c in CANONICAL_COLS])
        placeholders = ', '.join([f'${i+1}' for i in range(len(CANONICAL_COLS))])
        update_cols = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in CANONICAL_COLS if col != 'EmployeeID'])
        sql = f'INSERT INTO employees ({cols}) VALUES ({placeholders}) ON CONFLICT ("EmployeeID") DO UPDATE SET {update_cols}'
        
        await db.execute(sql, *normalized_emp.values())

    return {"message": "Employee updated"}

# --- DELETE employee ---
@app.delete("/api/employees/{emp_id}")
async def api_delete_employee(request: Request, emp_id: str, user: str = Depends(get_current_user_from_cookie)):
    """
    Delete an employee by EmployeeID.
    """
    logging.info(f"[Delete Employee] Received DELETE for EmployeeID={emp_id}")
    async with db_connection(request) as db:
        result = await db.execute('DELETE FROM employees WHERE "EmployeeID" = $1', emp_id)
        if result == 'DELETE 0':
            logging.warning(f"[Delete Employee] EmployeeID={emp_id} not found")
            raise HTTPException(status_code=404, detail="Employee not found")

    return JSONResponse({"message": "Employee deleted"}, status_code=200)

# --- Authentication Routes ---
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serves the login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_for_access_token(request: Request, username: str = Form(...), password: str = Form(...)):
    """Processes login form, sets cookie on success."""
    if not verify_password(password, settings.AUTH_PASSWORD) or username.lower() != settings.AUTH_USERNAME.lower():
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": settings.AUTH_USERNAME}, expires_delta=access_token_expires
    )

    # Set the token in a secure, HttpOnly cookie
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True, # Prevents client-side JS from accessing the cookie
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    logging.info(f"User '{username}' logged in at {datetime.now().isoformat()}")
    return response

@app.get("/logout")
async def logout(request: Request, user: str = Depends(get_current_user_from_cookie)):
    """Logs the user out by clearing the cookie."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    # The `user` is the username from the token, available via the dependency
    logging.info(f"User '{user}' logged out at {datetime.now().isoformat()}")
    return response


# --- Page-serving Routes (HTML out) ---
@app.get("/export")
async def export(request: Request, user: str = Depends(get_current_user_from_cookie)):
    """Export all employees as a CSV file (even if empty)."""
    df = await load_employees(request)
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
async def index(request: Request, q: str = "", user: str = Depends(get_current_user_from_cookie)):
    """
    Home page: View/search employee table
    """
    employees = await load_employees(request)
    if q:
        q_lower = q.lower()
        employees = [emp for emp in employees if any(str(val).lower().find(q_lower) != -1 for val in emp.values())]
    return templates.TemplateResponse("index.html", {"request": request, "employees": employees, "search": q})


# Step 1: Enter Employee ID
@app.get("/add", response_class=HTMLResponse)
async def add_employee_id_form(request: Request, user: str = Depends(get_current_user_from_cookie)):
    """
    Step 1: Ask for Employee ID
    """
    return templates.TemplateResponse("addEmployee1.html", {"request": request})

# Step 2: Enter all other fields
@app.post("/add_id")
async def add_employee_id(
    request: Request, 
    emp_id: str = Form(...),
    work_email: str = Form(...),
    user: str = Depends(get_current_user_from_cookie)):
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
    years_of_service: str = Form(None),
    user: str = Depends(get_current_user_from_cookie)
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
        async with db_connection(request) as db:
            cols = ', '.join([f'"{c}"' for c in CANONICAL_COLS])
            placeholders = ', '.join([f'${i+1}' for i in range(len(CANONICAL_COLS))])
            sql = f"INSERT INTO employees ({cols}) VALUES ({placeholders})"
            await db.execute(sql, *normalized_emp.values())

        # Redirect to home page to show updated database
        return RedirectResponse("/", status_code=303)
    except Exception as e:
        logging.error(f"[Add Employee] Unexpected error: {e}")
        # Fallback: redirect to home with error (could be improved to show error page)
        return RedirectResponse("/", status_code=303)


# Run with: uvicorn main:app --reload
