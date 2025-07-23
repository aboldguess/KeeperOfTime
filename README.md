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

## Development

Changes to the database schema can be handled via `Flask-Migrate` using the helper script `database_migrate_tool.py`.


