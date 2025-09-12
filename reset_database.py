#!/usr/bin/env python3
"""
数据库重置脚本
删除现有数据库并重新创建，填充丰富的测试数据
"""

import asyncio
import sys
from sqlalchemy import text
from app.db.session import engine
from app.db.init_db import init_db

async def reset_database():
    """重置数据库"""
    print("🔄 开始重置数据库...")
    
    try:
        # 删除所有表
        async with engine.begin() as conn:
            print("🗑️  删除现有表...")
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SET FOREIGN_KEY_CHECKS = 0")))
            
            # 获取所有表名
            result = await conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            
            # 删除所有表
            for table in tables:
                await conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                print(f"   ✅ 删除表: {table}")
            
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SET FOREIGN_KEY_CHECKS = 1")))
            print("✅ 所有表已删除")
        
        # 重新创建数据库和表
        print("🏗️  重新创建数据库...")
        await init_db()
        
        print("🎉 数据库重置完成！")
        print("\n📊 创建的测试数据包括:")
        print("   👥 5个用户")
        print("   👤 5个成员")
        print("   🏠 8个房间")
        print("   📱 8种设备型号")
        print("   🔧 16个设备")
        print("   🔗 房间设备关联")
        print("   🔐 成员设备权限")
        print("   📊 设备参数数据")
        print("   📝 设备日志记录")
        print("   ⚠️  告警记录")
        
    except Exception as e:
        print(f"❌ 数据库重置失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(reset_database())
