import hashlib
import random
import string
from datetime import datetime, timedelta, timezone

from extensions import db
from models import AppConfig, ActivityLog, SystemMetric


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_random_password(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

def set_config(key, value):
    config = AppConfig.query.filter_by(key=key).first()
    if config:
        config.value = str(value)
    else:
        config = AppConfig(key=key, value=str(value))
    db.session.add(config)

def log_activity(level, message):
    try:
        log = ActivityLog(level=level, message=message)
        db.session.add(log)
        # Keep only the last 20 logs
        logs_to_delete = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).offset(20).all()
        for log_del in logs_to_delete:
            db.session.delete(log_del)
        db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
        db.session.rollback()

def calculate_growth(metric_key, current_value):
    last_week = datetime.now(timezone.utc).date() - timedelta(days=7)
    last_metric = SystemMetric.query.filter_by(key=metric_key).filter(SystemMetric.date <= last_week).order_by(SystemMetric.date.desc()).first()
    if last_metric and last_metric.value > 0:
        return round(((current_value - last_metric.value) / last_metric.value) * 100, 1)
    return 0

