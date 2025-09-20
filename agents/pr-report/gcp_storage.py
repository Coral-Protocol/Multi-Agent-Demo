"""
GCP Cloud Storage utilities for uploading PDF reports
"""

import os
from datetime import datetime
from typing import Optional
from google.cloud import storage
import io


class GCPStorageUploader:
    """Handle PDF uploads to Google Cloud Storage"""
    
    def __init__(self, bucket_name: str = None, credentials_path: str = None):
        """
        Initialize GCP Storage client
        
        Args:
            bucket_name: GCS bucket name (can also be set via GCP_BUCKET_NAME env var)
            credentials_path: Path to service account JSON (can also be set via GOOGLE_APPLICATION_CREDENTIALS env var)
        """
        self.bucket_name = bucket_name or os.getenv("GCP_BUCKET_NAME")
        if not self.bucket_name:
            raise ValueError("GCP_BUCKET_NAME must be provided either as parameter or environment variable")
        
        # Set credentials path if provided
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        elif not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set. Using default credentials.")
        
        # Initialize the client
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
        except Exception as e:
            raise Exception(f"Failed to initialize GCP Storage client: {str(e)}")
    
    def upload_pdf(self, pdf_bytes: bytes, filename: str = None, folder: str = "reports") -> str:
        """
        Upload PDF bytes to GCS and return public URL
        
        Args:
            pdf_bytes: PDF file content as bytes
            filename: Custom filename (defaults to timestamped name)
            folder: Folder/prefix in bucket (default: "reports")
            
        Returns:
            Public URL of the uploaded PDF
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            filename = f"news-report-{timestamp}.pdf"
        
        # Add folder prefix if specified
        if folder:
            blob_name = f"{folder}/{filename}"
        else:
            blob_name = filename
        
        try:
            # Create blob and upload
            blob = self.bucket.blob(blob_name)
            
            # Upload the PDF bytes
            blob.upload_from_string(pdf_bytes, content_type='application/pdf')
            
            # Generate public URL (works with uniform bucket-level access)
            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"
            print(f"Successfully uploaded PDF to: {public_url}")
            
            return public_url
            
        except Exception as e:
            raise Exception(f"Failed to upload PDF to GCS: {str(e)}")
    
    def upload_pdf_with_metadata(self, pdf_bytes: bytes, topic: str, sections_count: int, 
                                filename: str = None, folder: str = "reports") -> dict:
        """
        Upload PDF with metadata and return detailed response
        
        Args:
            pdf_bytes: PDF file content as bytes
            topic: The news topic that was processed
            sections_count: Number of sections in the report
            filename: Custom filename (defaults to topic-based name)
            folder: Folder/prefix in bucket
            
        Returns:
            Dictionary with upload details and public URL
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_topic = safe_topic.replace(' ', '-').lower()[:30]  # Limit length
            filename = f"{safe_topic}-report-{timestamp}.pdf"
        
        # Add folder prefix if specified
        if folder:
            blob_name = f"{folder}/{filename}"
        else:
            blob_name = filename
        
        try:
            # Create blob and upload
            blob = self.bucket.blob(blob_name)
            
            # Set metadata
            blob.metadata = {
                'topic': topic,
                'sections_count': str(sections_count),
                'created_at': datetime.now().isoformat(),
                'content_type': 'news_report'
            }
            
            # Upload the PDF bytes
            blob.upload_from_string(pdf_bytes, content_type='application/pdf')
            
            # Generate public URL (works with uniform bucket-level access)
            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"
            
            # Return detailed response
            response = {
                'success': True,
                'pdf_url': public_url,
                'filename': filename,
                'blob_name': blob_name,
                'bucket_name': self.bucket_name,
                'size_bytes': len(pdf_bytes),
                'topic': topic,
                'sections_count': sections_count,
                'uploaded_at': datetime.now().isoformat()
            }
            
            print(f"Successfully uploaded PDF: {response['pdf_url']}")
            return response
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to upload PDF to GCS: {str(e)}",
                'pdf_url': None
            }


def upload_report_to_gcs(pdf_bytes: bytes, topic: str, sections_count: int, 
                        bucket_name: str = None) -> dict:
    """
    Convenience function to upload a report PDF to GCS
    
    Args:
        pdf_bytes: PDF content as bytes
        topic: News topic
        sections_count: Number of report sections
        bucket_name: GCS bucket name (optional, uses env var if not provided)
        
    Returns:
        Upload result dictionary with PDF URL
    """
    try:
        uploader = GCPStorageUploader(bucket_name=bucket_name)
        return uploader.upload_pdf_with_metadata(pdf_bytes, topic, sections_count)
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'pdf_url': None
        }
