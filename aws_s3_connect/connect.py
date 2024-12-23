from dotenv import load_dotenv
import boto3
import os
from botocore.exceptions import NoCredentialsError, ClientError
from Logging_folder.logger import logger

load_dotenv()
# AWS Credentials from environment variables
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')  # Default region if not specified


def create_s3_client():
    """
    Create and return an S3 client with configured credentials
    
    :return: Boto3 S3 client
    """
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

def upload_to_s3(local_file_path, bucket_name='yash-soni-db', s3_folder='resume_files/'):
    """
    Upload a file to an S3 bucket
    
    :param local_file_path: Path to the local file to upload
    :param bucket_name: Name of the S3 bucket
    :param s3_folder: Folder path within the bucket (include trailing '/')
    :return: True if file was uploaded, else False
    """
    # Create an S3 client
    s3 = create_s3_client()
    
    try:
        # Get the filename from the path
        filename = os.path.basename(local_file_path)
        
        # Construct the full S3 key (path) 
        s3_key = os.path.join(s3_folder, filename)
        
        # Upload the file
        s3.upload_file(local_file_path, bucket_name, s3_key)
        logger.info(f"Successfully uploaded {filename} to {bucket_name}/{s3_key}")
        return True
    
    except FileNotFoundError:
        logger.error(f"The file {local_file_path} was not found")
        return False
    
    except NoCredentialsError:
        logger.error("Credentials not available")
        return False
    
    except ClientError as e:
        logger.error(f"An error occurred: {e}")
        return False

def download_from_s3(filename, bucket_name='yash-soni-db', s3_folder='resume_files/', 
                     local_dir='extracted_files/'):
    """
    Download a specific file from S3 bucket
    
    :param filename: Name of the file to download
    :param bucket_name: Name of the S3 bucket
    :param s3_folder: Folder path within the bucket (include trailing '/')
    :param local_dir: Local directory to save the downloaded file
    :return: Path to the downloaded file or None if download fails
    """
    # Create an S3 client
    s3 = create_s3_client()
    
    # Create local directory if it doesn't exist
    os.makedirs(local_dir, exist_ok=True)
    
    try:
        # Construct the full S3 key (path)
        s3_key = os.path.join(s3_folder, filename)
        
        # Local file path
        local_file_path = os.path.join(local_dir, filename)
        
        # Download the file
        s3.download_file(bucket_name, s3_key, local_file_path)
        
        logger.info(f"Successfully downloaded {filename} to {local_file_path}")
        return local_file_path
    
    except ClientError as e:
        logger.error(f"Error downloading {filename}: {e}")
        return None


def upload_resume_file(filename, directory_path='extracted_files'):
    """
    Upload a specific file from a directory to S3
    
    :param filename: Name of the file to upload
    :param directory_path: Path to the directory containing the file
    :return: True if file was uploaded successfully, False otherwise
    """
    # Construct full file path
    file_path = os.path.join(directory_path, filename)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        logger.error(f"File {filename} not found in {directory_path}")
        return False
    
    # Check if it's a file (not a directory)
    if not os.path.isfile(file_path):
        logger.error(f"{filename} is not a file")
        return False
    
    # Attempt to upload the file
    return upload_to_s3(file_path)