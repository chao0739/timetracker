"""入口"""
from pathlib import Path
from .db import Database, LOCAL_USER_ID
from .service import TimerService
from .tui import TimeTrackerApp


DB_PATH = Path.home() / ".timetracker.db"


def main():
    db = Database(DB_PATH)
    service = TimerService(db, user_id=LOCAL_USER_ID)
    app = TimeTrackerApp(service)
    app.run()


if __name__ == "__main__":
    main()
