# Bulk update all employees (overwrite db.csv)

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
import pandas as pd
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request as StarletteRequest
from starlette.responses import HTMLResponse as StarletteHTMLResponse


logging.basicConfig(level=logging.INFO)


CSV_PATH = os.path.join(os.path.dirname(__file__), "db.csv")


# --- Canonical CSV Helpers ---
def load_employees():
    try:
        df = pd.read_csv(CSV_PATH)
        # Enrich every row with WorkEmail and YearsOfService
        df = df.fillna('')
        records = df.to_dict(orient='records')
        enriched = [enrich_employee_row(dict(row)) for row in records]
        df = pd.DataFrame(enriched)
        # Replace NaN/None/empty with 'N/A' for frontend display
        df = df.where(pd.notnull(df), 'N/A')
        df = df.replace('', 'N/A')
        return df
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return pd.DataFrame()

def save_employees(df, source=None, added=None):
    try:
        # Canonical column order
        canonical_cols = [
            'EmployeeID', 'Username', 'WorkEmail', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
            'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
            'MobilePhone', 'EmploymentType', 'EmploymentStatus', 'YearsOfService'
        ]
        for col in canonical_cols:
            if col not in df.columns:
                df[col] = 'N/A'
        df = df[canonical_cols]
        # Enrich every row before saving
        df = df.fillna('')
        records = df.to_dict(orient='records')
        enriched = [enrich_employee_row(dict(row)) for row in records]
        df = pd.DataFrame(enriched)
        # Replace NaN/None/empty with 'N/A' before saving
        df = df.where(pd.notnull(df), 'N/A')
        df = df.replace('', 'N/A')
        df.to_csv(CSV_PATH, index=False)
        # Logging
        import inspect
        frame = inspect.currentframe().f_back
        source = frame.f_locals.get('source', None)
        added = frame.f_locals.get('added', None)
        logging.info(f"[db.csv] Database updated. {len(df)} total rows written. Source: {source or 'unknown'}")
        if added is not None:
            logging.info(f"[db.csv] Added: {added}")
        for idx, row in df.iterrows():
            logging.debug(f"[db.csv] Row {idx+1}: {row.to_dict()}")
    except Exception as e:
        print(f"Error saving CSV: {e}")


# --- FastAPI app and setup ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Bulk update all employees (overwrite db.csv)
@app.post("/api/employees")
async def api_bulk_update_employees(data: dict):
    employees = data.get('employees')
    if not employees or not isinstance(employees, list):
        return JSONResponse({"error": "Invalid data"}, status_code=400)
    canonical_cols = [
        'EmployeeID', 'Username', 'WorkEmail', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
        'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
        'MobilePhone', 'EmploymentType', 'EmploymentStatus', 'YearsOfService'
    ]
    for emp in employees:
        for col in canonical_cols:
            if col not in emp:
                emp[col] = 'N/A'
    df = pd.DataFrame(employees)[canonical_cols]
    # Replace NaN/None/empty with 'N/A' for canonical storage
    df = df.where(pd.notnull(df), 'N/A')
    df = df.replace('', 'N/A')
    save_employees(df, source="api_bulk_update_employees", added=f"{len(employees)} employees")
    logging.info(f"[API] Bulk update: {len(df)} employees saved to db.csv")
    return {"message": f"Bulk update: {len(df)} employees saved."}
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- REST API Models ---
from pydantic import BaseModel


from fastapi import Body
# --- Import/Export (AJAX/JSON for modal) ---
@app.post("/import/preview")
async def import_preview(file: UploadFile = File(...)):
    """AJAX: Upload file, return preview and columns as JSON."""
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
        # Replace NaN/None/empty with 'N/A' for preview
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
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
    """AJAX or form: Confirm import, save data, update Excel/CSV."""
    try:
        # Try to get csv_b64 from JSON body (AJAX)
        try:
            data = await request.json()
            csv_b64 = data.get('csv_b64')
        except Exception:
            # Fallback: get from form data
            form = await request.form()
            csv_b64 = form.get('csv_b64')
        if not csv_b64:
            return JSONResponse({"error": "Missing csv_b64"}, status_code=400)
        csv_bytes = base64.b64decode(csv_b64)
        df_new = pd.read_csv(io.BytesIO(csv_bytes))
        # Always strip spaces from all column names after reading
        df_new.columns = [c.strip() for c in df_new.columns]
        # Do NOT strip spaces from values; allow values to have spaces
        # Replace NaN/None/empty with 'N/A' for import
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
        logging.info(f"[Import Confirm] CSV Header: {list(df_new.columns)}")
        for idx, row in df_new.iterrows():
            logging.debug(f"[Import Confirm] Row {idx+1}: {row.to_dict()}")
        df = load_employees()
        df = df.where(pd.notnull(df), 'N/A')
        df = df.replace('', 'N/A')
        # Append new employees
        df = pd.concat([df, df_new], ignore_index=True)
        save_employees(df, source="import_confirm", added=df_new.to_dict(orient="records"))
        logging.info(f"[Import Confirm] Confirmed import of {len(df_new)} employees. db.csv updated.")
        return JSONResponse({"message": f"Imported {len(df_new)} employees."})
    except Exception as e:
        logging.error(f"[Import] Confirm error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)


# POST (create new employee)
@app.post("/api/employees")
async def api_create_employee(emp: dict):
    df = load_employees()
    if emp.get('EmployeeID') in df['EmployeeID'].astype(str).values:
        raise HTTPException(status_code=400, detail="EmployeeID already exists")
    # Canonicalize columns and fill missing
    canonical_cols = [
        'EmployeeID', 'Username', 'WorkEmail', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
        'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
        'MobilePhone', 'EmploymentType', 'EmploymentStatus', 'YearsOfService'
    ]
    for col in canonical_cols:
        if col not in emp:
            emp[col] = 'N/A'
    emp = {col: emp.get(col, 'N/A') for col in canonical_cols}
    df = pd.concat([df, pd.DataFrame([emp])], ignore_index=True)
    save_employees(df, source="api_create_employee", added=emp)
    logging.info(f"[API] Employee added: {emp}")
    return {"message": "Employee created"}

# PUT (update employee)
@app.put("/api/employees/{emp_id}")
async def api_update_employee(emp_id: str, emp: dict):
    df = load_employees()
    idx = df.index[df["EmployeeID"].astype(str) == emp_id].tolist()
    if not idx:
        raise HTTPException(status_code=404, detail="Employee not found")
    i = idx[0]
    before = df.loc[i].to_dict()
    changes = {}
    for col in df.columns:
        old = df.at[i, col]
        new = emp.get(col, 'N/A')
        if old != new:
            changes[col] = {'old': old, 'new': new}
        df.at[i, col] = new
    import logging
    logging.info(f"[Update Employee] EmployeeID={emp_id} changes: {changes if changes else 'No changes'}")
    save_employees(df, source="api_update_employee", added=changes)
    return {"message": "Employee updated"}

# DELETE (delete employee)
@app.delete("/api/employees/{emp_id}")
async def api_delete_employee(emp_id: str):
    df = load_employees()
    idx = df.index[df["EmployeeID"].astype(str) == str(emp_id)].tolist()
    if not idx:
        raise HTTPException(status_code=404, detail="Employee not found")
    deleted_rows = df.loc[idx].to_dict(orient='records')
    import logging
    logging.info(f"[Delete Employee] Deleting EmployeeID={emp_id}: {deleted_rows}")
    df = df.drop(idx)
    save_employees(df, source="api_delete_employee", added=f"Deleted {emp_id}")
    return {"message": "Employee deleted"}

# XSS (Cross-Site Scripting) is a vulnerability where attackers inject malicious scripts into web pages viewed by others. Always escape user input in templates and sanitize data before rendering.

# Toast notifications: To be implemented in the frontend (index.html/dannybase.js) for user feedback on actions like add, edit, delete, import, export.

@app.delete("/api/employees/{emp_id}")
async def api_delete_employee(emp_id: str):
    """Delete an employee by ID via API."""
    df = load_employees()
    idx = df.index[df["Employee ID"] == emp_id].tolist()
    if not idx:
        logging.warning(f"[API] Delete failed: Employee {emp_id} not found.")
        raise HTTPException(status_code=404, detail="Employee not found")
    df = df.drop(idx)
    save_employees(df)
    logging.info(f"[API] Deleted employee {emp_id} (Excel/CSV updated)")
    return JSONResponse({"message": "Employee deleted"})

# --- Import/Export ---
@app.get("/import", response_class=HTMLResponse)
async def import_form(request: Request):
    """Show the import form."""
    logging.info("[Import] Form displayed.")
    return templates.TemplateResponse("import.html", {"request": request})




@app.post("/import")
async def import_employees(request: Request, file: UploadFile = File(...)):
    """Step 1: Upload file, show preview and confirm."""
    try:
        if file.filename.endswith('.csv'):
            df_new = pd.read_csv(file.file)
        else:
            df_new = pd.read_excel(file.file)
        # Replace NaN/None/empty with 'N/A' for preview
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
        # Log the extracted data
        logging.info(f"[Import] Previewing {len(df_new)} employees: {df_new.to_dict(orient='records')}")
        # Store the data as base64 CSV in a hidden field for confirmation
        csv_bytes = df_new.to_csv(index=False).encode('utf-8')
        csv_b64 = base64.b64encode(csv_bytes).decode('utf-8')
        # Render confirmation page
        return templates.TemplateResponse("import.html", {
            "request": request,
            "preview": df_new.to_dict(orient="records"),
            "columns": list(df_new.columns),
            "csv_b64": csv_b64,
            "step": "confirm"
        })
    except Exception as e:
        logging.error(f"[Import] Error: {e}")
        return HTMLResponse(f"<h2>Error importing file: {e}</h2>", status_code=400)

@app.post("/import/confirm")
async def import_employees_confirm(request: Request, csv_b64: str = Form(...)):
    """Step 2: Confirm import, save data, update Excel/CSV, redirect."""
    try:
        csv_bytes = base64.b64decode(csv_b64)
        df_new = pd.read_csv(io.BytesIO(csv_bytes))
        # Replace NaN/None/empty with 'N/A' for import
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
        df = load_employees()
        df = df.where(pd.notnull(df), 'N/A')
        df = df.replace('', 'N/A')
        # Remove WorkEmail and YearsOfService if present
        if 'WorkEmail' in df_new.columns:
            df_new = df_new.drop(columns=['WorkEmail'])
        if 'YearsOfService' in df_new.columns:
            df_new = df_new.drop(columns=['YearsOfService'])
        # Auto-generate WorkEmail and YearsOfService
        from datetime import datetime
        current_year = datetime.now().year
        def calc_years(join_date):
            try:
                year = int(str(join_date).split('/')[-1])
                return str(current_year - year)
            except Exception:
                return 'N/A'
        df_new['WorkEmail'] = df_new['Username'].astype(str).str.lower() + '@mywinterhaven.com'
        df_new['YearsOfService'] = df_new['JoinDate'].apply(calc_years)
        # Ensure imported columns match canonical headers (order)
        canonical_cols = [
            'EmployeeID', 'Username', 'WorkEmail', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
            'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
            'MobilePhone', 'EmploymentType', 'EmploymentStatus', 'YearsOfService'
        ]
        for col in canonical_cols:
            if col not in df_new.columns:
                df_new[col] = 'N/A'
        df_new = df_new[canonical_cols]
        # Replace any remaining blanks with 'N/A'
        df_new = df_new.where(pd.notnull(df_new), 'N/A')
        df_new = df_new.replace('', 'N/A')
        df = pd.concat([df, df_new], ignore_index=True)
        save_employees(df)
        logging.info(f"[Import] Confirmed and imported {len(df_new)} employees (total now {len(df)}). CSV updated.")
        return RedirectResponse("/?imported=1", status_code=303)
    except Exception as e:
        logging.error(f"[Import] Confirm error: {e}")
        return HTMLResponse(f"<h2>Error confirming import: {e}</h2>", status_code=400)

import datetime
def enrich_employee_row(row):
    # WorkEmail: username@mywinterhaven.com if Username present
    if 'Username' in row and row['Username'] not in [None, '', 'N/A']:
        row['WorkEmail'] = f"{row['Username']}@mywinterhaven.com"
    else:
        row['WorkEmail'] = 'N/A'
    # YearsOfService: calculate from JoinDate if possible
    join_date = row.get('JoinDate') or row.get('Join Date')
    if join_date and join_date not in ['N/A', '', None]:
        try:
            dt = datetime.datetime.strptime(join_date, '%m/%d/%Y')
            today = datetime.datetime.today()
            years = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
            row['YearsOfService'] = str(years)
        except Exception:
            row['YearsOfService'] = 'N/A'
    else:
        row['YearsOfService'] = 'N/A'
    return row

@app.get("/export")
async def export():
    """Export all employees as a CSV file (even if empty)."""
    df = load_employees()
    # Ensure export matches canonical headers
    canonical_cols = [
        'EmployeeID', 'Username', 'WorkEmail', 'FirstName', 'LastName', 'Nickname', 'DepartmentCode', 'Department',
        'Position', 'JoinDate', 'Birthday', 'OfficeLocation', 'Supervisor', 'OfficePhoneAndExtension',
        'MobilePhone', 'EmploymentType', 'EmploymentStatus', 'YearsOfService'
    ]
    for col in canonical_cols:
        if col not in df.columns:
            df[col] = 'N/A'
    df = df[canonical_cols]
    # Enrich each row with correct WorkEmail and YearsOfService
    if not df.empty:
        for idx, row in df.iterrows():
            enriched = enrich_employee_row(row.to_dict())
            for k, v in enriched.items():
                if k in df.columns:
                    df.at[idx, k] = v
    # Replace NaN/None/empty with 'N/A' for export
    df = df.where(pd.notnull(df), 'N/A')
    df = df.replace('', 'N/A')
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    logging.info(f"[Export] Exported {len(df)} employees as CSV. (Visual table will refresh to match db.csv)")
    for idx, row in df.iterrows():
        logging.debug(f"[Export] Row {idx+1}: {row.to_dict()}")
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=employees_export.csv"
    return response
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=employees_export.csv"
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, q: str = ""):
    """
    Home page: View/search employee table
    """
    df = load_employees()
    if q:
        df = df[df.apply(lambda row: row.astype(str).str.contains(q, case=False).any(), axis=1)]
    employees = df.to_dict(orient="records")
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
async def add_employee_id(request: Request, emp_id: str = Form(...)):
    """
    Step 2: Redirect to full form with Employee ID
    """
    if not emp_id:
        return templates.TemplateResponse("addEmployee1.html", {"request": request, "error": "Employee ID is required."})
    return templates.TemplateResponse("addEmployee2.html", {"request": request, "emp_id": emp_id})

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
        # Auto-calculate YearsOfService from JoinDate (MM/DD/YYYY)
        from datetime import datetime
        try:
            join_year = int(str(join_date).split('/')[-1])
            years_of_service = str(datetime.now().year - join_year)
        except Exception:
            years_of_service = ''
        # Logging all fields
        logging.info(f"Adding employee: ID={emp_id}, Email={full_email}, First={first_name}, Last={last_name}, Nickname={nickname}, DeptCode={dept_code}, Dept={dept_desc}, Position={position}, Join={join_date}, Birthday={birthday}, OfficeLoc={office_location}, Supervisor={supervisor}, OfficePhone={office_phone}, MobilePhone={mobile_phone}, EmpType={employment_type}, EmpStatus={employment_status}, Years={years_of_service}")
        df = load_employees()
        new_row = {
            "EmployeeID": emp_id,
            "Username": work_email,
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
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        logging.info(f"[Add Employee] Adding new row: {new_row}")
        save_employees(df, source="manual_form", added=new_row)
        logging.info(f"[Add Employee] Employee {emp_id} added to database (manual form). Current DB:")
        for idx, row in df.iterrows():
            logging.debug(f"[Add Employee] Row {idx+1}: {row.to_dict()}")
        # Redirect to home page to show updated database
        return RedirectResponse("/", status_code=303)
    except Exception as e:
        logging.error(f"[Add Employee] Unexpected error: {e}")
        # Fallback: redirect to home with error (could be improved to show error page)
        return RedirectResponse("/", status_code=303)

@app.post("/edit/{emp_id}")
async def edit_employee(request: Request, emp_id: int, name: str = Form(...), title: str = Form(...), email: str = Form(...)):
    """
    Edit employee info by ID
    """
    df = load_employees()
    if emp_id not in df["ID"].values:
        raise HTTPException(status_code=404, detail="Employee not found")
    df.loc[df["ID"] == emp_id, ["Name", "Title", "Email"]] = [name, title, email]
    save_employees(df)
    return RedirectResponse("/", status_code=303)

@app.post("/delete/{emp_id}")
async def delete_employee(request: Request, emp_id: int):
    """
    Delete employee by ID
    """
    df = load_employees()
    idx = df.index[df["EmployeeID"].astype(str) == str(emp_id)].tolist()
    if not idx:
        raise HTTPException(status_code=404, detail="Employee not found")
    df = df.drop(idx)
    save_employees(df, source="manual_delete", added=f"Deleted {emp_id}")
    return RedirectResponse("/", status_code=303)

# Debug route: Download Excel file
@app.get("/download", response_class=HTMLResponse)
async def download_excel(request: Request):
    """
    Download the Excel file for backup/debugging
    """
    return RedirectResponse("/static/Dannybase.xlsx", status_code=303)

# Run with: uvicorn main:app --reload
