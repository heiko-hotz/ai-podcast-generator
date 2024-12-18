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

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
import os
from uuid import uuid4
from pathlib import Path
import json
import uvicorn

# Import functions from our scripts
from functions.topic_extraction import extract_main_topics
from functions.script_generation import generate_full_podcast_script
from functions.audio_generation import generate_audio_from_transcript
from utils.utils import upload_to_gcs

app = FastAPI()

class ExtractTopicRequest(BaseModel):
    pdf_path: str
    topic: int

class PodcastScriptRequest(BaseModel):
    pdf_path: str
    topic: dict
    language: str = 'en-US'
    transcripts_dir: str
    prompt_files: dict

class AudioRequest(BaseModel):
    transcript_path: str
    language: str
    output_audio: str


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/extract_main_topics")
async def extract_main_topics(request: ExtractTopicRequest) -> list:
    return extract_main_topics(request.pdf_path,
                               request.n
                            )

@app.post("/generate_full_podcast_script")
async def generate_full_podcast_script(request: PodcastScriptRequest) -> str:
    return generate_full_podcast_script(request.pdf_path,
                                        request.topic,
                                        request.language,
                                        request.transcripts_dir,
                                        request.prompt_files
                                    )

@app.post("/generate_audio_from_transcript")
async def generate_audio_from_transcript(request: AudioRequest):
    return generate_audio_from_transcript(request.transcript_path,
                                          request.language,
                                          request.output_audio
                                        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
