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








# # Google Model Setup
# import os
# from langchain_google_vertexai import ChatVertexAI
# from structured_output import json_schema


# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "tubenotes-2e5836a7c65a.json"

# # Initialize the model
# llm = ChatVertexAI(
#     project_id="tubenotes",
#     location='us-central1',
#     model="gemini-1.5-flash-002"
# )

# response = llm.invoke("What is the capital of France?")
# print(response)

# Create an endpoint for model



# In many cases, especially when the amount of text is large compared to the size of the model's context window,
# it can be helpful (or necessary) to break up the summarization task into smaller components.

# from langchain.prompts import PromptTemplate
# from langchain.chains.summarize import load_summarize_chain
# from langchain.text_splitter import RecursiveCharacterTextSplitter

# def summarize_transcript(transcript):
#     text_splitter = RecursiveCharacterTextSplitter(separators=["\n\n", "\n"], chunk_size=10000, chunk_overlap=500)
#     docs = text_splitter.create_documents([transcript])

#     num_docs = len(docs)
#     num_tokens_first_doc = len(docs[0].page_content.split())

#     print(f"We have {num_docs} documents and the first one has {num_tokens_first_doc} tokens")

#     map_prompt = """
#     Write a concise summary of the following:
#     "{text}"
#     """
#     map_prompt_template = PromptTemplate(template=map_prompt, input_variables=["text"])

#     combine_prompt = """
#     Write a concise summary of the following text delimited by triple slashes.
#     ///{text}///

#     Always include descriptive headers in your response.

#     Never include asterisks in your response.
#     Never begin your response with 'here is..'
#     Never include promotions or advertisements in your response.
#     Never include repetitive statements in your response.
    
#     Always provide your response in the following format:
#     Intro to Python
#     - Python is a popular programming language
#     - It was created by Guido van Rossum, and released in 1991

#     Use Cases
#     - Python can be used on a server to create web applications
#     - Python can be used alongside software to create workflows

#     Why Python?
#     - Python works on different platforms (Windows, Mac, Linux, Raspberry Pi, etc)
#     - Python has a simple syntax similar to the English language
#     """

#     combine_prompt_template = PromptTemplate(template=combine_prompt, input_variables=["text"])
    
#     summary_chain = load_summarize_chain(llm=llm,
#                                          chain_type='map_reduce',
#                                          map_prompt=map_prompt_template,
#                                          combine_prompt=combine_prompt_template,
#                                          # verbose=True
#                                          )

#     output = summary_chain.invoke(docs)

#     return output['output_text']



# # Groq Model Setup
# import os
# from langchain_groq import ChatGroq
# from structured_output import json_schema

# # Set Groq API key for development
# # os.environ["GROQ_API_KEY"] = "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"

# # Langchain Structured Output
# llm = ChatGroq(model="llama-3.3-70b-versatile")

# def summarize_transcript(transcript):
#     prompt = f"""
#              Summarize the following text in the provided JSON schema.
#              {transcript}
#              """
    
#     structured_llm = llm.with_structured_output(json_schema)
    
#     result = structured_llm.invoke(prompt)    
#     return result