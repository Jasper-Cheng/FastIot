"""
时间工具函数
"""
from datetime import datetime, timezone, timedelta


def get_local_time():
    """获取正确的本地时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    local_time = utc_now + timedelta(hours=8)
    return local_time


def get_utc_time():
    """获取UTC时间"""
    return datetime.now(timezone.utc)
