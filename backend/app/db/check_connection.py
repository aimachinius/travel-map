
from sqlalchemy import text

from app.db.session import engine


def main():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT current_database(), version()"))
            database_name, database_version = result.fetchone()

            print(f"Ket noi thanh cong: {database_name}")
            print(f"PostgreSQL: {database_version}")

    except Exception as error:
        print("Ket noi database that bai.")
        print(f"Chi tiet: {error}")
        raise

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
