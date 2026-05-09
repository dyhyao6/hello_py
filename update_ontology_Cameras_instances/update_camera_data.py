#!/usr/bin/env python3
"""
根据 StandId 更新 ontology 数据库中 Camera 实例的 properties 字段。
数据来源：源库 edi_data 的 v_algorithm_param_post_roi 表
目标库：ontology 数据库的 object_instances 表
"""

import json
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# 源库配置（只读，查询 v_algorithm_param_post_roi）
SOURCE_DB_CONFIG = {
    "host": "10.143.36.7",
    "port": 31647,
    "database": "edi_data",
    "user": "readonly",
    "password": "88UM6Joj7BhBPKjN0E1B"
}

# 目标库配置（更新 object_instances）
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


def get_stand_camera_ids(stand_id: str):
    """根据 StandId 查询 Stand 记录，返回 cameraID 列表"""
    conn = get_target_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT properties
        FROM object_instances
        WHERE object_type_api_name = 'Stand'
          AND state = 'ACTIVE'
          AND properties->>'standID' = %s
        LIMIT 1
    """, (stand_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        print(f"未找到 standID={stand_id} 的 Stand 记录")
        return []

    properties = row["properties"]
    camera_ids = properties.get("cameraID", [])
    if isinstance(camera_ids, str):
        camera_ids = [camera_ids]
    print(f"Stand {stand_id} 的 cameraID 列表: {camera_ids}")
    return camera_ids


def get_camera_instance_by_id(camera_id: str):
    """根据 cameraID 查询 Camera 实例的 properties"""
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

    return row if row else None


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


def update_camera_instance(camera_id: str, new_properties: dict):
    """更新 Camera 实例的 properties 字段"""
    conn = get_target_connection()
    cur = conn.cursor()

    sql = """
        UPDATE object_instances
        SET properties = %s,
            version = version + 1,
            updated_at = CURRENT_TIMESTAMP,
            last_updated = CURRENT_TIMESTAMP
        WHERE object_type_api_name = 'Camera'
          AND state = 'ACTIVE'
          AND properties::text LIKE %s
    """
    cur.execute(sql, (json.dumps(new_properties, ensure_ascii=False), f"%{camera_id}%"))
    affected = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return affected


def process_stand(stand_id: str):
    """处理单个 Stand，更新其下所有 Camera 实例的 properties"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== 开始处理 StandId: {stand_id} ==========")

    # 1. 获取 Stand 的 cameraID 列表
    camera_ids = get_stand_camera_ids(stand_id)
    if not camera_ids:
        print(f"未找到 Stand {stand_id} 下的 cameraID")
        return

    # 2. 遍历 cameraID，查询源库数据并更新目标库
    for camera_id in camera_ids:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 处理 Camera: {camera_id}")

        # 查询 Camera 实例（获取原有 properties 作为基础）
        camera_instance = get_camera_instance_by_id(camera_id)
        if not camera_instance:
            print(f"  未找到 Camera {camera_id} 的实例，跳过")
            continue

        original_properties = camera_instance["properties"]
        instance_id = camera_instance["id"]
        print(f"  实例ID: {instance_id}")
        print(f"  原 properties: {json.dumps(original_properties, ensure_ascii=False)[:200]}...")

        # 查询源库 roi 数据
        post_safeguard, safety_scenarios = query_post_roi_from_source(camera_id)
        print(f"  源库 roi 数据: postSafeguard={len(post_safeguard)}条, safetyScenarios={len(safety_scenarios)}条")

        # 查询源库 grid 数据 (index, point, geopoint)
        grid_data = query_grid_from_source(camera_id)
        if grid_data:
            print(f"  源库 grid 数据: index={len(grid_data['index'])}项, point={len(grid_data['point'])}项, geopoint={len(grid_data['geopoint'])}项")
        else:
            print(f"  源库 grid 数据: 未找到")

        # 构建新 properties（保留原 properties 中的基础字段，更新 roi 和 grid 相关字段）
        new_properties = dict(original_properties)
        new_properties["postSafeguard"] = post_safeguard
        new_properties["safetyScenarios"] = safety_scenarios
        if grid_data:
            new_properties["index"] = grid_data["index"]
            new_properties["point"] = grid_data["point"]
            new_properties["geopoint"] = grid_data["geopoint"]

        # 更新目标库
        affected = update_camera_instance(camera_id, new_properties)
        if affected > 0:
            print(f"  更新成功，affected rows: {affected}")
        else:
            print(f"  更新失败，未影响到任何行")

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== StandId {stand_id} 处理完成 ==========")


def main():
    stand_id = "102"
    process_stand(stand_id)


if __name__ == "__main__":
    main()
