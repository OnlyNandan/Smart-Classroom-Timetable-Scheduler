# Smart Classroom Timetable Scheduler AI

## 1. Project Overview
Smart Classroom Timetable Scheduler AI is a web-based, intelligent timetable scheduling application designed for educational institutions. It leverages a **Genetic Algorithm** to automatically generate optimized, conflict-free timetables.  

The platform provides a modern, sleek **"glass" UI** for administrators to manage master data (courses, teachers, rooms) and for teachers to view their personalized schedules.

---

## 2. Core Features

- **Admin Dashboard**  
  Central hub for administrators to perform CRUD operations on courses, teachers, classrooms, and student groups.

- **Genetic Algorithm**  
  Automatically generates conflict-free timetables by satisfying hard constraints (e.g., no two classes in the same room at the same time) and minimizing penalties for soft constraints (e.g., minimizing gaps).

- **Role-Based Access Control**  
  - **Admin:** Full control over master data and timetable generation.  
  - **Teacher:** View-only access to their personal schedule.

- **Sleek Glass UI**  
  Modern, responsive interface built with **Tailwind CSS**, featuring a frosted glass aesthetic and a **dark/light mode toggle**.

- **Dynamic Timetable View**  
  Displays generated schedules in a clean, easy-to-read **grid/calendar format**.

- **Analytics Dashboard**  
  Visualizes key metrics like **room utilization** and **faculty workload** using **Chart.js**.

---

## 3. Tech Stack

- **Backend:** Python, Flask  
- **Database:** MySQL  
- **ORM:** Flask-SQLAlchemy  
- **Scheduling Algorithm:** Genetic Algorithm implemented in Python with Pandas  
- **Frontend:** HTML, Tailwind CSS, JavaScript  
- **Charting:** Chart.js  

---

## 4. Setup and Installation

### Prerequisites
- Python 3.8+  
- A running MySQL server instance  

### Step-by-Step Guide

#### 1. Clone the Repository
> Ensure all project files are in a single directory.

#### 2. Create and Activate a Virtual Environment
**Windows**
```bash
python -m venv venv
.\venv\Scripts\activate

```
**Mac**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Install Dependencies**
```bash
pip install -r requirements.txt
```

Set Up the MySQL Database

Log in to your MySQL server.

Create a new database for the project. The application is configured to use the name timetabledb.

CREATE DATABASE timetabledb;

Configure the Database Connection

Open the app.py file.

Verify that the SQLALCHEMY_DATABASE_URI string matches your MySQL credentials (username, password, host, and database name). The default is set to:

'mysql+pymysql://root:secretpassword@localhost/timetabledb'

Initialize the Database
Run the init_db.py script once to create all the necessary tables and populate the database with initial sample data (users, courses, teachers, etc.).

python init_db.py

This will also create a default admin user.

Run the Flask Application
Start the development server.

python app.py

The application will now be running at http://127.0.0.1:5000.

5. How to Use the Application
Log In

Navigate to http://127.0.0.1:5000 in your web browser.

Log in with the default administrator credentials:

Username: admin

Password: admin

Manage Master Data

Use the sidebar to navigate to the Courses, Teachers, Classrooms, and Student Groups pages.

Add the necessary data for your institution. The application comes with pre-populated sample data.

Generate a Timetable

Navigate back to the Dashboard.

Click the "Generate New Timetable" button.

Wait for the Genetic Algorithm to finish processing. You can monitor the progress in the terminal where the Flask app is running.

You will see a success message on the dashboard upon completion.

View the Timetable

Click on the "Timetable" link in the sidebar to see the newly generated schedule in a grid view.
