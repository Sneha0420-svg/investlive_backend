from pydantic import BaseModel
from datetime import date

# Base schema with common fields and orm_mode
class UploadBase(BaseModel):
    id: int
    group_id: str
    upload_date: date
    data_date: date
    data_type: str
    file_name: str
    file_path: str

    class Config:
        orm_mode = True

# Schema for creating a new upload (optional if needed)
class UploadCreate(BaseModel):
    upload_date: date
    data_date: date
    data_type: str
    file_name: str
    file_path: str

# Schema for returning a response after upload
class UploadResponse(BaseModel):
    status: str
    uploaded_file: str
    data_type: str
