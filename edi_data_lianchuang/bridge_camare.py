import requests
import json
import time

# 机位编号
NUMBERS = [
    213, 215, 216, 224, 225, 227, 228, 231, 232, 234,
    256, 261, 262, 263, 265, 269, 270, 272, 274, 275, 276
]

CATEGORY_URL = "http://10.143.36.10:31894/api/category/searchCategory"
CAMERA_URL = "http://10.143.36.10:31894/api/camera/foda/searchCamera"

HEADERS = {
    "Content-Type": "application/json"
}

def get_category_ids(number):
    """根据编号获取所有 category_id，返回列表"""
    payload = {
        "page": 1,
        "pageSize": 10,
        "name": str(number),
        "type": "BRIDGE"
    }
    try:
        resp = requests.post(CATEGORY_URL, headers=HEADERS, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("list")
        if not items or not isinstance(items, list):
            # 如果 list 是 None 或不是 list，直接返回空列表
            return []

        # 返回所有 id
        return [item.get("id") for item in items if item.get("id") is not None]

    except Exception as e:
        print(f"❌ category {number} error: {e}")
        return []

def get_cameras(category_id):
    """根据 category_id 获取摄像头信息"""
    payload = {
        "page": 1,
        "pageSize": 10,
        "filter": False,
        "category_id": category_id
    }
    try:
        resp = requests.post(CAMERA_URL, headers=HEADERS, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        cameras = []
        for item in data.get("list", []):
            cameras.append({
                "category": item.get("category"),
                "cameraId": item.get("cameraId"),
                "name": item.get("name"),
                "online": item.get("online")
            })
        return cameras
    except Exception as e:
        print(f"❌ camera category_id {category_id} error: {e}")
        return []

def main():
    final_list = []
    seen_camera_ids = set()  # 去重 cameraId

    for number in NUMBERS:
        print(f"🔹 Processing number: {number}")
        category_ids = get_category_ids(number)
        if not category_ids:
            print(f"❌ No category_id found for {number}")
            continue

        for category_id in category_ids:
            cameras = get_cameras(category_id)
            if cameras:
                for cam in cameras:
                    if cam["cameraId"] not in seen_camera_ids:
                        seen_camera_ids.add(cam["cameraId"])
                        final_list.append(cam)
                print(f"✔ Found {len(cameras)} cameras for category {number} id {category_id}")
            else:
                print(f"❌ No cameras found for category {number} id {category_id}")

        time.sleep(0.1)  # 防止接口压力过大

    # 输出结果
    print("\n=== RESULT ===")
    print(json.dumps(final_list, indent=2, ensure_ascii=False))

    # 保存文件
    with open("camera_result.json", "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    print("\n✔ 已保存到 camera_result.json")


if __name__ == "__main__":
    main()