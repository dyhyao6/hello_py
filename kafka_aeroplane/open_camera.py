import requests


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


def main():
    for camera in CAMERA_LIST:
        start_infer(camera)


if __name__ == "__main__":
    main()