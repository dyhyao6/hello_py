from pydantic import BaseModel
from typing import Optional
import datetime

class FileResponse(BaseModel):
    id: int
    user_id: Optional[int]
    name: Optional[str]
    size: Optional[int]
    bucket: Optional[str]
    path: Optional[str]
    md5: Optional[str]
    upload_status: int
    upload_id: Optional[str]
    part_size: Optional[int]
    part_count: Optional[int]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {
        "from_attributes": True  # 开启 from_orm 功能
    }