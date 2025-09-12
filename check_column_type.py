#!/usr/bin/env python3
"""
检查数据库中 can_control 字段的类型
"""

import asyncio
from sqlalchemy import text
from app.db.session import engine

async def check_column_type():
    """检查 can_control 字段类型"""
    async with engine.begin() as conn:
        # 查询表结构
        result = await conn.execute(text("DESCRIBE member_device_permission"))
        columns = result.fetchall()
        
        print("📋 member_device_permission 表结构:")
        print("-" * 50)
        for column in columns:
            field, type_info, null, key, default, extra = column
            print(f"字段: {field}")
            print(f"类型: {type_info}")
            print(f"允许NULL: {null}")
            print(f"键: {key}")
            print(f"默认值: {default}")
            print(f"额外: {extra}")
            print("-" * 30)
        
        # 查询一些示例数据
        result = await conn.execute(text("SELECT id, member_id, device_id, can_control FROM member_device_permission LIMIT 5"))
        rows = result.fetchall()
        
        print("\n📊 示例数据:")
        print("-" * 50)
        for row in rows:
            print(f"ID: {row[0]}, Member: {row[1]}, Device: {row[2]}, Can Control: {row[3]} (类型: {type(row[3])})")

if __name__ == "__main__":
    asyncio.run(check_column_type())
