import psycopg2
from Logging_folder.logger import logger

hostname = 'localhost'
username = 'postgres'
password = '123456'
database = 'ResumeDB'
port_id = 5432

def pgadmin_connect():
    try:
        conn = psycopg2.connect(
        host=hostname,
        user=username,
        password=password,
        dbname=database,
        port=port_id
        )
        cur = conn.cursor()
        cur.execute("""
                CREATE TABLE IF NOT EXISTS resume_table (
                    unique_id NUMERIC PRIMARY KEY,
                    resume_name VARCHAR(100) ,
                    resume_content TEXT ,
                    resume_key_aspect TEXT ,
                    score INTEGER
                )
            """)
        conn.commit()

    except (Exception, psycopg2.Error) as error:
        logger.error("Error while connecting to PostgreSQL: %s", error)
        return None, None
    return conn, cur