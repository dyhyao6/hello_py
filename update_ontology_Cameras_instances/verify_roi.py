#!/usr/bin/env python3
"""
ROI + Grid 数据校验脚本
功能：根据 cameraID 查询源库和目标库，对比 index、point、geopoint、postSafeguard、safetyScenarios 数据是否一致
"""

import json
import psycopg2
from psycopg2.extras import RealDictCursor

# 源库配置
SOURCE_DB_CONFIG = {
    "host": "10.143.36.7",
    "port": 31647,
    "database": "edi_data",
    "user": "readonly",
    "password": "88UM6Joj7BhBPKjN0E1B"
}

# 目标库配置
TARGET_DB_CONFIG = {
    "host": "172.16.11.20",
    "port": 54332,
    "database": "sync_engine_db",
    "user": "postgres",
    "password": "postgres"
}


def parse_json_field(value):
    if not value:
        return []
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except:
        return []


def normalize_data(data):
    """标准化数据用于比对"""
    if isinstance(data, list):
        return sorted([tuple(item) if isinstance(item, list) else item for item in data])
    return data


def query_source_grid(camera_id: str):
    """从源库查询 v_algorithm_param_grid"""
    conn = psycopg2.connect(**SOURCE_DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT index, point, gis
        FROM v_algorithm_param_grid
        WHERE camera_id = %s
        LIMIT 1
    """, (camera_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "index": parse_json_field(row["index"]),
            "point": parse_json_field(row["point"]),
            "geopoint": parse_json_field(row["gis"])
        }
    return None


def query_source_roi(camera_id: str, roi_type: str = None, area_title: str = None, aircraft_model: str = None):
    """从源库查询 v_algorithm_param_post_roi"""
    conn = psycopg2.connect(**SOURCE_DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
        SELECT type, roi, roi_of_detection, aircraft_model, area_title, name
        FROM v_algorithm_param_post_roi
        WHERE camera_id = %s
          AND (type = 'post_safeguard' OR type = 'post_safety_scenarios')
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

    post_safeguard = []
    safety_scenarios = []

    for row in results:
        item = {
            "type": row["type"],
            "roi": parse_json_field(row["roi"]),
            "roi_of_detection": parse_json_field(row["roi_of_detection"]),
            "aircraft_model": row["aircraft_model"],
            "area_title": row["area_title"],
            "name": row["name"]
        }
        if row["type"] == "post_safeguard":
            post_safeguard.append(item)
        else:
            safety_scenarios.append(item)

    return post_safeguard, safety_scenarios


def query_target(camera_id: str):
    """从目标库查询 Camera 的 properties"""
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

    if row:
        return row["properties"]
    return None


def compare_field(field_name: str, source_data, target_data):
    """对比单个字段"""
    source_norm = normalize_data(source_data) if source_data else None
    target_norm = normalize_data(target_data) if target_data else None

    if source_norm == target_norm:
        return True, None
    else:
        return False, {
            "source_len": len(source_data) if source_data else 0,
            "target_len": len(target_data) if target_data else 0
        }


def verify_grid(camera_id: str):
    """校验 grid 数据 (index, point, geopoint)"""
    print("\n========== Grid 数据校验 (index, point, geopoint) ==========")

    source = query_source_grid(camera_id)
    target = query_target(camera_id)

    if not source:
        print(f"  源库: 未找到 v_algorithm_param_grid 数据")
        return

    print(f"  源库: index={len(source['index'])}项, point={len(source['point'])}项, geopoint={len(source['geopoint'])}项")

    if not target:
        print(f"  目标库: 未找到 Camera {camera_id} 的 properties")
        return

    print(f"  目标库: index={len(target.get('index', []))}项, point={len(target.get('point', []))}项, geopoint={len(target.get('geopoint', []))}项")

    # 对比 index
    match, detail = compare_field("index", source["index"], target.get("index", []))
    if match:
        print(f"  index: 一致 ✓")
    else:
        print(f"  index: 差异 ✗ (源库{detail['source_len']}项, 目标库{detail['target_len']}项)")

    # 对比 point
    match, detail = compare_field("point", source["point"], target.get("point", []))
    if match:
        print(f"  point: 一致 ✓")
    else:
        print(f"  point: 差异 ✗ (源库{detail['source_len']}项, 目标库{detail['target_len']}项)")

    # 对比 geopoint
    match, detail = compare_field("geopoint", source["geopoint"], target.get("geopoint", []))
    if match:
        print(f"  geopoint: 一致 ✓")
    else:
        print(f"  geopoint: 差异 ✗ (源库{detail['source_len']}项, 目标库{detail['target_len']}项)")


def verify_roi(camera_id: str, roi_type: str = None, area_title: str = None, aircraft_model: str = None):
    """校验 roi 数据 (postSafeguard, safetyScenarios)"""
    print("\n========== ROI 数据校验 (postSafeguard, safetyScenarios) ==========")

    source_ps, source_ss = query_source_roi(camera_id, roi_type, area_title, aircraft_model)
    target = query_target(camera_id)

    print(f"  源库: postSafeguard={len(source_ps)}条, safetyScenarios={len(source_ss)}条")

    if not target:
        print(f"  目标库: 未找到 Camera {camera_id} 的 properties")
        return

    target_ps = target.get("postSafeguard", [])
    target_ss = target.get("safetyScenarios", [])

    print(f"  目标库: postSafeguard={len(target_ps)}条, safetyScenarios={len(target_ss)}条")

    # 按 (type, area_title, aircraft_model) 分组对比
    def group_by_key(items):
        result = {}
        for item in items:
            key = (item.get("type"), item.get("area_title"), item.get("aircraft_model"))
            result[key] = item
        return result

    source_ps_dict = group_by_key(source_ps)
    target_ps_dict = group_by_key(target_ps)

    source_ss_dict = group_by_key(source_ss)
    target_ss_dict = group_by_key(target_ss)

    # 对比 postSafeguard
    print("\n  postSafeguard 对比:")
    all_keys = set(source_ps_dict.keys()) | set(target_ps_dict.keys())
    all_match = True
    for key in sorted(all_keys, key=str):
        src = source_ps_dict.get(key)
        tgt = target_ps_dict.get(key)
        if src is None:
            print(f"    [差异] 源库无，目标库有: {key}")
            all_match = False
        elif tgt is None:
            print(f"    [差异] 源库有，目标库无: {key}")
            all_match = False
        else:
            src_roi = normalize_data(src.get("roi"))
            tgt_roi = normalize_data(tgt.get("roi"))
            if src_roi == tgt_roi:
                print(f"    [一致] {key}: roi长度={len(src_roi)}")
            else:
                print(f"    [差异] {key}: 源库roi={len(src_roi)}项, 目标库roi={len(tgt_roi)}项")
                all_match = False

    # 对比 safetyScenarios
    print("\n  safetyScenarios 对比:")
    all_keys = set(source_ss_dict.keys()) | set(target_ss_dict.keys())
    all_match_ss = True
    for key in sorted(all_keys, key=str):
        src = source_ss_dict.get(key)
        tgt = target_ss_dict.get(key)
        if src is None:
            print(f"    [差异] 源库无，目标库有: {key}")
            all_match_ss = False
        elif tgt is None:
            print(f"    [差异] 源库有，目标库无: {key}")
            all_match_ss = False
        else:
            src_roi = normalize_data(src.get("roi"))
            tgt_roi = normalize_data(tgt.get("roi"))
            if src_roi == tgt_roi:
                print(f"    [一致] {key}: roi长度={len(src_roi)}")
            else:
                print(f"    [差异] {key}: 源库roi={len(src_roi)}项, 目标库roi={len(tgt_roi)}项")
                all_match_ss = False

    return all_match and all_match_ss


def main(camera_id: str = None, roi_type: str = None, area_title: str = None, aircraft_model: str = None):
    print("=" * 60)
    print("ROI + Grid 数据校验")
    print("=" * 60)
    print(f"camera_id:      {camera_id}")
    if roi_type:
        print(f"type:          {roi_type}")
    if area_title:
        print(f"area_title:    {area_title}")
    if aircraft_model:
        print(f"aircraft_model: {aircraft_model}")
    print("=" * 60)

    # 校验 grid
    verify_grid(camera_id)

    # 校验 roi
    verify_roi(camera_id, roi_type, area_title, aircraft_model)

    print("\n" + "=" * 60)
    print("校验完成")
    print("=" * 60)


if __name__ == "__main__":
    main(camera_id='55108135936', roi_type=None, area_title=None, aircraft_model=None)