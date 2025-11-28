# Celery任务示例

这是一个Celery分布式任务队列的完整示例。

## 功能特性

- 基本任务定义和执行
- 异步任务处理
- 任务链和任务组
- 定时任务配置
- 错误处理
- 监控工具集成
- Redis连接测试
- Celery-Redis集成测试

## 安装依赖

```bash
pip install -r requirements.txt
```

## Redis测试

在使用Celery之前，建议先测试Redis服务是否正常：

### 快速测试
```bash
python test_redis_simple.py
```

### 完整测试
```bash
python test_redis.py
```

### Celery-Redis集成测试
```bash
python test_integration.py
```

## 启动服务

### 1. 启动Redis
确保Redis服务已启动：
```bash
redis-server
```

### 2. 测试Redis连接
```bash
# 快速测试
python test_redis_simple.py

# 完整测试
python test_redis.py

# 集成测试
python test_integration.py
```

### 3. 启动Celery Worker
```bash
python run_worker.py worker
```

### 4. 启动Celery Beat（可选，用于定时任务）
```bash
python run_worker.py beat
```

### 5. 启动Flower监控（可选）
```bash
python run_worker.py flower
```
然后访问 http://localhost:5555 查看任务状态

## 使用示例

### 基本使用
```python
from celery_task.tasks import add, multiply

# 同步执行
result = add(4, 6)

# 异步执行
task = add.delay(10, 20)
result = task.get(timeout=10)
```

### 运行示例
```bash
python example_usage.py
```

## 测试脚本说明

### test_redis_simple.py
- 快速测试Redis连接
- 测试基本读写操作
- 测试队列操作
- 适合快速验证Redis状态

### test_redis.py
- 全面的Redis功能测试
- 连接测试
- 基本操作测试（字符串、列表、哈希）
- Celery兼容性测试
- 性能测试
- 内存使用测试
- 支持命令行参数配置

### test_integration.py
- Celery和Redis集成测试
- 配置验证
- 任务执行测试
- Worker状态检查
- 批量任务测试

## 故障排除

### Redis连接失败
1. 检查Redis是否启动：`redis-cli ping`
2. 检查Redis配置是否正确
3. 检查网络连接
4. 使用测试脚本诊断：`python test_redis_simple.py`

### Celery任务无法执行
1. 运行集成测试：`python test_integration.py`
2. 检查Worker是否启动
3. 检查Redis连接
4. 查看Worker日志

### 性能问题
1. 运行性能测试：`python test_redis.py`
2. 检查Redis内存使用
3. 优化任务设计

## 任务类型

1. **add**: 加法任务
2. **multiply**: 乘法任务
3. **process_data**: 数据处理任务
4. **periodic_task**: 定时任务
5. **error_task**: 错误演示任务

## 配置说明

- 使用Redis作为消息代理和结果存储
- 支持JSON序列化
- 配置了默认队列
- 包含定时任务调度
- 支持环境变量配置

## 监控和管理

- 使用Flower进行任务监控
- 支持任务状态查看
- 支持Worker管理
- 内置测试工具