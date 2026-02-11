#!/usr/bin/env python3
"""
S3 Storage — Upload/download utility for YouTube Shorts pipeline.

All assets (images, videos, metadata) are organized by job:
  s3://michael-comfyui-outputs/jobs/{job_id}/
    ├── plan.json           ← Story/prompt metadata
    ├── input_image.png     ← Generated cut image
    ├── clip_01.mp4         ← Individual video clips
    ├── clip_02.mp4
    └── final.mp4           ← Final video (with audio)

Environment Variables:
  S3_ACCESS_KEY_ID       AWS access key
  S3_SECRET_ACCESS_KEY   AWS secret key
  S3_BUCKET_NAME         Bucket name (default: michael-comfyui-outputs)
  S3_ENDPOINT_URL        S3 endpoint URL
  S3_REGION              AWS region (default: us-east-1)

Usage:
    from s3_storage import S3Storage

    s3 = S3Storage()
    job_id = s3.generate_job_id()

    # Upload
    s3.upload("/tmp/shorts/cut.png", f"jobs/{job_id}/input_image.png")
    s3.upload("/tmp/shorts/video.mp4", f"jobs/{job_id}/clip_01.mp4")

    # Upload with helper
    s3.upload_job_asset("/tmp/shorts/cut.png", job_id, "input_image.png")

    # Download
    s3.download(f"jobs/{job_id}/clip_01.mp4", "/tmp/shorts/downloaded.mp4")

    # List job assets
    assets = s3.list_job_assets(job_id)
"""

import json
import os
import time
import uuid
from pathlib import Path
# boto3 is available (checked: v1.38.27)
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    boto3 = None  # type: ignore[assignment]
    HAS_BOTO3 = False


class S3Storage:
    """S3 storage client for YouTube Shorts pipeline assets."""

    def __init__(self):
        self.bucket = os.environ.get("S3_BUCKET_NAME", "michael-comfyui-outputs")
        self.access_key = os.environ.get("S3_ACCESS_KEY_ID")
        self.secret_key = os.environ.get("S3_SECRET_ACCESS_KEY")
        self.endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        self.region = os.environ.get("S3_REGION", "us-east-1")
        self._client = None

        if not HAS_BOTO3:
            raise ImportError("boto3 is required: pip install boto3")

        if not self.access_key or not self.secret_key:
            raise ValueError(
                "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY environment variables are required"
            )

    @property
    def client(self):
        """Lazy-initialize boto3 S3 client."""
        if self._client is None:
            kwargs = {
                "service_name": "s3",
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key,
                "region_name": self.region,
            }
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            self._client = boto3.client(**kwargs)
        return self._client

    def upload(self, local_path: str, s3_key: str) -> str:
        """Upload file to S3.

        Args:
            local_path: Local file path
            s3_key: S3 object key (e.g. "jobs/abc123/input_image.png")

        Returns:
            S3 URI (s3://bucket/key)
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"File not found: {local_path}")

        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        print(f"☁️ Uploading to S3: {s3_key} ({size_mb:.2f} MB)")

        # Set content type based on extension
        ext = Path(local_path).suffix.lower()
        content_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".mp4": "video/mp4",
            ".json": "application/json",
            ".txt": "text/plain",
        }.get(ext, "application/octet-stream")

        self.client.upload_file(
            local_path,
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )

        s3_uri = f"s3://{self.bucket}/{s3_key}"
        print(f"   Uploaded: {s3_uri}")
        return s3_uri

    def download(self, s3_key: str, local_path: str) -> str:
        """Download file from S3 to local path.

        Args:
            s3_key: S3 object key
            local_path: Local destination path

        Returns:
            Local file path
        """
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        print(f"☁️ Downloading from S3: {s3_key}")

        self.client.download_file(self.bucket, s3_key, local_path)

        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        print(f"   Downloaded: {local_path} ({size_mb:.2f} MB)")
        return local_path

    def upload_job_asset(self, local_path: str, job_id: str, filename: str) -> str:
        """Upload a file as a job asset.

        Args:
            local_path: Local file path
            job_id: Job identifier
            filename: Asset filename (e.g. "input_image.png", "clip_01.mp4")

        Returns:
            S3 URI
        """
        s3_key = f"{self.get_job_prefix(job_id)}{filename}"
        return self.upload(local_path, s3_key)

    def upload_job_metadata(self, job_id: str, metadata: dict) -> str:
        """Upload job metadata (plan.json) to S3.

        Args:
            job_id: Job identifier
            metadata: Dict to serialize as JSON

        Returns:
            S3 URI
        """
        s3_key = f"{self.get_job_prefix(job_id)}plan.json"
        json_bytes = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")

        print(f"☁️ Uploading metadata to S3: {s3_key}")
        self.client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=json_bytes,
            ContentType="application/json",
        )

        s3_uri = f"s3://{self.bucket}/{s3_key}"
        print(f"   Uploaded: {s3_uri}")
        return s3_uri

    def list_job_assets(self, job_id: str) -> list[dict]:
        """List all assets for a job.

        Args:
            job_id: Job identifier

        Returns:
            List of dicts with 'key', 'size', 'last_modified'
        """
        prefix = self.get_job_prefix(job_id)
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)

        assets = []
        for obj in response.get("Contents", []):
            assets.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
                "filename": obj["Key"].removeprefix(prefix),
            })
        return assets

    @staticmethod
    def generate_job_id() -> str:
        """Generate unique job ID: YYYYMMDD_HHMMSS_shortUUID."""
        ts = time.strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"{ts}_{short_uuid}"

    @staticmethod
    def get_job_prefix(job_id: str) -> str:
        """Return S3 prefix for a job: jobs/{job_id}/"""
        return f"jobs/{job_id}/"


# =============================================================================
# CLI Test
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="S3 Storage Test")
    parser.add_argument("--upload", type=str, help="File to upload")
    parser.add_argument("--key", type=str, help="S3 key for upload")
    parser.add_argument("--download", type=str, help="S3 key to download")
    parser.add_argument("--output", "-o", type=str, help="Download output path")
    parser.add_argument("--list-job", type=str, help="List assets for a job ID")
    parser.add_argument("--test", action="store_true", help="Run connectivity test")
    args = parser.parse_args()

    # Load .env if dotenv is available
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded .env from {env_path}")
    except ImportError:
        pass

    s3 = S3Storage()

    if args.test:
        print(f"Bucket: {s3.bucket}")
        print(f"Region: {s3.region}")
        job_id = s3.generate_job_id()
        print(f"Sample job ID: {job_id}")
        print(f"Sample prefix: {s3.get_job_prefix(job_id)}")

        # Quick connectivity test: list bucket
        try:
            response = s3.client.list_objects_v2(
                Bucket=s3.bucket, Prefix="jobs/", MaxKeys=5
            )
            count = response.get("KeyCount", 0)
            print(f"S3 connectivity OK ({count} objects in jobs/)")
        except Exception as e:
            print(f"S3 connectivity FAILED: {e}")

    elif args.upload and args.key:
        s3.upload(args.upload, args.key)

    elif args.download and args.output:
        s3.download(args.download, args.output)

    elif args.list_job:
        assets = s3.list_job_assets(args.list_job)
        if assets:
            for a in assets:
                size_kb = a["size"] / 1024
                print(f"  {a['filename']:30s} {size_kb:>10.1f} KB")
        else:
            print("  No assets found")

    else:
        parser.print_help()
