from sqlalchemy import Column, BigInteger, String, Text, Boolean, DateTime, JSON, Enum
from sqlalchemy.sql import func
from app.db.base import Base


class VersionInfo(Base):
    """版本信息表"""
    __tablename__ = "version_info"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="版本ID")
    version_code = Column(String(20), nullable=False, comment="版本号（如：1.0.0）")
    version_name = Column(String(50), nullable=False, comment="版本名称（如：FastIoT v1.0.0）")
    platform = Column(Enum('android', 'ios', 'web', 'server', 'all', name='platform_enum'), 
                     nullable=False, default='all', comment="目标平台：android/ios/web/server/all")
    title = Column(String(255), nullable=False, comment="版本标题")
    description = Column(Text, nullable=False, comment="版本描述")
    download_url = Column(String(500), nullable=True, comment="下载链接")
    file_size = Column(BigInteger, nullable=True, comment="文件大小（字节）")
    md5_hash = Column(String(32), nullable=True, comment="文件MD5校验值")
    is_force_update = Column(Boolean, default=False, comment="是否强制更新")
    min_supported_version = Column(String(20), nullable=True, comment="最低支持版本")
    extra = Column(JSON, nullable=True, comment="扩展信息")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="更新时间")
