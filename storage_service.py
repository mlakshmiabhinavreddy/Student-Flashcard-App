"""
STUDYFLIP — Google Cloud Storage Service

Handles uploads and downloads for study materials.
"""

import os

from google.cloud import storage


# Use the environment variable when deployed.
# Fall back to the existing STUDYFLIP bucket locally.
GCS_BUCKET_NAME = os.getenv(
    "GCS_BUCKET_NAME",
    "digital-flashcard-app-files-2026"
)

GCS_PROJECT = (
    os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("GCP_PROJECT")
    or "digital-flashcard-app"
)


# Create the client lazily.
# This prevents the Flask application from failing during import
# if credentials are temporarily unavailable.
_storage_client = None


def get_storage_client():
    """Return a lazily-created Google Cloud Storage client."""
    global _storage_client

    if _storage_client is None:
        print(
            f"[STORAGE] Connecting to bucket: "
            f"gs://{GCS_BUCKET_NAME}"
        )

        _storage_client = storage.Client(
            project=GCS_PROJECT
        )

        print(
            f"[STORAGE] Storage client ready "
            f"for project: {GCS_PROJECT}"
        )

    return _storage_client


def get_storage_bucket():
    """Return the configured STUDYFLIP Cloud Storage bucket."""
    client = get_storage_client()
    return client.bucket(GCS_BUCKET_NAME)


def upload_file(
    file_obj,
    destination_name,
    content_type=None
):
    """
    Upload a file-like object to Cloud Storage.

    Args:
        file_obj:
            Flask uploaded file object.

        destination_name:
            Object path inside the bucket.

        content_type:
            MIME type of the uploaded file.

    Returns:
        The Cloud Storage object name.
    """

    bucket = get_storage_bucket()
    blob = bucket.blob(destination_name)

    blob.upload_from_file(
        file_obj,
        content_type=content_type
    )

    print(
        f"[STORAGE] Uploaded: "
        f"gs://{GCS_BUCKET_NAME}/{destination_name}"
    )

    return blob.name


def download_file(destination_name):
    """
    Download an object from Cloud Storage.

    Returns:
        Tuple containing:
            file bytes
            content type
    """

    bucket = get_storage_bucket()
    blob = bucket.blob(destination_name)

    if not blob.exists():
        raise FileNotFoundError(
            f"Storage object not found: {destination_name}"
        )

    data = blob.download_as_bytes()

    return data, blob.content_type or "application/octet-stream"


def delete_file(destination_name):
    """Delete an object from Cloud Storage."""

    bucket = get_storage_bucket()
    blob = bucket.blob(destination_name)

    if blob.exists():
        blob.delete()

        print(
            f"[STORAGE] Deleted: "
            f"gs://{GCS_BUCKET_NAME}/{destination_name}"
        )

        return True

    return False


def list_files(prefix=None):
    """
    List objects in the bucket.

    Args:
        prefix:
            Optional object prefix.

    Returns:
        List of object names.
    """

    client = get_storage_client()
    blobs = client.list_blobs(
        GCS_BUCKET_NAME,
        prefix=prefix
    )

    return [blob.name for blob in blobs]