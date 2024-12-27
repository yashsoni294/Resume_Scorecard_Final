from templates.templates import TEMPLATES
from model_calling.openai_call import get_conversation_openai
import asyncio
from files_reading import utils
from Logging_folder.logger import logger

conversation_resume = get_conversation_openai(TEMPLATES["resume"])
conversation_score = get_conversation_openai(TEMPLATES["score"])

async def run_in_executor(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

async def async_key_aspect_extractor(filename, data):
    try:
        logger.info(f"Extracting key aspects for: {filename} - START")
        # Assuming conversation_resume is synchronous
        result = await run_in_executor(conversation_resume, {"resume_text": data["content"]})
        return filename, result
    except Exception as e:
        logger.exception(f"Error in key aspect extraction for {filename}: {e}")
        return filename, None

async def async_resume_scorer(filename, key_aspect, job_description):
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