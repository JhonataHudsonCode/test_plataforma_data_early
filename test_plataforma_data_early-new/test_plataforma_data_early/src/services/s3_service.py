import os
import shutil
from pathlib import Path
import zipfile
import boto3
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class S3Service:

    def __init__(self):
        self.bucket = os.getenv("S3_BUCKET")
        self.region = os.getenv("AWS_REGION", "us-east-1")

        if not self.bucket:
            raise ValueError("S3_BUCKET environment variable is not set.")

        self.s3 = boto3.client(
            "s3",
            region_name=self.region,
        )

 
    def zip_report(self) -> Path:
        report_path = Path("reports/client-validation").resolve()   
        if not report_path.is_dir():
            raise FileNotFoundError(f"Report directory not found at {report_path}") 
        file_path = report_path / "relatorio_geral.html"
    
        if not file_path.is_file():
            raise FileNotFoundError(f"FIle not found at {file_path}")   
        
        zip_path = report_path.parent / "report-early.zip"
    
        with zipfile.ZipFile(
	    	zip_path,
	    	"w",
	    	compression=zipfile.ZIP_DEFLATED,
	    ) as zip_file:
    
            zip_file.write(
                file_path,
                arcname=file_path.name,
            )   

        print (f"Report zipped at {zip_path}")
        return zip_path

    def upload_report(self) -> str:
        zip_path = self.zip_report()

        execution_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        s3_key = (
            f"report-geral/"
            f"{execution_date}/"
            f"report-early.zip"
        )

        self.s3.upload_file(
            str(zip_path),
            self.bucket,
            s3_key
        )

        print("========================================")
        print("Report uploaded to S3 successfully.")
        print(f"Bucket: {self.bucket}")
        print(f"Key: {s3_key}")
        print("========================================")
        return s3_key