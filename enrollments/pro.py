import collections
import contextlib
import logging.config
import sqlite3
import datetime
from typing import Optional
from fastapi import FastAPI, Depends, Response, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import jwt


"""
Helper Functions
"""

def decode_jwt(request: Request):
    token_from_header = request.headers.get('Authorization')
    token = token_from_header[7:] # Removing Bearer
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except jwt.ExpiredSignatureError:
        # Handle token expiration
        return None
    except jwt.DecodeError:
        # Handle token decoding error
        return None

async def get_current_user(request: Request, token: str = Depends(decode_jwt)):
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


class Enrollment(BaseModel):
    ClassId: int

class Class(BaseModel):
    InstructorUserName: str
    InstructorName: str
    Department: str
    ClassName: str
    CourseCode: str
    SectionNumber: int
    MaxEnrollment: int = 40
    AutomaticEnrollmentFrozen: int = 0

class UpdateInstructor(BaseModel):
    InstructorUserName: str
    InstructorName: str

app = FastAPI()


def get_db():
    with contextlib.closing(sqlite3.connect("enrollments/pro1.db")) as db:
        db.row_factory = sqlite3.Row
        yield db

@app.get("/",status_code=status.HTTP_200_OK)
def default():
    hidden_paths = ["/openapi.json", "/docs/oauth2-redirect", "/redoc", "/openapi.json", "/docs", "/"]
    url_list = list(filter(lambda x: x["path"] not in hidden_paths, [{"path" : route.path, "name": route.name} for route in app.routes]))
    return {"routes" : url_list, "message" : f'{len(url_list)} routes found'}
    # return RedirectResponse("/docs")

"""
STUDENTS API ENDPOINTS
"""

# List available classses to students
@app.get("/classes", status_code=status.HTTP_200_OK)
def list_available_classes(db: sqlite3.Connection = Depends(get_db), current_user=Depends(get_current_user)):
    classes = db.execute("""
                         SELECT 
                         ClassId,
                         CourseCode,
                         SectionNumber,
                         ClassName,                         
                         InstructorName,
                         CurrentEnrollment,
                         MaxEnrollment
                         FROM classes 
                         WHERE CurrentEnrollment < MaxEnrollment 
                         AND AutomaticEnrollmentFrozen = 0""")
    # print({"user_info": current_user})
    username, fullName, roles = current_user.get("sub"), current_user.get("name"), current_user.get("roles")
    print(username)
    print(fullName)
    print(roles)
    if not classes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Classes not found"
        )
    return {"classes": classes.fetchall()}


# Attempt to enroll in a class
@app.post("/enrollments/", status_code=status.HTTP_201_CREATED)
def create_enrollment(
    enrollment: Enrollment, response: Response, db: sqlite3.Connection = Depends(get_db), current_user=Depends(get_current_user)
):
    # Current User Info
    username, fullName = current_user.get("sub"), current_user.get("name")
    print(username)
    cur = db.execute("select CurrentEnrollment, MaxEnrollment, AutomaticEnrollmentFrozen from Classes where ClassId = ?",[enrollment.ClassId])
    # checking if class exists
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail= 'Class Does Not Exist',
            )
    currentEnrollment, maxEnrollment, automaticEnrollmentFrozen = entry
    # # checking if student exist
    # cur = db.execute("Select * from Students where StudentId = ?",[enrollment.StudentId])
    # entry = cur.fetchone()
    # if(not entry):
    #     raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail= 'Student Does Not Exist',
    #         )

    # Checking if enrollment frozen is on
    if(automaticEnrollmentFrozen==1):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Enrollment is closed',
            )

    # Checking if student is Already enrolled to the course
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentUsername = ? and dropped = 0",[enrollment.ClassId, username])
    sameClasses = cur.fetchall()
    if(sameClasses):
        raise HTTPException(status_code=409, detail="You are already enrolled") #HTTP status code 409, which stands for "Conflict." 
    
    # Checking if Class is full then adding student to waitlist
    if(currentEnrollment >= maxEnrollment):

        # Checking if student is already on waitList
        cur = db.execute("Select * from WaitingLists where ClassId = ? and  StudentUsername = ?",[enrollment.ClassId, username])
        alreadyOnWaitlist = cur.fetchall()
        if(alreadyOnWaitlist):
            raise HTTPException(status_code=409, detail="You are already on waitlist") #HTTP status code 409, which stands for "Conflict." 

        # Checking that student is not on more than 3 waitlist (not checked)
        cur = db.execute("Select * from Waitinglists where StudentUsername = ?",[username])
        moreThanThree = cur.fetchall()
        if(len(moreThanThree)>3):
            raise HTTPException(status_code=409, detail="Class is full and You are already on three waitlists so, you can't be placed on a waitlist") #HTTP status code 409, which stands for "Conflict." 
        
        # Adding to the waitlist if waitlist is not full
        cur = db.execute("Select * from Waitinglists where ClassId = ?",[enrollment.ClassId])
        entries = cur.fetchall()
        if(len(entries)>=15):
            raise HTTPException(status_code=403, detail="Waiting List if full for this class") # Forbidden
        waitListPosition = len(entries)+1
        e = dict(enrollment)
        try:
            cur = db.execute(
                """
                INSERT INTO WaitingLists(StudentUserName,StudentName,ClassID,WaitingListPos,DateAdded)
                VALUES(?,?, ?, ? , datetime('now')) 
                """,
                [username,fullName,enrollment.ClassId,waitListPosition]
            )
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        e["id"] = cur.lastrowid
        response.headers["Location"] = f"/WaitingLists/{e['id']}"
        message = f"Class is full you have been placed on waitlist position {waitListPosition}"
        # Sagar: new function Checking if student was enrolled earlier
        raise HTTPException(status_code=400, detail=message)
    
    # Checking if student was enrolled earlier
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentUserName = ?",[enrollment.ClassId, username])
    entry = cur.fetchone()
    if(entry):
        try:
            db.execute("""
                    UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentUserName = ?
                    """,
                    [enrollment.ClassId,username]) 
            db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment+1),enrollment.ClassId])
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
        return {"success":"Enrolled"}
        
    else:
    # Registering Students if class is not full
        e = dict(enrollment)
        try:
            cur = db.execute(
                """
                INSERT INTO enrollments(StudentUserName,StudentName,ClassID,EnrollmentDate)
                VALUES(?,?,?, datetime('now')) 
                """,
                [username,fullName,enrollment.ClassId],
            )
            # Updating currentEnrollment
            cur = db.execute("UPDATE Classes SET currentEnrollment = ? where ClassId = ?",[(currentEnrollment+1),enrollment.ClassId])
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        e["id"] = cur.lastrowid
        response.headers["Location"] = f"/enrollments/{e['id']}"
        return {"success":e}

# Delete enrollment of student
@app.delete("/students/enrollments/{ClassId}",status_code=status.HTTP_200_OK)
def drop_enrollment(
    ClassId:int , db: sqlite3.Connection = Depends(get_db), current_user=Depends(get_current_user)
):
    # Current User Info
    username, fullName = current_user.get("sub"), current_user.get("name")
    print(username)
    cur = db.execute("select CurrentEnrollment, MaxEnrollment, AutomaticEnrollmentFrozen from Classes where ClassId = ?",[ClassId])
    entries = cur.fetchone()
    # check if class exists
    if(not entries):
        raise HTTPException(status_code=404, detail="Class does not exist")
    currentEnrollment, maxEnrollment, automaticEnrollmentFrozen = entries
    
    # Checking if student was enrolled to the course
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentUserName = ? and dropped = 0",[ClassId, username])
    entries = cur.fetchone()
    if(not entries):
        raise HTTPException(status_code=404, detail="You are not enrolled in this course") #student enrollement not found
    # student_dropped = entries['dropped']
     
    # dropping the course
    try:
        db.execute("""
                    UPDATE Enrollments SET dropped = 1 where ClassId = ? and StudentUserName = ?
                    """,
                    [ClassId,username]) 
        db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment-1),ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    db.commit()
    cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY WaitingListPos ASC",[ClassId])
    entry = cur.fetchone()
    if (not automaticEnrollmentFrozen and (currentEnrollment-1)<maxEnrollment and entry):

        # Enrolling student who is on top of the waitlist
                # Checking if student was enrolled to that course earlier
        cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentUserName = ?",[ClassId, entry['StudentUserName']])
        enrollment_entry = cur.fetchone()
        if(enrollment_entry):
            try:
                cur = db.execute("UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentUserName = ?",[ClassId, entry['StudentUserName']])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentUserName = ? and ClassId= ? 
                            """,
                            [entry['StudentUserName'],ClassId])
                
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        else:
            try:
                cur = db.execute(
                """
                INSERT INTO enrollments(StudentUserName, StudentName,ClassID,EnrollmentDate)
                VALUES(?,?, ?, datetime('now')) 
                """,
                [entry['StudentUserName'], fullName, ClassId],
            )
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentUserName = ? and ClassId= ? 
                            """,
                            [entry['StudentUserName'],ClassId])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        # updating waitlist positions
        cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY DateAdded ASC",[ClassId])
        entries = cur.fetchall()
        for entry in entries:
            try:
                db.execute("""
                            UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                            """,
                            [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        
        db.commit()
        return  {
                "Message": "successfully dropped"
            }
    db.commit()
    return  {
                "Message": "successfully dropped"
            }

# View Waiting List Position
@app.get("/students/waiting-list/{ClassId}",status_code=status.HTTP_200_OK)
def retrieve_waitinglist_position(
    ClassId: int, db: sqlite3.Connection = Depends(get_db), current_user=Depends(get_current_user)
):
    # Current User Info
    username, fullName = current_user.get("sub"), current_user.get("name")
    # checking if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    # cur = db.execute("SELECT * FROM WaitingLists WHERE StudentUserName = ? and ClassId= ?", [StudentUserName,ClassId])
    # cur = db.execute("""SELECT
    #                  Students.StudentId as student_username,
    #                  Students.FirstName || ', ' || Students.LastName as student_name,
    #                  Classes.CourseCode || ' - ' || Classes.SectionNumber as class_section,
    #                  Classes.ClassName as class_name,
    #                  WaitingLists.WaitingListPos as waiting_list_position

    #                  FROM WaitingLists

    #                  JOIN Students
    #                  ON WaitingLists.StudentId = Students.StudentId 

    #                  JOIN Classes
    #                  ON WaitingLists.ClassId = Classes.ClassId

    #                  WHERE WaitingLists.StudentId = ? 
    #                  and WaitingLists.ClassId= ?""", [StudentId, ClassId])

    cur = db.execute("""SELECT
                     WaitingLists.StudentName as student_name,
                     Classes.CourseCode || ' - ' || Classes.SectionNumber as class_section,
                     Classes.ClassName as class_name,
                     WaitingLists.WaitingListPos as waiting_list_position

                     FROM WaitingLists

                     JOIN Classes
                     ON WaitingLists.ClassId = Classes.ClassId

                     WHERE WaitingLists.StudentUserName = ? 
                     and WaitingLists.ClassId= ?""", [username, ClassId])
    waitingList = cur.fetchone()
    if not waitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Position not found"
        )
    return  {
            "data": waitingList,
            }
    

# Remove from Waiting List
@app.delete("/students/waiting-list/{ClassId}",status_code=status.HTTP_200_OK)
def delete_waitinglist(
    ClassId: int, db: sqlite3.Connection = Depends(get_db), current_user=Depends(get_current_user)
):
    # Current User Info
    username, fullName = current_user.get("sub"), current_user.get("name")

    # checking if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail= 'Class Does Not Exist',
            )
    
    # checking if student exist in the waitlist
    cur = db.execute("SELECT WaitListId FROM WaitingLists WHERE StudentUserName = ? and ClassId= ?", [username,ClassId])
    waitingList = cur.fetchone()
    if not waitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not in Waitlist"
        )
     # updating waitlist positions
    try:
        # 
        cur = db.execute("Select * from WaitingLists where ClassId = ? and WaitListId > ?",[ClassId, waitingList['WaitListId']])
        entries = cur.fetchall()
        for entry in entries:
            db.execute("""
                        UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                        """,
                        [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
        db.execute("DELETE FROM WaitingLists WHERE StudentUserName = ? and ClassId= ?", [username,ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
    db.commit()
    return  {
                "Message": "successfully removed from the waiting list"
            }

"""
Instructors API ENDPOINTS
"""

# View Current Enrollment for Their Classes
@app.get("/instructors/{InstructorId}/classes",status_code=status.HTTP_200_OK)
def retrieve_Instructors_Classes(
    InstructorId: int, db: sqlite3.Connection = Depends(get_db)
):
    
    cur = db.execute("SELECT classname,currentenrollment FROM Classes WHERE InstructorUserName = ?", [InstructorId])
    instructorClasses = cur.fetchall()
    if not instructorClasses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instructor does not have any classes"
        )
    return  {
            "instructorClasses": instructorClasses
            }

# View the current waiting list for the course
@app.get("/classes/{ClassId}/wait-list",status_code=status.HTTP_200_OK)
def retrieve_Classes_WaitingList(
    ClassId: int, db: sqlite3.Connection = Depends(get_db)
):
    # checking if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    
    cur = db.execute("""SELECT 
                     WaitListId,
                     StudentName as student_name,
                     ClassId,
                     WaitingListPos,
                     DateAdded
                     FROM WaitingLists 
                     WHERE ClassId = ?""", [ClassId])
    classesWaitingList = cur.fetchall()
    if not classesWaitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting List doest not exist for this class"
        )
    return  {
            "Total Waitlisted Students": len(classesWaitingList),
            "instructorClassesWaitingList": classesWaitingList
            }

# View Students Who Have Dropped the Class
@app.get("/instructors/{ClassId}/dropped-students",status_code=status.HTTP_200_OK)
def retrieve_instructors_dropped_students(
    ClassId:int, db: sqlite3.Connection = Depends(get_db)
):
    # checking if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail= 'Class Does Not Exist',
            )
    # cur = db.execute("SELECT * FROM Students WHERE StudentId in (SELECT StudentId FROM Enrollments WHERE  ClassId = ? and Dropped = 1)", [ClassId])
    cur = db.execute("""
                     SELECT
                     StudentName as student_name,
                     FROM Enrollments
                     WHERE ClassId = ?
                     AND Dropped = 1
                     """, [ClassId])
    studentsWhoDropped = cur.fetchall()
    if not studentsWhoDropped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No students have dropped this class"
        )
    return  {
            "Dropped Students": studentsWhoDropped
            }

# Drop students administratively
@app.delete("/instructors/{InstructorId}/drop-student/{StudentId}/{ClassId}")
def drop_students_administratively(
    InstructorId:int, StudentId:int, ClassId:int, db: sqlite3.Connection = Depends(get_db)
):
    # checking if instructor exist
    cur = db.execute("Select * from instructors where InstructorId = ?",[InstructorId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Instructor Does Not Exist',
            )
    
    # check if class exists
    cur = db.execute("select CurrentEnrollment, MaxEnrollment, AutomaticEnrollmentFrozen, InstructorId from Classes where ClassId = ?",[ClassId])

    entries = cur.fetchone()
    if(not entries):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class does not exist")
    currentEnrollment, maxEnrollment, automaticEnrollmentFrozen, instructorId = entries

    # checking if InstructorId is valid
    if(InstructorId != instructorId):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the instructor of this class") # Forbidden srtatus code

    # Checking if student was enrolled to the course
    cur = db.execute(
        """
        Select * from Enrollments where ClassId = ? and  StudentId = ? and dropped = 0
        """,
        [ClassId, StudentId])
    entries = cur.fetchone()
    if(not entries):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student is not enrolled in this class") #Not Found 
     
    # dropping the course
    try:
        db.execute("""
                    UPDATE Enrollments SET dropped = 1 where ClassId = ? and StudentId = ?
                    """,
                    [ClassId,StudentId]) 
        db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment-1),ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    
    cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY WaitingListPos ASC",[ClassId])
    entry = cur.fetchone()
    if (not automaticEnrollmentFrozen and (currentEnrollment-1)<maxEnrollment and entry):

        # Enrolling student who is on top of the waitlist
                # Checking if student was enrolled to that course earlier
        cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ?",[ClassId, entry['StudentId']])
        enrollment_entry = cur.fetchone()
        if(enrollment_entry):
            try:
                cur = db.execute("UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentId = ?",[ClassId, entry['StudentId']])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        else: # adding him to the enrollments
            try:
                cur = db.execute(
                """
                INSERT INTO enrollments(StudentId,ClassID,EnrollmentDate)
                VALUES(?, ?, datetime('now')) 
                """,
                [entry['StudentId'], ClassId],
            )
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.commit()
            except sqlite3.IntegrityError as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        # updating waitlist positions
        cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY DateAdded ASC",[ClassId])
        entries = cur.fetchall()
        for entry in entries:
            try:
                db.execute("""
                            UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                            """,
                            [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
                db.commit()
            except sqlite3.IntegrityError as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        db.commit()
        return  {
                "Message": "Student Dropped Successfully"
            }
    
    db.commit()
    return  {
                "Message": "Student Dropped Successfully"
            }


#### Registrar's API Endpoints ####

# Add New Classes and Sections
@app.post("/classes/", status_code=status.HTTP_201_CREATED)
def create_class(
    class_: Class, response: Response, db: sqlite3.Connection = Depends(get_db)
):
    
    # checking if same class and section exist
    cur = db.execute("Select * from classes where ClassName = ? and SectionNumber = ?",[class_.ClassName, class_.SectionNumber])
    entry = cur.fetchone()
    newClassId = 0
    if(entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Already Exist',
            )
    try:
        cur = db.execute(
            """
            INSERT INTO Classes(InstructorUserName, InstructorName,Department,CourseCode,SectionNumber,
            ClassName,CurrentEnrollment,MaxEnrollment,AutomaticEnrollmentFrozen)
            VALUES(?,?, ?, ? , ?, ?, 0, ?, ?) 
            """,
                [class_.InstructorUserName, class_.InstructorName,class_.Department,class_.CourseCode,class_.SectionNumber,
                class_.ClassName,class_.MaxEnrollment,class_.AutomaticEnrollmentFrozen]
            )
        newClassId = cur.lastrowid
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
        status_code=status.HTTP_40, 
        detail={"type": type(e).__name__, "msg": str(e)},
        )
    response.headers["Location"] = f"/classes/{newClassId}"
    return {'status':"Class created successfully"}

# Remove Existing Sections
@app.delete("/classes/{classId}",status_code=status.HTTP_200_OK)
def remove_section(
    classId:int , db: sqlite3.Connection = Depends(get_db)
):
    # checking if class exist
    cur = db.execute("Select ClassId from classes where ClassId = ?",[classId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist'
            )
    try:
        db.executescript(f'''
                         DELETE FROM Classes WHERE ClassId= {classId};
                         DELETE FROM Enrollments WHERE ClassId={classId};
                         DELETE FROM WaitingLists WHERE ClassId= {classId};
                         ''')
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_40, 
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return {'status':"Class Deleted Successfully"}

# Change Instructor for a Section
@app.put("/classes/{ClassId}/instructor",status_code=status.HTTP_200_OK)
def change_instructor(
    ClassId:int, Instructor:UpdateInstructor , db: sqlite3.Connection = Depends(get_db)
):
    # checking if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    # checking if instructor exist
    # cur = db.execute("Select * from instructors where InstructorId = ?",[Instructor.InstructorId])
    # entry = cur.fetchone()
    # if(not entry):
    #     raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail= 'Instructor Does Not Exist',
    #         )
    try:
        db.execute(
            """
            UPDATE Classes SET InstructorUserName = ?, InstructorName = ? where ClassId = ?
            """,
            [Instructor.InstructorUserName, Instructor.InstructorName,ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_40, 
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return {'status':"Instructor Changed Successfully"}

# Freeze automatic enrollment from waiting lists
@app.put("/classes/{ClassId}/freeze-enrollment",status_code=status.HTTP_200_OK)
def freeze_enrollment(
    ClassId:int, db: sqlite3.Connection = Depends(get_db)
):
    # checking if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    if(entry['AutomaticEnrollmentFrozen'] == 1):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Automatic Enrollment Frozen is already ON',
            ) 
    try:
        db.execute(
            """
            UPDATE Classes SET AutomaticEnrollmentFrozen = 1 where ClassId = ?
            """,
            [ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_40, 
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return {'status':"Successfully turned on automatic enrollment frozen"}