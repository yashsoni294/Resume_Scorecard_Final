import os
import boto3
from botocore.exceptions import NoCredentialsError
from dotenv import load_dotenv
from Logging_folder.logger import logger

load_dotenv()

# DigitalOcean Space Credentials from environment variables
DO_ACCESS_KEY_ID = os.getenv('DO_ACCESS_KEY_ID')
DO_SECRET_ACCESS_KEY = os.getenv('DO_SECRET_ACCESS_KEY')
DO_REGION = os.getenv('DO_REGION', 'blr1')  # Default region if not specified


def create_digitalocean_space_client():
    """
    Create and return a DigitalOcean Space client with configured credentials

    :return: Boto3 S3 client
    """
    return boto3.client(
        's3',
        endpoint_url=f'https://{DO_REGION}.digitaloceanspaces.com',
        aws_access_key_id=DO_ACCESS_KEY_ID,
        aws_secret_access_key=DO_SECRET_ACCESS_KEY
    )


def upload_to_digitalocean_space(local_file_path, bucket_name='yash-soni-db', space_folder='resume_files/'):
    """
    Upload a file to a DigitalOcean Space

    :param local_file_path: Path to the local file to upload
    :param bucket_name: Name of the DigitalOcean Space
    :param space_folder: Folder path within the Space (include trailing '/')
    :return: True if file was uploaded, else False
    """
    # Create a DigitalOcean Space client
    s3 = create_digitalocean_space_client()

    try:
        # Get the filename from the path
        filename = os.path.basename(local_file_path)

        # Construct the full Space key (path)
        space_key = os.path.join(space_folder, filename)

        # Upload the file with public-read ACL
        s3.upload_file(local_file_path, bucket_name, space_key, ExtraArgs={'ACL': 'public-read'})
        cdn_url = f'https://{bucket_name}.{DO_REGION}.cdn.digitaloceanspaces.com/{space_key}'
        logger.info(f"Successfully uploaded {filename} to {bucket_name}/{space_key}")
        return cdn_url

    except FileNotFoundError as e:
        logger.exception(f"The file {local_file_path} was not found: {e}")
        return False

    except NoCredentialsError as e:
        logger.exception(f"Credentials not available: {e}")
        return False

    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        return False


def upload_resume_file_DO(filename, directory_path='extracted_files'):
    """
    Upload a specific file from a directory to a DigitalOcean Space

    :param filename: Name of the file to upload
    :param directory_path: Path to the directory containing the file
    :return: True if file was uploaded successfully, False otherwise
    """
    # Construct full file path
    file_path = os.path.join(directory_path, filename)

    try:
        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(f"File {filename} not found in {directory_path}")
            return False

        # Check if it's a file (not a directory)
        if not os.path.isfile(file_path):
            logger.error(f"{filename} is not a file")
            return False

        # Attempt to upload the file
        return upload_to_digitalocean_space(file_path)

    except Exception as e:
        # Catch any exception and log the error
        logger.exception(f"An error occurred while uploading {filename}: {e}")
        return False
