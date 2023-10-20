# CPSC 449 - Project 1

## Back-end Web Service to manage course enrollment and waiting lists with functionality similar to CSUF TitanOnline using FastAPI.

## REST API ENDPOINTS
### Available REST API endpoints for the project
<img src="img\endpoints.png" alt="not found" width="80%">

</br>

Allow students to:
* List available classes
* Attempt to enroll in a class
* Drop a class
* View their current position on the waiting list
* Remove themselves from a waiting list

Allow Instructors to:
* View current enrollment for their classes
* View students who have dropped the class
* Drop students administratively (e.g. if they do not show up to class)
* View the current waiting list for the course
  
Allow Registrar to:
* Add new classes and sections
* Remove existing sections
* Change the instructor for a section
* Freeze automatic enrollment from waiting lists (e.g. during the second week of classes)
  
## Installation
1. Clone this project
2. Install dependencies using "pip install -r requirements.txt"
3. Run database seed script (pro_db.py) using "python pro_db.py"

## Run this project
On Windows/Mac (using uvicorn)
1. Run this command "uvicorn pro:app --reload"
   
On Linux (using foreman)
1. Install Foreman</br>
   sudo apt update </br>
   sudo apt install --yes ruby-foreman </br>
2. Run this command "foreman start"