from langchain_core.prompts import PromptTemplate
import openai
from dotenv import load_dotenv
import os

# Load API Key
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = API_KEY

def get_conversation_openai(template, model="gpt-4o-mini", temperature=0.1, max_tokens=None):

    """
    Creates a function that interacts with the OpenAI model based on a provided template.
    
    Args:
        template (str): A string template for generating prompts dynamically. The template should use placeholders
                        that can be filled with dynamic input values.
        model (str, optional): The name of the OpenAI model to use for generating responses. Defaults to "gpt-4o-mini".
        temperature (float, optional): Sampling temperature to control the randomness of the response. 
                                       Lower values make output more focused and deterministic. Defaults to 0.1.
        max_tokens (int, optional): The maximum number of tokens to include in the response. Defaults to None, 
                                    allowing the model to determine the length.

    Returns:
        function: A callable function that takes a dictionary of inputs, formats the prompt based on the template,
                  and interacts with the OpenAI model to generate a response.

    """
 
    # Define a nested function to handle API interaction
    def call_openai_model(inputs):
        """
        Invokes the OpenAI model using the provided template and inputs.
        
        Args:
            inputs (dict): A dictionary containing values for the placeholders in the template.

        Returns:
            str: The content of the response generated by the OpenAI model.
        """
        # Generate the prompt by formatting the template with the provided inputs
        prompt = PromptTemplate.from_template(template).format(**inputs)
        # Call the OpenAI Chat API to generate a response
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "system", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        # Extract and return the content of the response
        return response["choices"][0]["message"]["content"]
    
    # Return the nested function for reuse
    return call_openai_model