from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import os
import openai
import io
import zipfile
from dotenv import load_dotenv
from datetime import datetime
import re
import psycopg2
import shutil
from files_reading import utils
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import base64
import threading
import os
from templates.templates import TEMPLATES
from model_calling.openai_call import get_conversation_openai
from model_calling.async_api_call import run_in_executor, process_resumes_async
from aws_s3_connect.connect import upload_resume_file, download_from_s3
from Logging_folder.logger import logger

# Lock for synchronizing access to the filename generation
filename_lock = threading.Lock()

# Load API Key
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = API_KEY

hostname = 'localhost'
username = 'postgres'
password = '123456'
database = 'ResumeDB'
port_id = 5432

conn = None
cur = None

app = FastAPI()

origins = [
    "http://192.168.31.238:3000",  # Your frontend (React/Vite or similar)
    "https://1331-2409-40c2-4009-3586-70a3-7974-1e5-3d49.ngrok-free.app ",  # Your backend exposed via ngrok
]
 
# Add CORS middleware to the application
app.add_middleware(
    CORSMiddleware,
    allow_origins= origins,  # List of allowed origins
    allow_credentials=True,  # Allow cookies and credentials
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.post("/upload-files/")
async def upload_files(job_description: str, files: list[UploadFile] = File(...)):
    response_data = {}

    conversation_jd = get_conversation_openai(TEMPLATES["job_description"])
    jd_response = conversation_jd({"job_description_text": job_description})
    processed_jd = jd_response
    logger.info("Processing the Job Description...\n")

    # Create a unique directory for each upload session
    session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    extract_path = f"extracted_files_{session_id}"
    
    # Create the unique directory for the session
    os.makedirs(extract_path, exist_ok=True)

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

            if file.content_type == "application/zip" or file_extension == "zip":
                zip_data = await file.read()
                zip_file = io.BytesIO(zip_data)
                extracted_files = []
                with zipfile.ZipFile(zip_file, 'r') as z:
                    # Extract files
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

                    if file_name.endswith(".pdf"):
                        with open(file_path, "rb") as pdf_file:
                            # Now read for text extraction
                            resume_content = utils.read_pdf(pdf_file)
                            response_data[original_name] = {"content": resume_content, "file_path": file_name}
                    
                    # Process TXT files
                    elif file_name.endswith(".txt"):
                        with open(file_path, "rb") as txt_file:
                            # Now read for text extraction
                            resume_content = utils.read_txt(txt_file)
                            response_data[original_name] = {"content": resume_content, "file_path": file_name}

                    elif file_name.endswith(".docx"):
                        try:
                            with open(file_path, "rb") as docx_file:
                                # Now read for text extraction
                                resume_content = utils.read_docx(docx_file)
                                response_data[original_name] = {"content": resume_content, "file_path": file_name}
                        except Exception as e:
                            response_data[original_name] = {"content": f"Error reading DOCX file: {str(e)}", "file_path": file_name}

                    # Process DOC files
                    elif file_name.endswith(".doc"):
                        resume_content, _ = utils.read_doc(file_path)
                        response_data[original_name] = {"content": resume_content, "file_path": file_name}
                
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
                            logger.error(f"Error storing {resume_name} in database: {str(e)}")
                            conn.rollback()
                    else:
                        logger.warning(f"Skipping {resume_name} - No content or blob data available")

                    upload_resume_file(filename=file_name, directory_path=extract_path)
                    logger.info(f"Uploaded {file_name} to S3 Bucket")

                    # Clean up the extracted file
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.error(f"Error removing temporary file {file_path}: {str(e)}")

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
                        response_data[file_name] = {"content": str(e)}
                
                elif file_extension == "doc":
                    resume_content, _ = utils.read_doc(file_path)
                    response_data[file_name] = {"content": resume_content}
                
                else:
                    logger.warning(f"Unsupported file type: {file_extension}")
                    # response_data[file_name] = {
                    #     "error": "Unsupported file type. Supported formats: .pdf, .d ocx, .doc, .txt, .zip, .rar"
                    # }
                    pass
                # Add file path to the response data
                response_data[file_name]["file_path"] = f"{unique_id}_{resume_name}"

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
                        logger.error(f"Error removing temporary file {file_path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            response_data[file.filename] = {
                "error": str(e)
            }
             
    response_data = await process_resumes_async(response_data, processed_jd)

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

    if cur is not None:
        cur.close()
        logger.info("Database cursor closed.")

    if conn is not None:
        conn.close()
        logger.info("Database connection closed.")

    # Clean up the unique directory after processing
    shutil.rmtree(extract_path)
    return response_data


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
 
    except FileNotFoundError:
        logger.error(f"PDF file not found: {file_path}")
        raise HTTPException(status_code=404, detail="PDF file not found")
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Optional: Clean up the downloaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up file {file_path}: {cleanup_error}")
