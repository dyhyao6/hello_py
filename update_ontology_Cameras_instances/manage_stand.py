#!/usr/bin/env python3
"""
Stand 实例管理脚本
功能：
1. 根据 StandId 检查 Stand 记录是否存在
2. 不存在则新增 Stand 记录
3. 存在则更新 cameraIDs 属性
"""

import json
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# 数据库配置
DB_CONFIG = {
    "host": "172.16.11.20",
    "port": 54332,
    "database": "sync_engine_db",
    "user": "postgres",
    "password": "postgres"
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def check_stand_exists(stand_id: str):
    """检查 Stand 记录是否存在"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                SELECT id, properties
                FROM object_instances
                WHERE object_type_api_name = 'Stand'
                  AND state = 'ACTIVE'
                  AND properties ->>'standID' = %s
                    LIMIT 1
                """, (stand_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def create_stand(stand_id: str, camera_ids: list = None):
    """创建新的 Stand 记录"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 生成 UUID 作为 id
    instance_id = str(uuid.uuid4())

    # 构建 properties
    properties = {
        "ID": stand_id,
        "standID": stand_id,
        "cameraID": camera_ids or [],
        "category": stand_id,
        "aeroplaneInPosition": "false"
    }

    cur.execute("""
                INSERT INTO object_instances (id, object_type_id, object_type_api_name, properties, version, state,
                                              source_id)
                VALUES (%s, %s, 'Stand', %s, 1, 'ACTIVE', %s) RETURNING id
                """, (instance_id, str(uuid.uuid4()), json.dumps(properties, ensure_ascii=False), f"stand_{stand_id}"))

    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 创建 Stand {stand_id} 成功，新记录ID: {new_id}")
    return new_id


def update_stand_camera_ids(stand_id: str, camera_ids: list):
    """更新 Stand 记录的 cameraIDs 属性"""
    conn = get_connection()
    cur = conn.cursor()

    properties = {
        "ID": stand_id,
        "standID": stand_id,
        "cameraID": camera_ids,
        "category": stand_id,
        "aeroplaneInPosition": "false"
    }

    cur.execute("""
                UPDATE object_instances
                SET properties   = %s,
                    version      = version + 1,
                    updated_at   = CURRENT_TIMESTAMP,
                    last_updated = CURRENT_TIMESTAMP
                WHERE object_type_api_name = 'Stand'
                  AND state = 'ACTIVE'
                  AND properties ->>'standID' = %s
                    RETURNING id
                """, (json.dumps(properties, ensure_ascii=False), stand_id))

    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if row:
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 更新 Stand {stand_id} 的 cameraIDs 成功，ID: {row['id']}")
        return row['id']
    return None


def process_stand(stand_id: str, camera_ids: list = None):
    """
    处理 Stand 记录
    1. 检查是否存在
    2. 不存在则创建，存在则更新 cameraIDs
    """
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== 处理 Stand: {stand_id} ==========")

    # 检查是否存在
    existing = check_stand_exists(stand_id)

    if existing:
        print(f"Stand {stand_id} 已存在，ID: {existing['id']}")
        print(f"  原 cameraIDs: {existing['properties'].get('cameraID', [])}")

        if camera_ids:
            # 更新 cameraIDs
            update_stand_camera_ids(stand_id, camera_ids)
            print(f"  新 cameraIDs: {camera_ids}")
        else:
            print("  未提供 cameraIds，跳过更新")
    else:
        print(f"Stand {stand_id} 不存在，即将创建...")
        if camera_ids is None:
            camera_ids = []
        create_stand(stand_id, camera_ids)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== Stand {stand_id} 处理完成 ==========")


def main():
    # 直接写在代码里
    stand_id = "102"
    camera_ids = []  # 可选，None 则只查询不更新

    process_stand(stand_id, camera_ids)


if __name__ == "__main__":
    main()
