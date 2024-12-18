# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
import json
import tempfile
from pathlib import Path

import streamlit as st
from tqdm import tqdm
import requests

from topic_extraction import extract_main_topics
from script_generation import generate_full_podcast_script
from audio_generation import generate_audio_from_transcript

HOST = os.getenv("HOST", "http://localhost:8000")

def initialize_session_state():
    """
    Initializes the Streamlit session state variables.
    """
    default_state = {
        'selected_topic': None,
        'generate_podcast': False,
        'topics': None,
        'language': 'English'
    }
    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value

def main():
    """
    Main function to run the Streamlit app.
    """
    st.title("AI Podcast Generator")
    initialize_session_state()

    # Create artifacts folder if it doesn't exist
    artifacts_folder = Path("artifacts")
    artifacts_folder.mkdir(exist_ok=True)

    uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

    # Load language mapping
    with open('language_mapping.json', 'r') as f:
        language_mapping = json.load(f)

    # Language selection dropdown
    language_options = list(language_mapping.keys())
    selected_language = st.selectbox("Select podcast language", language_options, index=0)
    st.session_state.language = selected_language

    if uploaded_file is not None:
        with st.spinner("Processing uploaded file..."):
            # Save the uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

        if st.session_state.topics is None:
            with st.spinner("Extracting main topics..."):
                #topics_data = extract_main_topics(tmp_file_path, 3)
                request_values = {
                    "pdf_path": tmp_file_path,
                    "n": 3,
                }
                topics_data = requests.post(
                    f"{HOST}/extract_main_topics/",
                    json=request_values,
                    headers={'Content-Type': 'application/json'}
                )
                st.session_state.topics = topics_data.get('subtopics', [])

        st.subheader("Topics")
        topics = st.session_state.topics

        if topics:
            # Add "Entire Paper" option to the topics list
            topic_options = ["Entire Paper"] + [f"{index}. {topic['title']}" for index, topic in enumerate(topics, start=1)]
            selected_topic_title = st.selectbox("Select a topic for the podcast", topic_options, key="topic_selector")
            
            if selected_topic_title == "Entire Paper":
                selected_topic = None
            else:
                selected_topic_index = topic_options.index(selected_topic_title) - 1  # Subtract 1 to account for "Entire Paper" option
                selected_topic = topics[selected_topic_index]

            # Display topic details if a specific topic is selected
            if selected_topic:
                st.markdown(f"""
                **Selected Topic: {selected_topic['title']}**

                ***Summary:*** {selected_topic['summary']}

                ***Significance:*** {selected_topic['relation_to_main_topic']}
                """)
            else:
                st.markdown("**Selected Topic: Entire Paper**")

            # Define the prompt files
            prompts_dir = Path('prompts')  # Adjust the path as necessary
            prompt_files = {
                "introduction": prompts_dir / "introduction_prompt.txt",
                "background": prompts_dir / "background_prompt.txt",
                "key_findings": prompts_dir / ("key_findings_prompt.txt" if selected_topic is None else "key_findings_subtopic_prompt.txt"),
                "implications": prompts_dir / "implications_prompt.txt",
                "conclusion": prompts_dir / "conclusion_prompt.txt"
            }

            # Generate podcast button
            if st.button("Generate Podcast"):
                st.session_state.selected_topic = selected_topic
                st.session_state.language = selected_language
                st.session_state.generate_podcast = True

            # Generate podcast only when the button is clicked
            if st.session_state.generate_podcast:
                st.session_state.generate_podcast = False  # Reset the flag
                progress_bar = st.progress(0)
                status_text = st.empty()

                language_info = language_mapping[st.session_state.language]
                language_code = language_info["code"]

                # Generate podcast script
                status_text.text("Generating podcast script...")
                progress_bar.progress(10)
                transcripts_dir = Path('data/transcripts')  # Ensure this directory exists

                podcast_script = generate_full_podcast_script(
                    tmp_file_path, st.session_state.selected_topic, st.session_state.language, transcripts_dir, prompt_files
                )
                progress_bar.progress(40)

                # Save podcast transcript
                status_text.text("Saving podcast transcript...")
                transcript_path = artifacts_folder / "podcast_transcript.txt"
                with open(transcript_path, "w") as f:
                    f.write(podcast_script)
                progress_bar.progress(50)

                # Generate audio
                status_text.text("Generating audio...")
                progress_bar.progress(60)
                male_voice = language_info["male_voice"]
                female_voice = language_info["female_voice"]
                audio_path = artifacts_folder / "podcast.mp3"
                generate_audio_from_transcript(str(transcript_path), male_voice, female_voice, language_code, str(audio_path))

                # Ensure audio is generated before displaying
                status_text.text("Podcast generation complete!")
                progress_bar.progress(100)

                # Check if the audio file is ready
                if audio_path.exists() and audio_path.stat().st_size > 0:
                    # Play audio in Streamlit
                    st.subheader("Generated Podcast")
                    st.audio(str(audio_path))
                else:
                    st.error("Audio file generation failed. Please try again.")

                # Provide download link for transcript
                st.download_button(
                    label="Download Podcast Transcript",
                    data=podcast_script,
                    file_name="podcast_transcript.txt",
                    mime="text/plain"
                )

        else:
            st.error("No topics were extracted. Please check the AI model's response above.")

        # Clean up temporary files
        os.unlink(tmp_file_path)

if __name__ == '__main__':
    main()
