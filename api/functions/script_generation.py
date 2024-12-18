# script_generation.py

import os
import json
import argparse
import time
from pathlib import Path
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from google.api_core import exceptions as google_exceptions
from string import Template

# Initialize GenerativeModel
model = GenerativeModel("gemini-1.5-pro-002")

def retry_with_backoff(func, *args, max_retries=5, initial_delay=1, backoff_factor=2, **kwargs):
    """
    Retries a function with exponential backoff in case of specific exceptions.

    Args:
        func (callable): The function to retry.
        *args: Arguments to pass to the function.
        max_retries (int): Maximum number of retry attempts.
        initial_delay (int): Initial delay in seconds before retrying.
        backoff_factor (int): Factor by which the delay increases.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The result of the function call.

    Raises:
        Exception: If all retry attempts fail.
    """
    retry_exceptions = (
        google_exceptions.ResourceExhausted,
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
        google_exceptions.InternalServerError,
    )
    
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except retry_exceptions as e:
            if attempt < max_retries - 1:
                print(f"Error: {e}. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                print(f"Max retries reached. Last error: {e}")
                raise

            
def compile_transcripts(transcripts_dir: Path) -> str:
    """
    Compiles existing transcripts from the specified directory.

    Args:
        transcripts_dir (Path): The directory containing transcript files.

    Returns:
        str: All compiled transcripts as a single string.
    """
    all_transcripts = ""

    # for filename in sorted(transcripts_dir.glob("*.txt")):
    #     title = filename.stem.replace("-", " ")

    #     with open(filename, "r") as file:
    #         content = file.read()

    #     all_transcripts += f"# {title}\n\n{content}\n\n{'='*50}\n\n"
    
    # use bitesized.txt as a fallback
    if len(all_transcripts) == 0:
        with open("data/transcripts/bitesized.txt", "r") as file:
            all_transcripts = file.read()

    if len(all_transcripts) == 0:
        print("No transcripts found. Proceeding without previous transcripts.")
        # Optionally, set all_transcripts to a default value or leave it empty.

    return all_transcripts


def generate_podcast_section(pdf_path: str, topic: dict, language: str, transcripts_dir: Path, prompt_file: str, section_name: str, previous_content: str = "") -> str:
    """
    Generates a section of the podcast script based on the selected topic and language.

    Args:
        pdf_path (str): The path to the PDF file.
        topic (dict): The selected topic for the podcast (None for entire paper).
        language (str): The language for the podcast.
        transcripts_dir (Path): The directory containing transcript files.
        prompt_file (str): The path to the prompt file for this section.
        section_name (str): The name of the section being generated.
        previous_content (str): The content of previously generated sections.

    Returns:
        str: The generated section of the podcast script.
    """
    all_transcripts = compile_transcripts(transcripts_dir)

    # Load the prompt template from the file
    with open(prompt_file, 'r') as file:
        prompt_template = Template(file.read())

    # Fill in the template with the required variables
    prompt_vars = {
        'all_transcripts': all_transcripts,
        'language': language,
        'previous_content': previous_content
    }

    if topic:
        prompt_vars.update({
            'subtopic': topic['title'],
            'subtopic_summary': topic['summary'],
            'subtopic_relation_to_main_topic': topic['relation_to_main_topic']
        })

    prompt = prompt_template.safe_substitute(prompt_vars)

    print(f"Generating {section_name} section...")

    with open(pdf_path, "rb") as pdf_file:
        document = Part.from_data(
            mime_type="application/pdf",
            data=pdf_file.read()
        )

    def generate_content():
        return model.generate_content(
            [
                document,
                prompt
            ],
            generation_config=GenerationConfig(
                max_output_tokens=8192,
                temperature=0.9,
            ),
        )

    try:
        response = retry_with_backoff(generate_content)
        return response.text
    except Exception as e:
        print(f"Failed to generate {section_name} section after multiple retries. Error: {e}")
        return f"[Error generating {section_name} section]"

def generate_full_podcast_script(pdf_path: str, topic: dict, language: str, transcripts_dir: Path, prompt_files: dict) -> str:
    """
    Generates the full podcast script by combining all sections.

    Args:
        pdf_path (str): The path to the PDF file.
        topic (dict): The selected topic for the podcast (None for entire paper).
        language (str): The language for the podcast.
        transcripts_dir (Path): The directory containing transcript files.
        prompt_files (dict): A dictionary containing paths to prompt files for each section.

    Returns:
        str: The complete generated podcast script.
    """
    sections = [
        ("introduction", "Introduction"),
        ("background", "Background"),
        ("key_findings", "Key Findings and Discussion"),
        ("implications", "Implications and Applications"),
        ("conclusion", "Conclusion")
    ]

    full_script = ""
    previous_content = ""

    for section_key, section_name in sections:
        try:
            section_content = generate_podcast_section(
                pdf_path, topic, language, transcripts_dir,
                prompt_files[section_key], section_name, previous_content
            )
            full_script += f"-----\n\n{section_name}\n\n{section_content}\n\n"
            previous_content += section_content
        except Exception as e:
            print(f"Error generating {section_name} section: {e}")
            full_script += f"-----\n\n{section_name}\n\n[Error generating this section]\n\n"

    return full_script

def main():
    parser = argparse.ArgumentParser(description="Generate podcast script from a PDF and a selected topic.")
    parser.add_argument('pdf_path', type=str, help='Path to the PDF file.')
    parser.add_argument('topics_json', type=str, help='Path to the topics JSON file.')
    parser.add_argument('--topic_index', type=int, default=-1, help='Index of the topic to select (-1 for entire paper, 0 or greater for specific subtopic).')
    parser.add_argument('--language', type=str, default='English', help='Language for the podcast script.')
    parser.add_argument('--transcripts_dir', type=str, default='data/transcripts', help='Directory containing previous transcripts.')
    parser.add_argument('--output', type=str, default='podcast_script.txt', help='Output text file for the podcast script.')
    parser.add_argument('--prompts_dir', type=str, default='prompts', help='Directory containing prompt files.')

    args = parser.parse_args()

    with open(args.topics_json, 'r') as f:
        topics_data = json.load(f)

    subtopics = topics_data['subtopics']
    if args.topic_index >= len(subtopics):
        print(f"Invalid topic index. Please select a value between -1 and {len(subtopics)-1}")
        return

    selected_topic = None
    if args.topic_index >= 0:
        selected_topic = subtopics[args.topic_index]
    
    transcripts_dir = Path(args.transcripts_dir)
    prompts_dir = Path(args.prompts_dir)

    prompt_files = {
        "introduction": prompts_dir / ("introduction_prompt.txt" if args.topic_index == -1 else "introduction_subtopic_prompt.txt"),
        "background": prompts_dir / "background_prompt.txt",
        "key_findings": prompts_dir / ("key_findings_prompt.txt" if args.topic_index == -1 else "key_findings_subtopic_prompt.txt"),
        "implications": prompts_dir / "implications_prompt.txt",
        "conclusion": prompts_dir / "conclusion_prompt.txt"
    }

    try:
        podcast_script = generate_full_podcast_script(args.pdf_path, selected_topic, args.language, transcripts_dir, prompt_files)

        with open(args.output, 'w') as f:
            f.write(podcast_script)
        print(f"Podcast script saved to {args.output}")
    except Exception as e:
        print(f"An error occurred while generating the podcast script: {e}")
        print("Please check the logs for more details and try again.")

if __name__ == "__main__":
    main()

# Example usage:
# python script_generation.py ./data/research_paper.pdf ./data/topics.json --topic_index 0 --language English --transcripts_dir ./data/transcripts --output ./data/podcast_script.txt --prompts_dir ./data/prompts

