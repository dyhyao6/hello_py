#!/usr/bin/env python3
"""
Celery环境检查脚本
在启动服务前运行此脚本检查环境
"""

import sys
import subprocess
import os


def check_redis():
    """检查Redis"""
    print("1. 检查Redis服务...")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True, socket_connect_timeout=3)
        if r.ping():
            print("   ✅ Redis服务运行正常")
            return True
        else:
            print("   ❌ Redis服务无响应")
            return False
    except ImportError:
        print("   ❌ 未安装redis包")
        return False
    except Exception as e:
        print(f"   ❌ Redis连接失败: {e}")
        return False


def check_celery():
    """检查Celery"""
    print("2. 检查Celery...")
    try:
        import celery
        print(f"   ✅ Celery已安装: {celery.__version__}")
        return True
    except ImportError:
        print("   ❌ 未安装celery包")
        return False


def check_python_version():
    """检查Python版本"""
    print("3. 检查Python版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 7:
        print(f"   ✅ Python版本符合要求: {version.major}.{version.minor}")
        return True
    else:
        print(f"   ❌ Python版本过低: {version.major}.{version.minor}, 需要3.7+")
        return False


def check_project_structure():
    """检查项目结构"""
    print("4. 检查项目结构...")
    
    required_files = [
        'celery_app.py',
        'tasks.py',
        '__init__.py',
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if not missing_files:
        print("   ✅ 项目结构完整")
        return True
    else:
        print(f"   ❌ 缺少文件: {missing_files}")
        return False


def main():
    """主函数"""
    print("Celery环境检查")
    print("=" * 50)
    
    checks = [
        check_python_version,
        check_celery,
        check_redis,
        check_project_structure,
    ]
    
    passed = 0
    total = len(checks)
    
    for check in checks:
        if check():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"检查结果: {passed}/{total} 项通过")
    
    if passed == total:
        print("🎉 环境检查通过！可以启动Celery服务")
        print("\n启动步骤:")
        print("1. 启动Worker:")
        print("   celery -A celery_task worker --loglevel=info")
        print("2. 启动Beat (可选):")
        print("   celery -A celery_task beat --loglevel=info")
        return 0
    else:
        print("❌ 环境检查未通过，请修复问题后重试")
        return 1


if __name__ == "__main__":
    sys.exit(main())