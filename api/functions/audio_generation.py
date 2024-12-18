# audio_generation.py

import os
import json
import argparse
from pathlib import Path
import time
from tqdm import tqdm
from google.cloud import texttospeech_v1beta1 as texttospeech
from google.api_core import exceptions as google_exceptions
import re
import io

from pydub import AudioSegment
from pydub.utils import which

AudioSegment.converter = which("ffmpeg")
print("Using FFmpeg from:", AudioSegment.converter)

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

def load_language_mapping():
    """
    Loads the language mapping configuration from JSON file.
    
    Returns:
        dict: Language mapping configuration
    """
    with open('language_mapping.json', 'r') as f:
        return json.load(f)

def split_section_content(section_content: str, max_lines: int = 6) -> list[tuple[str, list[str]]]:
    """Split section content into smaller chunks."""
    lines = section_content.strip().split('\n')
    chunks = []
    
    for i in range(0, len(lines), max_lines):
        chunk_lines = lines[i:i + max_lines]
        chunk_name = f"part_{i//max_lines + 1}"
        chunks.append((chunk_name, chunk_lines))
    
    return chunks

def generate_audio_section(section_text: str, language: str, output_path: str, section_name: str, file_counter: int):
    """Generate audio for a single section of the transcript."""
    # Create chunks directory if it doesn't exist
    chunks_dir = output_path.parent / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    
    language_config = load_language_mapping()[language]
    language_code = language_config["code"]

    # Split section into smaller chunks
    chunks = split_section_content(section_text)
    chunk_files = []
    
    for i, (chunk_name, chunk_lines) in enumerate(chunks):
        full_chunk_name = f"{(file_counter + i):03d}_{section_name}_{chunk_name}"
        
        # Process chunk turns
        turns = []
        for line in tqdm(chunk_lines, desc=f"Processing {full_chunk_name}"):
            if line.strip() and ': ' in line:
                parts = line.split(': ', 1)
                if len(parts) == 2:
                    speaker_info, text = parts
                    if '[R]' in speaker_info:
                        speaker = 'R'
                    elif '[S]' in speaker_info:
                        speaker = 'S'
                    else:
                        raise ValueError(f"Invalid speaker label in line: {line}")
                    
                    turns.append(
                        texttospeech.MultiSpeakerMarkup.Turn(
                            text=text.strip(),
                            speaker=speaker
                        )
                    )

        if not turns:  # Skip empty chunks
            continue

        # Create multi-speaker markup and generate audio as before
        multi_speaker_markup = texttospeech.MultiSpeakerMarkup(turns=turns)
        synthesis_input = texttospeech.SynthesisInput(
            multi_speaker_markup=multi_speaker_markup
        )
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=f"{language_code}-Studio-MultiSpeaker"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        print(f"Generating audio for {full_chunk_name}...")
        try:
            response = retry_with_backoff(
                tts_client.synthesize_speech,
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            # Save chunk audio to chunks directory instead
            chunk_output = chunks_dir / f"{full_chunk_name.lower().replace(' ', '_')}.wav"
            with open(chunk_output, "wb") as out:
                out.write(response.audio_content)
            chunk_files.append(chunk_output)
        except Exception as e:
            print(f"Error generating audio for {full_chunk_name}: {e}")
            continue

    return chunk_files

def concatenate_audio_files(output_dir: Path, final_output: Path):
    """Concatenate all wav files in the chunks directory into a single file."""
    chunks_dir = output_dir.parent / "chunks"
    if not chunks_dir.exists():
        print(f"Chunks directory not found: {chunks_dir}")
        return
        
    wav_files = list(chunks_dir.glob("*.wav"))
    
    def get_file_number(filename):
        match = re.search(r'(\d{3})_', filename.name)
        if match:
            return int(match.group(1))
        return 0
    
    wav_files.sort(key=get_file_number)
    
    if len(wav_files) < 1:
        print("No wav files found in chunks directory")
        return
    
    print(f"Concatenating {len(wav_files)} files...")
    
    try:
        # Load the first file
        combined_audio = AudioSegment.from_file(wav_files[0], format="wav")
        print(f"Loaded first file, duration: {len(combined_audio)}ms")
        
        # Set overlap duration
        overlap_duration_ms = 200  # 1 second overlap
        
        # Process remaining files
        for i in range(1, len(wav_files)):
            print(f"Processing file {i+1}/{len(wav_files)}: {wav_files[i].name}")
            
            next_audio = AudioSegment.from_file(wav_files[i], format="wav")
            print(f"Loaded file, duration: {len(next_audio)}ms")
            
            # Calculate overlap point
            overlap_start_point = len(combined_audio) - overlap_duration_ms
            
            # Ensure the overlap point is valid
            if overlap_start_point < 0:
                overlap_start_point = 0
                overlap_duration_ms = len(combined_audio)
            
            # Slice the combined audio
            combined_audio_sliced = combined_audio[:overlap_start_point]
            
            # Slice the next audio file
            next_audio_overlap = next_audio[:overlap_duration_ms]
            
            # Mix the overlapping parts
            mixed_overlap = combined_audio[overlap_start_point:].overlay(next_audio_overlap)
            
            # Create new combined audio
            combined_audio = combined_audio_sliced + mixed_overlap + next_audio[overlap_duration_ms:]
            print(f"Current combined audio length: {len(combined_audio)}ms")
        
        # Export the final audio file
        print(f"Creating final concatenated audio file: {final_output}")
        combined_audio.export(str(final_output), format="mp3")
        print(f"Successfully created concatenated audio file")
        
    except Exception as e:
        print(f"Error during concatenation: {str(e)}")
        import traceback
        traceback.print_exc()



def generate_audio_from_transcript(transcript_path: str, language: str, output_audio: str):
    """Generate audio for the entire transcript, section by section."""
    output_path = Path(output_audio)
    file_counter = 1  # Global counter for all files, starting at 1
    all_chunk_files = []
    
    # Read transcript
    with open(transcript_path, 'r') as f:
        transcript = f.read()

    # Split into sections
    sections = transcript.split("-----")
    
    for section in sections:
        if not section.strip():
            continue
        
        # Extract section name from first line
        lines = section.strip().split('\n')
        section_name = lines[0].strip()
        section_content = '\n'.join(lines[1:])
        
        try:
            chunk_files = generate_audio_section(
                section_content, 
                language, 
                output_path, 
                section_name,
                file_counter  # Pass the current counter
            )
            all_chunk_files.extend(chunk_files)
            file_counter += len(chunk_files)  # Increment counter by number of chunks generated
        except Exception as e:
            print(f"Error generating audio for {section_name}: {e}")
            continue

    # Concatenate all audio files at the end
    if all_chunk_files:
        concatenate_audio_files(output_path.parent, output_path)

def main():
    parser = argparse.ArgumentParser(description="Generate audio from a podcast transcript.")
    parser.add_argument('transcript_path', type=str, help='Path to the transcript text file.')
    parser.add_argument('--language', type=str, default='English', help='Language for the voices (e.g., English, German).')
    parser.add_argument('--output_audio', type=str, default='podcast.mp3', help='Output audio file path.')
    parser.add_argument('--concat_only', action='store_true', help='Only concatenate existing audio files without generating new ones.')

    args = parser.parse_args()
    
    if args.concat_only:
        output_path = Path(args.output_audio)
        print("Concatenation mode: using existing audio files...")
        concatenate_audio_files(output_path.parent, output_path)
    else:
        generate_audio_from_transcript(args.transcript_path, args.language, args.output_audio)

if __name__ == "__main__":
    main()

# Example usage:
# For full generation and concatenation:
# python audio_generation.py ./data/podcast_script.txt --language English --output_audio ./data/podcast.mp3
# For concatenation only:
# python audio_generation.py ./data/podcast_script.txt --output_audio ./data/podcast.mp3 --concat_only