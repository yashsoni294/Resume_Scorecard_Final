from PyPDF2 import PdfReader
from docx import Document
import win32com.client
from Logging_folder.logger import logger
import os
import io
import re
import zipfile
from aws_s3_connect.connect import upload_resume_file
from Postgres_connect.pgadmin_connect import pgadmin_connect, pgadmin_disconnect
from Postgres_connect.query_insertion import insert_resume_data
import uuid


def extract_first_two_digit_number(text):
    """
    Extract the first two-digit number from the input text.

    Args:
        text (str): The input text.

    Returns:
        str or None: The first two-digit number as a string, or None if no two-digit number is found.
    """
    # Use regex to find the first two-digit number
    match = re.search(r'\b\d{2}\b', text)
    return match.group() if match else "0"

def clean_text(text):
    # To Remove HTML tags
    text = re.sub(r'<[^>]*?>', ' ', text)
    # To Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', ' ', text)
    # To Remove special characters
    text = re.sub(r'[^a-zA-Z0-9 ]', ' ', text)
    # To Replace multiple spaces with a single space
    text = re.sub(r'\s{2,}', ' ', text)
    # To Trim leading and trailing whitespace
    text = text.strip()
    # To Remove extra whitespace
    text = ' '.join(text.split())
    return text


def read_pdf(file_path):
    """
    Extract text from a PDF file using PyPDF2 library.

    This function takes a PDF file as a BytesIO object and extracts 
    the text content from all pages of the PDF.

    Args:
        file (io.BytesIO): A file-like object containing the PDF data.

    Returns:
        str: A string containing the extracted text from all pages of the PDF,
             with leading and trailing whitespaces removed.

    Raises:
        Exception: If there are issues reading the PDF file.
    """
    # Create a PDF reader object from the input file
    try:
        with open(file_path, "rb") as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            
            # Initialize an empty string to store extracted text
            extracted_text = ""
            
            # Iterate through each page of the PDF
            for page in pdf_reader.pages:
                # Extract text from the current page and append to the result
                extracted_text += page.extract_text()
            
            # Return the extracted text with leading and trailing whitespaces removed
        return clean_text(extracted_text.strip())
    except Exception as e:
        logger.exception(f"Error reading PDF file: {str(e)}")
        return f"Error reading PDF file: {str(e)}"

def read_docx(file_path):
    """Extract text from a DOCX file."""
    try:
        with open(file_path, "rb") as docx_file:
            document = Document(docx_file)
            extracted_text = ""
            for paragraph in document.paragraphs:
                extracted_text += paragraph.text + "\n"
            return clean_text(extracted_text.strip())
    except Exception as e:
            logger.exception(f"Error reading DOCX file: {str(e)}")
            return f"Error reading PDF file: {str(e)}"



def read_doc(file_path: str):
    """
    Extract text from a DOC file using COM automation (Windows only).
    """
    word = None
    try:
        # Now extract text using Word automation
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(os.path.abspath(file_path))
        text = doc.Content.Text
        doc.Close(False)
        resume_content = clean_text(text)
        return resume_content
    except Exception as e:
        logger.exception(f"Error reading DOC file: {str(e)}")     
        return f"Error reading DOC file: {str(e)}", None
    finally:
        if word is not None:
            try:
                word.Quit()
            except:
                pass  # Ignore errors during Word cleanup

def read_txt(file_path):
    """Extract text from a plain text file."""
    try:
        with open(file_path, "rb") as txt_file:
            contents = txt_file.read()
            return clean_text(contents.decode("utf-8").strip())
    except Exception as e:
        logger.exception(f"Error processing TXT file: {str(e)}")
        return f"Error processing TXT file: {str(e)}"
    

async def process_zip_file(file, extract_path):
    """
    Process a ZIP file containing resumes.

    This function extracts the contents of the ZIP file, reads the text from each resume file,
    stores the extracted text in the database, and uploads the processed resumes to an S3 bucket.

    Args:
        file (bytes): The ZIP file data as bytes.
        extract_path (str): The path to extract the contents of the ZIP file.

    Returns:
        dict: A dictionary containing the extracted text and file paths of each resume file.
    """
    zip_response_data = {}
    conn, cur = pgadmin_connect()
    zip_data = await file.read()
    zip_file = io.BytesIO(zip_data)
    extracted_files = []
    with zipfile.ZipFile(zip_file, 'r') as z:
        # Extract files from the ZIP archive
        file_name_list = z.namelist()
        for original_file_name in file_name_list:
            # Generate a unique file name for each file in the ZIP archive
            id = str(uuid.uuid4())
            unique_file_name = f"{id}_{original_file_name}"
            z.extract(original_file_name, extract_path)
            # Rename the extracted file to its unique name
            os.rename(os.path.join(extract_path, original_file_name),
                        os.path.join(extract_path, unique_file_name))
            extracted_files.append(unique_file_name)

    # Process each extracted file
    for index, file_name in enumerate(extracted_files):
        original_name = file_name_list[index]
        logger.info(f"Reading file: {original_name}")
        file_path = os.path.join(extract_path, file_name)
        unique_id = re.match(r'^[a-f0-9\-]+', file_name).group()

        # Process PDF files
        if file_name.endswith(".pdf"):
            resume_content = read_pdf(file_path)
            zip_response_data[original_name] = {"content": resume_content}
                    
        # Process TXT files
        elif file_name.endswith(".txt"):
            resume_content = read_txt(file_path)
            zip_response_data[original_name] = {"content": resume_content}

        # Process DOCX files
        elif file_name.endswith(".docx"):
            resume_content = read_docx(file_path)
            zip_response_data[original_name] = {"content": resume_content}

        # Process DOC files
        elif file_name.endswith(".doc"):
            resume_content = read_doc(file_path)
            zip_response_data[original_name] = {"content": resume_content}
                    
        zip_response_data[original_name]["file_path"] = file_name
                
        # If resume content is extracted, store it in the database
        if resume_content is not None:
            insert_resume_data(unique_id, original_name, resume_content)
        else:
            logger.warning(f"Skipping {original_name} - No content or blob data available")

        # Upload the processed resume file to S3
        upload_resume_file(filename=file_name, directory_path=extract_path)
        logger.info(f"Uploaded {file_name} to S3 Bucket")

        # Clean up the extracted file
        cleanup_file(file_path)

    # Close the database cursor and connection
    pgadmin_disconnect(conn, cur)
    
    return zip_response_data

def cleanup_file(file_path):
    """Delete the temporary file after processing."""
    # Clean up the extracted file
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.exception(f"Error removing temporary file {file_path}: {str(e)}")