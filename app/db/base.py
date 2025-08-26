from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# 创建基础模型类
Base = declarative_base()

# 创建元数据对象
metadata = MetaData()
