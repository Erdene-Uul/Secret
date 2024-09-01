import psycopg2

def create_tables():
    try:
        # Connect to the newly created database
        connection = psycopg2.connect(
            host="localhost",
            database="auction",  # Replace with your database name
            user="postgres",              # Replace with your username
            password="postgres",      # Replace with your password
            port="5432"
        )

        # Create a cursor object
        cursor = connection.cursor()

        # SQL to create a table
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            age INT NOT NULL,
            department VARCHAR(50)
        );
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price INT NOT NULL,
            image INT NOT NULL,
            department VARCHAR(50)
        );
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price INT NOT NULL,
            image INT NOT NULL,
            department VARCHAR(50)
        );
        '''

        # Execute the table creation
        cursor.execute(create_table_query)
        connection.commit()

        print("Table 'employees' created successfully!")

        # Close cursor and connection
        cursor.close()
        connection.close()

    except Exception as e:
        print(f"Error creating table: {e}")

# Call the function to create tables
create_tables()
