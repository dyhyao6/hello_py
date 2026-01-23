import requests
from fastapi import FastAPI, HTTPException

K8S_API = "https://localhost:6443"


# kubectl proxy
# http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/

# kubectl create sa api-reader
# kubectl create clusterrolebinding api-reader-admin --clusterrole=cluster-admin --serviceaccount=default:api-reader
# kubectl create token api-reader

TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IktwYUwwbGV3MU9jVnVwMXNaZzNkTFQ4bGpabXoycFdsRGRtbkc3enFjVEEifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiXSwiZXhwIjoxNzY4Mjg5MzgzLCJpYXQiOjE3NjgyODU3ODMsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiNGE0ZWQ3NzktNDRjNS00ZmUxLTljZjItMGQzMTdmODY3ZGQwIiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJkZWZhdWx0Iiwic2VydmljZWFjY291bnQiOnsibmFtZSI6ImFwaS1yZWFkZXIiLCJ1aWQiOiI0OTE2YjA2My02ZWU3LTQ1MzYtYjJlNi1hMThiYjNkMzdmMjkifX0sIm5iZiI6MTc2ODI4NTc4Mywic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6YXBpLXJlYWRlciJ9.2eUB1yWb6Ig0cyNg54eDn5t8mzrsN3QuuZYHwKm9VpOKOsDlJJ3LfPBArR2h2m-1GAzsOFODh2qh8_smpk7KEGYBPA8Pkoi1a9q1iKzZmVi85W-U7Aeb54qLOrMkuF2gVOo_xFWtPwyNo5ZpJbsu749C19MP-3kJmfBxIP1eeGHRENJgqywqwrjb2MZrnapOpNwvYBPlefBRHBNTo347HGbjWHYkpXm-yB9O42gru96bf4d_k-yxuPzomX2UnXK9zgdLsCd5AqdQ3SJ7iT_BnsRJEGE8tXamGfYz8WDHof8a-2CQnb4xlRotFot59RDppfRCwMJi3HbLDqoH1aTvlg"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}

app = FastAPI(title="K8s Cluster Resource API")


def k8s_get(path: str):
    url = f"{K8S_API}{path}"
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_cluster_resources():
    # 1️⃣ 节点信息（容量）
    nodes = k8s_get("/api/v1/nodes")

    # 2️⃣ 节点资源使用情况
    metrics = k8s_get("/apis/metrics.k8s.io/v1beta1/nodes")
    metrics_map = {
        item["metadata"]["name"]: item["usage"]
        for item in metrics.get("items", [])
    }
    result = {
        "node_count": len(nodes["items"]),
        "nodes": []
    }

    for node in nodes["items"]:
        print(node)
        name = node["metadata"]["name"]
        status = node["status"]

        capacity = status["capacity"]
        allocatable = status["allocatable"]
        usage = metrics_map.get(name, {})

        result["nodes"].append({
            "name": name,
            "cpu": {
                "capacity": capacity.get("cpu"),
                "allocatable": allocatable.get("cpu"),
                "usage": usage.get("cpu"),
            },
            "memory": {
                "capacity": capacity.get("memory"),
                "allocatable": allocatable.get("memory"),
                "usage": usage.get("memory"),
            }
        })

    return result


def get_node_by_name(node_name: str):
    """返回指定节点的详细信息"""
    try:
        node = k8s_get(f"/api/v1/nodes/{node_name}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Node {node_name} not found")
        else:
            raise
    print(node)


def get_stats_summary():
    """返回指定节点的详细信息"""
    try:
        node = k8s_get(f"/api/v1/nodes/docker-desktop/proxy/stats/summary")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Node not found")
        else:
            raise
    print(node)

if __name__ == "__main__":
    print(get_cluster_resources())
    # get_node_by_name('docker-desktop')
    # get_stats_summary()
