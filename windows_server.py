"""Helper script to run KeeperOfTime easily on Windows.

This script installs required dependencies, prepares the database and
launches the application using Waitress.  A specific port can be
provided as the first command line argument.
"""

import subprocess
import sys
from pathlib import Path

from waitress import serve

# Import application and helpers from the main module
from timesheet_app import (
    app,
    db,
    apply_schema_updates,
    User,
    generate_password_hash,
    init_example_projects,
    init_dummy_data,
)


def install_requirements() -> None:
    """Install packages listed in requirements.txt using pip."""
    requirements = Path(__file__).with_name("requirements.txt")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements)])


def initialize_database() -> None:
    """Create tables and populate initial data if needed."""
    # Ensure the existing database has the latest schema
    apply_schema_updates()

    # Create any missing tables
    db.create_all()

    # Add default admin user on first run
    if not User.query.filter_by(username="admin").first():
        hashed = generate_password_hash("admin")
        db.session.add(User(username="admin", password_hash=hashed, role="admin"))
        db.session.commit()

    # Insert example content so the UI isn't empty
    init_example_projects()
    init_dummy_data()


def main() -> None:
    """Entry point for running the app."""
    # Default port if not provided
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port '{sys.argv[1]}', using {port}.")

    # Ensure dependencies are installed before launching
    install_requirements()

    # Perform DB setup in the Flask application context
    with app.app_context():
        initialize_database()

    # Start the Waitress WSGI server
    serve(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
