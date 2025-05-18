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
    import faiss as faiss_s3
    import numpy as np

    if isinstance(index, np.ndarray):
        raise ValueError("❌ Tried to upload a NumPy array instead of FAISS index")

    print("✅ Saving FAISS index to S3:", s3_key)
    print("🧪 FAISS index: is_trained =", index.is_trained, "ntotal =", index.ntotal)

    serialized_index = faiss_s3.serialize_index(index)

    # ✅ Convert to bytes if it's a NumPy array
    if isinstance(serialized_index, np.ndarray):
        serialized_index = serialized_index.tobytes()

    s3.put_object(Body=serialized_index, Bucket=AWS_S3_BUCKET, Key=s3_key)



def download_faiss_from_s3(s3_key):
    import faiss as faiss_s3
    import numpy as np

    print("📥 Downloading FAISS index from S3:", s3_key)

    response = s3.get_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
    serialized_index = response['Body'].read()
    index = faiss_s3.deserialize_index(np.frombuffer(serialized_index, dtype=np.uint8))
    print("✅ FAISS index loaded: ntotal =", index.ntotal)
    return index



def delete_from_s3(s3_key):
    s3.delete_object(Bucket=AWS_S3_BUCKET, Key=s3_key)

def s3_key_for(user_id, embedding_name, filename):
    return f"{user_id}/{embedding_name}/{filename}"

def download_file_bytes_from_s3(s3_key):
    buf = io.BytesIO()
    s3.download_fileobj(AWS_S3_BUCKET, s3_key, buf)
    buf.seek(0)
    return buf.read()
