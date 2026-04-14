import json
import os
from datetime import datetime
import psycopg2

# 数据库配置
DB_CONFIG = {
    "host": "172.16.11.14",
    "port": 5432,
    "database": "edi_data_lianchuang",
    "user": "user_pCB6S3",
    "password": "password_haW2jY"
}

def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

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

def query_algorithm_param_grid(cursor, camera_id):
    """查询 algorithm_param_grid 表"""
    sql = """
        SELECT point, index, gis
        FROM algorithm_param_grid
        WHERE camera_id = %s
        LIMIT 1
    """
    cursor.execute(sql, (camera_id,))
    result = cursor.fetchone()
    if result:
        return {
            "point": parse_json_field(result[0]),
            "index": parse_json_field(result[1]),
            "gis": parse_json_field(result[2])
        }
    return {"point": [], "index": [], "gis": []}

def query_algorithm_param_post_safeguard(cursor, camera_id):
    """查询 algorithm_param_post_safeguard 表"""
    sql = """
        SELECT type, roi, roi_of_detection, aircraft_model, area_title, name
        FROM algorithm_param_post_safeguard
        WHERE camera_id = %s
    """
    cursor.execute(sql, (camera_id,))
    results = cursor.fetchall()
    post_safeguard_list = []
    for row in results:
        post_safeguard_list.append({
            "type": row[0] or "",
            "roi": parse_json_field(row[1]),
            "roi_of_detection": parse_json_field(row[2]),
            "aircraft_model": row[3] or "",
            "area_title": row[4] or "",
            "name": row[5] or ""
        })
    return post_safeguard_list

def query_algorithm_param_post_safety_scenarios(cursor, camera_id):
    """查询 algorithm_param_post_safety_scenarios 表"""
    sql = """
        SELECT type, roi, roi_of_detection, aircraft_model, area_title, name
        FROM algorithm_param_post_safety_scenarios
        WHERE camera_id = %s
    """
    cursor.execute(sql, (camera_id,))
    results = cursor.fetchall()
    safety_scenarios_list = []
    for row in results:
        safety_scenarios_list.append({
            "type": row[0] or "",
            "roi": parse_json_field(row[1]),
            "roi_of_detection": parse_json_field(row[2]),
            "aircraft_model": row[3] or "",
            "area_title": row[4] or "",
            "name": row[5] or ""
        })
    return safety_scenarios_list

def integrate_camera_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_dir, "camera_info.json")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== 开始数据整合 ==========")

    # 读取摄像头JSON文件
    with open(input_file, 'r', encoding='utf-8') as f:
        camera_list = json.load(f)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 读取摄像头文件成功，共 {len(camera_list)} 条记录")

    # 连接数据库
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    conn = get_db_connection()
    cursor = conn.cursor()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据库连接成功")

    integrated_list = []
    total = len(camera_list)

    for idx, camera in enumerate(camera_list, 1):
        camera_id = camera.get("cameraId", "")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{idx}/{total}] 处理摄像头: {camera_id} - {camera.get('name', '')}")

        # 查询数据库
        grid_data = query_algorithm_param_grid(cursor, camera_id)
        post_safeguard = query_algorithm_param_post_safeguard(cursor, camera_id)
        safety_scenarios = query_algorithm_param_post_safety_scenarios(cursor, camera_id)

        # 构建整合后的数据
        integrated_data = {
            "cameraID": camera_id,
            "name": camera.get("name", ""),
            "isActive": True,
            "areaCode": camera.get("category", ""),
            "point": grid_data["point"],
            "index": grid_data["index"],
            "geopoint": grid_data["gis"],
            "postSafeguard": post_safeguard,
            "safetyScenarios": safety_scenarios
        }
        integrated_list.append(integrated_data)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   -> point: {type(grid_data['point']).__name__}, postSafeguard: {len(post_safeguard)}条, safetyScenarios: {len(safety_scenarios)}条")

    # 关闭数据库连接
    cursor.close()
    conn.close()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据库连接已关闭")

    # 写入整合后的文件
    output_file = os.path.join(base_dir, "camera_data.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(integrated_list, f, ensure_ascii=False, indent=4)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ========== 数据整合完成 ==========")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 输出文件: {output_file}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 共处理 {len(integrated_list)} 条摄像头数据")

if __name__ == "__main__":
    integrate_camera_data()
