import logging

# Initialize a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a file handler for logging
file_handler = logging.FileHandler('logger.log')
file_handler.setLevel(logging.INFO)

# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)