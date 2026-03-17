import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from app.config import S3_BUCKET, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

try:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'virtual'}
        )
    )

    # List objects in your bucket to test
    resp = s3.list_objects_v2(Bucket=S3_BUCKET)
    if 'Contents' in resp:
        print("S3 access successful. Objects:")
        for obj in resp['Contents']:
            print(obj['Key'])
    else:
        print("S3 access successful. Bucket is empty.")

except (BotoCoreError, ClientError) as e:
    print("S3 access failed:", e)