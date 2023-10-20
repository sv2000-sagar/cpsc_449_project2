import sqlite3
import datetime

def create_database():
    conn = sqlite3.connect("pro1.db")  
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Instructors (
            InstructorId INTEGER PRIMARY KEY,
            FirstName TEXT,
            LastName TEXT,
            Email TEXT
        )
    ''')
    conn.execute("insert into Instructors(FirstName,LastName,Email) values('Jane','Doe','abc@gmail.com');")
    conn.execute("insert into Instructors(FirstName,LastName,Email) values('John','Doe','123@gmail.com');")
    conn.execute("insert into Instructors(FirstName,LastName,Email) values('Prof','Avery','profavery@gmail.com');")


    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Classes (
            ClassId INTEGER PRIMARY KEY,
            InstructorId INT REFERENCES Instructors(InstructorId),
            Department TEXT,
            CourseCode TEXT,
            SectionNumber INTEGER,
            ClassName TEXT,
            CurrentEnrollment INTEGER,
            MaxEnrollment INTEGER,
            AutomaticEnrollmentFrozen INTEGER DEFAULT 0
        )
    ''')
    conn.execute("insert into Classes(Department,CourseCode,SectionNumber,ClassName,InstructorID,\
                 CurrentEnrollment,MaxEnrollment) values('Computer Science','CPSC449',1,\
                 'Web-backend Engineering',3,34,40);")
    conn.execute("insert into Classes(Department,CourseCode,SectionNumber,ClassName,InstructorID,\
                 CurrentEnrollment,MaxEnrollment) values('Computer Science','CPSC541',1,\
                 'SE-I',1,0,5);")
    conn.execute("insert into Classes(Department,CourseCode,SectionNumber,ClassName,InstructorID,\
                 CurrentEnrollment,MaxEnrollment) values('Computer Science','CPSC544',2,\
                 'SE-II',2,5,5);")
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Students (
            StudentId INTEGER PRIMARY KEY,
            FirstName TEXT,
            LastName TEXT,
            Email TEXT
        )
    ''')
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student1','Doe1','xyz1@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student2','Doe2','xyz2@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student3','Doe3','xyz3@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student4','Doe4','xyz4@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student5','Doe5','xyz5@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student6','Doe6','xyz6@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student7','Doe7','xyz7@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student8','Doe8','xyz8@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student9','Doe9','xyz9@gmail.com');")
    conn.execute("insert into Students(FirstName,LastName,Email) values('Student10','Doe10','xyz10@gmail.com');")


    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Enrollments (
            EnrollmentId INTEGER PRIMARY KEY,
            StudentId INT REFERENCES Students(StudentId),
            ClassId INT REFERENCES Classes(ClassId),
            EnrollmentDate TEXT,
            Dropped INT DEFAULT 0
        )
    ''')
    
    # conn.execute("insert into Enrollments(StudentID,ClassID,EnrollmentDate) values(1,1,datetime('now'));",)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS WaitingLists (
            WaitListId INTEGER PRIMARY KEY,
            StudentId INT REFERENCES Students(StudentId),
            ClassId INT REFERENCES Classes(ClassId),
            WaitingListPos INT,
            DateAdded TEXT
        )
    ''')
    
    # conn.execute("insert into waitingLists(StudentID,ClassID,WaitingListPos,DateAdded) values(1,1,1,datetime('now'));",)

    

    conn.commit()
    conn.close()

create_database()


# conn = sqlite3.connect("pro1.db")  
# cursor = conn.cursor()
# conn.execute("insert into Classes(Department,CourseCode,SectionNumber,ClassName,InstructorID,\
#               CurrentEnrollment,MaxEnrollment) values('Computer Science','CPSC541',1,\
#             'Advance Software Process',2,40,40);")
# conn.commit()
# conn.close()