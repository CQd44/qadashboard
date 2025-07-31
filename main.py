#QA dashboard and QA score processing
#Very basic, but works!
#port 9999

from openpyxl import load_workbook
from fastapi import FastAPI, Form, Request, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import psycopg2
import toml
import aiofiles # type: ignore
import os.path
import os
from datetime import datetime
import pytimeparse
import math
import csv
from icecream import ic

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static") #logo and favicon go here
templates = Jinja2Templates(directory="templates") #load HTML file from this directory

CONFIG = toml.load("./config.toml") #load variables from toml file
CLINICS: dict[str, str] = CONFIG['qas'] #dict of QA name : clinic mapping

# Home page with the form
@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("form.html", {"request": request})

# Acknowledge file was uploaded and process file!
@app.post("/upload", response_class=HTMLResponse)
async def process_file(file: UploadFile):
    if not os.path.exists(f'QAs\\{file.filename}'):
        try:
            contents = await file.read()
            async with aiofiles.open(f"QAs\\{file.filename}", 'wb') as f: # type: ignore
                await f.write(contents)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'Something went wrong. Tell Clay! {e}')
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

            handle_time = str(sheet_ranges['G7'].value)
            if not handle_time:
                handle_time = sheet_ranges['F7'].value.split(":")[-1].strip()
            
            parsed_time = 1.5 * (pytimeparse.parse(handle_time)) # type: ignore
            minutes = str(math.floor(parsed_time / 60)) # type: ignore
            seconds = str(int(parsed_time % 60)) # type: ignore
            if len(minutes) == 1:
                minutes = '0' + minutes
            if len(seconds) == 1:
                seconds = '0' + seconds
            scoring_time = f'0:{minutes}:{seconds}'
            print(handle_time, scoring_time)

            try:
                gen_call_score = int(sheet_ranges['I22'].value.split("/")[0].strip())
            except:
                gen_call_score: int = 0
            try:
                sched_call_score = int(sheet_ranges['I33'].value.split("/")[0].strip())
            except:
                sched_call_score: int = 0
            try:
                complaint_call_score = int(sheet_ranges['I44'].value.split("/")[0].strip())
            except:
                complaint_call_score: int = 0
            try:
                procedure_call_score = int(sheet_ranges['I56'].value.split("/")[0].strip())
            except:
                procedure_call_score: int = 0
            
            cust_service_notes = ''
            for i in range(62, 70):
                if sheet_ranges[f'A{i}'].value:
                    cust_service_notes = cust_service_notes + '\n' + sheet_ranges[f'A{i}'].value
            
            try:
                sched_proc_veri_score = int(sheet_ranges['I83'].value.split("/")[0].strip())
            except:
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
                    filename,
                    scoring_time)
                    VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);'''
            DATA = (agent, extension, clinic, date_time, phone, handle_time, gen_call_score, sched_call_score, complaint_call_score, procedure_call_score, sched_proc_veri_score, trainer, qa_date, overall_result, qa_filename, scoring_time)
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
                <p>You uploaded: %s <br></p>""" % (file.filename, )

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
async def read_root() -> HTMLResponse:    
    # HTML table with auto-refresh
    html_content = """
    <html>
        <head>
            <meta http-equiv="refresh" content="300"> <!-- Auto-refresh every 5 minutes -->
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
            <title>Quality Assurance Dashboard</title>
        </head>
        <link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
        <body>
        <div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "320px" height = "87.5px"></div>
        <div><h2>Daily Quality Assurance Counts (as of %s)</h2></div>
<table>
                <tr>
                    <th>Clinic(s)</th>
                    <th>Trainer</th>
                    <th>Quality Assurance Count Today</th>
                    <th>Average Score Today</th>
                    <th>Weekly Target</th>
                    <th>Weekly Goal</th>
                </tr>
    """ % (datetime.now().strftime("%I:%M %p"),) 

    for name in CLINICS.keys():
        clinic: str = CLINICS[name]

        running_total = get_running_total(name)

        weekly_progress = (round(running_total / 200, 2) * 100)

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

        if running_total == 200:
            color2 = 'green'
        else:
            color2 = 'red'

        html_content += f"""
                <tr>
                    <td>{clinic}</td>
                    <td>{name}</td>
                    <td>{count} / 40</td>
                    <td style="color: {color}"><b>{average_score}</b></td>
                    <td style="color: {color2}">{weekly_progress}%</td>
                    <td>200</td
                </tr>
        """

    html_content += """
            </table>
        </body>
        <!-- Clay was here! :) -->
    </html>
    """

    return HTMLResponse(content=html_content)

#endpoints for all the trainers to view what files they uploaded that day
@app.get("/monica", response_class=HTMLResponse)
async def monica_files(request: Request):
    return file_check(request)

@app.get("/juan", response_class=HTMLResponse)
async def juan_files(request: Request):
    return file_check(request)

@app.get("/eric", response_class=HTMLResponse)
async def eric_files(request: Request):
    return file_check(request)

@app.get("/daisy", response_class=HTMLResponse)
async def daisy_files(request: Request):
    return file_check(request)

@app.get("/bianca", response_class=HTMLResponse)
async def bianca_files(request: Request):
    return file_check(request)

@app.get("/lori", response_class=HTMLResponse)
async def lori_files(request: Request):
    return file_check(request)    

@app.get("/josie", response_class=HTMLResponse)
async def josie_files(request: Request):
    return file_check(request)

@app.get("/jewlyssa", response_class=HTMLResponse)
async def jewlyssa_files(request: Request):
    return file_check(request)

@app.get("/gabriel", response_class=HTMLResponse)
async def gabriel_files(request: Request):
    return file_check(request)

@app.get("/debra", response_class=HTMLResponse)
async def debra_files(request: Request):
    return file_check(request)

@app.post("/report")
async def run_report(month_from: int = Form(...), day_from: int = Form(...), year_from: int = Form(...), month_to: int = Form(...), day_to: int = Form(...), year_to: int = Form(...)) -> FileResponse | HTMLResponse:
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()

    from_date = str(year_from) + "-" + str(month_from) + "-" + str(day_from)
    to_date = str(year_to) + "-" + str(month_to) + "-" + str(day_to)

    if datetime.strptime(to_date, '%Y-%m-%d') < datetime.strptime(from_date, '%Y-%m-%d'):
        html_content="""
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
            <h2>Report range error!</h2>
            <p>Please go back and check your report range and make sure the "From" date is before or the same as the "To" date</p>
            <p><div><a href="/" class="active">Go back</a></div>
            </body>
            </html>            
            """
        return HTMLResponse(content=html_content)

    with open('qa_report.csv', 'w', newline = '') as output:
        team_scoring_time = 0

        cur.execute("SELECT DATE %s - DATE %s as date_diff;", (to_date, from_date))
        date_diff = cur.fetchone()[0] # type: ignore

        cur.execute("SELECT DATE %s - INTERVAL '%s DAYS' as new_from;", (from_date, date_diff))
        new_from = cur.fetchone()[0]  # type: ignore
        
        writer = csv.writer(output)
        writer.writerow(["QA Name", "Clinics", "Agents Scored", "Average Score", "Number of Calls", "Date Range", "Agents Trending Download in Score", "Agents Trending Upward in Score", "Total Time Scoring Calls"])
        for name in CLINICS.keys():
            try:
                SQL = "SELECT agent FROM qa WHERE (trainer = %s AND (upload_date >= %s AND upload_date <= %s));"
                DATA = (name, from_date, to_date)
                cur.execute(SQL, DATA)
                agents = cur.fetchall()

                SQL = "SELECT COUNT(*) FROM qa WHERE (trainer = %s AND (upload_date >= %s AND upload_date <= %s));"
                DATA = (name, from_date, to_date)
                cur.execute(SQL, DATA)
                calls = cur.fetchone()[0] # type: ignore

                agents_scored = []
                trending_up = []
                trending_down = []
                for agent in agents:
                    if agent[0] not in agents_scored:
                        agents_scored.append(agent[0])

                date_range = from_date + ' - ' + to_date
                
                SQL = "SELECT scoring_time FROM qa WHERE (trainer = %s AND (upload_date >= %s AND upload_date <= %s));"
                DATA = (name, from_date, to_date)
                cur.execute(SQL, DATA)
                score_times = cur.fetchall()
                time_scoring = 0                
                for time in score_times:
                    if time[0] != None:
                        time_scoring += int(pytimeparse.parse(time[0])) # type: ignore                
                
                team_scoring_time += time_scoring #add QA team member's time to total time here
                hours = str(math.floor(time_scoring / 3600))
                minutes = str(math.floor((time_scoring % 3600) / 60)) # type: ignore
                seconds = str(int(time_scoring % 60)) # type: ignore
                
                if len(minutes) == 1:
                    minutes = '0' + minutes
                if len(seconds) == 1:
                    seconds = '0' + seconds
                total_scoring_time = f'{hours}:{minutes}:{seconds}'

                SQL = """SELECT 
                                AVG(CASE 
                                    WHEN gen_call_score != 0 THEN gen_call_score 
                                    WHEN sched_call_score != 0 THEN sched_call_score 
                                    WHEN complaint_call_score != 0 THEN complaint_call_score 
                                    WHEN procedure_call_score != 0 THEN procedure_call_score
                                    WHEN sched_proc_veri_score != 0 THEN sched_proc_veri_score
                                END) AS overall_avg_non_zero 
                                FROM qa 
                                WHERE (trainer = %s AND (upload_date >= %s AND upload_date <= %s));"""
                DATA = (name, from_date, to_date)
                cur.execute(SQL, DATA)
                try:
                    avg = round(cur.fetchone()[0], 2) # type: ignore
                except Exception as e:
                    avg = 0

                # try to get trending info on agents
                for agent in agents:
                    SQL = """SELECT 
                                AVG(CASE 
                                    WHEN gen_call_score != 0 THEN gen_call_score 
                                    WHEN sched_call_score != 0 THEN sched_call_score 
                                    WHEN complaint_call_score != 0 THEN complaint_call_score 
                                    WHEN procedure_call_score != 0 THEN procedure_call_score
                                    WHEN sched_proc_veri_score != 0 THEN sched_proc_veri_score
                                END) AS overall_avg_non_zero
                                FROM qa 
                                WHERE (trainer = %s AND agent = %s AND (upload_date >= %s AND upload_date <= %s));"""
                    DATA = (name, agent, from_date, to_date)
                    cur.execute(SQL, DATA)
                    agent_current_average = cur.fetchone()[0] # type: ignore

                    SQL = """SELECT 
                                AVG(CASE 
                                    WHEN gen_call_score != 0 THEN gen_call_score 
                                    WHEN sched_call_score != 0 THEN sched_call_score 
                                    WHEN complaint_call_score != 0 THEN complaint_call_score 
                                    WHEN procedure_call_score != 0 THEN procedure_call_score
                                    WHEN sched_proc_veri_score != 0 THEN sched_proc_veri_score
                                END) AS overall_avg_non_zero
                                FROM qa 
                                WHERE (trainer = %s AND agent = %s AND (upload_date >= %s AND upload_date <= %s));"""
                    DATA = (name, agent, new_from, from_date) # the from_date becomes the new "to" date
                    cur.execute(SQL, DATA)
                    agent_past_average = cur.fetchone()[0] # type: ignore
                    if agent_current_average != None and agent_past_average != None:
                        if agent_current_average > agent_past_average:
                            if agent[0] not in trending_up:
                                trending_up.append(agent[0])
                        elif agent_current_average < agent_past_average:
                            if agent[0] not in trending_down:
                                trending_down.append(agent[0])
                
                writer.writerow([name, CLINICS[name], ', '.join(agents_scored), avg, calls, date_range, ', '.join(trending_down), ', '.join(trending_up), total_scoring_time]) # type: ignore
               
            except Exception as e:
                ic(e)
                continue        
        hours = str(math.floor(team_scoring_time / 3600))
        minutes = str(math.floor((team_scoring_time % 3600) / 60)) # type: ignore
        seconds = str(int(team_scoring_time % 60)) # type: ignore
        
        
        if len(minutes) == 1:
            minutes = '0' + minutes
        if len(seconds) == 1:
            seconds = '0' + seconds
        team_scoring_time = f'{hours}:{minutes}:{seconds}'

        writer.writerow([])
        writer.writerow(['', '', '', '', '', '', '', "Total time team spent scoring calls:", team_scoring_time])
    cur.close()
    con.close()    
    return FileResponse(path='.\qa_report.csv', status_code=200, media_type="csv", filename="qa_report.csv") # type: ignore


"""

Functions

I have separated them from the FastAPI endpoints for ease of working and maintaining this code.

"""

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
                filename TEXT,
                scoring_time TEXT)
                ;'''
            )
    cur.close()
    con.commit()

def get_trainer_files(trainer) -> list[tuple]:
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}')
    cur = con.cursor()
    SQL = "SELECT filename FROM qa WHERE (trainer = %s AND upload_date = CURRENT_DATE);"
    cur.execute(SQL, (trainer,))
    files = cur.fetchall()
    cur.close()
    con.close()
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

def file_check(request: Request) -> HTMLResponse:
    for key in CLINICS.keys():
        if str(request.url).split("/")[-1] in key.split(" ")[0].lower():
            name = key
    trainer_files = get_trainer_files(name) # type: ignore
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
                <h2>%s's Uploaded Files for the Day</h2>""" % (str(request.url).split("/")[-1].title()) # type: ignore

    for item in trainer_files:
        html_content += f"""
        {item[0]}<br>"""

    html_content += """<p>To upload a file, click the link below.</p>
        <div><a href="/" class="active">Go back</a></div>
        </body>
        </html>"""

    return HTMLResponse(content=html_content)