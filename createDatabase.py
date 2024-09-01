import psycopg2
from psycopg2 import sql

def create_database(dbname):
    try:
        # Connect to PostgreSQL with an admin account (like 'postgres')
        connection = psycopg2.connect(
            dbname="auction",
            user="postgres",
            password="qwerty",  # Replace with your password
            host="localhost",
            port="5432"
        )
        connection.autocommit = True

        # Create a cursor object
        cursor = connection.cursor()

        # Create the database
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
        print(f"Database '{dbname}' created successfully!")

        # Close cursor and connection
        cursor.close()
        connection.close()

    except Exception as e:
        print(f"Error creating database: {e}")

create_database("auction")
