import boto3


def get_presigned_image_url(image, expires_in=600):
    """
    Generate a temporary URL for an image stored in S3.
    """

    if image.storage_backend != "s3":
        raise ValueError(
            f"Unsupported storage backend: "
            f"{image.storage_backend}"
        )

    if not image.storage_bucket:
        raise ValueError(
            "Image has no S3 bucket."
        )

    if not image.storage_key:
        raise ValueError(
            "Image has no S3 object key."
        )

    s3 = boto3.client(
        "s3",
        region_name="us-east-1"
    )

    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": image.storage_bucket,
            "Key": image.storage_key,
        },
        ExpiresIn=expires_in,
    )