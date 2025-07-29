#QA side of the QA dashboards
#port 9999

from openpyxl import load_workbook
from fastapi import FastAPI, Form, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import psycopg2
import toml
from time import localtime, strftime
from fastapi.staticfiles import StaticFiles
import aiofiles
from tempfile import NamedTemporaryFile
import os.path
import os
from datetime import datetime

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static") #logo and favicon go here
templates = Jinja2Templates(directory="templates") #loads HTML files from this directory

CONFIG = toml.load("./config.toml") #load variables from toml file
SERVER: str = CONFIG['comms']['server']
PORT: int = CONFIG['comms']['port']
FROM: str = CONFIG['comms']['from']
TO: list[str] = CONFIG['comms']['emails'] #list of emails to send responses to

# Set up postgresql table
def init_db():
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}')
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS qa 
                (id SERIAL PRIMARY KEY, 
                agent TEXT,
                extension TEXT,
                clinic TEXT,
                date_time TEXT,
                phone TEXT,
                handle_time TEXT,
                upload_date DATE DEFAULT CURRENT_DATE,
                gen_call_score INT,
                sched_call_score INT,
                complaint_call_score INT,
                procedure_call_score INT,
                cust_service_notes TEXT,
                sched_proc_veri_score INT,
                trainer TEXT,
                qa_date DATE,
                overall_result TEXT,
                filename TEXT)
                ;'''
            )
    cur.close()
    con.commit()

# Home page with the form
@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

# Acknowledge file was uploaded and process file!
@app.post("/upload", response_class=HTMLResponse)
async def process_file(file: UploadFile):
    _filename = file.filename
    if not os.path.exists(f'QAs\\{file.filename}'):
        try:
            contents = await file.read()
            async with aiofiles.open(f"QAs\\{file.filename}", 'wb') as f: # type: ignore
                await f.write(contents)
        except Exception as e:
            raise HTTPException(status_code=500, detail='Something went wrong')
        finally:
            await file.close()
        wb = load_workbook(filename= f'QAs\\{file.filename}')  # type: ignore
        sheet_ranges = wb['Sheet1']

        try:

            agent = sheet_ranges['G2'].value
            if not agent:
                agent = sheet_ranges['F2'].value.split(":")[-1].strip()

            extension = str(sheet_ranges['G3'].value)

            if extension == "None":
                extension = str(sheet_ranges['F3'].value.split(":")[-1].strip())
            if len(extension) == 4:
                extension = "2" + extension

            clinic = sheet_ranges['G4'].value
            if not clinic:
                clinic = sheet_ranges['F4'].value.split(":")[-1].strip()

            date_time = sheet_ranges['G5'].value
            if not date_time:
                date_time = ''
                date_time_list = sheet_ranges['F5'].value.split(":")
                date_time_list.pop(0)
                for item in date_time_list:
                    date_time = date_time + item

            phone = sheet_ranges['G6'].value
            if not phone:
                phone = sheet_ranges['F6'].value.split(":")[-1].strip()

            handle_time = sheet_ranges['G7'].value
            if not handle_time:
                handle_time = sheet_ranges['F7'].value.split(":")[-1].strip()

            try:
                gen_call_score = int(sheet_ranges['I22'].value.split("/")[0].strip())
            except:
                print("No general call score.")
                gen_call_score: int = 0
            try:
                sched_call_score = int(sheet_ranges['I33'].value.split("/")[0].strip())
            except:
                print("No scheduling call score.")
                sched_call_score: int = 0
            try:
                complaint_call_score = int(sheet_ranges['I44'].value.split("/")[0].strip())
            except:
                print("No complaint call score.")
                complaint_call_score: int = 0
            try:
                procedure_call_score = int(sheet_ranges['I56'].value.split("/")[0].strip())
            except:
                print("No procedure call score.")
                procedure_call_score: int = 0
            
            cust_service_notes = ''
            for i in range(62, 70):
                if sheet_ranges[f'A{i}'].value:
                    cust_service_notes = cust_service_notes + '\n' + sheet_ranges[f'A{i}'].value
            
            try:
                sched_proc_veri_score = int(sheet_ranges['I83'].value.split("/")[0].strip())
            except:
                print("No scheduling/procedure verification call score.")
                sched_proc_veri_score: int = 0

            verification_notes = ''
            for i in range(85, 94):
                if sheet_ranges[f'A{i}'].value:
                    verification_notes = verification_notes + '\n' + sheet_ranges[f'A{i}'].value

            spec_feedback = ''
            for i in range(95, 102):
                if sheet_ranges[f'A{i}'].value:
                    spec_feedback = spec_feedback + '\n' + sheet_ranges[f'A{i}'].value

            if "Yes" in sheet_ranges['A103'].value:
                one_on_one = True
            elif "No" in sheet_ranges['A103'].value:
                one_on_one = False

            trainer_cell = sheet_ranges['A104'].value.split(":")
            trainer = trainer_cell[-1].strip()

            super_cell = sheet_ranges['A105'].value.split(":")
            floor_super = super_cell[-1].strip()

            qa_date = sheet_ranges['G104'].value.split(":")[-1].strip()
            
            if qa_date == None or qa_date == "":
                qa_date = datetime.today().strftime('%Y-%m-%d')

            overall_result = sheet_ranges['I108'].value
            
            qa_filename = file.filename

            con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}')
            cur = con.cursor()
            SQL = '''INSERT INTO qa 
                    (agent,
                    extension,
                    clinic,
                    date_time,
                    phone,
                    handle_time,
                    gen_call_score,
                    sched_call_score,
                    complaint_call_score,
                    procedure_call_score,
                    sched_proc_veri_score,
                    trainer,
                    qa_date,
                    overall_result,
                    filename)
                    VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);'''
            DATA = (agent, extension, clinic, date_time, phone, handle_time, gen_call_score, sched_call_score, complaint_call_score, procedure_call_score, sched_proc_veri_score, trainer, qa_date, overall_result, qa_filename)
            cur.execute(SQL, DATA)
            cur.close()
            con.commit()

            files_today = get_trainer_files(trainer)

            html_content = """
            <html>
            <head>            
                <style>
                body {
            margin: 0;
            display: grid;
            min-height: 10vh;
            place-items: center;
            background-color: lightgray;
        }
        div {
            text-align: center;
        }

        p, button {
            text-align: center;
        }
                </style>
            </head>
            <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
            <body>
            <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
                <h2>File  uploaded!</h2>
                <p>You uploaded: %s <br></p>""" % (_filename, )

            for item in files_today:
                html_content += f"""
                {item[0]}<br>"""

            html_content += """<p>To upload another file, click the link below.</p>
                <div><a href="/" class="active">Go back</a></div>
                </body>
                </html>
    """

            return HTMLResponse(content=html_content)
        except Exception as e:
            os.remove(f'QAs\\{file.filename}')
            return HTMLResponse(content=f"Tell Clay about this!\n\n{e}\n\nShow him that error and the file you tried!")
    else:
        wb = load_workbook(filename= f'QAs\\{file.filename}')  # type: ignore
        sheet_ranges = wb['Sheet1']
        trainer_cell = sheet_ranges['A104'].value.split(":")
        trainer = trainer_cell[-1].strip()
        files_today = get_trainer_files(trainer)
        
        html_content = """
        <html>
        <head>            
            <style>
            body {
		margin: 0;
		display: grid;
		place-items: center;
		background-color: lightgray;
	}
	div {
		text-align: center;
	}

	p, button {
		text-align: center;
	}
            </style>
        </head>
        <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
        <body>
        <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
            <h2>File already uploaded!</h2>
            <p>You tried uploading: <b>%s</b></p>
            <p>Please go back and select a different file.</p>
            <p>You've already uploaded these files:</p>""" % (file.filename, )

        print("File already uploaded!")
        for item in files_today:
            html_content += f"""
            {item[0]}<br>"""

        html_content += """<p><div><a href="/" class="active">Go back</a></div>
            </body>
            </html>"""

        return HTMLResponse(content=html_content)

# Initialize the database table when the app starts
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
    except Exception as e:
        print(e)

@app.get("/dashboard", response_class=HTMLResponse)
async def read_root():
    names = ["Monica Estrada", "Daisy Colin", "Eric Gaona", "Juan I. Recio"] #names of QAs
    
    # HTML table with auto-refresh
    html_content = """
    <html>
        <head>
            <meta http-equiv="refresh" content="300"> <!-- Auto-refresh every 5 minutes seconds -->
            <style>
            h2 {
            font-size: 40px;
            }
            body {
		margin: 0;
        padding: 0;
		place-items: center;
		background-color: lightgray;
	}
	div {
		text-align: center;
        line-height: 1;
        margin: 0;
        padding: 0;
	}

	p, button {
		text-align: center;
        margin: 0;
        padding: 0;
        line-height: 1;
	}
    th, tr {
    padding-right: 15;
    text-align: center;
    border: solid;
    font-size: 24px;
    }

    td {
    background-color: white;
    border: 2px solid;
    white-space: pre-line;
    text-align : center;}

            </style>
        </head>
        <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
        <body>
        <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
        <div><h2>Daily Quality Assurance Counts (as of %s)</h2></div>
<table>
                <tr>
                    <th>Clinic(s)</th>
                    <th>Name</th>
                    <th>Quality Assurance Count Today</th>
                    <th>Average Score Today</th>
                    <th>Running Weekly Total</th>
                    <th>Weekly Goal</th>
                </tr>
    """ % (datetime.now().strftime("%I:%M %p"),) 

    for name in names:
        clinic: str = ''
        if name == "Monica Estrada":
            clinic = "Neuro / Operators"
        elif name == "Eric Gaona":
            clinic = """Transplant / Counseling
    ENT / ENT South 
    All MSCs / Rheuma / Diabetes & Endo """
        elif name == "Daisy Colin":
            clinic = "Surgery"
        elif name == "Juan I. Recio":
            clinic = "Endo"

        running_total = get_running_total(name)

        progress_bar = '                    '
        count = int(round((running_total / 200) * 20, 0))
        final_bar = progress_bar.replace(' ', '=', count) # type: ignore

        count = get_daily_qa_count(name)
        try:
            average_score = round(get_average_score(name), 2)
        except: #catches if QA has not scored anyone yet
            average_score = 0
        if average_score <= 80:
            color = 'red'
        elif average_score <= 90:
            color = 'orange'
        else:
            color = 'green'
        
        html_content += f"""
                <tr>
                    <td>{clinic}</td>
                    <td>{name}</td>
                    <td>{count} / 40</td>
                    <td style="color: {color}"><b>{average_score}</b></td>
                    <td>{running_total}</td>
                    <td><pre>[{final_bar}]</pre></td
                </tr>
        """

    html_content += """
            </table>
        </body>
        <!-- Clay was here! :) -->
    </html>
    """

    return HTMLResponse(content=html_content)

@app.get("/monica", response_class=HTMLResponse)
async def monica_files(request: Request):
    monica_files = get_trainer_files("Monica Estrada")
    html_content = """
            <html>
            <head>            
                <style>
                body {
            margin: 0;
            display: grid;
            min-height: 10vh;
            place-items: center;
            background-color: lightgray;
        }
        div {
            text-align: center;
        }

        p, button {
            text-align: center;
        }
                </style>
            </head>
            <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
            <body>
            <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
                <h2>Monica's Uploaded Files for the Day</h2>"""                

    for item in monica_files:
        html_content += f"""
        {item[0]}<br>"""

    html_content += """<p>To upload a file, click the link below.</p>
        <div><a href="/" class="active">Go back</a></div>
        </body>
        </html>"""

    return HTMLResponse(content=html_content)

@app.get("/juan", response_class=HTMLResponse)
async def juan_files(request: Request):
    juan_files = get_trainer_files("Juan I. Recio")
    html_content = """
            <html>
            <head>            
                <style>
                body {
            margin: 0;
            display: grid;
            min-height: 10vh;
            place-items: center;
            background-color: lightgray;
        }
        div {
            text-align: center;
        }

        p, button {
            text-align: center;
        }
                </style>
            </head>
            <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
            <body>
            <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
                <h2>Juan's Uploaded Files for the Day</h2>"""                

    for item in juan_files:
        html_content += f"""
        {item[0]}<br>"""

    html_content += """<p>To upload a file, click the link below.</p>
        <div><a href="/" class="active">Go back</a></div>
        </body>
        </html>"""

    return HTMLResponse(content=html_content)

@app.get("/eric", response_class=HTMLResponse)
async def eric_files(request: Request):
    eric_files = get_trainer_files("Eric Gaona")
    html_content = """
            <html>
            <head>            
                <style>
                body {
            margin: 0;
            display: grid;
            min-height: 10vh;
            place-items: center;
            background-color: lightgray;
        }
        div {
            text-align: center;
        }

        p, button {
            text-align: center;
        }
                </style>
            </head>
            <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
            <body>
            <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
                <h2>Eric's Uploaded Files for the Day</h2>"""                

    for item in eric_files:
        html_content += f"""
        {item[0]}<br>"""

    html_content += """<p>To upload a file, click the link below.</p>
        <div><a href="/" class="active">Go back</a></div>
        </body>
        </html>"""

    return HTMLResponse(content=html_content)

@app.get("/daisy", response_class=HTMLResponse)
async def daisy_files(request: Request):
    daisy_files = get_trainer_files("Daisy Colin")
    html_content = """
            <html>
            <head>            
                <style>
                body {
            margin: 0;
            display: grid;
            min-height: 10vh;
            place-items: center;
            background-color: lightgray;
        }
        div {
            text-align: center;
        }

        p, button {
            text-align: center;
        }
                </style>
            </head>
            <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
            <body>
            <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
                <h2>Daisy's Uploaded Files for the Day</h2>"""                

    for item in daisy_files:
        html_content += f"""
        {item[0]}<br>"""

    html_content += """<p>To upload a file, click the link below.</p>
        <div><a href="/" class="active">Go back</a></div>
        </body>
        </html>"""

    return HTMLResponse(content=html_content)

def get_trainer_files(trainer) -> list[tuple]:
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}')
    cur = con.cursor()
    SQL = "SELECT filename FROM qa WHERE (trainer = %s AND upload_date = CURRENT_DATE);"
    cur.execute(SQL, (trainer,))
    files = cur.fetchall()
    return files

def get_daily_qa_count(name) -> int:
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}')
    cur = con.cursor()
    SQL = """SELECT COUNT(*) 
    FROM qa 
    WHERE (trainer = %s AND upload_date = CURRENT_DATE); """
    cur.execute(SQL, (name,))
    count = cur.fetchone()[0] # type: ignore
    cur.close()
    con.close()
    return count

def get_average_score(name) -> float:
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}')
    cur = con.cursor()
    SQL ="""
    SELECT  
       AVG(CASE 
           WHEN gen_call_score != 0 THEN gen_call_score 
           WHEN sched_call_score != 0 THEN sched_call_score 
           WHEN complaint_call_score != 0 THEN complaint_call_score 
           WHEN procedure_call_score != 0 THEN procedure_call_score
           WHEN sched_proc_veri_score != 0 THEN sched_proc_veri_score
       END) AS overall_avg_non_zero       
    FROM qa
    WHERE (trainer = %s AND upload_date = CURRENT_DATE);"""
    cur.execute(SQL, (name,))
    avg_score = cur.fetchone()[0] # type: ignore
    cur.close()
    con.close()
    return avg_score

def get_running_total(name) -> int:
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}')
    cur = con.cursor()
    SQL = """SELECT COUNT(*) 
    FROM qa 
    WHERE trainer = %s AND (upload_date >= DATE_TRUNC('week', CURRENT_DATE) AND
    upload_date < DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '7 days')"""
    cur.execute(SQL, (name,))
    running_total = cur.fetchone()[0] # type: ignore
    cur.close()
    con.close()
    return running_total