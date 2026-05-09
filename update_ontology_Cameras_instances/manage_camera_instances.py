#!/usr/bin/env python3
"""
Camera 实例管理脚本
功能：
1. 检查 Camera 实例是否存在
2. 不存在则新增，存在则更新
3. properties 数据从源库 v_algorithm_param_grid 和 v_algorithm_param_post_roi 获取
"""

import json
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# 源库配置（查询 v_algorithm_param_grid 和 v_algorithm_param_post_roi）
SOURCE_DB_CONFIG = {
    "host": "10.143.36.7",
    "port": 31647,
    "database": "edi_data",
    "user": "readonly",
    "password": "88UM6Joj7BhBPKjN0E1B"
}

# 目标库配置（object_instances）
TARGET_DB_CONFIG = {
    "host": "172.16.11.20",
    "port": 54332,
    "database": "sync_engine_db",
    "user": "postgres",
    "password": "postgres"
}


def get_source_connection():
    return psycopg2.connect(**SOURCE_DB_CONFIG)


def get_target_connection():
    return psycopg2.connect(**TARGET_DB_CONFIG)


def parse_json_field(value):
    """解析JSON字符串字段，保持原始类型"""
    if not value:
        return []
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def check_camera_exists(camera_id: str):
    """检查 Camera 实例是否存在"""
    conn = get_target_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id, properties
        FROM object_instances
        WHERE object_type_api_name = 'Camera'
          AND state = 'ACTIVE'
          AND properties::text LIKE %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (f"%{camera_id}%",))

    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def query_grid_from_source(camera_id: str):
    """从源库查询 v_algorithm_param_grid 视图，返回 index, point, geopoint 数据"""
    conn = get_source_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
        SELECT index, point, gis
        FROM v_algorithm_param_grid
        WHERE camera_id = %s
        LIMIT 1
    """
    cur.execute(sql, (camera_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "index": parse_json_field(row["index"]),
        "point": parse_json_field(row["point"]),
        "geopoint": parse_json_field(row["gis"])
    }


def query_post_roi_from_source(camera_id: str):
    """从源库查询 v_algorithm_param_post_roi 表，返回 postSafeguard 和 safetyScenarios 数据"""
    conn = get_source_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
        SELECT type, roi, roi_of_detection, aircraft_model, area_title, name
        FROM v_algorithm_param_post_roi
        WHERE camera_id = %s
          AND (type = 'post_safeguard' OR type = 'post_safety_scenarios')
    """
    cur.execute(sql, (camera_id,))
    results = cur.fetchall()
    cur.close()
    conn.close()

    post_safeguard_list = []
    safety_scenarios_list = []

    for row in results:
        item = {
            "type": row["type"] or "",
            "roi": parse_json_field(row["roi"]),
            "roi_of_detection": parse_json_field(row["roi_of_detection"]),
            "aircraft_model": row["aircraft_model"] or "",
            "area_title": row["area_title"] or "",
            "name": row["name"] or ""
        }
        if row["type"] == "post_safeguard":
            post_safeguard_list.append(item)
        elif row["type"] == "post_safety_scenarios":
            safety_scenarios_list.append(item)

    return post_safeguard_list, safety_scenarios_list


def create_camera(camera_data: dict, properties: dict):
    """创建新的 Camera 实例"""
    conn = get_target_connection()
    cur = conn.cursor()

    instance_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO object_instances (id, object_type_id, object_type_api_name, properties, version, state, source_id)
        VALUES (%s, %s, 'Camera', %s, 1, 'ACTIVE', %s)
        RETURNING id
    """, (instance_id, str(uuid.uuid4()), json.dumps(properties, ensure_ascii=False), f"camera_{camera_data['cameraID']}"))

    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 创建 Camera {camera_data['cameraID']} 成功，ID: {new_id}")
    return new_id


def update_camera(camera_id: str, properties: dict):
    """更新 Camera 实例"""
    conn = get_target_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE object_instances
        SET properties = %s,
            version = version + 1,
            updated_at = CURRENT_TIMESTAMP,
            last_updated = CURRENT_TIMESTAMP
        WHERE object_type_api_name = 'Camera'
          AND state = 'ACTIVE'
          AND properties::text LIKE %s
        RETURNING id
    """, (json.dumps(properties, ensure_ascii=False), f"%{camera_id}%"))

    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if row:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 更新 Camera {camera_id} 成功，ID: {row['id']}")
        return row['id']
    return None


def build_camera_properties(camera_id: str, base_data: dict):
    """从源库构建完整的 Camera properties"""
    # 查询 grid 数据
    grid_data = query_grid_from_source(camera_id)

    # 查询 roi 数据
    post_safeguard, safety_scenarios = query_post_roi_from_source(camera_id)

    # 构建 properties
    properties = {
        "name": base_data.get("name", ""),
        "index": grid_data["index"] if grid_data else [],
        "point": grid_data["point"] if grid_data else [],
        "areaCode": base_data.get("areaCode", ""),
        "cameraID": camera_id,
        "geopoint": grid_data["geopoint"] if grid_data else [],
        "isActive": True,
        "postSafeguard": post_safeguard,
        "safetyScenarios": safety_scenarios
    }

    return properties


def process_camera(camera_data: dict):
    """
    处理单个 Camera 实例
    camera_data: {"name": "4034(新)", "cameraID": "551932025727", "areaCode": "234"}
    """
    camera_id = camera_data["cameraID"]
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== 处理 Camera: {camera_id} ==========")

    # 检查是否存在
    existing = check_camera_exists(camera_id)

    # 从源库构建 properties 数据
    properties = build_camera_properties(camera_id, camera_data)

    if existing:
        print(f"Camera {camera_id} 已存在，ID: {existing['id']}")
        update_camera(camera_id, properties)
    else:
        print(f"Camera {camera_id} 不存在，即将创建...")
        create_camera(camera_data, properties)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== Camera {camera_id} 处理完成 ==========")


def process_cameras(camera_list: list):
    """批量处理 Camera 列表"""
    for camera_data in camera_list:
        process_camera(camera_data)


def main():
    # 直接写在代码里
    camera_data_list = [
        {"name": "4034(新)", "cameraID": "551932025727", "areaCode": "234"},
        # 可以添加更多 Camera 数据
    ]

    process_cameras(camera_data_list)


if __name__ == "__main__":
    main()