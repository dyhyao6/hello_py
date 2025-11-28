from pydantic import BaseModel, Field
import datetime


class FileUploadRequest(BaseModel):
    id: int = Field(default=43245)
    user_id: int = Field(default=2)
    name: str = Field(default="test")
    size: int = Field(default=1024)
    bucket: str = Field(default="test_bucket")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    path: str = Field(default="test")
    md5: str = Field(default="test")
    upload_status: int = Field(default=1)
    upload_id: str = Field(default="test")
    part_size: int = Field(default=10)
    part_count: int = Field(default=10)
