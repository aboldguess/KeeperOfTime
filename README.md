# KeeperOfTime

KeeperOfTime is a small Flask application used to track time on projects and manage leave requests.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies using:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Run the application with `python3 timesheet_app.py`.

The default SQLite database is stored in `instance/timesheet_app.db`. On first run an admin account is created with username `admin` and password `admin`.
Example projects with sample work packages and tasks are automatically added so you can explore the interface immediately. Administrators can manage these records from the **Dummy Data** page.

## Project Management

Tasks now support optional start and end dates. When creating a task under a work package you can specify when the work is scheduled to begin and finish. These dates are visible throughout the admin dashboards to aid basic project planning.

Projects, work packages and tasks can also record a budget of planned hours. When adding new items through the admin interface simply enter the expected hours and the value will be displayed alongside actual hours booked.

## Development

Changes to the database schema can be handled via `Flask-Migrate` using the helper script `database_migrate_tool.py`.


