import requests
import json
import time


URL = "http://10.143.36.10:31894/api/camera/foda/searchCamera"

NUMBERS = [
    213, 215, 216, 224, 225, 227, 228, 231, 232, 234,
    256, 261, 262, 263, 265, 269, 270, 272, 274, 275, 276
]


def fetch_camera_data():
    headers = {
        "Content-Type": "application/json"
    }

    result = []
    seen = set()  # 去重 cameraId

    for num in NUMBERS:
        name = f"HQ-{num:04d}"

        payload = {
            "page": 1,
            "pageSize": 10,
            "filter": False,
            "name": name
        }

        try:
            resp = requests.post(URL, headers=headers, json=payload, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("list", []):
                camera_id = item.get("cameraId")

                if camera_id in seen:
                    continue

                seen.add(camera_id)

                result.append({
                    "category": item.get("category"),
                    "cameraId": camera_id,
                    "name": item.get("name"),
                    "online": item.get("online")
                })

            print(f"✔ processed {name}")

        except Exception as e:
            print(f"❌ error {name}: {e}")

        time.sleep(0.1)  # 防止接口压力过大

    return result


def main():
    data = fetch_camera_data()

    # 打印结果
    print("\n=== RESULT ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # 保存文件
    with open("摄像头-停机位.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("\n✔ 已保存到 camera_result.json")


if __name__ == "__main__":
    main()