# topic_extraction.py

import os
import json
import argparse
import time
from string import Template
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from google.api_core import exceptions as google_exceptions

# Initialize GenerativeModel
model = GenerativeModel("gemini-1.5-pro-002")

def retry_with_backoff(func, *args, **kwargs):
    """
    Retries a function with exponential backoff in case of ResourceExhausted exception.

    Args:
        func (callable): The function to retry.
        *args: Arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The result of the function call.
    """
    max_retries = 3
    retry_delay = 10

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except google_exceptions.ResourceExhausted as e:
            if attempt < max_retries - 1:
                print(f"Resource exhausted. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                raise e

def extract_main_topics(pdf_path: str, n: int) -> list:
    """
    Extracts the main topics from a PDF document and returns them as a list of dictionaries.

    Args:
        pdf_path (str): The path to the PDF file.
        n (int): The number of topics to extract.

    Returns:
        list: A list of topics, each topic is a dictionary with keys 'title', 'summary', and 'significance'.
    """
    response_schema = {
        "type": "object",
        "properties": {
            "main_topic": {"type": "string"},
            "paper_length": {"type": "integer"},
            "subtopics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "length": {"type": "integer"},
                        "summary": {"type": "string"},
                        "relation_to_main_topic": {"type": "string"}
                    },
                    "required": ["title", "length", "summary", "relation_to_main_topic"]
                },
            }
        },
        "required": ["main_topic", "paper_length", "subtopics"]
    }

    with open(pdf_path, "rb") as pdf_file:
        document = Part.from_data(
            mime_type="application/pdf",
            data=pdf_file.read()
        )

    # Load the prompt template from the file
    prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompts', 'topic_extraction_prompt.txt')
    with open(prompt_file_path, 'r') as file:
        prompt_template = Template(file.read())

    max_attempts = 3
    for attempt in range(max_attempts):
        # Fill in the template with the required variables
        prompt = prompt_template.safe_substitute(n=n)

        def generate_content():
            return model.generate_content(
                [document, prompt],
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    max_output_tokens=1024,
                    temperature=1.0,
                ),
            )

        response = retry_with_backoff(generate_content)
        topics_json = response.text

        try:
            topics = json.loads(topics_json)
            if len(topics.get('subtopics', [])) == n:
                return topics
            else:
                print(f"Attempt {attempt + 1}: Extracted {len(topics.get('subtopics', []))} subtopics instead of {n}. Retrying...")
        except json.JSONDecodeError as e:
            print(f"Attempt {attempt + 1}: Failed to parse the topics. The AI model's response was not valid JSON.")
            print("AI Model's Response:")
            print(topics_json)

    print(f"Failed to extract exactly {n} subtopics after {max_attempts} attempts.")
    return {}

def main():
    parser = argparse.ArgumentParser(description="Extract main topics from a PDF document.")
    parser.add_argument('pdf_path', type=str, help='Path to the PDF file.')
    parser.add_argument('--num_topics', type=int, default=3, help='Number of topics to extract.')
    parser.add_argument('--output', type=str, default='topics.json', help='Output JSON file for topics.')

    args = parser.parse_args()

    topics = extract_main_topics(args.pdf_path, args.num_topics)
    if topics:
        with open(args.output, 'w') as f:
            json.dump(topics, f, indent=4)
        print(f"Extracted topics saved to {args.output}")
    else:
        print("No topics were extracted.")

if __name__ == "__main__":
    main()

# Example usage:
# python topic_extraction.py ./data/research_paper.pdf --num_topics 3 --output ./data/topics.json
