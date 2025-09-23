import os
import json
from datetime import datetime, timezone
from flask import Flask, request, redirect, url_for, g

from config import Config
from extensions import db
from models import AppConfig, User, Subject, Course, TimetableEntry, SystemMetric

def create_app(config_class=Config):
    # --- App Initialization ---
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Initialize Extensions ---
    db.init_app(app)

    # --- Import and Register Blueprints ---
    from routes.main import main_bp
    from routes.structure import structure_bp
    from routes.subjects import subjects_bp
    from routes.staff import staff_bp
    from routes.classrooms import classrooms_bp
    from routes.sections import sections_bp
    from routes.timetable import timetable_bp
    from routes.analytics import analytics_bp
    from routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(structure_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(classrooms_bp)
    app.register_blueprint(sections_bp)
    app.register_blueprint(timetable_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(api_bp)

    # --- Application Hooks & Context Processors ---
    @app.before_request
    def check_setup():
        # Allow static files and the setup page to be accessed without checks
        if request.endpoint and ('static' in request.endpoint or 'main.setup' in request.endpoint):
            return
        try:
            # If setup is not complete, redirect to the setup page
            if not AppConfig.query.filter_by(key='setup_complete', value='true').first():
                return redirect(url_for('main.setup'))
            # Load the application mode (school/college) into the global context `g`
            g.app_mode = AppConfig.query.filter_by(key='app_mode').first().value
        except Exception as e:
            # If the database/tables don't exist, an error will occur. Redirect to setup.
            print(f"Redirecting to setup due to error: {e}")
            return redirect(url_for('main.setup'))

    @app.context_processor
    def inject_global_vars():
        # This makes 'institute_name' available in all templates
        try:
            config = AppConfig.query.filter_by(key='institute_name').first()
            return {'institute_name': config.value if config else 'Scheduler AI'}
        except Exception:
            return {'institute_name': 'Scheduler AI'}

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()
        
        # Log system metrics once per day
        today = datetime.now(timezone.utc).date()
        if not SystemMetric.query.filter_by(date=today).first():
             db.session.add(SystemMetric(key='total_students', value=User.query.filter_by(role='student').count()))
             db.session.add(SystemMetric(key='total_teachers', value=User.query.filter_by(role='teacher').count()))
             total_subjects = Subject.query.count() + Course.query.count()
             db.session.add(SystemMetric(key='total_subjects', value=total_subjects))
             db.session.add(SystemMetric(key='classes_scheduled', value=TimetableEntry.query.count()))
             db.session.commit()
             
    app.run(debug=True)
