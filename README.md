# KeeperOfTime

KeeperOfTime is a small Flask application used to track time on projects and manage leave requests.

## Setup

1. Create and activate a Python virtual environment.

   **Linux / Raspberry Pi**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies using:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:

   ```bash
   python3 timesheet_app.py
   ```

   To change the port or switch to the Flask development server, set the following environment variables before running:

   **Linux / Raspberry Pi**
   ```bash
   export KOT_PORT=5000          # optional port number
   export KOT_PRODUCTION=false   # use Flask's debug server
   python3 timesheet_app.py
   ```

   **Windows**
   ```powershell
   set KOT_PORT=5000
   set KOT_PRODUCTION=false
   python timesheet_app.py
   ```

The default SQLite database is stored in `instance/timesheet_app.db`. On first run an admin account is created with username `admin` and password `admin`.
Example projects with sample work packages and tasks are automatically added so you can explore the interface immediately. Administrators can manage these records from the **Dummy Data** page. When dummy projects are created through this page each task is given a simple start and end date along with budget hours so reports show meaningful schedules from the outset.

## Hosting on Raspberry Pi

Use the `rpi_server.py` helper script to run the application on a Raspberry Pi.
Specify an optional port number when launching the script:

```bash
python3 rpi_server.py 8080  # listens on port 8080
```

If no port argument is provided the server defaults to `8000`.

## Windows Quick Start

Run `windows_server.py` to automatically install dependencies, prepare the database and launch the application. An optional port number can be passed:

```bash
python windows_server.py 5000  # listens on port 5000
```

If omitted, the app uses port `8000`.


## Project Management

Tasks now support optional start and end dates. When creating a task under a work package you can specify when the work is scheduled to begin and finish. These dates are visible throughout the admin dashboards to aid basic project planning.

Projects, work packages and tasks can also record a budget of planned hours. When adding new items through the admin interface simply enter the expected hours and the value will be displayed alongside actual hours booked.

## Development

Changes to the database schema can be handled via `Flask-Migrate` using the helper script `database_migrate_tool.py`.


