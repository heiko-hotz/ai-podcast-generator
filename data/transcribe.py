import os
import base64
import asyncio
from vertexai.generative_models import GenerativeModel, Part

def encode_audio(audio_file):
    with open(audio_file, "rb") as audio_file:
        audio_bytes = audio_file.read()
    return base64.b64encode(audio_bytes).decode('utf-8')

async def transcribe_audio_async(audio_file):
    """Transcribes the audio file using Gemini asynchronously."""
    model = GenerativeModel("gemini-1.5-flash-002")
    encoded_audio = encode_audio(audio_file)
    
    prompt = """
Please transcribe this interview in the following format:
[Female/male speaker]: <Dialogue or caption>.
Use square brackets around the name of the speaker.
Ensure the transcription captures all spoken words accurately, including filler words where appropriate.
Create a new line for each new speaker! Don't create any extra lines.
Only use plain text. Don't use any markdown formatting.
Make sure that the speakers alternate between male and female. I.e. there cannot be two lines with the same speaker.
You MUST indicate how many milliseconds of silence there is between each line (roughly)
Example:
[Female speaker]: Hello, how are you?
[PAUSE=250]
[Male speaker]: I'm fine, thank you. How can I help you today?
"""
    audio_part = Part.from_data(encoded_audio, mime_type="audio/wav")
    
    response = await model.generate_content_async([audio_part, prompt])
    return response.text

async def process_audio_file_async(audio_file):
    """Process a single audio file asynchronously."""
    print(f"Processing {audio_file}...")
    audio_path = os.path.join(os.path.dirname(__file__), "audio", audio_file)
    transcript = await transcribe_audio_async(audio_path)
    
    # Save transcript
    transcript_file = os.path.splitext(audio_file)[0] + ".txt"
    transcript_path = os.path.join(os.path.dirname(__file__), "transcripts_test", transcript_file)
    with open(transcript_path, "w") as f:
        f.write(transcript)
    
    print(f"Transcription complete for {audio_file}")

async def main_async():
    # Ensure transcript directory exists
    transcript_dir = os.path.join(os.path.dirname(__file__), "transcripts_test")
    os.makedirs(transcript_dir, exist_ok=True)

    # Get list of audio files
    audio_dir = os.path.join(os.path.dirname(__file__), "audio")
    audio_files = [f for f in os.listdir(audio_dir) if f.endswith(('.wav', '.mp3', '.flac'))]

    # Process audio files concurrently
    tasks = [process_audio_file_async(audio_file) for audio_file in audio_files]
    await asyncio.gather(*tasks)

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()