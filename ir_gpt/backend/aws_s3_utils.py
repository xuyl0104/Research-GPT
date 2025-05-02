import os
import io
import boto3
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

def upload_pickle_to_s3(obj, s3_key):
    buf = io.BytesIO()
    import pickle
    pickle.dump(obj, buf)
    buf.seek(0)
    s3.upload_fileobj(buf, AWS_S3_BUCKET, s3_key)

def download_pickle_from_s3(s3_key):
    buf = io.BytesIO()
    s3.download_fileobj(AWS_S3_BUCKET, s3_key, buf)
    buf.seek(0)
    import pickle
    return pickle.load(buf)

def upload_faiss_to_s3(index, s3_key):
    import faiss
    local_path = "/tmp/temp.index"
    faiss.write_index(index, local_path)
    s3.upload_file(local_path, AWS_S3_BUCKET, s3_key)

def download_faiss_from_s3(s3_key):
    import faiss
    local_path = "/tmp/temp.index"
    s3.download_file(AWS_S3_BUCKET, s3_key, local_path)
    return faiss.read_index(local_path)

def delete_from_s3(s3_key):
    s3.delete_object(Bucket=AWS_S3_BUCKET, Key=s3_key)

def s3_key_for(user_id, embedding_name, filename):
    return f"{user_id}/{embedding_name}/{filename}"
