from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import re
import uuid
import shutil
from files_reading import utils
from fastapi.middleware.cors import CORSMiddleware
import base64
import os
from templates.templates import TEMPLATES
from model_calling.openai_call import get_conversation_openai
from model_calling.async_api_call import run_in_executor, process_resumes_async
from aws_s3_connect.connect import upload_resume_file, download_from_s3
from Logging_folder.logger import logger
from Postgres_connect.query_insertion import insert_resume_data, update_resume_data
from dotenv import load_dotenv
from files_reading.utils import process_zip_file, cleanup_file

# Load environment variables from .env file
load_dotenv()

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
    # allow_origins= origins,  # List of allowed origins
    allow_origins= ["*"],  # List of allowed origins
    allow_credentials=True,  # Allow cookies and credentials
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define the endpoint for uploading files and processing resumes
@app.post("/upload-files/")
async def upload_files(job_description: str, files: list[UploadFile] = File(...)):
    """
    Upload and process multiple files along with a job description. This endpoint:
    - Accepts a job description and a list of files.
    - Processes each file based on its type (PDF, TXT, DOCX and DOC.), extracts content, and stores it.
    - Handles ZIP files by extracting and processing each file within the archive.
    - Uploads processed files to an S3 bucket and inserts resume data into a database.
    - Applies job description context to resumes and updates key features and scores in the database.
    
    Args:
        job_description (str): A job description to extract context for resume matching.
        files (list[UploadFile]): A list of files to be processed, which may include resumes in various formats.

    Returns:
        dict: A dictionary containing extracted content, file paths, and processing details for each file.
    """

    # Initialize an empty dictionary to store response data
    response_data = {}

    # Get conversation context for job description using OpenAI model
    conversation_jd = get_conversation_openai(TEMPLATES["job_description"])
    # Extract the key features from the job description
    jd_response = conversation_jd({"job_description_text": job_description})
    processed_jd = jd_response
    logger.info("Processing the Job Description...\n")

    # Create a unique directory for each upload session
    session_id = str(uuid.uuid4())
    extract_path = f"extracted_files_{session_id}"
    
    # Create the unique directory for the session
    os.makedirs(extract_path, exist_ok=True)

    # Iterate over each file uploaded
    for file in files:
        try:
            # Fallback to file extension if MIME type is not reliable
            file_extension = file.filename.split(".")[-1].lower()

            # Generate a unique file name using UUID
            id = str(uuid.uuid4())
            file_name = file.filename
            unique_filename = f"{id}_{file_name}"
            file_path = os.path.join(extract_path, unique_filename)

            # Check if the file is a ZIP archive
            if file.content_type == "application/zip" or file_extension == "zip":
                # Dictionary will be returned of Zip files data
                zip_response_data = await process_zip_file(file, extract_path) 
                # Adding the Zip files data to the response data
                response_data.update(zip_response_data) 

            # Process non-ZIP files
            else:
                # Save individual file to extracted_files directory
                file_content = await file.read()
                
                with open(file_path, "wb") as f:
                    f.write(file_content)

                logger.info(f"Reading file: {file_name}")
                # Process based on file type
                if file_extension == "pdf":
                    resume_content = utils.read_pdf(file_path)
                    response_data[file_name] = {"content": resume_content}
                
                elif file_extension == "txt":
                    resume_content = utils.read_txt(file_path)
                    response_data[file_name] = {"content": resume_content}
                
                elif file_extension == "docx":
                    resume_content = utils.read_docx(file_path)
                    response_data[file_name] = {"content": resume_content}
                
                elif file_extension == "doc":
                    resume_content = utils.read_doc(file_path)
                    response_data[file_name] = {"content": resume_content}
                
                else:
                    logger.warning(f"Unsupported file type: {file_extension}")

                # Add file path to the response data
                response_data[file_name]["file_path"] = f"{id}_{file_name}"

                # Upload the processed resume file to S3
                upload_resume_file(filename = f"{id}_{file_name}", directory_path=extract_path)
                logger.info(f"Uploaded {file_name} to S3 Bucket")
            
                # SQL query to insert data into the database.
                insert_resume_data(id, file_name, resume_content) 
            
                # Clean up the extracted file
                cleanup_file(file_path)

        except Exception as e:
            logger.exception(f"Error processing file: {str(e)}")
             
    # Process the resumes asynchronously
    response_data = await process_resumes_async(response_data, processed_jd)

    # Update the database with key features and scores for each resume
    for key, value in response_data.items():
        resume_key_aspect = value["key_feature"]
        score = value["score"]
        unique_id = re.match(r'^[a-f0-9\-]+', value["file_path"]).group()
        resume_name = key

        update_resume_data(unique_id, resume_key_aspect, score, resume_name)

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
        # Clean up the downloaded file
        cleanup_file(file_path)
