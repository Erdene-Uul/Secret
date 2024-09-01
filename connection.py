import psycopg2
from psycopg2 import sql
# Define your connection details
connection = psycopg2.connect(
    host="localhost",      # e.g., "localhost"
    database="your_db",    # your database name
    user="your_user",      # your database user
    password="your_password",  # your password
    port="5432"            # default PostgreSQL port
)

def create_database(dbname):
    try:
        # Connect to PostgreSQL with an admin account (like 'postgres')
        connection = psycopg2.connect(
            user="postgres",
            password="postgres", 
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

# Call the function to create a new database
create_database("new_database_name")

# Create a cursor object
cursor = connection.cursor()

# Write an SQL query
sql_query = "SELECT * FROM your_table;"

# Execute the query
cursor.execute(sql_query)

# Fetch all results from the executed query
results = cursor.fetchall()

# Print the results
for row in results:
    print(row)

# Close the cursor and connection
cursor.close()
connection.close()
