import json
from collections import defaultdict
from typing import Any

from kubernetes import client, config
from kubernetes.client import ApiException


def bytes_to_mb(b: int) -> float:
    return b / 1024 / 1024


def parse_cpu_nano(cpu_str: str) -> int:
    # e.g. "123456789n"
    return int(cpu_str.replace("n", ""))


def parse_mem_ki(mem_str: str) -> int:
    # e.g. "102400Ki"
    return int(mem_str.replace("Ki", ""))


def ki_to_mb(ki: int) -> float:
    return ki / 1024


def nano_cpu_to_mhz(nano: int) -> float:
    return nano / 1_000_000


def parse_quantity(value: str) -> float:
    """
    解析 k8s 资源单位，返回 Ki
    """
    if value.endswith("Ki"):
        return float(value[:-2])
    if value.endswith("Mi"):
        return float(value[:-2]) * 1024
    if value.endswith("Gi"):
        return float(value[:-2]) * 1024 * 1024
    if value.endswith("Ti"):
        return float(value[:-2]) * 1024 * 1024 * 1024

    # cpu 特殊情况：n / u / m
    if value.endswith("n"):
        return float(value[:-1]) / 1_000_000
    if value.endswith("u"):
        return float(value[:-1]) / 1_000
    if value.endswith("m"):
        return float(value[:-1])

    # 无单位（极少）
    return float(value)


def load_k8s_config(
        kubeconfig_path: str | None = None,
        request_timeout: float = 1.0
) -> client.ApiClient:
    """
    自动适配：
    - 集群内：ServiceAccount
    - 本地：kubeconfig
    同时统一设置 request_timeout
    """
    try:
        # 集群内
        config.load_incluster_config()
        print("Using in-cluster config")
    except config.ConfigException:
        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
            print(f"Using local kubeconfig: {kubeconfig_path}")
        else:
            config.load_kube_config()
            print("Using local kubeconfig: ~/.kube/config")

    # ⚠️ 关键：复制一份 Configuration，避免污染全局
    cfg = client.Configuration.get_default_copy()

    # === 性能关键参数 ===
    cfg.request_timeout = request_timeout  # 🔥 1 秒超时
    cfg.retries = 0  # 不自动重试
    cfg.client_side_validation = False  # 减少序列化开销

    return client.ApiClient(configuration=cfg)


class K8sClient:

    def __init__(self, kubeconfig_path: str | None = "./config"):
        api_client = load_k8s_config(
            kubeconfig_path=kubeconfig_path,
            request_timeout=1.0
        )

        # ⚠️ 重点：共用 api_client
        self.core_v1 = client.CoreV1Api(api_client)
        self.custom_api = client.CustomObjectsApi(api_client)
        self.batch_v1 = client.BatchV1Api(api_client)

    # ------------------------------------------------------------
    # 1️⃣ Node 基本信息
    # ------------------------------------------------------------
    def list_nodes(self):
        nodes = self.core_v1.list_node().items
        result = []

        for node in nodes:
            print(node)
            ready_condition = next(
                (c for c in node.status.conditions if c.type == "Ready"),
                None
            )

            node = {
                "uid": node.metadata.uid,
                "name": node.metadata.name,
                "ip": node.status.addresses[0].address,
                "Address": node.status.addresses[1].address,
                "ready": "ready" if ready_condition and ready_condition.status == "True" else "down",
                # "conditions": conditions,
                # "capacity": node.status.capacity,
                # "allocatable": node.status.allocatable,
                "Drain": True if node.spec.unschedulable else False,
                "SchedulingEligibility": "ineligible" if node.spec.unschedulable else "eligible",
            }
            # print(node)
            result.append(node)

        return result

    def metric_nodes(self):
        # ---------- 1. 节点 capacity ----------
        nodes = self.core_v1.list_node().items
        node_capacity = {}

        for node in nodes:
            name = node.metadata.name
            cap = node.status.capacity or {}

            cpu_core = int(cap.get("cpu", 0))
            mem_ki = int(cap.get("memory", "0Ki").replace("Ki", ""))
            disk_ki = int(cap.get("ephemeral-storage", "0Ki").replace("Ki", ""))

            gpu_cards = int(cap.get("nvidia.com/gpu", 0))

            node_capacity[name] = {
                "total_cpu_mhz": cpu_core * 1000,
                "total_memory_mb": ki_to_mb(mem_ki),
                "total_disk_mb": ki_to_mb(disk_ki),
                "total_gpu_card_count": gpu_cards,
            }

        # ---------- 2. metrics-server ----------
        metrics = self.custom_api.list_cluster_custom_object(
            group="batch.volcano.sh",
            version="v1beta1",
            plural="nodes"
        )

        node_res = []

        for item in metrics.get("items", []):
            meta = item.get("metadata", {})
            usage = item.get("usage", {})

            node_name = meta.get("name")
            cap = node_capacity.get(node_name, {})

            # CPU
            cpu_nano = int(usage.get("cpu", "0n").replace("n", ""))
            used_cpu_mhz = nano_cpu_to_mhz(cpu_nano)

            # Memory
            mem_ki = int(usage.get("memory", "0Ki").replace("Ki", ""))
            used_memory_mb = ki_to_mb(mem_ki)

            node_res.append({
                "id": node_name,
                "name": node_name,

                "total_cpu_mhz": cap.get("total_cpu_mhz", 0),
                "total_memory_mb": cap.get("total_memory_mb", 0),
                "total_disk_mb": cap.get("total_disk_mb", 0),

                "used_cpu_mhz": round(used_cpu_mhz, 2),
                "used_memory_mb": used_memory_mb,
                "used_disk_mb": 0,  # metrics-server 不支持

                "total_gpu_mb": 0,  # 需要 DCGM
                "used_gpu_mb": 0,  # 需要 DCGM
                "total_gpu_card_count": cap.get("total_gpu_card_count", 0),
                "used_gpu_card_count": 0,  # 需从 Pod request 或 DCGM
            })

    def metric_jobs(self):

        # ---------- 2. metrics-server ----------
        nodes = self.custom_api.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="nodes"
        )

        items = nodes.get("items", [])
        results = []
        for item in items:
            node_name = item["metadata"]["name"]

            # -------- CPU / Memory / Disk（stats/summary）--------
            try:
                raw = self.core_v1.connect_get_node_proxy_with_path(
                    name=node_name,
                    path="stats/summary"
                )

                # ⚠️ raw 是字符串，必须 json.loads
                stats = eval(raw)
                node_stats = stats.get("node", {})

                # ---------------- CPU ----------------
                cpu_stats = node_stats.get("cpu", {})

                # 使用量（nano cores → millicores）
                used_cpu_mhz = cpu_stats.get("usageNanoCores", 0) / 1_000_000

                # 总量（⚠️ stats/summary 不给，需要从 capacity）
                # 👉 你应该提前从 node.status.capacity 里拿

                # ---------------- Memory ----------------
                mem_stats = node_stats.get("memory", {})

                # 使用量（Bytes → MB）
                used_memory_mb = mem_stats.get("usageBytes", 0) / 1024 / 1024

                # 总量（Bytes → MB）
                total_memory_mb = mem_stats.get("availableBytes", 0) / 1024 / 1024 \
                                  + used_memory_mb

                # ---------------- Disk ----------------
                fs_stats = node_stats.get("fs", {})

                used_disk_mb = fs_stats.get("usedBytes", 0) / 1024 / 1024
                total_disk_mb = fs_stats.get("capacityBytes", 0) / 1024 / 1024

            except Exception as e:
                print(f"Error getting node stats [{node_name}]: {e}")
                used_cpu_mhz = 0
                used_memory_mb = 0
                total_memory_mb = 0
                used_disk_mb = 0
                total_disk_mb = 0

            results.append({
                "node": node_name,
                "used_cpu_mhz": used_cpu_mhz,
                "used_memory_mb": used_memory_mb,
                "used_disk_mb": used_disk_mb,
                "total_memory_mb": total_memory_mb,
                "total_cpu_mhz": 0,
                "total_disk_mb": total_disk_mb,
            })

        return results

    def get_all_allocations(self, payload: dict | None = None) -> list[dict[str, Any]]:
        # 获取所有命名空间的 Pod
        pods = self.core_v1.list_namespaced_pod(namespace='default').items
        # 遍历
        pods_alloc = []
        for pod in pods:
            # scheduler = pod.spec.scheduler_name
            # if scheduler != "volcano":
            #     continue
            status = pod.status.phase.lower()
            pods_alloc.append(status)
        return pods_alloc

    def cluster_gpu_summary(self):
        """
        统计 Kubernetes 集群 GPU 总数和已使用 GPU 数量（从 Pod requests 计算）
        """
        # ---------- 1. 节点总 GPU ----------
        pods = self.core_v1.list_pod_for_all_namespaces().items
        allocations = []

        for pod in pods:
            status = pod.status.phase.lower()

            alloc = {"ClientStatus": status, "AllocatedResources": {"Tasks": {}}}

            for container in pod.spec.containers:
                task_name = container.name
                devices = []

                if container.resources and container.resources.requests:
                    gpu_request = container.resources.requests.get("nvidia.com/gpu")
                    if gpu_request:
                        try:
                            gpu_count = int(gpu_request)
                            devices.append({
                                "Type": "gpu",
                                "DeviceIDs": list(range(gpu_count))  # 模拟 DeviceIDs
                            })
                        except ValueError:
                            pass

                alloc["AllocatedResources"]["Tasks"][task_name] = {"Devices": devices}

            allocations.append(alloc)

        print(len(allocations))
        return allocations

    def calc_used_gpu_by_pod_request(self) -> dict[str, int]:
        """
        返回:
        {
            node_name: used_gpu_card_count
        }
        """
        node_gpu_used = {}

        pods = self.core_v1.list_pod_for_all_namespaces(
            field_selector="status.phase=Running"
        ).items

        for pod in pods:
            print(pod)
            break
            node_name = pod.spec.node_name
            if not node_name:
                continue

            for container in pod.spec.containers:
                req = container.resources.requests or {}
                gpu = req.get("nvidia.com/gpu")

                if gpu:
                    node_gpu_used[node_name] += int(gpu)

        return node_gpu_used

    def cluster_summary(self):
        core_v1 = self.core_v1
        batch_v1 = client.BatchV1Api()

        nodes = core_v1.list_node().items

        node_count = len(nodes)
        active_node_count = 0
        inactive_node_count = 0
        maintenance_node_count = 0

        total_cpu_mhz = 0
        total_memory_mb = 0
        total_disk_mb = 0
        total_gpu_card_count = 0

        used_cpu_mhz = 0.0
        used_memory_mb = 0.0
        used_disk_mb = 0.0
        used_gpu_card_count = 0  # 近似：按 Pod GPU request 算

        # ---------- Node 维度 ----------
        for node in nodes:
            conditions = {c.type: c.status for c in node.status.conditions}
            ready = conditions.get("Ready") == "True"

            if ready:
                active_node_count += 1
            else:
                inactive_node_count += 1

            # CPU
            cpu_core = int(node.status.capacity.get("cpu", 0))
            total_cpu_mhz += cpu_core * 1000

            # Memory
            mem_ki = int(node.status.capacity.get("memory", "0Ki").replace("Ki", ""))
            total_memory_mb += ki_to_mb(mem_ki)

            # Disk (ephemeral-storage)
            disk_ki = int(
                node.status.capacity.get("ephemeral-storage", "0Ki")
                .replace("Ki", "")
            )
            total_disk_mb += ki_to_mb(disk_ki)

            # GPU
            gpu = node.status.capacity.get("nvidia.com/gpu")
            if gpu:
                total_gpu_card_count += int(gpu)

            # ---------- 使用量（stats/summary） ----------
            try:
                raw = core_v1.connect_get_node_proxy_with_path(
                    name=node.metadata.name,
                    path="stats/summary"
                )
                stats = eval(raw)

                node_stats = stats.get("node", {})

                used_cpu_mhz += nano_cpu_to_mhz(
                    node_stats.get("cpu", {}).get("usageNanoCores", 0)
                )
                used_memory_mb += bytes_to_mb(
                    node_stats.get("memory", {}).get("usageBytes", 0)
                )
                used_disk_mb += bytes_to_mb(
                    node_stats.get("fs", {}).get("usedBytes", 0)
                )

            except Exception:
                # 某些节点 metrics 不可达时忽略
                pass

        # ---------- Job 维度 ----------
        jobs = batch_v1.list_job_for_all_namespaces().items

        run_task_count = 0
        pending_task_count = 0
        complete_task_count = 0

        for job in jobs:
            status = job.status
            if status.active:
                run_task_count += status.active
            if status.succeeded:
                complete_task_count += status.succeeded
            if status.failed:
                pending_task_count += status.failed

        return {
            "node_count": node_count,
            "active_node_count": active_node_count,
            "inactive_node_count": inactive_node_count,
            "maintenance_node_count": maintenance_node_count,

            "run_task_count": run_task_count,
            "pending_task_count": pending_task_count,
            "complete_task_count": complete_task_count,

            "alloc_count": total_gpu_card_count,  # 你给的字段名
            "total_gpu_card_count": total_gpu_card_count,
            "used_gpu_card_count": used_gpu_card_count,  # 精确值需从 Pod request 算

            "total_cpu_mhz": total_cpu_mhz,
            "total_memory_mb": int(total_memory_mb),
            "total_disk_mb": int(total_disk_mb),

            "used_cpu_mhz": used_cpu_mhz,
            "used_memory_mb": int(used_memory_mb),
            "used_disk_mb": int(used_disk_mb),
        }

    # ------------------------------------------------------------
    # 2️⃣ CPU / 内存使用情况（metrics-server）
    # ------------------------------------------------------------
    def get_node_metrics(self):
        try:
            metrics = self.custom_api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes"
            )
        except ApiException as e:
            raise RuntimeError("metrics-server not available") from e

        result = {}
        for item in metrics["items"]:
            result[item["metadata"]["name"]] = {
                "cpu": item["usage"]["cpu"],
                "memory": item["usage"]["memory"],
                "timestamp": item["timestamp"]
            }

        return result

    # ------------------------------------------------------------
    # 3️⃣ 磁盘 / 详细资源（kubelet stats）
    # ------------------------------------------------------------
    def get_node_stats_summary(self, node_name: str):
        try:
            data = self.core_v1.connect_get_node_proxy_with_path(
                name=node_name,
                path="stats/summary"
            )
            data = eval(data) if data else {}
        except ApiException as e:
            raise RuntimeError(f"Failed to get stats for node {node_name}") from e
        node_fs = data.get("node", {}).get("fs", {})
        cpu = data.get("node", {}).get("cpu", {})
        memory = data.get("node", {}).get("memory", {})

        return {
            "cpu": {
                "usageNanoCores": cpu.get("usageNanoCores"),
                "usageCoreNanoSeconds": cpu.get("usageCoreNanoSeconds")
            },
            "memory": {
                "usageBytes": memory.get("usageBytes"),
                "availableBytes": memory.get("availableBytes")
            },
            "disk": {
                "capacityBytes": node_fs.get("capacityBytes"),
                "usedBytes": node_fs.get("usedBytes"),
                "availableBytes": node_fs.get("availableBytes")
            }
        }

    def get_node_detail(self, node_id: str = '5d0b058f-a343-4ca8-a612-c6e7e0ee1459') -> dict:
        """
        根据节点 ID 获取节点详情（K8s）

        :param node_id: 节点 metadata.name 或 UID
        :return: dict
        """
        # 获取所有节点
        nodes = self.core_v1.list_node().items

        for node in nodes:
            # 匹配节点 name 或 UID
            if node.metadata.name != node_id and node.metadata.uid != node_id:
                continue

            # Ready 状态
            ready_condition = next(
                (c for c in node.status.conditions if c.type == "Ready"),
                None
            )
            status = "ready" if ready_condition and ready_condition.status == "True" else "down"

            # IP 地址
            internal_ip = next(
                (a.address for a in node.status.addresses if a.type == "InternalIP"),
                ""
            )
            hostname = next(
                (a.address for a in node.status.addresses if a.type == "Hostname"),
                ""
            )
            # 资源总量
            capacity = node.status.capacity or {}
            allocatable = node.status.allocatable or {}

            # CPU
            total_cpu = int(capacity.get("cpu", 0))
            alloc_cpu = int(allocatable.get("cpu", 0))

            # 内存
            def parse_memory(mem_str: str) -> float:
                """解析 K8s 内存字符串，返回 MB"""
                if mem_str.endswith("Ki"):
                    return int(mem_str.replace("Ki", "")) / 1024
                elif mem_str.endswith("Mi"):
                    return int(mem_str.replace("Mi", ""))
                elif mem_str.endswith("Gi"):
                    return int(mem_str.replace("Gi", "")) * 1024
                else:
                    return int(mem_str) / 1024 / 1024

            total_memory = parse_memory(capacity.get("memory", "0Ki"))
            alloc_memory = parse_memory(allocatable.get("memory", "0Ki"))

            # GPU 卡
            total_gpu_cards = int(capacity.get("nvidia.com/gpu", 0))
            alloc_gpu_cards = int(allocatable.get("nvidia.com/gpu", 0))

            node_detail = {
                "id": node.metadata.uid,
                "name": node.metadata.name,
                "hostname": hostname,
                "ip_address": internal_ip,
                "status": status,
                "capacity": {
                    "cpu": total_cpu,
                    "memory_mb": total_memory,
                    "gpu_cards": total_gpu_cards
                },
                "allocatable": {
                    "cpu": alloc_cpu,
                    "memory_mb": alloc_memory,
                    "gpu_cards": alloc_gpu_cards
                },
                "data_center": "",
                "architecture": node.status.node_info.architecture,
                "os": node.status.node_info.operating_system,
                "kernel_version": node.status.node_info.kernel_version,
                "updated_at": node.metadata.creation_timestamp,
            }

            return node_detail

        # 没找到节点
        return {}

    # ------------------------------------------------------------
    # 4️⃣ GPU（只能拿 capacity / allocatable）
    # ------------------------------------------------------------
    def get_node_gpu_info(self):
        nodes = self.core_v1.list_node().items
        result = {}

        for node in nodes:
            print(node.__dict__)
            capacity = node.status.capacity.get("nvidia.com/gpu")
            if capacity:
                result[node.metadata.name] = {
                    "capacity": int(capacity),
                    "allocatable": int(
                        node.status.allocatable.get("nvidia.com/gpu", 0)
                    )
                }

        return result

    # ------------------------------------------------------------
    # 5️⃣ 集群总览（最常用）
    # ------------------------------------------------------------
    def get_cluster_overview(self):
        nodes = self.list_nodes()
        metrics = self.get_node_metrics()
        gpu_info = self.get_node_gpu_info()

        overview = []

        for node in nodes:
            name = node["name"]

            overview.append({
                "name": name,
                "ready": node["ready"],
                "ip": node["addresses"].get("InternalIP"),
                "nodeInfo": node["nodeInfo"],
                "capacity": node["capacity"],
                "allocatable": node["allocatable"],
                "usage": metrics.get(name),
                "gpu": gpu_info.get(name)
            })

        return overview

    def list_namespaces(self):
        namespaces = self.core_v1.list_namespace().items
        result = []
        for ns in namespaces:
            print(ns)
            result.append({
                "name": ns.metadata.name,
                "status": ns.status.phase,
                "creationTimestamp": ns.metadata.creation_timestamp,
                "labels": ns.metadata.labels,
                "annotations": ns.metadata.annotations
            })
        return result

    def get_namespace_details(self, namespace_name: str):
        try:
            namespace = self.core_v1.read_namespace(namespace_name)
        except ApiException as e:
            raise RuntimeError(f"Failed to get details for namespace {namespace_name}") from e

        return {
            "name": namespace,
        }

    def create_job_in_default_namespace(self,
                                        job_name: str,
                                        image: str = "busybox",
                                        command: list[str] | None = None
                                        ):
        """
        在 default 命名空间创建一个 Job
        """

        batch_v1 = client.BatchV1Api()

        if command is None:
            command = ["sh", "-c", "echo Hello Kubernetes && sleep 5"]

        # 1️⃣ 容器
        container = client.V1Container(
            name="job-container",
            image=image,
            command=command
        )

        # 2️⃣ Pod 模板
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"job-name": job_name}),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container]
            )
        )

        # 3️⃣ Job Spec
        job_spec = client.V1JobSpec(
            template=template,
            backoff_limit=3
        )

        # 4️⃣ Job 对象
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace="default"
            ),
            spec=job_spec
        )

        # 5️⃣ 调用 API 创建
        try:
            resp = batch_v1.create_namespaced_job(
                namespace="default",
                body=job
            )
            print(f"✅ Job created: {resp.metadata.name}")
            return resp
        except ApiException as e:
            print(f"❌ Failed to create job: {e.reason}")
            raise

    def create_long_running_job(self, job_name: str,
                                image: str = "busybox",
                                run_time_seconds: int = 7200,  # 默认两小时
                                command: list[str] | None = None):
        """
        在 default 命名空间创建一个长时间运行的 Job（默认 2 小时）
        """

        batch_v1 = client.BatchV1Api()

        if command is None:
            # sleep 指令让 Pod 持续运行指定时间
            command = ["sh", "-c", f"echo Job started && sleep {run_time_seconds}"]

        # 1️⃣ 容器
        container = client.V1Container(
            name="job-container",
            image=image,
            command=command
        )

        # 2️⃣ Pod 模板
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"job-name": job_name}),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container]
            )
        )

        # 3️⃣ Job Spec
        job_spec = client.V1JobSpec(
            template=template,
            backoff_limit=3,  # 出错最多重试3次
            active_deadline_seconds=run_time_seconds  # Job 最大持续时间
        )

        # 4️⃣ Job 对象
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace="default"
            ),
            spec=job_spec
        )

        # 5️⃣ 创建 Job
        try:
            resp = batch_v1.create_namespaced_job(
                namespace="default",
                body=job
            )
            print(f"✅ Long-running Job created: {resp.metadata.name}")
            return resp
        except ApiException as e:
            print(f"❌ Failed to create job: {e.reason}")
            raise

    def create_failing_job(self, job_name: str, namespace: str = "default", image: str = "busybox"):
        """
        在指定命名空间创建一个必定失败的 Job
        """
        # 加载 Kubernetes 配置
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        batch_v1 = client.BatchV1Api()

        # 容器，执行一个必定失败的命令
        container = client.V1Container(
            name="failing-job-container",
            image=image,
            command=["sh", "-c", "exit 1"]  # 直接失败
        )

        # Pod 模板
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"job-name": job_name}),
            spec=client.V1PodSpec(
                restart_policy="Never",  # 不重启失败的容器
                containers=[container]
            )
        )

        # Job Spec
        job_spec = client.V1JobSpec(
            template=template,
            backoff_limit=0  # 失败不重试
        )

        # Job 对象
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=namespace
            ),
            spec=job_spec
        )

        # 创建 Job
        try:
            resp = batch_v1.create_namespaced_job(
                namespace=namespace,
                body=job
            )
            print(f"✅ Failing Job created: {resp.metadata.name}")
            return resp
        except ApiException as e:
            print(f"❌ Failed to create job: {e.reason}")
            raise

    def list_jobs(self, namespace="default"):

        jobs = self.custom_api.list_namespaced_custom_object(
            group="batch.volcano.sh",
            version="v1alpha1",
            namespace=namespace,
            plural="jobs"
        )
        for job in jobs.get("items", []):
            print(job)
            return

    def list_jobs_by_node(self, node_name: str, namespace: str = "default") -> list[dict]:
        """
        将 K8s Pod + Volcano Job 伪装成 Nomad allocation 结构
        """
        pods = self.core_v1.list_namespaced_pod(
            namespace=namespace,
            field_selector=f"spec.nodeName={node_name}"
        ).items

        allocs = []

        for pod in pods:
            labels = pod.metadata.labels or {}

            job_name = labels.get("volcano.sh/job-name")
            if not job_name:
                continue

            # ---------- 状态映射（Pod -> Nomad ClientStatus）----------
            phase = pod.status.phase
            if phase in {'Completing', 'Pending', 'Unknown'}:
                client_status = "Running"
            elif phase == "Succeeded":
                client_status = "Healthy"
            else:
                client_status = "Unknown"
            # ---------- 资源（requests，贴近 Nomad allocation）----------
            cpu_mhz = 0
            mem_mb = 0

            for c in pod.spec.containers:
                req = c.resources.requests or {}

                cpu = req.get("cpu")
                mem = req.get("memory")

                # cpu: "500m" / "1"
                if cpu:
                    if isinstance(cpu, str) and cpu.endswith("m"):
                        cpu_mhz += int(cpu[:-1])
                    else:
                        cpu_mhz += int(float(cpu) * 1000)

                # memory: "1Gi" / "512Mi"
                if mem:
                    if mem.endswith("Gi"):
                        mem_mb += int(float(mem[:-2]) * 1024)
                    elif mem.endswith("Mi"):
                        mem_mb += int(float(mem[:-2]))

            # ---------- CreateTime（ns，对齐 Nomad）----------
            create_time = pod.metadata.creation_timestamp
            if create_time:
                create_ts_ns = int(create_time.timestamp() * 1e9)
            else:
                create_ts_ns = 0

            allocs.append({
                "ID": pod.metadata.uid,
                "Name": pod.metadata.name,
                "JobID": job_name,
                "ClientStatus": client_status,
                "CreateTime": create_ts_ns,
                "Resources": {
                    "CPU": cpu_mhz,
                    "MemoryMB": mem_mb,
                }
            })

        return allocs

    def get_job(self):
        # 1️⃣ 找 Job 对应的 Pod
        # 初始化 API
        namespace = "default"
        job_name = "jvub0790pb0x"
        core_api = client.CoreV1Api()
        metrics_api = client.CustomObjectsApi()

        # 1️⃣ 找 Job 对应的 Pod
        pods = core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"job-name={job_name}"
        ).items

        # 2️⃣ 获取 namespace 下所有 Pod metrics
        metrics_list = metrics_api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods"
        )

        # 将 metrics 按 pod 名索引
        metrics_dict = {m["metadata"]["name"]: m for m in metrics_list["items"]}

        total_cpu_m = 0
        total_mem_mi = 0

        for pod in pods:
            pod_name = pod.metadata.name
            if pod_name not in metrics_dict:
                print(f"Pod {pod_name} metrics 未找到，可能 metrics-server 未安装或 Pod 已完成")
                continue
            metrics = metrics_dict[pod_name]
            for container in metrics["containers"]:
                cpu = container["usage"]["cpu"]
                mem = container["usage"]["memory"]

                # CPU
                if cpu.endswith("n"):
                    cpu_m = int(cpu[:-1]) / 1_000_000
                elif cpu.endswith("m"):
                    cpu_m = int(cpu[:-1])
                else:
                    cpu_m = int(cpu) * 1000

                # 内存
                if mem.endswith("Ki"):
                    mem_mi = int(mem[:-2]) / 1024
                elif mem.endswith("Mi"):
                    mem_mi = int(mem[:-2])
                elif mem.endswith("Gi"):
                    mem_mi = int(mem[:-2]) * 1024
                else:
                    mem_mi = int(mem) / (1024 * 1024)

                total_cpu_m += cpu_m
                total_mem_mi += mem_mi

        print(f"Job {job_name} 实际使用资源：")
        print(f"CPU: {total_cpu_m / 1000:.2f} 核")
        print(f"内存: {total_mem_mi:.2f} MiB")

    def read_job_status(self, namespace: str, job_name: str):
        batch_v1 = client.BatchV1Api()
        return batch_v1.read_namespaced_job_status(
            name=job_name,
            namespace=namespace
        )


k8s_client = K8sClient()

if __name__ == "__main__":
    # nodes = k8s_client.get_node_stats_summary("docker-desktop")
    # print(nodes)
    # print(k8s_client.list_nodes())
    # print(k8s_client.list_namespaces())
    # print(k8s_client.get_namespace_details("default"))

    # 创建任务
    # k8s_client.create_job_in_default_namespace(
    #     job_name="demo-job",
    #     image="busybox",
    #     command=["sh", "-c", "date && echo job done"]
    # )

    # k8s_client.create_long_running_job("my-long-job")

    #  创建一定失败的任务
    # k8s_client.create_failing_job("must-failing-job")
    # print(k8s_client.list_jobs())
    # print(k8s_client.get_job("default", "must-failing-job"))
    # print(k8s_client.get_job_logs("my-long-job", "default"))
    # print(k8s_client.read_job_status(namespace='default', job_name='demo-job'))

    # 计算 cluster_summary 花了多少时间

    # print(k8s_client.cluster_summary_fast())
    # print(k8s_client.calc_used_gpu_by_pod_request())
    # print(k8s_client.cluster_summary())

    print(k8s_client.list_nodes())
    # print(k8s_client.get_node_detail())
    # print(k8s_client.get_all_allocations())
    # print(k8s_client.list_jobs_by_node(node_name='lianchuang-worker1'))
