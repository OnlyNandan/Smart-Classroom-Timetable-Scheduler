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
- **Database:** SQLite (default) / MySQL / PostgreSQL  
- **ORM:** Flask-SQLAlchemy  
- **Scheduling Algorithm:** Gemini AI API for intelligent timetable generation  
- **Frontend:** HTML, Tailwind CSS, JavaScript  
- **Charting:** Chart.js  
- **AI Integration:** Google Gemini API  

---

## 4. Setup and Installation

### Prerequisites
- Python 3.8+  
- Google Gemini API Key (for AI-powered timetable generation)
- Optional: MySQL/PostgreSQL server (SQLite is used by default)  

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

#### 3. Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///timetable.db

# Gemini AI API Configuration
GEMINI_API_KEY=your-gemini-api-key-here

# Optional: Database Configuration (if using MySQL/PostgreSQL)
# DATABASE_URL=mysql://username:password@localhost/database_name
# DATABASE_URL=postgresql://username:password@localhost/database_name
```

**Getting a Gemini API Key:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create a new API key
4. Copy the key and add it to your `.env` file

#### 4. Database Setup

The application uses SQLite by default, which requires no additional setup. If you prefer MySQL or PostgreSQL:

**For MySQL:**
1. Create a database: `CREATE DATABASE timetabledb;`
2. Update the `DATABASE_URL` in your `.env` file
3. Install PyMySQL: `pip install PyMySQL`

**For PostgreSQL:**
1. Create a database: `CREATE DATABASE timetabledb;`
2. Update the `DATABASE_URL` in your `.env` file
3. Install psycopg2: `pip install psycopg2-binary`

#### 5. Run the Application

Start the development server:

```bash
python app.py
```

The application will be running at http://127.0.0.1:5000.

---

## 5. How to Use the Application

### Initial Setup
1. Navigate to http://127.0.0.1:5000
2. Complete the initial setup wizard
3. Configure your institution type (School/College)
4. Set up basic timetable settings (working days, periods, etc.)

### Managing Data
1. **Structure**: Set up grades/streams (school) or semesters/departments (college)
2. **Subjects/Courses**: Add subjects or courses with their requirements
3. **Staff**: Add teachers and assign them to subjects/courses
4. **Sections**: Create student sections/classes
5. **Classrooms**: Add available classrooms and their features

### Generating Timetables
1. Navigate to the **Timetable** page
2. Click **"Generate Timetable"** button
3. The AI will analyze all constraints and generate an optimal schedule
4. View the generated timetable in the interactive grid

### Features
- **Multi-view Support**: View by section, teacher, or classroom
- **Filtering**: Filter timetables by specific criteria
- **Export**: Export timetables for printing or sharing
- **Real-time Updates**: See changes immediately
- **Conflict Detection**: Automatic detection of scheduling conflicts

---

## 6. Key Features

### AI-Powered Generation
- Uses Google Gemini AI for intelligent timetable optimization
- Considers teacher availability, classroom capacity, and subject requirements
- Minimizes conflicts and maximizes efficiency

### Flexible Institution Support
- **School Mode**: Grades, Streams, Subjects with weekly hours
- **College Mode**: Semesters, Departments, Courses with credits
- Automatic adaptation based on institution type

### Modern Interface
- Responsive design that works on all devices
- Glass-morphism UI with smooth animations
- Dark/light mode support
- Intuitive navigation and controls

### Comprehensive Management
- Full CRUD operations for all entities
- Bulk operations and data validation
- Activity logging and audit trails
- Export capabilities for reports
