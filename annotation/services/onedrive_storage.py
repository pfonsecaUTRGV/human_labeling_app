from urllib.parse import quote

import requests

from django.conf import settings


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


def build_onedrive_path(image):
    """
    Convert the Image.image_path stored in Django into
    the path used in OneDrive.
    """

    base_path = (
        settings.ONEDRIVE_BASE_PATH
        .rstrip("/")
    )

    relative_path = (
        image.image_path
        .lstrip("/")
    )

    return (
        f"{base_path}/{relative_path}"
    )


def build_drive_item_url(image):
    """
    Build the Microsoft Graph URL for an image.
    """

    drive_id = (
        settings.ONEDRIVE_DRIVE_ID
    )

    path = build_onedrive_path(
        image
    )

    encoded_path = quote(
        path,
        safe="/"
    )

    return (
        f"{GRAPH_BASE_URL}"
        f"/drives/{drive_id}"
        f"/root:{encoded_path}"
    )


def get_drive_item(
    image,
    access_token
):

    url = build_drive_item_url(
        image
    )

    headers = {
        "Authorization":
            f"Bearer {access_token}"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return response.json()