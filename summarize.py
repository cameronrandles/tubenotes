# Google Model Setup
import os
import google.generativeai as genai
from structured_output import response_schema
import json

# Configure API key
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize LLM
model = genai.GenerativeModel("gemini-1.5-flash-latest")

def summarize_transcript(transcript):
    # Limit transcript length to avoid token limits
    max_chars = 5000
    truncated = transcript[:max_chars]

    prompt = f"""Summarize the following text using two bullets per section.
    {truncated}
    """

    generation_config = genai.GenerationConfig(
    response_mime_type="application/json",
    response_schema=response_schema
    )

    result = model.generate_content(prompt, generation_config=generation_config)

    # Parse the result text as JSON
    try:
        result_dict = json.loads(result.text)
        return result_dict
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None
