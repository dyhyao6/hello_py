from typing import Optional

from sqlalchemy import Integer, BigInteger, String, DateTime, SmallInteger
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
import datetime

Base = declarative_base()

class File(Base):
    """
    maas_demo.file 表对应的 Doris 实体类
    """
    __tablename__ = "file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键ID")  # Doris 不支持 autoincrement
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="更新时间")
    user_id: Mapped[Optional[int]] = mapped_column(Integer, comment="用户id")
    md5: Mapped[Optional[str]] = mapped_column(String(50), comment="md5")
    name: Mapped[Optional[str]] = mapped_column(String(100), comment="名称")
    size: Mapped[Optional[int]] = mapped_column(BigInteger, comment="文件大小(单位 byte)")
    bucket: Mapped[Optional[str]] = mapped_column(String(50), comment="bucket")
    path: Mapped[Optional[str]] = mapped_column(String(200), comment="存储路径")
    upload_id: Mapped[Optional[str]] = mapped_column(String(300), comment="分片上传id")
    part_size: Mapped[Optional[int]] = mapped_column(Integer, comment="分片大小(单位 M)")
    part_count: Mapped[Optional[int]] = mapped_column(Integer, comment="分片数量")
    upload_status: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="上传状态（0: 进行中, 1: 成功）")