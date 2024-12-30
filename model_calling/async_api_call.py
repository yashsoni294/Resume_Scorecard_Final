from templates.templates import TEMPLATES
from model_calling.openai_call import get_conversation_openai
import asyncio
from files_reading import utils
from Logging_folder.logger import logger

conversation_resume = get_conversation_openai(TEMPLATES["resume"])
conversation_score = get_conversation_openai(TEMPLATES["score"])

async def run_in_executor(func, *args, **kwargs):
    """
    Run a synchronous function in a separate thread or process, making it asynchronous.

    This utility allows blocking (synchronous) functions to be run in the background, 
    avoiding the blocking of the event loop in asynchronous applications.

    Args:
        func (callable): The synchronous function to run in the executor.
        *args: The positional arguments to pass to the function.
        **kwargs: The keyword arguments to pass to the function.

    Returns:
        The result of the function once it completes.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

async def async_key_aspect_extractor(filename, data):
    """
    Asynchronously extract key aspects from the resume content using a synchronous function in an executor.

    This function runs the key aspect extraction process for a resume asynchronously to avoid blocking the event loop.
    It leverages an executor to run a synchronous function (`conversation_resume`) in the background to extract 
    relevant key features from the provided resume content.

    Args:
        filename (str): The name of the file being processed.
        data (dict): A dictionary containing the resume content under the "content" key.

    Returns:
        tuple: A tuple containing the filename and the extraction result. If extraction is successful, the result 
               contains the extracted key aspects, otherwise, it returns None in case of an error.
    """
    try:
        logger.info(f"Extracting key aspects for: {filename} - START")
        # Assuming conversation_resume is synchronous
        result = await run_in_executor(conversation_resume, {"resume_text": data["content"]})
        return filename, result
    except Exception as e:
        logger.exception(f"Error in key aspect extraction for {filename}: {e}")
        return filename, None

async def async_resume_scorer(filename, key_aspect, job_description):
    """
    Asynchronously score a resume based on its key aspects and a provided job description.

    This function calculates a score for a resume by comparing its key aspects with the provided job description.
    It uses a synchronous function (`conversation_score`) for scoring, which is run asynchronously in an executor 
    to avoid blocking the event loop.

    Args:
        filename (str): The name of the resume file being processed.
        key_aspect (str): The key aspects extracted from the resume content.
        job_description (str): The job description text used to compare against the resume's key aspects.

    Returns:
        tuple: A tuple containing the filename and the result of the scoring. If an error occurs, the result will 
        be `None`.
    """
    try:
        logger.info(f"Scoring resume: {filename} - START")
        # Assuming conversation_score is synchronous
        result = await run_in_executor(conversation_score, {
            "resume_text": key_aspect,
            "job_description": job_description
        })
        return filename, result
    except Exception as e:
        logger.exception(f"Error in scoring for {filename}: {e}")
        return filename, None

async def process_resumes_async(response_data, job_description):
    """
    Asynchronously process resumes to extract key aspects and calculate scores.

    This function performs two key operations asynchronously for each resume in the provided `response_data`:
    1. **Key Aspect Extraction**: It extracts key features from each resume's content.
    2. **Scoring**: It calculates a score for each resume based on the extracted key aspects and the provided job description.

    Both operations are performed concurrently using asynchronous tasks to improve efficiency.

    Args:
        response_data (dict): A dictionary where keys are filenames and values contain resume data (including the content).
        job_description (str): The job description used to calculate the resume score.

    Returns:
        dict: The updated `response_data` dictionary with additional fields:
            - 'key_feature': The extracted key aspects of each resume.
            - 'score': The calculated score for each resume based on the job description.
    """
    # Create async tasks for key aspect extraction
    key_aspect_tasks = [
        asyncio.create_task(async_key_aspect_extractor(filename, data)) 
        for filename, data in response_data.items()
    ]
    
    # Wait for all key aspect extraction tasks to complete
    key_aspects = await asyncio.gather(*key_aspect_tasks, return_exceptions=True)
    key_aspects_dict = {filename: result for filename, result in key_aspects if result is not None}
    
    # Create async tasks for scoring
    scoring_tasks = [
        asyncio.create_task(async_resume_scorer(filename, key_aspects_dict.get(filename, ""), job_description)) 
        for filename in response_data.keys()
    ]
    
    # Wait for all scoring tasks to complete concurrently
    scores = await asyncio.gather(*scoring_tasks, return_exceptions=True)
    scores_dict = {filename: result for filename, result in scores if result is not None}
    
    # Update response_data with results
    for filename in response_data.keys():
        response_data[filename]['key_feature'] = utils.clean_text(key_aspects_dict.get(filename, ""))
        response_data[filename]['score'] = utils.extract_first_two_digit_number(scores_dict.get(filename, ""))
    
    return response_data