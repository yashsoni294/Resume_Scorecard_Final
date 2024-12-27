from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import io
import zipfile
from datetime import datetime
import re
import shutil
from files_reading import utils
from fastapi.middleware.cors import CORSMiddleware
import base64
import threading
import os
from templates.templates import TEMPLATES
from model_calling.openai_call import get_conversation_openai
from model_calling.async_api_call import run_in_executor, process_resumes_async
from aws_s3_connect.connect import upload_resume_file, download_from_s3
from Logging_folder.logger import logger
from Postgres_connect.pgadmin_connect import pgadmin_connect
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Lock for synchronizing access to the filename generation
filename_lock = threading.Lock()

# Initialize FastAPI application
app = FastAPI()

# Access the environment variables
frontend_url = os.getenv("FRONTEND_URL")
backend_url = os.getenv("BACKEND_URL")

# Define origins list using the environment variables
origins = [
    frontend_url,
    backend_url
]
 
# Add CORS middleware to the application
app.add_middleware(
    CORSMiddleware,
    allow_origins= origins,  # List of allowed origins
    allow_credentials=True,  # Allow cookies and credentials
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define the endpoint for uploading files and processing resumes
@app.post("/upload-files/")
async def upload_files(job_description: str, files: list[UploadFile] = File(...)):
    """
    Endpoint to upload files and process resumes.

    This endpoint accepts a job description and a list of uploaded files (PDF, DOC, DOCX, TXT, or ZIP). 
    It extracts and processes the content of the resumes, scores them against the job description, 
    and stores the processed data in a PostgreSQL database. The endpoint also uploads the processed 
    files to an S3 bucket and returns the extracted information and scores.

    Parameters:
        job_description (str): The job description against which the resumes will be scored.
        files (list[UploadFile]): A list of files to be processed. Supported formats include:
            - Individual resume files: PDF, DOC, DOCX, TXT.
            - Compressed ZIP files containing resumes.

    Returns:
        dict: A dictionary containing the processed data for each file. Each entry includes:
            - "content": The extracted text content of the resume.
            - "file_path": The path to the file stored temporarily.
            - "key_feature" (optional): Key features extracted from the resume relevant to the job description.
            - "score" (optional): A score representing the match between the resume and the job description.

    Notes:
        - ZIP files are extracted, and each file within them is processed separately.
        - The resumes are stored in a PostgreSQL database with their extracted content, key aspects, and scores.
        - Processed files are uploaded to an S3 bucket.
        - Temporary files and directories created during processing are cleaned up after execution.

    Exceptions:
        - Files that cannot be processed due to unsupported formats or errors during extraction will 
          include an error message in the response.
        - Any database or S3 upload errors are logged and handled appropriately.
    """

    # Initialize an empty dictionary to store response data
    response_data = {}

    # Get conversation context for job description using OpenAI model
    conversation_jd = get_conversation_openai(TEMPLATES["job_description"])
    jd_response = conversation_jd({"job_description_text": job_description})
    processed_jd = jd_response
    logger.info("Processing the Job Description...\n")

    # Create a unique directory for each upload session
    session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    extract_path = f"extracted_files_{session_id}"
    
    # Create the unique directory for the session
    os.makedirs(extract_path, exist_ok=True)

    # Connect to PostgreSQL database
    conn, cur = pgadmin_connect()

    # Iterate over each file uploaded
    for file in files:
        try:
            # Fallback to file extension if MIME type is not reliable
            file_extension = file.filename.split(".")[-1].lower()

            # Generate a unique file name using a timestamp
            with filename_lock:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                file_name = file.filename
                unique_filename = f"{timestamp}_{file_name}"
                file_path = os.path.join(extract_path, unique_filename)

            # Check if the file is a ZIP archive
            if file.content_type == "application/zip" or file_extension == "zip":
                # Process ZIP files
                zip_data = await file.read()
                zip_file = io.BytesIO(zip_data)
                extracted_files = []
                with zipfile.ZipFile(zip_file, 'r') as z:
                    # Extract files from the ZIP archive
                    file_name_list = z.namelist()
                    for original_file_name in file_name_list:
                        # Generate a unique file name for each file in the ZIP
                        with filename_lock:
                            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                            unique_file_name = f"{timestamp}_{original_file_name}"
                        z.extract(original_file_name, extract_path)
                        # Rename the extracted file to its unique name
                        os.rename(os.path.join(extract_path, original_file_name),
                                  os.path.join(extract_path, unique_file_name))
                        extracted_files.append(unique_file_name)

                # Initialize a dictionary to store contents of PDF files
                pdf_contents = {}
                i = 0
                for file_name in extracted_files:
                    original_name = file_name_list[i]
                    i += 1
                    logger.info(f"Reading file: {original_name}")
                    file_path = os.path.join(extract_path, file_name)
                    unique_id = re.match(r'^\d+', file_name).group()
                    resume_name = original_name
                    resume_content = None

                    # Process PDF files
                    if file_name.endswith(".pdf"):
                        with open(file_path, "rb") as pdf_file:
                            # Now read for text extraction
                            resume_content = utils.read_pdf(pdf_file)
                            response_data[original_name] = {"content": resume_content}
                    
                    # Process TXT files
                    elif file_name.endswith(".txt"):
                        with open(file_path, "rb") as txt_file:
                            # Now read for text extraction
                            resume_content = utils.read_txt(txt_file)
                            response_data[original_name] = {"content": resume_content}

                    # Process DOCX files
                    elif file_name.endswith(".docx"):
                        try:
                            with open(file_path, "rb") as docx_file:
                                # Now read for text extraction
                                resume_content = utils.read_docx(docx_file)
                                response_data[original_name] = {"content": resume_content}
                        except Exception as e:
                            logger.exception(f"Error reading DOCX file: {str(e)}")
                            response_data[original_name] = {"content": f"Error reading DOCX file: {str(e)}"}

                    # Process DOC files
                    elif file_name.endswith(".doc"):
                        resume_content, _ = utils.read_doc(file_path)
                        response_data[original_name] = {"content": resume_content}
                    
                    response_data[original_name]["file_path"] = file_name
                
                    # If resume content is extracted, store it in the database
                    if resume_content is not None:
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
                    else:
                        logger.warning(f"Skipping {resume_name} - No content or blob data available")

                    # Upload the processed resume file to S3
                    upload_resume_file(filename=file_name, directory_path=extract_path)
                    logger.info(f"Uploaded {file_name} to S3 Bucket")

                    # Clean up the extracted file
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.exception(f"Error removing temporary file {file_path}: {str(e)}")

            # Process non-ZIP files
            else:
                unique_id = timestamp
                resume_name = file_name
                resume_content = None

                # Save individual file to extracted_files directory
                file_content = await file.read()
                
                with open(file_path, "wb") as f:
                    f.write(file_content)

                logger.info(f"Reading file: {file_name}")
                # Process based on file type
                if file_extension == "pdf":
                    with open(file_path, "rb") as pdf_file:
                        # Now read for text extraction
                        resume_content = utils.read_pdf(pdf_file)
                        response_data[file_name] = {"content": resume_content}
                
                elif file_extension == "txt":
                    with open(file_path, "rb") as txt_file:
                        # Now read for text extraction
                        resume_content = utils.read_txt(txt_file)
                        response_data[file_name] = {"content": resume_content}
                
                elif file_extension == "docx":
                    try:
                        with open(file_path, "rb") as docx_file:
                            # Now read for text extraction
                            resume_content = utils.read_docx(docx_file)
                            response_data[file_name] = {"content": resume_content}
                            
                    except Exception as e:
                        logger.exception(f"Error reading DOCX file: {str(e)}")
                        response_data[file_name] = {"content": str(e)}
                
                elif file_extension == "doc":
                    resume_content, _ = utils.read_doc(file_path)
                    response_data[file_name] = {"content": resume_content}
                
                else:
                    logger.warning(f"Unsupported file type: {file_extension}")

                # Add file path to the response data
                response_data[file_name]["file_path"] = f"{unique_id}_{resume_name}"

                # Upload the processed resume file to S3
                upload_resume_file(filename = f"{unique_id}_{resume_name}", directory_path=extract_path)
                logger.info(f"Uploaded {file_name} to S3 Bucket")
            
                # SQL query to insert data into the database. 
                cur.execute( 
                        "INSERT INTO resume_table(unique_id,resume_name,resume_content) "
                        "VALUES(%s,%s,%s)", (unique_id, resume_name, resume_content)
                        )
                conn.commit()
                
                # Clean up the extracted file
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.exception(f"Error removing temporary file {file_path}: {str(e)}")

        except Exception as e:
            logger.exception(f"Error processing file: {str(e)}")
            response_data[file.filename] = {
                "error": str(e)
            }
             
    # Process the resumes asynchronously
    response_data = await process_resumes_async(response_data, processed_jd)

    # Update the database with key features and scores for each resume
    for key, value in response_data.items():
        resume_key_aspect = value["key_feature"]
        score = value["score"]
        unique_id = value["file_path"]
        unique_id = re.match(r"^\d{20}", unique_id).group()

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

    # Close the database cursor
    if cur is not None:
        cur.close()
        logger.info("Database cursor closed.")

    # Close the database connection
    if conn is not None:
        conn.close()
        logger.info("Database connection closed.")

    # Clean up the unique directory after processing
    shutil.rmtree(extract_path)
    return response_data


# Define the endpoint for downloading a file by its name
@app.post("/download-resume/{file_path}")
async def download_file(file_path: str):
    """
    Asynchronous endpoint to download a file by its name.
    
    :param file_path: Path of the file to download
    :return: JSON response with base64 encoded PDF URL
    """
    try:
        # Download file from S3 asynchronously using run_in_executor
        file_path = await run_in_executor(download_from_s3, file_path)
        
        # Read the PDF file as binary using run_in_executor to avoid blocking
        pdf_binary = await run_in_executor(lambda: open(file_path, "rb").read())
 
        # Encode the binary content to Base64
        pdf_base64 = base64.b64encode(pdf_binary).decode("utf-8")
 
        # Create a Data URL for the PDF
        pdf_url = f"data:application/pdf;base64,{pdf_base64}"
 
        # Return the Data URL to the frontend    
        return JSONResponse(content={"pdf_url": pdf_url})
 
    except FileNotFoundError as e:
        logger.exception(f"PDF file not found: {file_path} - {str(e)}")
        raise HTTPException(status_code=404, detail="PDF file not found")
    except Exception as e:
        logger.exception(f"Error downloading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Optional: Clean up the downloaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up file {file_path}: {cleanup_error}")
