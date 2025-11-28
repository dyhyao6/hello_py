#!/usr/bin/env python3
"""
Celery和Redis集成测试脚本
"""

import time
import sys

from celery.bin.control import inspect

from celery_task.celery_app import app
from celery_task.tasks import add, multiply
import redis


def test_celery_redis_integration():
    """测试Celery和Redis的集成"""
    print("开始Celery-Redis集成测试...")
    print("-" * 50)
    
    try:
        # 测试1: 检查Celery配置
        print("1. 检查Celery配置...")
        broker_url = app.conf.broker_url
        backend_url = app.conf.result_backend
        
        print(f"   Broker URL: {broker_url}")
        print(f"   Backend URL: {backend_url}")
        
        if 'redis' in broker_url and 'redis' in backend_url:
            print("   ✅ Celery已配置Redis")
        else:
            print("   ❌ Celery未正确配置Redis")
            return False
        
        # 测试2: 测试Redis连接
        print("\n2. 测试Redis连接...")
        
        # 解析Redis配置
        import re
        redis_pattern = r'redis://(?:(?P<password>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)/(?P<db>\d+)'
        
        broker_match = re.match(redis_pattern, broker_url)
        backend_match = re.match(redis_pattern, backend_url)
        
        if broker_match:
            redis_config = broker_match.groupdict()
            host = redis_config.get('host', 'localhost')
            port = int(redis_config.get('port', 6379))
            db = int(redis_config.get('db', 0))
            password = redis_config.get('password')
            
            # 测试Redis连接
            r = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5
            )
            
            if r.ping():
                print("   ✅ Redis连接正常")
            else:
                print("   ❌ Redis连接失败")
                return False
        else:
            print("   ❌ 无法解析Redis配置")
            return False
        
        # 测试3: 测试简单任务
        print("\n3. 测试简单任务...")
        
        # 异步执行任务
        task1 = add.delay(5, 3)
        task2 = multiply.delay(4, 7)
        
        print(f"   任务1 ID: {task1.id}")
        print(f"   任务2 ID: {task2.id}")
        
        # 等待任务完成
        print("   等待任务完成...")
        result1 = task1.get(timeout=10)
        result2 = task2.get(timeout=10)
        
        if result1 == 8 and result2 == 28:
            print(f"   ✅ 任务结果正确: add(5,3)={result1}, multiply(4,7)={result2}")
        else:
            print(f"   ❌ 任务结果错误: add(5,3)={result1}, multiply(4,7)={result2}")
            return False
        
        # 测试4: 检查任务状态
        print("\n4. 检查任务状态...")
        
        # 创建新任务
        task3 = add.delay(10, 20)
        
        # 检查不同状态
        print(f"   任务状态: {task3.status}")
        
        # 等待完成
        task3.get(timeout=10)
        print(f"   完成后状态: {task3.status}")
        
        if task3.status == 'SUCCESS':
            print("   ✅ 任务状态正常")
        else:
            print("   ❌ 任务状态异常")
            return False
        
        # 测试5: 测试任务队列
        print("\n5. 测试任务队列...")
        
        # 批量创建任务
        tasks = []
        for i in range(5):
            task = add.delay(i, i*2)
            tasks.append(task)
        
        print(f"   创建了 {len(tasks)} 个任务")
        
        # 等待所有任务完成
        results = []
        for task in tasks:
            result = task.get(timeout=15)
            results.append(result)
        
        expected_results = [i + i*2 for i in range(5)]
        if results == expected_results:
            print(f"   ✅ 批量任务结果正确: {results}")
        else:
            print(f"   ❌ 批量任务结果错误: {results}")
            return False
        
        print("\n" + "-" * 50)
        print("🎉 Celery-Redis集成测试全部通过!")
        return True
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        return False


def test_worker_status():
    """测试Worker状态"""
    print("\n6. 检查Worker状态...")
    
    try:
        # 使用Celery inspect检查worker

        i = inspect()
        
        # 检查活跃worker
        active_workers = i.active()
        if active_workers:
            print(f"   ✅ 发现活跃Worker: {len(active_workers)} 个")
            for worker_name, tasks in active_workers.items():
                print(f"      - {worker_name}: {len(tasks)} 个活跃任务")
        else:
            print("   ⚠️ 未发现活跃Worker")
            print("   提示: 请确保已启动Celery Worker:")
            print("   celery -A celery_task worker --loglevel=info")
        
        # 检查已注册任务
        registered_tasks = i.registered()
        if registered_tasks:
            print(f"   ✅ 已注册任务:")
            for worker_name, tasks in registered_tasks.items():
                print(f"      - {worker_name}:")
                for task in tasks:
                    print(f"        * {task}")
        
        return True
        
    except Exception as e:
        print(f"   ⚠️ 无法检查Worker状态: {e}")
        print("   提示: 请确保Worker已启动")
        return True  # 这不是致命错误


def main():
    """主函数"""
    print("Celery-Redis集成测试工具")
    print("=" * 60)
    
    # 运行集成测试
    success = test_celery_redis_integration()
    
    # 检查Worker状态
    test_worker_status()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 集成测试完成，系统运行正常!")
        print("\n下一步:")
        print("1. 启动Celery Worker:")
        print("   celery -A celery_task worker --loglevel=info")
        print("2. 启动Celery Beat (可选):")
        print("   celery -A celery_task beat --loglevel=info")
        print("3. 运行任务示例:")
        print("   python example_usage.py")
        return 0
    else:
        print("❌ 集成测试失败，请检查配置!")
        return 1


if __name__ == "__main__":
    main()