import threading
from multiprocessing import Process
from threading import Thread


def task(n):
    print(f"Process {n} running")


def run_processes():
    """
    概念
        •	多进程指在操作系统层面创建多个独立的进程，每个进程有自己的 内存空间、资源和全局变量。
        •	进程之间相互独立，不共享内存，通信需要 IPC（如管道 Pipe、队列 Queue、共享内存 SharedMemory 等）。

    特点
        •	独立性强：一个进程崩溃不影响其他进程。
        •	资源占用大：每个进程都要分配独立内存。
        •	Python 中可以绕过 GIL，适合 CPU 密集型任务。
    :return:
    """
    processes = [Process(target=task, args=(i,)) for i in range(3)]
    for p in processes:
        p.start()
    for p in processes:
        p.join()


def run_threading():
    """
      概念
        •	多线程是在同一个进程内创建多个线程，线程共享进程的内存空间。
        •	线程之间通信简单，因为共享内存，但也可能发生 数据竞争。

      特点
        •	轻量级：相比进程，线程创建和切换开销小。
        •	受 GIL 限制：Python 中的 CPU 密集型任务不能并行执行（GIL 是全局解释器锁）。
        •	适合 I/O 密集型任务：网络请求、文件读写、数据库操作。
    :return:
    """
    threads = [Thread(target=task, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


import asyncio


async def task(n):
    print(f"Task {n} start")
    await asyncio.sleep(1)
    print(f"Task {n} done")


async def run_asyncio():
    """
    概念
        •	协程是 用户态的轻量级线程，不依赖操作系统调度，由程序主动切换执行。
        •	Python 中通过 async/await 实现协程，通常配合事件循环（asyncio）使用。

    特点
        •	极轻量：同一线程中可以运行成千上万的协程。
        •	非抢占式：协程之间的切换由程序控制（通过 await）。
        •	适合高并发 I/O：网络请求、Web 服务、高并发爬虫。
    :return:
    """
    await asyncio.gather(*(task(i) for i in range(3)))


# asyncio.run(run_asyncio())


# 线程安全
counter = 0
lock = threading.Lock()
def add():
    global counter
    for _ in range(100000):
        with lock:  # 上锁
            counter += 1


def run_add_safe():
    """
    线程安全版本
    不安全：
    import threading

    counter = 0
    def add():
        global counter
        for _ in range(100000):
            counter += 1

    threads = [threading.Thread(target=add) for _ in range(2)]
    for t in threads: t.start()
    for t in threads: t.join()

    print(counter)  # 期望 200000，但实际可能小于 200000

    :return:
    """
    threads = [threading.Thread(target=add) for _ in range(2)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(counter)  # 200000，结果正确

