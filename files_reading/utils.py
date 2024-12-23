from PyPDF2 import PdfReader
from docx import Document
import win32com.client
from Logging_folder.logger import logger
import os
import io
import re


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


def read_pdf(file: io.BytesIO):
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
    pdf_reader = PdfReader(file)
    
    # Initialize an empty string to store extracted text
    extracted_text = ""
    
    # Iterate through each page of the PDF
    for page in pdf_reader.pages:
        # Extract text from the current page and append to the result
        extracted_text += page.extract_text()
    
    # Return the extracted text with leading and trailing whitespaces removed
    return clean_text(extracted_text.strip())

def read_docx(file: io.BytesIO):
    """Extract text from a DOCX file."""
    document = Document(file)
    extracted_text = ""
    for paragraph in document.paragraphs:
        extracted_text += paragraph.text + "\n"
    return clean_text(extracted_text.strip())



def read_doc(file_path: str):
    """
    Extract text from a DOC file using COM automation (Windows only).
    """
    word = None
    try:
        # First read the file as binary for blob storage
        with open(file_path, "rb") as doc_file:
            data = doc_file.read()
            blob_data = None

        # Now extract text using Word automation
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(os.path.abspath(file_path))
        text = doc.Content.Text
        doc.Close(False)
        resume_content = clean_text(text)
        return resume_content, blob_data
    except Exception as e:
        logger.error(f"Error reading DOC file: {str(e)}")     
        return f"Error reading DOC file: {str(e)}", None
    finally:
        if word is not None:
            try:
                word.Quit()
            except:
                pass  # Ignore errors during Word cleanup

def read_txt(file: io.BytesIO):
    """Extract text from a plain text file."""
    try:
        contents = file.read()
        return clean_text(contents.decode("utf-8").strip())
    except Exception as e:
        logger.error(f"Error processing TXT file: {str(e)}")
        return f"Error processing TXT file: {str(e)}"


# def retrieve_resume_blob(unique_id):
#     conn = None
#     try:
#         # Connect to the PostgreSQL server
#         conn = psycopg2.connect(
#             host=hostname,
#             dbname=database,
#             user=username,
#             password=password,
#             port=port_id
#         )

#         # Create a cursor
#         cur = conn.cursor()

#         # SQL query to retrieve the BLOB data
#         cur.execute(
#             "SELECT unique_id, resume_name, blob_data FROM resume_table WHERE unique_id = %s", 
#             (unique_id,)
#         )

#         # Fetch the result
#         result = cur.fetchone()

#         if result:
#             unique_id, resume_name, blob_data = result
            
#             # Define the output directory (you can modify this path as needed)
#             output_dir = r"extracted_files"
            
#             # Create the directory if it doesn't exist
#             import os
#             os.makedirs(output_dir, exist_ok=True)

#             # Full path for the output file
#             output_path = os.path.join(output_dir, f"{unique_id}_{resume_name}")

#             # Write the BLOB data to a file
#             with open(output_path, 'wb') as file:
#                 file.write(blob_data)

#             print(f"Resume retrieved and saved to: {output_path}")
#             return output_path
#         else:
#             print(f"No resume found with unique_id: {unique_id}")
#             return None

#     except (Exception, psycopg2.DatabaseError) as error:
#         print(f"Error retrieving resume: {error}")
#     finally:
#         if cur is not None:
#             cur.close()
#             print('Cursor closed.')

#         if conn is not None:
#             conn.close()
#             print('Database connection closed.')

#     return output_path