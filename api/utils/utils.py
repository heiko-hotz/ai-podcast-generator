import time
from google.cloud import storage
from google.api_core import exceptions as google_exceptions


def upload_to_gcs(bucket_name: str, source_file_name: str, destination_blob_name: str):
    """Uploads a file to the specified GCS bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name} in bucket {bucket_name}.")

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