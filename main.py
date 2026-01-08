#QA dashboard and QA score processing
#Very basic, but works!
#port 9999

from openpyxl import load_workbook
from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import psycopg2
import toml
import aiofiles # type: ignore
import os.path
import os
from datetime import datetime
import pytimeparse # type: ignore
import math
import csv
from icecream import ic
from pydantic import BaseModel
from typing import List, Tuple
import warnings

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static") #logo and favicon go here
templates = Jinja2Templates(directory="templates") #load HTML file from this directory

CONFIG = toml.load("./config.toml") #load variables from toml file
CLINICS: dict[str, str] = CONFIG['qas'] #dict of QA name : clinic mapping
PINS: dict[str, str] = CONFIG['pin'] # dict of name : PIN mapping
CONNECT_STR = f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}'

class SelectedRows(BaseModel):
    selectedRows: List[Tuple[str, str]]
    name: str
    pin: str

# Home page with the form
@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("form.html", {"request": request})

# Acknowledge file was uploaded and process file!
@app.post("/upload", response_class=HTMLResponse)
async def process_file(files: List[UploadFile]):
    filenames: list[str] = []
    error_files: list[str] = []
    prev_uploaded: list[str] = []
    try:        
        for file in files:        
            if not os.path.exists(f'QAs\\{file.filename}'):
                try:
                    contents = await file.read()
                    async with aiofiles.open(f"QAs\\{file.filename}", 'wb') as f: # type: ignore
                        await f.write(contents)
                except Exception as e:
                    error_files.append(file.filename) # type: ignore
                    #raise HTTPException(status_code=500, detail=f'Something went wrong. Tell Clay! {e}\n\n{file.filename}')
                finally:
                    await file.close()
                warnings.simplefilter(action='ignore', category=UserWarning)
                wb = load_workbook(filename= f'QAs\\{file.filename}', data_only=True)  # data_only is necessary because openpyxl can not evaluate formulas
                sheet_ranges = wb['Scorecard']
                try:
                    agent = sheet_ranges['G1'].value
                    extension = str(sheet_ranges['G2'].value)
                    clinic = sheet_ranges['G3'].value.strip()
                    date_time = str(sheet_ranges['G4'].value) + " " +  str(sheet_ranges['G5'].value) #concat both cells
                    phone = str(sheet_ranges['G6'].value)
                    handle_time = str(sheet_ranges['G7'].value)                        
                    parsed_time = 1.5 * (pytimeparse.parse(handle_time)) # type: ignore
                    hours =   str(math.floor(parsed_time / 3600))
                    minutes = str(math.floor(parsed_time / 60)) # type: ignore
                    seconds = str(int(parsed_time % 60)) # type: ignore
                    if len(minutes) == 1:
                        minutes = '0' + minutes
                    if len(minutes) > 2:
                        minutes = '03' 
                    if len(seconds) == 1:
                        seconds = '0' + seconds
                    scoring_time = f'{hours}:{minutes}:{seconds}'
                    ic(scoring_time)
                    try:
                        intro = int(sheet_ranges['I21'].value.split("/")[0].strip())
                    except:
                        intro: int = 0

                    try:
                        sched_call_score = int(sheet_ranges['I33'].value.split("/")[0].strip())
                    except:
                        sched_call_score: int = 0

                    try:
                        resched = int(sheet_ranges['I40'].value.split("/")[0].strip())
                    except:
                        resched: int = 0

                    try:
                        confirm = int(sheet_ranges['I47'].value.split("/")[0].strip())
                    except:
                        confirm: int = 0  

                    try:
                        clinical = int(sheet_ranges['I71'].value.split("/")[0].strip())
                    except:
                        clinical: int = 0  

                    try:
                        complaint = int(sheet_ranges['I59'].value.split("/")[0].strip())
                    except:
                        complaint: int = 0                

                    trainer_cell = sheet_ranges['A92'].value.split(":")
                    trainer = trainer_cell[-1].strip()

                    if "juan" in trainer.lower():
                        trainer = "Juan I. Recio"

                    if "monica" in trainer.lower():
                        trainer = "Monica Estrada"

                    if "eric" in trainer.lower():
                        trainer = "Eric Gaona"

                    if "daisy" in trainer.lower():
                        trainer = "Daisy Colin"

                    if trainer == "" or trainer == None:
                        os.remove(f'QAs\\{file.filename}')
                        error_files.append(file.filename) # type: ignore
                        
                    qa_date = sheet_ranges['G92'].value.split(":")[-1].strip()
                    
                    if qa_date == None or qa_date == "":
                        qa_date = datetime.today().strftime('%Y-%m-%d')

                    overall_result = sheet_ranges['I95'].value
                    
                    qa_filename = file.filename

                    ic(agent, extension, clinic, date_time, phone, handle_time, intro, sched_call_score, resched, confirm, clinical, complaint, trainer, qa_date, overall_result, qa_filename, scoring_time)
                    con = psycopg2.connect(CONNECT_STR)
                    cur = con.cursor()
                    QUERY = '''INSERT INTO qa 
                            (agent,
                            extension,
                            clinic,
                            date_time,
                            phone,
                            handle_time,
                            intro,
                            sched_call_score,
                            resched,
                            confirm,
                            clinical,
                            complaint_call_score,
                            trainer,
                            qa_date,
                            overall_result,
                            filename,
                            scoring_time)
                            VALUES 
                            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);'''
                    DATA = (agent, extension, clinic, date_time, phone, handle_time, intro, sched_call_score, resched, confirm, clinical, complaint, trainer, qa_date, overall_result, qa_filename, scoring_time)
                    cur.execute(QUERY, DATA)
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
                        <p><div><a href="/" class="active">Go back</a></p></div>
                        <p>You uploaded:<br></p>""" 
                    filenames.append(file) # type: ignore
                    for item in filenames:
                        html_content += f"{item.filename}<br>" # type: ignore

                    if len(error_files) > 0:
                        html_content += "<p>These files had some kind of issue and they need to be fixed:</p>"
                        for item in error_files:
                            html_content += f"{item.filename}<br>" # type: ignore
                    if len(prev_uploaded) > 0:
                        html_content += "<p>These files were previously uploaded: </p>"
                        for item in prev_uploaded:
                            html_content += f"{item.filename}<br>" # type: ignore

                    html_content += "<p>Today you've uploaded: </p>"

                    for item in files_today:
                        html_content += f"{item[0]}<br>"

                    html_content += """<p>To upload another file, click the link below.</p>
                        <div><a href="/" class="active">Go back</a></div>
                        </body>
                        </html>
            """
                    
                    #return HTMLResponse(content=html_content)
                except Exception as e:
                    print(file)
                    try:
                        os.remove(f'QAs\\{file.filename}')
                    except:
                        print("Unable to remove file.")
                    error_files.append(file.filename) # type: ignore
                    #return HTMLResponse(content=f"Tell Clay about this!\n\n{e}\n\nShow him that error and the file you tried!")
            else:
                prev_uploaded.append(file.filename) # type: ignore
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"Something went wrong! Tell Clay! {e}")
        
# Initialize the database table when the app starts
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
    except Exception as e:
        print(e)

@app.get("/dashboard", response_class=HTMLResponse)
async def read_root() -> HTMLResponse:
    CONFIG = toml.load("./config.toml")
    _GOALS: dict = CONFIG['goals']  

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

    a.button {
            text-align: center;
            place-items: center;
            padding: 1px 6px;
            border: 1px outset buttonborder;
            border-radius: 3px;
            color: black;
            background-color: gainsboro;
            text-decoration: none;
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

    total_today: float = 0 #needed to find weighted averages
    num_of_scores: int = 0

    for name in CLINICS.keys():
        goal = _GOALS[name]
        clinic: str = CLINICS[name]

        running_total = get_running_total(name)

        weekly_progress = round((round(running_total / 200, 2) * 100), 2)

        count = get_daily_qa_count(name)
        num_of_scores += count

        try:
            average_score = round(get_average_score(name), 2)
            total_today += round((average_score * count), 2)
        except: #catches if QA has not scored anyone yet
            average_score = 0
                    
        if average_score <= 80:
            color = 'red'
        elif average_score <= 90:
            color = 'orange'
        else:
            color = 'green'

        if running_total >= 200:
            color2 = 'green'
        else:
            color2 = 'red'

        html_content += f"""
                <tr>
                    <td>{clinic}</td>
                    <td>{name}</td>
                    <td>{count} / {goal}</td>
                    <td style="color: {color}"><b>{average_score}</b></td>
                    <td style="color: {color2}">{weekly_progress}%</td>
                    <td>200</td
                </tr>
        """
    if num_of_scores > 0:
        average_score_today = round((total_today / num_of_scores), 2)
        if average_score_today <= 80:
            color = 'red'
        elif average_score_today <= 90:
            color = 'orange'
        else:
            color = 'green'
    else:
        color = 'black'
        average_score_today = "-"

    html_content += f"""
                    <tr>
                        <td></td>
                        <td>Total:</td>
                        <td>{num_of_scores}</td>
                        <td style="color: {color}"><b>{average_score_today}</b></td>
                        <td></td>
                        <td></td>
                    </tr>
        """

    html_content += """
            </table>
            <div style="padding-top: 5% ;text-align: center; place-items: center;"><a class="button" href="/" class="button">Go Back</a></div>
        </body>
        <!-- Clay was here! :) -->
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/agents")
async def get_agents(request: Request) -> JSONResponse:
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()
    QUERY = "SELECT DISTINCT(agent) FROM qa ORDER BY agent;"
    cur.execute(QUERY)
    results = cur.fetchall()
    agent_dict = {agent[0] : agent[0] for agent in results}
    return JSONResponse(content=agent_dict)

@app.post("/agenthistory")
async def gethistory(request: Request, agentname: str = Form(...), pin: str = Form(...)):
    auth_pin = CONFIG["pin"]['Agent Check']
    if pin != auth_pin:
        return HTMLResponse(content="INVALID PIN")
    else:
        con = psycopg2.connect(CONNECT_STR)
        cur = con.cursor()
        QUERY = "SELECT agent, upload_date, intro, sched_call_score, complaint_call_score, confirm, clinical, resched FROM qa WHERE (agent = %s AND upload_date >= '1-1-2026');"
        DATA = (agentname, )
        cur.execute(QUERY, DATA)
        results = cur.fetchall()
        ic(results)
        scores = []
        dates = []
        for result in results:
            score = 0
            for i in range(2, 8):
                try:
                    score += result[i]
                except:
                    continue
            if score > 0:
                dates.append(str(result[1]))
                scores.append(score)
        html_content = """
     <html>
     <head>
     <style>

     	a.button {
            text-align: center;
            place-items: center;
            padding: 1px 6px;
            border: 1px outset buttonborder;
            border-radius: 3px;
            color: black;
            background-color: gainsboro;
            text-decoration: none;
            }
     </style>

    <script src="https://cdn.plot.ly/plotly-3.3.0.min.js" charset="utf-8"></script>
    <body style="background-color: lightgray;">
        <div style="height: 90vh; place-items: center;">
        <div></div>
        <div id="plot" style="background-color: lightgray; width:80vw; height: 80vh;"></div>
        </div>
        <script>

const trace1 = {
    x: %s,
    y: %s,
    type: 'scatter',
    mode: 'markers',
    marker: {
    size: 60
    }
};

var data = [trace1];

var layout = {
    title: { 
    text: '%s QA Scores Over Time',
    font: {
        family: 'Calibri',
        size: 24
            }
        },
    xaxis: {
        type: 'date',
        title: {
        font: {
        family: 'Calibri',
        size: 24
            },
        text: 'Date'
        }
    },
    yaxis: {
        title: {
        font: {
        family: 'Calibri',
        size: 24
            },
        text: 'Scores'
        }
    },
    autosize: true,
    margin: { t : 50}
};

var config = {
    responsive: true
};

Plotly.newPlot('plot', data, layout, config);
        </script>
        <div style="text-align: center; place-items: center;"><a class="button" href="/" class="button">Go Back</a></div>
        </body>
        </html>
""" % (dates, scores, agentname)
        return HTMLResponse(content=html_content)

#endpoints for all the trainers to view what files they uploaded that day
@app.get("/monica", response_class=HTMLResponse)
async def monica_files(request: Request) -> HTMLResponse:
    return file_check(request)

@app.get("/juan", response_class=HTMLResponse)
async def juan_files(request: Request) -> HTMLResponse:
    return file_check(request)

@app.get("/eric", response_class=HTMLResponse)
async def eric_files(request: Request) -> HTMLResponse:
    return file_check(request)

@app.get("/daisy", response_class=HTMLResponse)
async def daisy_files(request: Request) -> HTMLResponse:
    return file_check(request)

@app.post("/report") #Allows user to download a report. Report is mostly static except for the date range.
async def run_report(month_from: int = Form(...), day_from: int = Form(...), year_from: int = Form(...), month_to: int = Form(...), day_to: int = Form(...), year_to: int = Form(...)) -> FileResponse:
    con = psycopg2.connect(CONNECT_STR)
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
        return HTMLResponse(content=html_content) # type: ignore

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
                            AVG(intro + sched_call_score + complaint_call_score + confirm + clinical + resched) AS overall_avg
                        FROM qa 
                        WHERE trainer = %s 
                        AND upload_date BETWEEN %s AND %s;"""
                DATA = (name, from_date, to_date)
                cur.execute(SQL, DATA)
                try:
                    avg = round(cur.fetchone()[0], 2) # type: ignore
                except Exception as e:
                    avg = 0

                # try to get trending info on agents
                for agent in agents:
                    SQL = """SELECT 
                            AVG(intro + sched_call_score + complaint_call_score + confirm + clinical + resched) AS overall_avg 
                        FROM qa 
                        WHERE (trainer = %s AND agent = %s
                        AND upload_date BETWEEN %s AND %s);"""
                    DATA = (name, agent, from_date, to_date)
                    cur.execute(SQL, DATA)
                    agent_current_average = cur.fetchone()[0] # type: ignore

                    SQL = """SELECT 
                            AVG(intro + sched_call_score + complaint_call_score + confirm + clinical + resched) AS overall_avg
                        FROM qa 
                        WHERE (trainer = %s AND agent = %s
                        AND upload_date BETWEEN %s AND %s);"""
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
                ic("Error is here!", e)
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

@app.post("/removefiles", response_class=HTMLResponse)
async def remove_files(data: SelectedRows):
    name = data.name
    pin = data.pin
    if pin != PINS[name]:
        print(f"Incorrect PIN entered for {name}.")
    else:
        selected_rows = data.selectedRows
        con = psycopg2.connect(CONNECT_STR)
        cur = con.cursor()

        QUERY = "DELETE FROM qa WHERE filename = %s;"
        for row in selected_rows:
            DATA = (row[0], )
            cur.execute(QUERY, DATA)
            os.remove(f'QAs\\{row[0]}')
            print(f"Removed file: {row[0]}")
        cur.close()
        con.commit()
        return HTMLResponse(content="How did you get here? Well, the files were removed so... good job!")

"""

Functions

I have separated them from the FastAPI endpoints for ease of working and maintaining this code.

"""

# Set up postgresql table
def init_db():
    pass

def get_trainer_files(trainer) -> list[tuple]:
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()
    SQL = "SELECT filename FROM qa WHERE (trainer = %s AND upload_date = CURRENT_DATE);"
    cur.execute(SQL, (trainer,))
    files = cur.fetchall()
    cur.close()
    con.close()
    return files

def get_daily_qa_count(name) -> int:
    con = psycopg2.connect(CONNECT_STR)
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
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()
    SQL ="""
    SELECT 
        AVG(intro + sched_call_score + complaint_call_score + confirm + clinical + resched) AS overall_avg      
    FROM qa
    WHERE (trainer = %s AND upload_date = CURRENT_DATE);"""
    cur.execute(SQL, (name,))
    avg_score = cur.fetchone()[0] # type: ignore
    cur.close()
    con.close()
    return avg_score

def get_running_total(name) -> int:
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()
    SQL = """SELECT COUNT(*) 
    FROM qa 
    WHERE trainer = %s AND (upload_date >= DATE_TRUNC('week', CURRENT_DATE) AND
    upload_date < DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '7 days');"""
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
                <h2>%s's Uploaded Files for the Day</h2>
                <form id="dynamicForm" method="post" action="/removefiles">
                <input type="hidden" id="name" name="name" value="%s" />
<table style="text-align: center; align-items: center;">
                <tr>
                    <th>Filename</th>
                    <th>Remove?</th>
                </tr>""" % (str(request.url).split("/")[-1].title(), name) # type: ignore

    for item in trainer_files:
        html_content += f"""
                        <tr>                        
                            <td>{item[0]}</td>
                            <td> <input type="checkbox" data-id="{item[0]}" name="selectedRows"  data-name="{item[0]}">
                <label for="filename"></label><br></td>
                        </tr>
                        """

    html_content += """</table>
        <div><label>PIN: <input type = "text" id = "pin" name = "pin" minlength = "4" maxlength="4" required></label><input type="submit" id="submitbtn" value="Submit"></div>
        </form>
    <p>To upload a file, click the link below.</p>
        <div><a href="/" class="active">Go back</a></div>
        
        <script>
            document.getElementById("dynamicForm").addEventListener("submit", async (event) => {
            event.preventDefault(); 

            const nameInput = document.querySelector('#name');
            const pinInput = document.querySelector('#pin');

            const checkboxes = document.querySelectorAll('input[name="selectedRows"]:checked');
            const selectedData = Array.from(checkboxes).map(checkbox => [
                checkbox.dataset.id,
                checkbox.dataset.name
            ]);            

            const form = document.getElementById("dynamicForm");
            const endpoint = form.action;

            const dataToSend = {
                selectedRows: selectedData, 
                name: nameInput.value,     
                pin: pinInput.value       
            };

            try {
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(dataToSend)
                });

                if (response.ok) {
                    const result = await response.json();
                    console.log("Server response:", result);
                    window.location.href = window.location.href;
                    // Optionally redirect or update UI based on response
                } else {
                    console.error("Error submitting data:", response.statusText);
                    window.location.href = window.location.href;
                }
            } catch (error) {
                console.error("Network error:", error);
                window.location.href = window.location.href;
            }
        });

        </script>               
        </body>
        </html>"""

    return HTMLResponse(content=html_content)