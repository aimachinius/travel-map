import os
import sys
import time
from sqlalchemy import text
from app.db.session import engine


def wait_for_db(max_retries: int = 30, delay: int = 1) -> bool:
    print(f"Waiting for database at {os.getenv('DB_HOST', '127.0.0.1')}:{os.getenv('DB_PORT', '5432')}...")
    for i in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("Database connection established successfully!")
                return True
        except Exception as e:
            print(f"Waiting for database ({i}/{max_retries}): {e}")
            time.sleep(delay)

    print("Could not connect to database after maximum retries.")
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
