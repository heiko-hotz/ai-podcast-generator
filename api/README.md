# AI Podcast Generator - Backend

## Run locally

Modify `main.py` PodcastRequest class to have a default `gcs_bucket` that matches your GCS bucket (otherwise this can be specified in the request to the API)

### Install the requirements

```
uv venv venv
. venv/bin/activate
uv pip install -r requirements
```

### Run the API 

```
python3 main.py
```

### Call the API

The request object looks like this, where the only required param is `pdf_url`, defaults are shown for the others:

```json
{
    "pdf_url": "",
    "num_topics": 3,
    "language": "en-US",
    "male_voice": "en-US-Casual-K",
    "female_voice": "en-US-Journey-O",
    "gcs_bucket": "ghchinoy-genai-sa-fabulae"
}
```

Example:

```
curl localhost:8000/generate_podcast -H "content-type: application/json" -d '{"pdf_url": "https://arxiv.org/pdf/2407.21783"}' 
```