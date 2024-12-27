import psycopg2
from Logging_folder.logger import logger
from dotenv import load_dotenv
import os
# Load environment variables from the .env file
load_dotenv()

# Retrieve database credentials from the environment variables
hostname = os.getenv('DB_HOST')  # Database host
username = os.getenv('DB_USER')  # Database user
password = os.getenv('DB_PASSWORD')  # Database password
database = os.getenv('DB_NAME')  # Database name
port_id = os.getenv('DB_PORT')  # Database port

def pgadmin_connect():
    """
    Connects to a PostgreSQL database using credentials from environment variables.
    If the connection is successful, it creates a table 'resume_table' if it doesn't already exist.

    The table schema includes:
    - unique_id: Numeric, primary key
    - resume_name: Name of the resume (varchar with max length of 100)
    - resume_content: Content of the resume (text)
    - resume_key_aspect: Key aspects of the resume (text)
    - score: Score related to the resume (integer)

    Returns:
        conn: Connection object for the PostgreSQL database.
        cur: Cursor object for executing queries.
        
    If an error occurs, logs the exception and returns None, None.
    """
    try:
        # Attempt to connect to the PostgreSQL database
        conn = psycopg2.connect(
            host=hostname,
            user=username,
            password=password,
            dbname=database,
            port=port_id
        )
        
        # Create a cursor object to interact with the database
        cur = conn.cursor()

        # SQL query to create the 'resume_table' if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS resume_table (
                unique_id NUMERIC PRIMARY KEY,
                resume_name VARCHAR(100),
                resume_content TEXT,
                resume_key_aspect TEXT,
                score INTEGER
            )
        """)

        # Commit the transaction (important to save changes to the database)
        conn.commit()

    except (Exception, psycopg2.Error) as error:
        # Log the error if an exception occurs while connecting or executing the SQL
        logger.exception("Error while connecting to PostgreSQL: %s", error)
        return None, None  # Return None for both conn and cur in case of error
    
    # Return the connection and cursor objects if successful
    return conn, cur
