# audio_generation.py

import os
import json
import argparse
from pathlib import Path
import time
from tqdm import tqdm
from google.cloud import texttospeech
from pydub import AudioSegment
from google.api_core import exceptions as google_exceptions

# Initialize Google Cloud Text-to-Speech client
tts_client = texttospeech.TextToSpeechClient()

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

def synthesize_speech(text: str, voice_params: texttospeech.VoiceSelectionParams, audio_config: texttospeech.AudioConfig) -> AudioSegment:
    """
    Synthesizes speech from the input text using the specified voice parameters.

    Args:
        text (str): The text to synthesize.
        voice_params (texttospeech.VoiceSelectionParams): The voice parameters for synthesis.
        audio_config (texttospeech.AudioConfig): The audio configuration for synthesis.

    Returns:
        AudioSegment: The synthesized audio segment.
    """
    input_text = texttospeech.SynthesisInput(text=text)
    response = tts_client.synthesize_speech(
        request={"input": input_text, "voice": voice_params, "audio_config": audio_config}
    )
    audio_segment = AudioSegment(
        data=response.audio_content,
        sample_width=2,
        frame_rate=24000,
        channels=1
    )
    return audio_segment

def load_language_mapping():
    """
    Loads the language mapping configuration from JSON file.
    
    Returns:
        dict: Language mapping configuration
    """
    with open('language_mapping.json', 'r') as f:
        return json.load(f)

def generate_audio_from_transcript(transcript_path: str, language: str, output_audio: str):
    """
    Generates audio from the transcript using voices specified in language mapping.

    Args:
        transcript_path (str): The path to the transcript file.
        language (str): The language name (e.g., "English", "German").
        output_audio (str): The output audio file path.
    """
    # Load language mapping and get voice configuration
    language_mapping = load_language_mapping()
    if language not in language_mapping:
        raise ValueError(f"Unsupported language: {language}")
    
    language_config = language_mapping[language]
    language_code = language_config["code"]
    male_voice = language_config["male_voice"]
    female_voice = language_config["female_voice"]

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    )

    voices = {
        "[Male speaker]": texttospeech.VoiceSelectionParams(
            language_code=language_code, 
            name=male_voice
        ),
        "[Female speaker]": texttospeech.VoiceSelectionParams(
            language_code=language_code, 
            name=female_voice
        )
    }

    with open(transcript_path, 'r') as f:
        transcript = f.read()

    lines = transcript.strip().split('\n')
    combined_audio = AudioSegment.silent(duration=100)
    crossfade_duration = 150
    pause_duration = 150

    for line in tqdm(lines, desc="Generating audio"):
        if line.strip():
            parts = line.split(': ', 1)
            if len(parts) == 2:
                speaker_info, text = parts
                # Extract speaker identifier without turn number
                if '. ' in speaker_info:
                    _, speaker = speaker_info.split('. ', 1)
                else:
                    speaker = speaker_info
                voice_params = voices.get(speaker.strip())
                if voice_params:
                    def synthesize():
                        return synthesize_speech(text, voice_params, audio_config)
                    segment = retry_with_backoff(synthesize)
                    if combined_audio.duration_seconds > 0:
                        combined_audio += AudioSegment.silent(duration=pause_duration)
                    combined_audio = combined_audio.append(segment, crossfade=crossfade_duration)
                else:
                    print(f"Unknown speaker: {speaker}")
    # Save audio to file
    combined_audio.export(output_audio, format="mp3")
    print(f"Audio saved to {output_audio}")

def main():
    parser = argparse.ArgumentParser(description="Generate audio from a podcast transcript.")
    parser.add_argument('transcript_path', type=str, help='Path to the transcript text file.')
    parser.add_argument('--language', type=str, default='English', help='Language for the voices (e.g., English, German).')
    parser.add_argument('--output_audio', type=str, default='podcast.mp3', help='Output audio file path.')

    args = parser.parse_args()
    generate_audio_from_transcript(args.transcript_path, args.language, args.output_audio)

if __name__ == "__main__":
    main()

# Example usage:
# python audio_generation.py ./data/podcast_script.txt --language English --output_audio ./data/podcast.mp3