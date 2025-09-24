# 🎓 Smart Classroom Timetable Scheduler

A comprehensive, AI-powered timetable scheduling system designed for educational institutions. This application provides intelligent timetable generation, real-time dashboard analytics, and complete management of academic resources.

## 🌟 Features

### 🧠 **Intelligent Timetable Generation**
- **Hybrid Algorithm**: Combines Greedy + Backtracking + Genetic Algorithm + Constraint Satisfaction
- **Real-time Accuracy**: Dynamic accuracy calculation based on actual algorithm performance
- **Conflict Resolution**: Automatic detection and resolution of scheduling conflicts
- **Flexible Scheduling**: Supports both school and college modes
- **Dynamic Resource Assignment**: Finds alternative teachers/classrooms when primary choices are unavailable

### 📊 **Real-time Dashboard**
- **Live Metrics**: Real-time updates of students, teachers, classes, and subjects
- **Performance Analytics**: Schedule accuracy and generation time tracking
- **Animated Updates**: Smooth value transitions with professional UI
- **Growth Tracking**: Historical data analysis with percentage changes

### 🏫 **Multi-Mode Support**
- **School Mode**: Grade-based structure with subjects and streams
- **College Mode**: Semester-department structure with courses and credits
- **Flexible Configuration**: Easy switching between modes

### 👥 **Comprehensive User Management**
- **Role-based Access**: Admin, Teacher, and Student roles
- **Secure Authentication**: Password hashing and session management
- **Bulk Import/Export**: CSV-based data management
- **Teacher Assignment**: Flexible subject/course assignment system

### 🏢 **Resource Management**
- **Classroom Management**: Capacity, features, and availability tracking
- **Section Management**: Student grouping and capacity management
- **Subject/Course Management**: Comprehensive academic content management
- **Exam Scheduling**: Integrated exam management system

### ♿ **Accessibility Features**
- **High Contrast Mode**: Enhanced visibility for visually impaired users
- **Dyslexia-friendly Fonts**: Easy-to-read typography
- **Reduced Motion**: Minimized animations for sensitive users
- **Voice Commands**: Hands-free navigation support
- **Keyboard Navigation**: Full keyboard accessibility

### 🎨 **Modern UI/UX**
- **Glass Morphism Design**: Beautiful, modern interface
- **Dark Mode**: Professional dark theme
- **Responsive Design**: Works on all device sizes
- **Real-time Indicators**: Live status updates
- **Smooth Animations**: Professional transitions and effects

## 🏗️ **System Architecture**

### **Backend (Flask)**
```
app.py                 # Main application entry point
├── models.py          # Database models and relationships
├── config.py          # Configuration management
├── extensions.py      # Flask extensions setup
├── utils.py           # Utility functions and helpers
└── routes/            # API endpoints and business logic
    ├── main.py        # Authentication and dashboard
    ├── timetable.py   # Timetable generation and management
    ├── staff.py       # Teacher management
    ├── sections.py    # Student section management
    ├── subjects.py    # Subject/course management
    ├── classrooms.py  # Classroom management
    ├── exams.py       # Exam scheduling
    ├── analytics.py   # Analytics and reporting
    ├── api.py         # REST API endpoints
    └── structure.py   # Academic structure management
```

### **Frontend (Vue.js + Tailwind CSS)**
```
templates/
├── base.html          # Base template with navigation
├── dashboard.html     # Real-time dashboard
├── timetable.html     # Timetable viewing and generation
├── staff.html         # Teacher management interface
├── sections.html      # Student section management
├── subjects.html      # Subject/course management
├── classrooms.html    # Classroom management
├── exams.html         # Exam scheduling interface
└── setup.html         # Initial setup wizard
```

### **Algorithm Engine**
```
advanced_timetable_generator.py
├── TimetableGenerator     # Main algorithm orchestrator
├── ConstraintManager      # Hard and soft constraint validation
├── GeneticOperators       # Genetic algorithm operations
├── Activity               # Timetable activity representation
└── TimeSlot              # Time slot management
```

## 🗄️ **Database Schema**

### **Core Models**
- **User**: Authentication and role management
- **Teacher**: Faculty information and constraints
- **Student**: Student records and section assignment
- **StudentSection**: Academic sections/groups
- **Classroom**: Physical classroom resources
- **TimetableEntry**: Individual class scheduling

### **Academic Structure**
- **School Mode**: SchoolGroup → Grade → Stream → Subject
- **College Mode**: Semester → Department → Course
- **Flexible Relationships**: Many-to-many associations

### **System Models**
- **AppConfig**: Application configuration
- **ActivityLog**: System activity tracking
- **SystemMetric**: Performance metrics
- **Exam/ExamSeating**: Examination management

## 🚀 **Installation & Setup**

### **Prerequisites**
- Python 3.8+
- MySQL 5.7+ or SQLite
- pip package manager

### **1. Clone Repository**
```bash
git clone https://github.com/yourusername/smart-classroom-timetable-scheduler.git
cd smart-classroom-timetable-scheduler
```

### **2. Create Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### **3. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **4. Environment Configuration**
Create a `.env` file in the root directory:
```env
DATABASE_URL=mysql://username:password@localhost/timetabledb
# OR for SQLite:
# DATABASE_URL=sqlite:///timetable.db

SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

### **5. Database Setup**
```bash
# Initialize with sample data
python init_db_realistic.py

# OR start fresh
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### **6. Run Application**
```bash
python app.py
```

The application will be available at `http://localhost:8000`

## 📊 **Default Login Credentials**

After running `init_db_realistic.py`:

- **Admin**: `admin` / `admin123`
- **Teachers**: `teacher01` to `teacher50` / `teacher123`
- **Students**: `student001` to `student500` / `student123`

## 🎯 **Usage Guide**

### **Initial Setup**
1. Access the application at `http://localhost:8000`
2. Complete the setup wizard (if first time)
3. Configure working days, time slots, and breaks
4. Set up academic structure (semesters/departments or grades/streams)

### **Managing Resources**
1. **Teachers**: Add faculty members and assign subjects/courses
2. **Students**: Import student data and assign to sections
3. **Classrooms**: Configure room capacities and features
4. **Subjects/Courses**: Set up academic content with credits/hours

### **Generating Timetables**
1. Navigate to the Timetable section
2. Click "Generate Timetable"
3. Monitor real-time progress
4. Review generated schedule and accuracy metrics
5. Make adjustments if needed

### **Viewing Analytics**
1. Dashboard shows real-time metrics
2. Performance tracking for accuracy and generation time
3. Growth analysis and trend monitoring
4. System health indicators

## 🔧 **Configuration Options**

### **Timetable Settings**
- **Working Days**: Monday-Friday (configurable)
- **Time Slots**: 9:00 AM - 5:00 PM (adjustable)
- **Period Duration**: 60 minutes (customizable)
- **Breaks**: Lunch break and other scheduled breaks
- **Max Classes per Day**: 8 classes (configurable)

### **Algorithm Parameters**
- **Population Size**: 30-80 (adaptive based on problem size)
- **Generations**: 15-25 (adaptive)
- **Mutation Rate**: 0.1-0.15 (adaptive)
- **Crossover Rate**: 0.7-0.9 (adaptive)

### **Accessibility Settings**
- **High Contrast**: Enhanced visibility mode
- **Dyslexia-friendly**: Easy reading fonts
- **Reduced Motion**: Minimized animations
- **Voice Commands**: Hands-free navigation

## 📈 **Performance Metrics**

### **Real-time Accuracy Calculation**
```
Accuracy = (Assignment Success Rate × 0.6) + (Algorithm Fitness Score × 0.4)
```

### **Generation Time Tracking**
- Measures actual algorithm execution time
- Tracks from start to finish
- Displays in seconds with decimal precision

### **System Metrics**
- **Uptime**: System availability percentage
- **Success Rate**: Timetable generation success rate
- **Resource Utilization**: Teacher and classroom usage
- **Conflict Resolution**: Automatic conflict detection and resolution

## 🛠️ **API Endpoints**

### **Authentication**
- `POST /login` - User authentication
- `POST /logout` - User logout
- `GET /dashboard` - Dashboard data

### **Timetable Management**
- `POST /api/generate_timetable` - Generate new timetable
- `GET /api/timetable_data` - Retrieve timetable data
- `GET /api/dashboard-stats` - Real-time dashboard metrics

### **Resource Management**
- `GET/POST /api/teachers` - Teacher management
- `GET/POST /api/sections` - Section management
- `GET/POST /api/classrooms` - Classroom management
- `GET/POST /api/subjects` - Subject management

## 🔒 **Security Features**

- **Password Hashing**: Secure password storage using Werkzeug
- **Session Management**: Secure session handling
- **Role-based Access**: Granular permission system
- **Input Validation**: Comprehensive data validation
- **SQL Injection Protection**: Parameterized queries

## 🧪 **Testing**

### **Run Database Initialization**
```bash
python init_db_realistic.py
```

### **Test Timetable Generation**
1. Login as admin
2. Navigate to Timetable section
3. Click "Generate Timetable"
4. Monitor real-time progress
5. Verify accuracy metrics

### **Test Real-time Updates**
1. Open dashboard
2. Generate new timetable
3. Observe real-time metric updates
4. Verify accuracy and timing changes

## 🐛 **Troubleshooting**

### **Common Issues**

**Database Connection Error**
```bash
# Check database URL in .env file
# Ensure MySQL is running
# Verify credentials
```

**Import Errors**
```bash
# Ensure virtual environment is activated
# Install all dependencies: pip install -r requirements.txt
# Check Python version compatibility
```

**Timetable Generation Fails**
```bash
# Check teacher-subject assignments
# Verify classroom availability
# Ensure sufficient time slots
```

**Real-time Updates Not Working**
```bash
# Check browser console for JavaScript errors
# Verify API endpoints are accessible
# Check network connectivity
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 **License**

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 **Acknowledgments**

- Flask framework for the web backend
- Vue.js for frontend interactivity
- Tailwind CSS for styling
- SQLAlchemy for database management
- Faker for sample data generation

## 📞 **Support**

For support and questions:
- Create an issue in the GitHub repository
- Check the troubleshooting section
- Review the documentation

---

**Built with ❤️ for educational institutions worldwide**