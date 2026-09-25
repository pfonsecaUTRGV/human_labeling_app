import base64
import requests


SHARING_URL = (
    "https://utrgv-my.sharepoint.com/:i:/g/personal/"
    "pedro_fonseca01_utrgv_edu/"
    "IQDlMTzqERmcRKfdzUSYo9OcAca6mLemO440V9TDx1GpUHI?e=mmX2g2"
)


def encode_sharing_url(url):
    encoded = base64.b64encode(
        url.encode("utf-8")
    ).decode("utf-8")

    encoded = (
        encoded
        .rstrip("=")
        .replace("/", "_")
        .replace("+", "-")
    )

    return "u!" + encoded


share_id = encode_sharing_url(
    SHARING_URL
)

print("Encoded share ID:")
print(share_id)

print()
print("Graph endpoint:")
print(
    f"https://graph.microsoft.com/v1.0/"
    f"shares/{share_id}/driveItem"
)