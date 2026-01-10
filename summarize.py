# Google Model Setup
import google.generativeai as genai
from structured_output import response_schema
import json

# Initialize LLM
model = genai.GenerativeModel("gemini-2.5-flash")

def summarize_transcript(transcript):
    prompt = f"""Summarize the following text using two bullets per section.
    {transcript}
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
