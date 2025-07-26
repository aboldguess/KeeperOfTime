"""Simple script to host KeeperOfTime on a Raspberry Pi using Waitress.

Usage:
    python3 rpi_server.py [PORT]

If PORT is omitted it defaults to 8000.
"""

import sys
from waitress import serve

# Import the Flask application and helpers from the main app module
from timesheet_app import (
    app,
    db,
    apply_schema_updates,
    User,
    generate_password_hash,
    init_example_projects,
    init_dummy_data,
)


def initialize_database():
    """Ensure the SQLite database exists and has sample data."""
    # Apply schema updates for older installations
    apply_schema_updates()

    # Create missing tables
    db.create_all()

    # Create the default admin user if not present
    if not User.query.filter_by(username="admin").first():
        hashed_password = generate_password_hash("admin")
        admin_user = User(
            username="admin", password_hash=hashed_password, role="admin"
        )
        db.session.add(admin_user)
        db.session.commit()

    # Populate example projects and dummy data on first run
    init_example_projects()
    init_dummy_data()


def main() -> None:
    """Entry point when executing the script."""
    # Default port if none is supplied via command line
    port = 8000

    # Attempt to read an integer port from the first argument
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port '{sys.argv[1]}', falling back to {port}.")

    # Perform database initialization within the application context
    with app.app_context():
        initialize_database()

    # Start the Waitress WSGI server
    serve(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
