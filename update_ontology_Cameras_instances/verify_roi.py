#!/usr/bin/env python3
"""
ROI 数据校验脚本
功能：根据 cameraID、type、area_title、aircraft_model 查询源库和目标库，对比 roi 数据是否一致
"""

import json
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

# 目标库配置（查询 object_instances）
TARGET_DB_CONFIG = {
    "host": "172.16.11.20",
    "port": 54332,
    "database": "sync_engine_db",
    "user": "postgres",
    "password": "postgres"
}


def query_source(camera_id: str, roi_type: str = None, area_title: str = None, aircraft_model: str = None):
    """查询源库 v_algorithm_param_post_roi 表"""
    conn = psycopg2.connect(**SOURCE_DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
        SELECT type, roi, roi_of_detection, aircraft_model, area_title, name
        FROM v_algorithm_param_post_roi
        WHERE camera_id = %s
    """
    params = [camera_id]

    if roi_type:
        sql += " AND type = %s"
        params.append(roi_type)
    if area_title:
        sql += " AND area_title = %s"
        params.append(area_title)
    if aircraft_model:
        sql += " AND aircraft_model = %s"
        params.append(aircraft_model)

    sql += " ORDER BY type, area_title"
    cur.execute(sql, params)
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


def query_target(camera_id: str, roi_type: str = None, area_title: str = None, aircraft_model: str = None):
    """查询目标库 object_instances 表的 Camera 记录"""
    conn = psycopg2.connect(**TARGET_DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT properties
        FROM object_instances
        WHERE object_type_api_name = 'Camera'
          AND state = 'ACTIVE'
          AND properties->>'cameraID' = %s
        LIMIT 1
    """, (camera_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return []

    properties = row["properties"]

    # 从 postSafeguard 和 safetyScenarios 中提取
    all_rois = []

    for field in ["postSafeguard", "safetyScenarios"]:
        items = properties.get(field, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if roi_type and item.get("type") != roi_type:
                continue
            if area_title and item.get("area_title") != area_title:
                continue
            if aircraft_model and item.get("aircraft_model") != aircraft_model:
                continue
            all_rois.append({
                "type": item.get("type"),
                "roi": item.get("roi"),
                "roi_of_detection": item.get("roi_of_detection"),
                "aircraft_model": item.get("aircraft_model"),
                "area_title": item.get("area_title"),
                "name": item.get("name"),
                "_source_field": field
            })

    return all_rois


def normalize_roi(roi_data):
    """标准化 roi 数据用于比对"""
    if isinstance(roi_data, str):
        try:
            roi_data = json.loads(roi_data)
        except:
            pass
    if not isinstance(roi_data, list):
        return None
    # 排序以保证顺序一致
    return sorted([tuple(item) if isinstance(item, list) else item for item in roi_data])


def main(camera_id: str = None, roi_type: str = None, area_title: str = None, aircraft_model: str = None):
    """
    camera_id: 必填，指定要校验的 Camera ID
    roi_type: 可选，指定 type 维度进行校验（如 post_safeguard 或 post_safety_scenarios）
    area_title: 可选，指定 area_title 维度进行校验
    aircraft_model: 可选，指定 aircraft_model 维度进行校验

    主函数，执行数据校验流程"""

    print("=" * 60)
    print("ROI 数据校验")
    print("=" * 60)
    print(f"camera_id:      {camera_id}")
    if roi_type:
        print(f"type:          {roi_type}")
    if area_title:
        print(f"area_title:    {area_title}")
    if aircraft_model:
        print(f"aircraft_model: {aircraft_model}")
    print("=" * 60)

    # 查询源库
    source_data = query_source(camera_id, roi_type, area_title, aircraft_model)
    print(f"\n源库 (v_algorithm_param_post_roi): 找到 {len(source_data)} 条记录")

    # 查询目标库
    target_data = query_target(camera_id, roi_type, area_title, aircraft_model)
    print(f"目标库 (object_instances): 找到 {len(target_data)} 条记录")

    if not source_data and not target_data:
        print("\n双方均无数据")
        return

    if not source_data:
        print("\n源库无数据，目标库有数据 - 数据不一致!")
        return

    if not target_data:
        print("\n源库有数据，目标库无数据 - 数据不一致!")
        return

    # 逐条比对
    print("\n" + "=" * 60)
    print("比对结果")
    print("=" * 60)

    source_dict = {}
    for item in source_data:
        key = (item["type"], item["area_title"], item["aircraft_model"])
        source_dict[key] = normalize_roi(item["roi"])

    target_dict = {}
    for item in target_data:
        key = (item["type"], item["area_title"], item["aircraft_model"])
        target_dict[key] = normalize_roi(item["roi"])

    all_keys = set(source_dict.keys()) | set(target_dict.keys())
    all_match = True

    for key in sorted(all_keys, key=str):
        src_roi = source_dict.get(key)
        tgt_roi = target_dict.get(key)

        if src_roi is None:
            print(f"\n[差异] 源库无，目标库有: type={key[0]}, area_title={key[1]}, aircraft_model={key[2]}")
            print(f"  目标 roi: {tgt_roi[:50] if tgt_roi else None}...")
            all_match = False
        elif tgt_roi is None:
            print(f"\n[差异] 源库有，目标库无: type={key[0]}, area_title={key[1]}, aircraft_model={key[2]}")
            print(f"  源 roi: {src_roi[:50] if src_roi else None}...")
            all_match = False
        elif src_roi == tgt_roi:
            print(f"\n[一致] type={key[0]}, area_title={key[1]}, aircraft_model={key[2]}")
            print(f"  roi 长度: {len(src_roi)}")
        else:
            print(f"\n[差异] type={key[0]}, area_title={key[1]}, aircraft_model={key[2]}")
            print(f"  源库 roi 长度: {len(src_roi)}")
            print(f"  目标库 roi 长度: {len(tgt_roi)}")
            print(f"  源库 roi 前5项: {src_roi[:5]}")
            print(f"  目标库 roi 前5项: {tgt_roi[:5]}")
            all_match = False

    print("\n" + "=" * 60)
    if all_match:
        print("结果: 全部一致 ✓")
    else:
        print("结果: 存在差异 ✗")
    print("=" * 60)


if __name__ == "__main__":
    # camera_id、type、area_title、aircraft_model 可根据需要修改进行不同维度的校验

    main(camera_id='55108135936', roi_type='post_safeguard', area_title='dinning_roi_three', aircraft_model='B737')
