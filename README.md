Super basic, super rough, super unoptimized functional testing version of a dashboard / database system I'm creating for management.

The process is:

QAs/Trainers go to the FastAPI endpoint (host:9999) and upload a completed QA scorecard.
This script will then parse that excel file (MUST be excel, and MUST be the latest one made) and populate a database with values pulled from it.
*Although I'm asking everyone uses the lastest version of that scorecard, I do have catches in place to try to correct if they accidentally use an older version. 

From the QA side of things, this is it. They will be met with a page telling them the upload was successful or not, what they just uploaded (or tried to upload), and a list of files they have uploaded that day.

On the /dashboard side of things:

The database will be queried and return values mostly based on the CURRENT_DATE and the trainer names (defined currently in a list in the script but will eventually be moved to TOML file)
The dashboard display some info, namely how many QAs each QA/Trainer has done and what the average score is across the agents those QA/Trainers are scoring. 

So far, file removal has been added (along with PIN verification so that QAs can only remove their own files) and the reporting functionality is working as intended, so as long as the QA team is consistent with their QAs. 
