# To do list:
# defaults, 
# cancel leave request, 
# leave calendar not working, 
# layout of requests, 
# non compulsory reasons, 
# remaining leave column for pending requests, 
# default text for approve comment of 'Sure! Please add this to your Outlook calendar. You now have XXX unbooked days to take before the end of the year', 
# backup/recover database, 
# dashboards,
# compulsory addition of at least one work package per project and at least one task per work package 
# task time budgets and budget remaining,  
# requirements
# deployment on rpi
# users' comments on leave request history
# Bank holidays?
# 'Approved by' and timestamp
# Add to calendar option upon approval
# Email confirmation
# Error messages seem to hang over and only pop up on login screen
# Option to toggle weekends for sitches where users normally work weekends

#imports
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from functools import wraps
import os
import calendar  # For month names
from sqlalchemy.orm import joinedload
from calendar import HTMLCalendar
from waitress import serve




app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')  # Store secret key in environment variable
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timesheet_app.db'  # Using SQLite database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'



##################################################
# Data Models                                    #
##################################################


class User(UserMixin, db.Model):
    """User model representing application users."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='user')
    status = db.Column(db.String(10), nullable=False, default='active')

    timesheets = db.relationship('Timesheet', backref='user', lazy=True)
    leave_requests = db.relationship('LeaveRequest', backref='user', lazy=True)
    leave_balance = db.relationship('LeaveBalance', backref='user', uselist=False, lazy=True)

    def check_password(self, password):
        """Check hashed password."""
        return check_password_hash(self.password_hash, password)

class Project(db.Model):
    """Project model representing projects."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)

    work_packages = db.relationship('WorkPackage', backref='project', lazy=True)

class WorkPackage(db.Model):
    """WorkPackage model representing work packages under projects."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

    tasks = db.relationship('Task', backref='work_package', lazy=True)

class Task(db.Model):
    """Task model representing tasks under work packages."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    work_package_id = db.Column(db.Integer, db.ForeignKey('work_package.id'), nullable=False)

    timesheets = db.relationship('Timesheet', backref='task', lazy=True)

class Timesheet(db.Model):
    """Timesheet model representing timesheet entries."""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)

class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10), nullable=False, default='Morning')  # 'Morning' or 'Afternoon'
    end_date = db.Column(db.Date, nullable=False)
    end_time = db.Column(db.String(10), nullable=False, default='Afternoon')  # 'Morning' or 'Afternoon'
    leave_type = db.Column(db.String(50), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    admin_comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
       
    def calculate_duration(self):
        return calculate_leave_days(
            self.start_date, self.start_time,
            self.end_date, self.end_time
        )

    def get_start_time_display(self):
        return self.start_time

    def get_end_time_display(self):
        return self.end_time

class LeaveBalance(db.Model):
    """Model to represent a user's leave balance."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    total_leave = db.Column(db.Float, nullable=False, default=20.0)  # Default annual leave entitlement
    used_leave = db.Column(db.Float, nullable=False, default=0.0)

class DummyData(db.Model):
    """Simple table containing dummy records used for testing."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=True)

##################################################
# Helper functions                               #
##################################################

#custom calendar
class TimesheetCalendar(HTMLCalendar):
    """Custom calendar to display timesheets."""
    def __init__(self, filled_dates, today, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filled_dates = filled_dates
        self.today = today

    def formatday(self, day, weekday):
        """Format a day as a table cell."""
        if day == 0:
            return '<td class="noday">&nbsp;</td>'
        else:
            date_obj = date(self.theyear, self.themonth, day)
            css_classes = []
            if date_obj == self.today:
                css_classes.append('today')
            if date_obj in self.filled_dates:
                css_classes.append('filled-date')
            css_class_str = ' '.join(css_classes)
            date_str = date_obj.strftime('%Y-%m-%d')
            return f'<td class="{css_class_str}"><a href="{url_for("timesheet_for_day", date_str=date_str)}">{day}</a></td>'

    def formatweek(self, theweek):
        """Format a week as a table row."""
        s = ''.join(self.formatday(d, wd) for (d, wd) in theweek)
        return f'<tr>{s}</tr>'

    def formatmonthname(self, theyear, themonth, withyear=True):
        """Format the month's name as a table row."""
        month_name = calendar.month_name[themonth]
        if withyear:
            s = f'{month_name} {theyear}'
        else:
            s = f'{month_name}'
        return f'<tr><th colspan="7" class="month-name">{s}</th></tr>'

    def formatmonth(self, theyear, themonth, withyear=True):
        """Format a month as a table."""
        self.theyear = theyear
        self.themonth = themonth
        v = []
        a = v.append
        a('<table class="calendar">')
        a(self.formatmonthname(theyear, themonth, withyear=withyear))
        a(self.formatweekheader())
        for week in self.monthdays2calendar(theyear, themonth):
            a(self.formatweek(week))
        a('</table>')
        return ''.join(v)

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login."""
    return User.query.get(int(user_id))

# Custom Decorators
def admin_required(f):
    """Decorator to restrict access to admin users."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def init_dummy_data():
    """Create a few dummy records for testing if table is empty."""
    if DummyData.query.count() == 0:
        examples = [
            DummyData(name='Example 1', value='First dummy value'),
            DummyData(name='Example 2', value='Second dummy value'),
            DummyData(name='Example 3', value='Third dummy value'),
        ]
        db.session.bulk_save_objects(examples)
        db.session.commit()

def init_example_projects():
    """Populate the database with example projects, work packages and tasks."""
    if Project.query.count() == 0:
        sample_data = [
            {
                'name': 'Project Alpha',
                'description': 'New website launch',
                'packages': [
                    {
                        'name': 'Planning',
                        'tasks': ['Requirements Gathering', 'Timeline Setup']
                    },
                    {
                        'name': 'Implementation',
                        'tasks': ['Frontend Development', 'Backend Integration']
                    }
                ]
            },
            {
                'name': 'Project Beta',
                'description': 'Mobile app development',
                'packages': [
                    {
                        'name': 'Design',
                        'tasks': ['UI Mockups', 'UX Flow']
                    },
                    {
                        'name': 'Testing',
                        'tasks': ['Unit Tests', 'User Acceptance']
                    }
                ]
            },
            {
                'name': 'Project Gamma',
                'description': 'Data analysis pipeline',
                'packages': [
                    {
                        'name': 'Data Collection',
                        'tasks': ['Gather Source Data', 'Clean Raw Data']
                    },
                    {
                        'name': 'Modeling',
                        'tasks': ['Build Models', 'Evaluate Results']
                    }
                ]
            }
        ]

        for proj in sample_data:
            project = Project(name=proj['name'], description=proj['description'])
            db.session.add(project)
            db.session.flush()  # Ensure project.id is available

            for pkg in proj['packages']:
                work_package = WorkPackage(name=pkg['name'], project_id=project.id)
                db.session.add(work_package)
                db.session.flush()
                for task_name in pkg['tasks']:
                    task = Task(name=task_name, work_package_id=work_package.id)
                    db.session.add(task)

        db.session.commit()

# Helper function to calculate the leave days, accounting for half days.
def calculate_leave_days(start_date, start_time, end_date, end_time):
    from datetime import timedelta

    # Validation: Ensure start date is not after end date
    if start_date > end_date:
        raise ValueError('Start date cannot be after end date.')

    # Calculate total days between start and end dates, inclusive
    delta_days = (end_date - start_date).days + 1

    # Generate list of dates between start and end dates
    date_list = [start_date + timedelta(days=i) for i in range(delta_days)]

    # Initialize total leave days
    total_leave_days = 0.0

    for single_date in date_list:
        if single_date.weekday() >= 5:
            # Skip weekends (Saturday=5, Sunday=6)
            continue

        if single_date == start_date:
            # First day
            if start_time == 'Morning' and (start_date != end_date or end_time == 'Afternoon'):
                # Taking the whole day or morning only
                total_leave_days += 1.0
            elif start_time == 'Afternoon':
                total_leave_days += 0.5
        elif single_date == end_date:
            # Last day
            if end_time == 'Afternoon':
                total_leave_days += 1.0
            elif end_time == 'Morning':
                total_leave_days += 0.5
        else:
            # Middle days are full days
            total_leave_days += 1.0

    # Adjust for the case when start and end date are the same
    if start_date == end_date:
        if start_time == 'Morning' and end_time == 'Afternoon':
            total_leave_days = 1.0
        elif start_time == 'Morning' and end_time == 'Morning':
            total_leave_days = 0.5
        elif start_time == 'Afternoon' and end_time == 'Afternoon':
            total_leave_days = 0.5
        else:
            # Invalid case: start in the afternoon and end in the morning
            raise ValueError('Invalid time selection on the same day.')

    return total_leave_days


##################################################
# Routes                                         #
##################################################

@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Authenticate user
        user = User.query.filter_by(username=username, status='active').first()
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout."""
    logout_user()
    return redirect(url_for('index'))

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    """User dashboard with simple statistics."""
    today = date.today()
    # Sum hours for the current month for the logged in user
    total_hours_month = db.session.query(db.func.sum(Timesheet.hours)).filter(
        Timesheet.user_id == current_user.id,
        db.extract('year', Timesheet.date) == today.year,
        db.extract('month', Timesheet.date) == today.month
    ).scalar() or 0

    # Get remaining leave balance
    leave_balance = LeaveBalance.query.filter_by(user_id=current_user.id).first()
    remaining_leave = 0
    if leave_balance:
        remaining_leave = leave_balance.total_leave - leave_balance.used_leave

    # Count upcoming approved leave requests
    upcoming_leave = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'Approved',
        LeaveRequest.start_date >= today
    ).count()

    month_year = today.strftime('%B %Y')

    return render_template(
        'user_dashboard.html',
        total_hours_month=total_hours_month,
        remaining_leave=remaining_leave,
        upcoming_leave=upcoming_leave,
        month_year=month_year
    )

@app.route('/user_dashboard/timesheets', methods=['GET'])
@app.route('/user_dashboard/timesheets/<int:year>/<int:month>', methods=['GET'])
@login_required
def timesheets_page(year=None, month=None):
    """Timesheets calendar page."""
    today = date.today()

    if year is None or month is None:
        current_year = today.year
        current_month = today.month
    else:
        current_year = year
        current_month = month

    # Calculate previous and next months for navigation
    prev_year, prev_month = (current_year, current_month - 1) if current_month > 1 else (current_year - 1, 12)
    next_year, next_month = (current_year, current_month + 1) if current_month < 12 else (current_year + 1, 1)

    # Get dates with timesheet entries for the current user
    timesheets = Timesheet.query.filter_by(user_id=current_user.id).all()
    filled_dates = set([t.date for t in timesheets])

    # Instantiate the custom calendar
    cal = TimesheetCalendar(filled_dates=filled_dates, today=today)
    calendar_html = cal.formatmonth(current_year, current_month)

    return render_template('timesheets_calendar.html',
                           calendar_html=calendar_html,
                           current_year=current_year,
                           current_month=current_month,
                           prev_year=prev_year,
                           prev_month=prev_month,
                           next_year=next_year,
                           next_month=next_month)

@app.route('/user_dashboard/timesheets/<date_str>', methods=['GET', 'POST'])
@login_required
def timesheet_for_day(date_str):
    """Timesheet entry for a specific day."""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

    if request.method == 'POST':
        # Get form data
        task_id = int(request.form['task_id'])
        hours = float(request.form['hours'])
        description = request.form['description']

        # Create new timesheet entry
        new_entry = Timesheet(user_id=current_user.id, task_id=task_id, date=date_obj, hours=hours, description=description)
        db.session.add(new_entry)
        db.session.commit()

        flash('Timesheet entry added successfully', 'success')
        return redirect(url_for('timesheet_for_day', date_str=date_str))

    # Get timesheets for the day
    timesheets = Timesheet.query.filter_by(user_id=current_user.id, date=date_obj).all()

    # Get projects for dropdowns
    projects = Project.query.all()

    return render_template('timesheet_day.html', timesheets=timesheets, date=date_str, projects=projects)

@app.route('/get_work_packages/<int:project_id>')
@login_required
def get_work_packages(project_id):
    """AJAX endpoint to get work packages for a project."""
    work_packages = WorkPackage.query.filter_by(project_id=project_id).all()
    work_package_list = [{'id': wp.id, 'name': wp.name} for wp in work_packages]
    return jsonify(work_package_list)

@app.route('/get_tasks/<int:work_package_id>')
@login_required
def get_tasks(work_package_id):
    """AJAX endpoint to get tasks for a work package."""
    tasks = Task.query.filter_by(work_package_id=work_package_id).all()
    task_list = [{'id': t.id, 'name': t.name} for t in tasks]
    return jsonify(task_list)

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard showing high level statistics."""
    # Basic counts for quick overview
    user_count = User.query.count()
    project_count = Project.query.count()
    total_hours = db.session.query(db.func.sum(Timesheet.hours)).scalar() or 0
    pending_leave_count = LeaveRequest.query.filter_by(status='Pending').count()

    return render_template(
        'admin_dashboard.html',
        user_count=user_count,
        project_count=project_count,
        total_hours=total_hours,
        pending_leave_count=pending_leave_count
    )


@app.route('/admin_dashboard/reports')
@admin_required
def admin_reports():
    """Aggregated reports providing managerial insights."""
    # Total hours logged per user
    user_hours = db.session.query(
        User.id,
        User.username,
        db.func.sum(Timesheet.hours)
    ).join(Timesheet).group_by(User.id).all()

    # Total hours logged per project
    project_hours = db.session.query(
        Project.id,
        Project.name,
        db.func.sum(Timesheet.hours)
    ).join(WorkPackage).join(Task).join(Timesheet).group_by(Project.id).all()

    return render_template(
        'reports.html',
        user_hours=user_hours,
        project_hours=project_hours
    )

@app.route('/admin_dashboard/reports/user/<int:user_id>')
@admin_required
def report_user_detail(user_id):
    """Return hours for a user broken down by project, work package and task."""
    # Aggregate hours by project/work package/task for the user
    entries = (
        db.session.query(
            Project.name.label('project'),
            WorkPackage.name.label('work_package'),
            Task.name.label('task'),
            db.func.sum(Timesheet.hours).label('hours')
        )
        .join(Task, Timesheet.task_id == Task.id)
        .join(WorkPackage, Task.work_package_id == WorkPackage.id)
        .join(Project, WorkPackage.project_id == Project.id)
        .filter(Timesheet.user_id == user_id)
        .group_by(Project.name, WorkPackage.name, Task.name)
        .all()
    )

    result = [
        {
            'project': row.project,
            'work_package': row.work_package,
            'task': row.task,
            'hours': row.hours or 0,
        }
        for row in entries
    ]

    return jsonify(result)

@app.route('/admin_dashboard/reports/project/<int:project_id>')
@admin_required
def report_project_detail(project_id):
    """Return hours for a project broken down by work package and task."""
    entries = (
        db.session.query(
            WorkPackage.name.label('work_package'),
            Task.name.label('task'),
            db.func.sum(Timesheet.hours).label('hours')
        )
        .join(Task, Timesheet.task_id == Task.id)
        .join(WorkPackage, Task.work_package_id == WorkPackage.id)
        .filter(WorkPackage.project_id == project_id)
        .group_by(WorkPackage.name, Task.name)
        .all()
    )

    result = [
        {
            'work_package': row.work_package,
            'task': row.task,
            'hours': row.hours or 0,
        }
        for row in entries
    ]

    return jsonify(result)

#
# New hierarchical report endpoints
# ---------------------------------
# These endpoints supply JSON data for the drill-down reports. Each endpoint
# aggregates timesheet hours at a specific level so the client can progressively
# load more detail only when required.

@app.route('/admin_dashboard/reports/user/<int:user_id>/projects')
@admin_required
def report_user_projects(user_id):
    """Return hours for a user grouped by project."""
    # Sum hours for each project this user has booked time on
    entries = (
        db.session.query(
            Project.id.label('project_id'),
            Project.name.label('project'),
            db.func.sum(Timesheet.hours).label('hours'),
        )
        .join(Task, Timesheet.task_id == Task.id)
        .join(WorkPackage, Task.work_package_id == WorkPackage.id)
        .join(Project, WorkPackage.project_id == Project.id)
        .filter(Timesheet.user_id == user_id)
        .group_by(Project.id, Project.name)
        .all()
    )

    result = [
        {
            'project_id': row.project_id,
            'project': row.project,
            'hours': row.hours or 0,
        }
        for row in entries
    ]

    return jsonify(result)


@app.route('/admin_dashboard/reports/user/<int:user_id>/project/<int:project_id>/work_packages')
@admin_required
def report_user_project_work_packages(user_id, project_id):
    """Return hours for a user's project grouped by work package."""
    entries = (
        db.session.query(
            WorkPackage.id.label('work_package_id'),
            WorkPackage.name.label('work_package'),
            db.func.sum(Timesheet.hours).label('hours'),
        )
        .join(Task, Timesheet.task_id == Task.id)
        .join(WorkPackage, Task.work_package_id == WorkPackage.id)
        .filter(Timesheet.user_id == user_id, WorkPackage.project_id == project_id)
        .group_by(WorkPackage.id, WorkPackage.name)
        .all()
    )

    result = [
        {
            'work_package_id': row.work_package_id,
            'work_package': row.work_package,
            'hours': row.hours or 0,
        }
        for row in entries
    ]

    return jsonify(result)


@app.route('/admin_dashboard/reports/user/<int:user_id>/work_package/<int:work_package_id>/tasks')
@admin_required
def report_user_work_package_tasks(user_id, work_package_id):
    """Return hours for a user's work package grouped by task."""
    entries = (
        db.session.query(
            Task.name.label('task'),
            db.func.sum(Timesheet.hours).label('hours'),
        )
        .join(Task, Timesheet.task_id == Task.id)
        .filter(Timesheet.user_id == user_id, Task.work_package_id == work_package_id)
        .group_by(Task.name)
        .all()
    )

    result = [
        {
            'task': row.task,
            'hours': row.hours or 0,
        }
        for row in entries
    ]

    return jsonify(result)


@app.route('/admin_dashboard/reports/project/<int:project_id>/work_packages')
@admin_required
def report_project_work_packages(project_id):
    """Return hours for a project grouped by work package."""
    entries = (
        db.session.query(
            WorkPackage.id.label('work_package_id'),
            WorkPackage.name.label('work_package'),
            db.func.sum(Timesheet.hours).label('hours'),
        )
        .join(Task, Timesheet.task_id == Task.id)
        .join(WorkPackage, Task.work_package_id == WorkPackage.id)
        .filter(WorkPackage.project_id == project_id)
        .group_by(WorkPackage.id, WorkPackage.name)
        .all()
    )

    result = [
        {
            'work_package_id': row.work_package_id,
            'work_package': row.work_package,
            'hours': row.hours or 0,
        }
        for row in entries
    ]

    return jsonify(result)


@app.route('/admin_dashboard/reports/work_package/<int:work_package_id>/tasks')
@admin_required
def report_work_package_tasks(work_package_id):
    """Return hours for a work package grouped by task."""
    entries = (
        db.session.query(
            Task.name.label('task'),
            db.func.sum(Timesheet.hours).label('hours'),
        )
        .join(Task, Timesheet.task_id == Task.id)
        .filter(Task.work_package_id == work_package_id)
        .group_by(Task.name)
        .all()
    )

    result = [
        {
            'task': row.task,
            'hours': row.hours or 0,
        }
        for row in entries
    ]

    return jsonify(result)

@app.route('/admin_dashboard/projects', methods=['GET', 'POST'])
@admin_required
def projects_page():
    """Projects management page with timesheet data."""
    if request.method == 'POST':
        # Get form data
        project_name = request.form['project_name']
        project_description = request.form['project_description']

        # Create new project
        new_project = Project(name=project_name, description=project_description)
        db.session.add(new_project)
        db.session.commit()

        flash(f'Project "{project_name}" added successfully', 'success')
        return redirect(url_for('projects_page'))

    # Fetch projects and timesheet data
    projects = Project.query.all()

    # Get timesheet data per project
    project_data = []
    for project in projects:
        total_hours = db.session.query(db.func.sum(Timesheet.hours))\
            .join(Task).join(WorkPackage)\
            .filter(WorkPackage.project_id == project.id)\
            .scalar() or 0
        users = db.session.query(User.username)\
            .join(Timesheet).join(Task).join(WorkPackage)\
            .filter(WorkPackage.project_id == project.id)\
            .distinct().all()
        project_data.append({
            'project': project,
            'total_hours': total_hours,
            'users': [u[0] for u in users]
        })

    return render_template('projects.html', project_data=project_data)

@app.route('/admin_dashboard/projects/<int:project_id>', methods=['GET', 'POST'])
@admin_required
def project_detail(project_id):
    """Project detail page with work packages and timesheet data."""
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        # Get form data
        work_package_name = request.form['work_package_name']

        # Create new work package
        new_work_package = WorkPackage(name=work_package_name, project_id=project.id)
        db.session.add(new_work_package)
        db.session.commit()

        flash(f'Work Package "{work_package_name}" added successfully', 'success')
        return redirect(url_for('project_detail', project_id=project_id))

    # Fetch work packages and timesheet data
    work_packages = WorkPackage.query.filter_by(project_id=project.id).all()

    # Get timesheet data per work package
    wp_data = []
    for wp in work_packages:
        total_hours = db.session.query(db.func.sum(Timesheet.hours))\
            .join(Task)\
            .filter(Task.work_package_id == wp.id)\
            .scalar() or 0
        users = db.session.query(User.username)\
            .join(Timesheet).join(Task)\
            .filter(Task.work_package_id == wp.id)\
            .distinct().all()
        wp_data.append({
            'work_package': wp,
            'total_hours': total_hours,
            'users': [u[0] for u in users]
        })

    return render_template('project_detail.html', project=project, wp_data=wp_data)

@app.route('/admin_dashboard/work_packages/<int:work_package_id>', methods=['GET', 'POST'])
@admin_required
def work_package_detail(work_package_id):
    """Work package detail page with tasks and timesheet data."""
    work_package = WorkPackage.query.get_or_404(work_package_id)

    if request.method == 'POST':
        # Get form data
        task_name = request.form['task_name']

        # Create new task
        new_task = Task(name=task_name, work_package_id=work_package.id)
        db.session.add(new_task)
        db.session.commit()

        flash(f'Task "{task_name}" added successfully', 'success')
        return redirect(url_for('work_package_detail', work_package_id=work_package_id))

    # Fetch tasks and timesheet data
    tasks = Task.query.filter_by(work_package_id=work_package.id).all()

    # Get timesheet data per task
    task_data = []
    for task in tasks:
        total_hours = db.session.query(db.func.sum(Timesheet.hours))\
            .filter_by(task_id=task.id)\
            .scalar() or 0
        users = db.session.query(User.username)\
            .join(Timesheet)\
            .filter(Timesheet.task_id == task.id)\
            .distinct().all()
        task_data.append({
            'task': task,
            'total_hours': total_hours,
            'users': [u[0] for u in users]
        })

    return render_template('work_package_detail.html', work_package=work_package, task_data=task_data)

@app.route('/admin_dashboard/tasks/<int:task_id>', methods=['GET'])
@admin_required
def task_detail(task_id):
    """Task detail page showing bookings by individual users."""
    task = Task.query.get_or_404(task_id)

    # Get timesheet data per user for this task
    user_data = db.session.query(
        User.id,
        User.username,
        db.func.sum(Timesheet.hours).label('total_hours')
    ).join(Timesheet)\
     .filter(Timesheet.task_id == task_id)\
     .group_by(User.id, User.username)\
     .all()

    return render_template('task_detail.html', task=task, user_data=user_data)

@app.route('/admin_dashboard/tasks/<int:task_id>/user/<int:user_id>', methods=['GET'])
@admin_required
def user_task_entries(task_id, user_id):
    """Page showing timesheet entries of a user for a specific task."""
    task = Task.query.get_or_404(task_id)
    user = User.query.get_or_404(user_id)

    # Get timesheet entries for this user and task
    timesheet_entries = Timesheet.query.filter_by(task_id=task_id, user_id=user_id).all()

    return render_template('user_task_entries.html', task=task, user=user, timesheet_entries=timesheet_entries)

@app.route('/admin_dashboard/users', methods=['GET', 'POST'])
@admin_required
def users_page():
    """Users management page."""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_user':
            # Get form data
            username = request.form['username']
            password = request.form['password']
            role = request.form['role']

            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash(f'Username "{username}" already exists. Please choose a different username.', 'danger')
            else:
                # Create new user
                hashed_password = generate_password_hash(password)
                new_user = User(username=username, password_hash=hashed_password, role=role)
                db.session.add(new_user)
                db.session.commit()

                flash(f'User "{username}" added successfully', 'success')

        elif action == 'change_password':
            user_id = int(request.form['user_id'])
            new_password = request.form['new_password']
            user = User.query.get_or_404(user_id)
            if user.username == 'admin':
                flash('Cannot change the password of the admin user here.', 'danger')
            else:
                user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash(f'Password for user "{user.username}" has been updated.', 'success')

        elif action == 'archive_user':
            user_id = int(request.form['user_id'])
            user = User.query.get_or_404(user_id)
            if user.username == 'admin':
                flash('Cannot archive the admin user.', 'danger')
            else:
                user.status = 'archived'
                db.session.commit()
                flash(f'User "{user.username}" archived successfully', 'success')

        elif action == 'activate_user':
            user_id = int(request.form['user_id'])
            user = User.query.get_or_404(user_id)
            user.status = 'active'
            db.session.commit()
            flash(f'User "{user.username}" has been activated.', 'success')

    users = User.query.all()

    return render_template('users.html', users=users)


# Leave Management Routes

@app.route('/user_dashboard/leave', methods=['GET'])
@login_required
def user_leave_dashboard():
    # Get user's leave balance
    leave_balance = LeaveBalance.query.filter_by(user_id=current_user.id).first()
    if not leave_balance:
        # Initialize leave balance if not exists
        leave_balance = LeaveBalance(user_id=current_user.id, total_leave=20.0, used_leave=0.0)
        db.session.add(leave_balance)
        db.session.commit()

    # Get user's leave requests
    leave_requests = LeaveRequest.query.filter_by(user_id=current_user.id).order_by(LeaveRequest.timestamp.desc()).all()

    return render_template('leave_dashboard.html', leave_balance=leave_balance, leave_requests=leave_requests)

@app.route('/user_dashboard/leave/request', methods=['GET', 'POST'])
@login_required
def submit_leave_request():
    if request.method == 'POST':
        # Get form data
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        leave_type = request.form['leave_type']
        comment = request.form.get('comment')  # Optional

        # Validate dates
        if end_date < start_date:
            flash('End date cannot be before start date.', 'danger')
            return redirect(url_for('submit_leave_request'))

        # Edge case: start and end on same day with invalid time selection
        if start_date == end_date and start_time == 'Afternoon' and end_time == 'Morning':
            flash('Invalid time selection on the same day.', 'danger')
            return redirect(url_for('submit_leave_request'))

        try:
            # Calculate leave days
            leave_days = calculate_leave_days(start_date, start_time, end_date, end_time)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('submit_leave_request'))

        # Check leave balance if not sick leave
        if leave_type != 'Sick Leave':
            leave_balance = LeaveBalance.query.filter_by(user_id=current_user.id).first()
            remaining_leave = leave_balance.total_leave - leave_balance.used_leave

            if leave_days > remaining_leave:
                flash('You do not have enough leave balance for this request.', 'danger')
                return redirect(url_for('submit_leave_request'))

        # Create leave request
        leave_request = LeaveRequest(
            user_id=current_user.id,
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
            leave_type=leave_type,
            comment=comment
        )
        db.session.add(leave_request)
        db.session.commit()

        flash('Leave request submitted successfully.', 'success')
        return redirect(url_for('user_leave_dashboard'))

    return render_template('submit_leave.html')

@app.route('/admin_dashboard/leave_requests', methods=['GET', 'POST'])
@admin_required
def manage_leave_requests():
    if request.method == 'POST':
        action = request.form.get('action')
        leave_request_id = int(request.form['leave_request_id'])
        leave_request = LeaveRequest.query.get_or_404(leave_request_id)
        admin_comment = request.form.get('admin_comment')

        if action == 'approve':
            try:
                leave_days = leave_request.calculate_duration()
            except ValueError as e:
                flash(f'Error calculating leave duration: {e}', 'danger')
                return redirect(url_for('manage_leave_requests'))

            # Update leave balance if not sick leave
            if leave_request.leave_type != 'Sick Leave':
                leave_balance = LeaveBalance.query.filter_by(user_id=leave_request.user_id).first()
                leave_balance.used_leave += leave_days
                db.session.commit()

            # Update request status
            leave_request.status = 'Approved'
            leave_request.admin_comment = admin_comment
            db.session.commit()

            flash(f'Leave request {leave_request.id} approved.', 'success')
        elif action == 'reject':
            leave_request.status = 'Rejected'
            leave_request.admin_comment = admin_comment
            db.session.commit()
            flash(f'Leave request {leave_request.id} rejected.', 'danger')

    # Fetch leave requests
    # joinedload eager loads the related User objects to reduce query count
    # using the joinedload function from SQLAlchemy ORM, not from the db object
    leave_requests = LeaveRequest.query.options(joinedload(LeaveRequest.user)).order_by(LeaveRequest.timestamp.desc()).all()
    return render_template('admin_leave_requests.html', leave_requests=leave_requests)

@app.route('/admin_dashboard/leave_balances', methods=['GET', 'POST'])
@admin_required
def adjust_leave_balances():
    """Admin view to adjust users' leave balances."""
    if request.method == 'POST':
        user_id = int(request.form['user_id'])
        total_leave = float(request.form['total_leave'])

        leave_balance = LeaveBalance.query.filter_by(user_id=user_id).first()
        if not leave_balance:
            leave_balance = LeaveBalance(user_id=user_id, total_leave=total_leave)
            db.session.add(leave_balance)
        else:
            leave_balance.total_leave = total_leave

        db.session.commit()
        flash(f'Leave balance updated for user ID {user_id}.', 'success')

    # Get all users and their leave balances
    users = User.query.all()
    leave_balances = {lb.user_id: lb for lb in LeaveBalance.query.all()}

    return render_template('adjust_leave_balances.html', users=users, leave_balances=leave_balances)

@app.route('/admin_dashboard/leave_calendar', methods=['GET'])
@admin_required
def leave_calendar():
    """Admin view to see approved leaves on a calendar."""
    # Get all approved leave requests
    approved_leaves = LeaveRequest.query.options(joinedload(LeaveRequest.user)).filter_by(status='Approved').all()

    # Prepare data for the calendar
    events = []
    for leave in approved_leaves:
        events.append({
            'title': f"{leave.user.username} - {leave.leave_type}",
            'start': leave.start_date.isoformat(),
            'end': (leave.end_date + timedelta(days=1)).isoformat(),  # FullCalendar's end date is exclusive
            'allDay': True,
        })

    return render_template('leave_calendar.html', events=events)

@app.route('/admin_dashboard/dummy_data', methods=['GET', 'POST'])
@admin_required
def dummy_data_page():
    """Allow administrators to manage dummy data records."""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            # Create a new dummy record
            name = request.form['name']
            value = request.form.get('value')
            db.session.add(DummyData(name=name, value=value))
            db.session.commit()
            flash(f'Dummy data "{name}" added.', 'success')
        elif action == 'update':
            # Update an existing dummy record
            dummy_id = int(request.form['dummy_id'])
            dummy = DummyData.query.get_or_404(dummy_id)
            dummy.name = request.form['name']
            dummy.value = request.form.get('value')
            db.session.commit()
            flash('Dummy data updated.', 'success')
        elif action == 'delete':
            # Remove an existing dummy record
            dummy_id = int(request.form['dummy_id'])
            dummy = DummyData.query.get_or_404(dummy_id)
            db.session.delete(dummy)
            db.session.commit()
            flash('Dummy data deleted.', 'success')

    # Fetch all dummy records for display
    dummies = DummyData.query.all()
    return render_template('dummy_data.html', dummies=dummies)

# Initialize the database and create admin user

#if __name__ == '__main__':
#    app.run(debug=True)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Create an admin user if not exists
        if not User.query.filter_by(username='admin').first():
            hashed_password = generate_password_hash('admin')
            admin_user = User(username='admin', password_hash=hashed_password, role='admin')
            db.session.add(admin_user)
            db.session.commit()

        # Create example projects, work packages and tasks on first run
        init_example_projects()

        # Populate dummy data so the UI has content immediately
        init_dummy_data()

    #app.run(debug=True)
    #app.run(host='0.0.0.0', port=5000, debug=False, threaded=False)
    serve(app, host='0.0.0.0', port=8000)
