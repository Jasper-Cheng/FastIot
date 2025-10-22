from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class PlatformEnum(str, Enum):
    android = "android"
    ios = "ios"
    web = "web"
    server = "server"
    all = "all"


class VersionInfoBase(BaseModel):
    version_code: str = Field(..., description="版本号")
    version_name: str = Field(..., description="版本名称")
    platform: PlatformEnum = Field(default=PlatformEnum.all, description="目标平台")
    title: str = Field(..., description="版本标题")
    description: str = Field(..., description="版本描述")
    download_url: Optional[str] = Field(None, description="下载链接")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    is_force_update: bool = Field(default=False, description="是否强制更新")
    min_supported_version: Optional[str] = Field(None, description="最低支持版本")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展信息")


class VersionInfoCreate(VersionInfoBase):
    pass


class VersionInfoUpdate(BaseModel):
    version_code: Optional[str] = None
    version_name: Optional[str] = None
    platform: Optional[PlatformEnum] = None
    title: Optional[str] = None
    description: Optional[str] = None
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    is_force_update: Optional[bool] = None
    min_supported_version: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class VersionInfo(VersionInfoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
