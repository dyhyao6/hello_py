"""
Redis服务快速测试脚本
"""

import redis


def redis_connection(host='127.0.0.1', port=6379, db=0):
    """快速测试Redis连接"""
    try:
        # 创建Redis连接
        r = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3
        )

        # 测试连接
        if r.ping():
            print("✅ Redis连接成功!")

            # 测试基本操作
            test_key = "celery_test"
            test_value = "Hello Celery!"

            r.set(test_key, test_value, ex=10)  # 10秒过期
            result = r.get(test_key)

            if result == test_value:
                print("✅ 基本读写操作正常!")

                # 测试列表操作（Celery使用）
                r.lpush("celery_queue", "test_task")
                queue_length = r.llen("celery_queue")
                print(f"✅ 队列操作正常，队列长度: {queue_length}")

                # 清理
                r.delete(test_key, "celery_queue")
                print("✅ 测试完成!")
                return True
            else:
                print("❌ 读写操作失败!")
                return False
        else:
            print("❌ Redis连接失败!")
            return False

    except redis.ConnectionError:
        print("❌ Redis连接错误!")
        return False
    except redis.TimeoutError:
        print("❌ Redis连接超时!")
        return False
    except Exception as e:
        print(f"❌ Redis测试失败: {e}")
        return False


def main():
    """主函数"""
    print("开始Redis服务测试...")
    # print("-" * 40)

    # 测试默认配置
    success = redis_connection()

    # print("-" * 40)
    if success:
        print("🎉 Redis服务正常，可以使用Celery!")
        return 0
    else:
        print("⚠️ Redis服务有问题，请检查:")
        print("  1. Redis是否已启动?")
        print("  2. Redis配置是否正确?")
        print("  3. 网络连接是否正常?")
        return 1


if __name__ == "__main__":
    main()
