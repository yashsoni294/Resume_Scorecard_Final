from Postgres_connect.pgadmin_connect import pgadmin_connect, pgadmin_disconnect
from Logging_folder.logger import logger

def insert_resume_data(unique_id, resume_name, resume_content):
    """
    Insert resume data into the PostgreSQL database.

    Args:
        unique_id (str): The unique identifier for the resume.
        resume_name (str): The name of the resume file.
        resume_content (str): The text content of the resume.

    Returns:
        None
    """ 
    # Connect to PostgreSQL database
    conn, cur = pgadmin_connect()
    try:
        # Insert the data into the database
        cur.execute("""
                    INSERT INTO resume_table (unique_id, resume_name, resume_content, resume_key_aspect, score)
                    VALUES (%s, %s, %s, %s, %s)
                """, (unique_id, resume_name, resume_content, None, None))
        conn.commit()
        logger.info(f"Successfully stored {resume_name} in database")
    except Exception as e:
        logger.exception(f"Error storing {resume_name} in database: {str(e)}")
        conn.rollback()

    pgadmin_disconnect(conn, cur)


def update_resume_data(unique_id, resume_key_aspect, score, resume_name):
    """
    Update resume data in the PostgreSQL database.

    Args:
        unique_id (str): The unique identifier for the resume.
        resume_key_aspect (str): The key aspect of the resume.
        score (float): The score of the resume.

    Returns:
        None
    """
    # Connect to PostgreSQL database
    conn, cur = pgadmin_connect()
    try:
        # Insert the data into the database
        cur.execute(
                """
                UPDATE resume_table 
                SET resume_key_aspect = %s, 
                    score = %s 
                    WHERE unique_id = %s
                """, 
                (resume_key_aspect, score, unique_id)
            )
        # Commit the changes
        conn.commit()
        logger.info(f"Successfully stored {resume_name} in database")
    except Exception as e:
        logger.exception(f"Error storing {resume_name} in database: {str(e)}")
        conn.rollback()

    pgadmin_disconnect(conn, cur)