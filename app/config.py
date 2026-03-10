import os
from dotenv import load_dotenv

# Determine environment (default to 'local')
ENV = os.getenv("ENV", "local")  # set ENV=prod in production

# Load the correct .env file
if ENV == "prod":
    load_dotenv(".env.prod")
else:
    load_dotenv(".env.local")

# S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")