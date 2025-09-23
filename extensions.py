# This file is used to instantiate extensions like SQLAlchemy
# to avoid circular import issues.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
