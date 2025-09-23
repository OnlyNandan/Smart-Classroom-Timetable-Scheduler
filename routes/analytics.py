from flask import Blueprint, session, redirect, url_for

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@analytics_bp.route('/')
def analytics_page():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return "<h1>Analytics Page</h1>"
