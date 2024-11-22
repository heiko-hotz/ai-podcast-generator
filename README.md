# Fabulae 

## Overview

Fabulae unleashes the knowledge trapped in your PDFs! Harnessing the power of Gemini and text-to-speech from Google Cloud, Fabulae transforms static documents into captivating audio experiences. Imagine your research papers, reports, or even ebooks springing to life as dynamic podcasts, complete with natural-sounding dialogue and engaging narration.  No more eye strain, just pure auditory bliss! Fabulae even provides a full transcript, so you can follow along or dive deeper into the content.

## 🌟 Key Features

- Convert any PDF into an  informative and entertaining Podcast episode
- Streamlit UI for easy interaction
- Multilanguage support
- Transcription generation

## 🚀 Quick Start

### Prerequisites

1. Poetry installed on your machine
2. Google Cloud Project with Cloud Services enabled (text-to-speech, aiplatform)
3. `gcloud` cli setup
    1. Authenticate using `gcloud auth application-default login`
    2. Reference the correct billing account `gcloud auth application-default set-quota-project my-quota-project`

## 💻 Local Development

```
streamlit run streamlit_app.py \
     --browser.serverAddress=localhost \
     --server.enableCORS=false \
     --server.enableXsrfProtection=false \
     --server.port 8080
```

## ☁️ Run on Google Cloud


## 🏗️ Project Structure


## ⚠️ Disclaimer

This is not an officially supported Google product.