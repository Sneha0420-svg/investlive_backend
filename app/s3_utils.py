import io
import boto3
from fastapi import HTTPException
from botocore.exceptions import BotoCoreError, ClientError
from app.config import S3_BUCKET, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

def upload_file_to_s3(file_obj, folder: str, filename: str = None) -> str:
    import os, uuid
    ext = os.path.splitext(filename)[1] if filename else ".dat"
    s3_key = f"{folder}/{uuid.uuid4()}{ext}"
    obj_to_upload = getattr(file_obj, "file", file_obj)
    try:
        s3.upload_fileobj(obj_to_upload, S3_BUCKET, s3_key)
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")
    return s3_key

def get_file_stream_from_s3(s3_key: str):
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        return io.BytesIO(response['Body'].read())
    except s3.exceptions.NoSuchKey:
        return None
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"S3 download failed: {e}")

def delete_file_from_s3(s3_key: str):
    if not s3_key:
        return
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=s3_key)
    except (BotoCoreError, ClientError):
        pass

def get_s3_file_url(s3_key: str) -> str:
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=3600
        )
    except Exception:
        return f"s3://{S3_BUCKET}/{s3_key}"