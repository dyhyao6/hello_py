#!/usr/bin/env python3
"""
Redis服务测试脚本
用于测试Redis连接和基本功能
"""

import redis
import sys
import time
import json
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class RedisTester:
    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.redis_client = None
        
    def connect(self):
        """测试Redis连接"""
        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # 测试连接
            ping_result = self.redis_client.ping()
            if ping_result:
                logger.info(f"✅ Redis连接成功: {self.host}:{self.port}")
                return True
            else:
                logger.error("❌ Redis连接失败: PING命令无响应")
                return False
                
        except redis.ConnectionError as e:
            logger.error(f"❌ Redis连接错误: {e}")
            return False
        except redis.TimeoutError as e:
            logger.error(f"❌ Redis连接超时: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Redis连接异常: {e}")
            return False
    
    def test_basic_operations(self):
        """测试基本操作"""
        logger.info("开始测试Redis基本操作...")
        
        try:
            # 测试字符串操作
            test_key = "celery_test_key"
            test_value = "Hello Redis!"
            
            self.redis_client.set(test_key, test_value)
            retrieved_value = self.redis_client.get(test_key)
            
            if retrieved_value == test_value:
                logger.info(f"✅ 字符串操作正常: {test_key} = {test_value}")
            else:
                logger.error(f"❌ 字符串操作失败: 期望值 {test_value}, 实际值 {retrieved_value}")
                return False
            
            # 测试过期时间
            self.redis_client.expire(test_key, 10)
            ttl = self.redis_client.ttl(test_key)
            logger.info(f"✅ 过期时间设置正常: TTL = {ttl}秒")
            
            # 测试列表操作
            list_key = "celery_test_list"
            self.redis_client.lpush(list_key, "item1", "item2", "item3")
            list_length = self.redis_client.llen(list_key)
            list_items = self.redis_client.lrange(list_key, 0, -1)
            
            if list_length == 3 and len(list_items) == 3:
                logger.info(f"✅ 列表操作正常: 长度={list_length}, 内容={list_items}")
            else:
                logger.error(f"❌ 列表操作失败")
                return False
            
            # 测试哈希操作
            hash_key = "celery_test_hash"
            hash_data = {"name": "test", "value": "123", "timestamp": str(time.time())}
            self.redis_client.hset(hash_key, mapping=hash_data)
            retrieved_hash = self.redis_client.hgetall(hash_key)
            
            if retrieved_hash.get("name") == "test":
                logger.info(f"✅ 哈希操作正常: {retrieved_hash}")
            else:
                logger.error(f"❌ 哈希操作失败")
                return False
            
            # 清理测试数据
            self.redis_client.delete(test_key, list_key, hash_key)
            logger.info("✅ 测试数据清理完成")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 基本操作测试失败: {e}")
            return False
    
    def test_celery_compatibility(self):
        """测试Celery兼容性"""
        logger.info("开始测试Celery兼容性...")
        
        try:
            # 测试JSON序列化
            test_data = {
                "task_id": "test_task_123",
                "task_name": "celery_task.tasks.add",
                "args": [4, 6],
                "kwargs": {},
                "timestamp": datetime.now().isoformat()
            }
            
            json_key = "celery_task_test"
            json_value = json.dumps(test_data)
            
            self.redis_client.set(json_key, json_value)
            retrieved_json = self.redis_client.get(json_key)
            parsed_data = json.loads(retrieved_json)
            
            if parsed_data.get("task_id") == "test_task_123":
                logger.info("✅ JSON序列化兼容正常")
            else:
                logger.error("❌ JSON序列化兼容失败")
                return False
            
            # 测试发布/订阅（模拟Celery消息队列）
            pubsub = self.redis_client.pubsub()
            test_channel = "celery_test_channel"
            test_message = "Hello Celery!"
            
            pubsub.subscribe(test_channel)
            time.sleep(0.1)  # 等待订阅生效
            
            self.redis_client.publish(test_channel, test_message)
            
            # 接收消息
            message = pubsub.get_message(timeout=1)
            if message and message.get("data") == test_message:
                logger.info("✅ 发布/订阅功能正常")
            else:
                logger.warning("⚠️ 发布/订阅功能可能有问题")
            
            # 清理
            pubsub.unsubscribe(test_channel)
            self.redis_client.delete(json_key)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Celery兼容性测试失败: {e}")
            return False
    
    def test_performance(self):
        """测试性能"""
        logger.info("开始性能测试...")
        
        try:
            # 测试写入性能
            start_time = time.time()
            num_operations = 1000
            
            for i in range(num_operations):
                key = f"perf_test_key_{i}"
                value = f"perf_test_value_{i}"
                self.redis_client.set(key, value, ex=60)  # 60秒过期
            
            write_time = time.time() - start_time
            write_ops_per_sec = num_operations / write_time
            
            logger.info(f"✅ 写入性能: {write_ops_per_sec:.2f} 操作/秒")
            
            # 测试读取性能
            start_time = time.time()
            
            for i in range(num_operations):
                key = f"perf_test_key_{i}"
                self.redis_client.get(key)
            
            read_time = time.time() - start_time
            read_ops_per_sec = num_operations / read_time
            
            logger.info(f"✅ 读取性能: {read_ops_per_sec:.2f} 操作/秒")
            
            # 清理测试数据
            for i in range(num_operations):
                key = f"perf_test_key_{i}"
                self.redis_client.delete(key)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 性能测试失败: {e}")
            return False
    
    def test_memory_usage(self):
        """测试内存使用情况"""
        logger.info("开始内存使用测试...")
        
        try:
            info = self.redis_client.info()
            memory_used = info.get('used_memory_human', 'N/A')
            total_keys = info.get('db0', {}).get('keys', 0)
            
            logger.info(f"✅ 内存使用: {memory_used}")
            logger.info(f"✅ 数据库键数量: {total_keys}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 内存使用测试失败: {e}")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("开始Redis服务全面测试")
        logger.info("=" * 60)
        
        tests = [
            ("连接测试", self.connect),
            ("基本操作测试", self.test_basic_operations),
            ("Celery兼容性测试", self.test_celery_compatibility),
            ("性能测试", self.test_performance),
            ("内存使用测试", self.test_memory_usage),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n--- {test_name} ---")
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} 通过")
            else:
                logger.error(f"❌ {test_name} 失败")
        
        logger.info("\n" + "=" * 60)
        logger.info(f"测试结果: {passed}/{total} 项测试通过")
        
        if passed == total:
            logger.info("🎉 所有测试通过！Redis服务运行正常")
        else:
            logger.warning("⚠️ 部分测试失败，请检查Redis配置")
        
        return passed == total


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Redis服务测试工具')
    parser.add_argument('--host', default='localhost', help='Redis主机地址')
    parser.add_argument('--port', type=int, default=6379, help='Redis端口')
    parser.add_argument('--db', type=int, default=0, help='Redis数据库编号')
    parser.add_argument('--password', default=None, help='Redis密码')
    
    args = parser.parse_args()
    
    logger.info(f"Redis测试配置: {args.host}:{args.port}, DB: {args.db}")
    
    tester = RedisTester(
        host=args.host,
        port=args.port,
        db=args.db,
        password=args.password
    )
    
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()