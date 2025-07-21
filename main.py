# main.py
"""
FastAPI backend for Winter Haven Tech Services HR tool
- Serves static frontend (HTML/JS/CSS)
- Manages employee records in Excel (Dannybase.xlsx)
- Uses pandas & openpyxl for Excel I/O
- Uses Jinja2 for HTML templates
"""

import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
from openpyxl import load_workbook

# Path to Excel file
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "Dannybase.xlsx")

app = FastAPI()

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Helper: Load employee data from Excel

def load_employees():
    try:
        df = pd.read_excel(EXCEL_PATH)
        return df
    except Exception as e:
        print(f"Error loading Excel: {e}")
        return pd.DataFrame()

# Helper: Save employee data to Excel

def save_employees(df):
    try:
        df.to_excel(EXCEL_PATH, index=False)
    except Exception as e:
        print(f"Error saving Excel: {e}")

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
    return templates.TemplateResponse("add_id.html", {"request": request})

# Step 2: Enter all other fields
@app.post("/add_id")
async def add_employee_id(request: Request, emp_id: str = Form(...)):
    """
    Step 2: Redirect to full form with Employee ID
    """
    if not emp_id:
        return templates.TemplateResponse("add_id.html", {"request": request, "error": "Employee ID is required."})
    return templates.TemplateResponse("add_fields.html", {"request": request, "emp_id": emp_id})

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
    df = load_employees()
    # Build new row, blank if not entered
    new_row = {
        "Employee ID": emp_id,
        "Work Email": work_email or "",
        "First Name": first_name or "",
        "Last Name": last_name or "",
        "Nickname": nickname or "",
        "Department Code": dept_code or "",
        "Department / Department Description": dept_desc or "",
        "Position": position or "",
        "Join Date": join_date or "",
        "Birthday": birthday or "",
        "Office Location": office_location or "",
        "Supervisor": supervisor or "",
        "Office Phone & Extension": office_phone or "",
        "Mobile Phone (if applicable)": mobile_phone or "",
        "Employment Type": employment_type or "",
        "Employment Status": employment_status or "",
        "Years of Service": years_of_service or ""
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_employees(df)
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
    if emp_id not in df["ID"].values:
        raise HTTPException(status_code=404, detail="Employee not found")
    df = df[df["ID"] != emp_id]
    save_employees(df)
    return RedirectResponse("/", status_code=303)

# Debug route: Download Excel file
@app.get("/download", response_class=HTMLResponse)
async def download_excel(request: Request):
    """
    Download the Excel file for backup/debugging
    """
    return RedirectResponse("/static/Dannybase.xlsx", status_code=303)

# Run with: uvicorn main:app --reload
