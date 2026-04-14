import json

import requests
from collections import defaultdict

URL = "http://10.143.32.8:8000/infer/start"
MODEL = "sh0122"

CAMERA_LIST = [
    "HQ-0234A",
    "HQ-0234B",
    "HQ-0261A",
    "HQ-0261B",
    "HQ-0262A",
    "HQ-0262B",
    "HQ-0265A",
    "HQ-0265B",
    "HQ-0269A",
    "HQ-0269B",
    "HQ-0270A",
    "HQ-0270B",
    "HQ-0274A",
    "HQ-0274B",
    "HQ-0275A",
    "HQ-0275B",
    "HQ-0276A",
]


def start_infer(camera_name: str):
    payload = {
        "model": MODEL,
        "camera_name": camera_name
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        print(f"Sending request for camera: {camera_name}")

        resp = requests.post(
            URL,
            json=payload,
            headers=headers,
            timeout=30
        )

        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        print("-" * 60)

    except Exception as e:
        print(f"Request failed for {camera_name}: {e}")
        print("-" * 60)



def get_bridge_numbers():
    """获取所有桥的编号"""
    bridge_numbers = []

    # 从 camera_result.json 文件读取摄像头列表
    try:
        with open("/kafka_aeroplane/camera_result.json", "r", encoding="utf-8") as f:
            camera_data = json.load(f)
            bridge_numbers = [camera["name"] for camera in camera_data]
        print(f"已加载 {len(bridge_numbers)} 个摄像头")
    except Exception as e:
        print(f"读取摄像头列表失败：{e}")
    print(bridge_numbers)
    return bridge_numbers



def print_bridge_camera_ids():
    """打印 category: [cameraId 列表]"""

    # 从 camera_result.json 文件读取摄像头列表
    try:
        with open("/kafka_aeroplane/camera_result.json", "r", encoding="utf-8") as f:
            camera_data = json.load(f)
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return

    # 按 category 分组
    category_dict = defaultdict(list)
    for cam in camera_data:
        category = cam.get("category")
        camera_id = cam.get("cameraId")
        if category and camera_id:
            category_dict[category].append(camera_id)

        # 打印结果，列表用双引号
    for category, ids in category_dict.items():
        print(f"{category}: {json.dumps(ids, ensure_ascii=False)}")


def main():
    bridge_numbers = get_bridge_numbers()
    for camera in bridge_numbers:
        start_infer(camera)


if __name__ == "__main__":
    main()
    # print_bridge_camera_ids()
