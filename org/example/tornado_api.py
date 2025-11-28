import os
import signal
import sys
import time
import tornado.ioloop
import tornado.web


# 定义一个简单的请求处理类
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, World!")


# 创建 Tornado 应用
def make_app():
    return tornado.web.Application([
        (r"/tornado", MainHandler),
    ])


# 启动服务
def start_server():
    pid_file = 'tornado.pid'
    if os.path.exists(pid_file):
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
            try:
                os.kill(int(pid), 0)
                print("服务正在运行中，不能重复启动。")
                return
            except (OSError, ValueError):
                pass
    app = make_app()
    app.listen(8888)
    pid = os.getpid()
    with open(pid_file, 'w') as f:
        f.write(str(pid))
    print("服务已启动，监听端口 8888。")
    tornado.ioloop.IOLoop.current().start()


# 停止服务
def stop_server():
    pid_file = 'tornado.pid'
    if os.path.exists(pid_file):
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
            try:
                os.kill(int(pid), signal.SIGTERM)
                time.sleep(1)
                try:
                    os.kill(int(pid), 0)
                    print("服务停止失败，请手动检查。")
                except (OSError, ValueError):
                    os.remove(pid_file)
                    print("服务已停止。")
            except (OSError, ValueError):
                os.remove(pid_file)
                print("服务未运行。")
    else:
        print("服务未运行。")


# 重启服务
def restart_server():
    stop_server()
    start_server()


# 策略接口
class CommandStrategy:
    def execute(self):
        pass


# 启动策略类
class StartCommandStrategy(CommandStrategy):
    def execute(self):
        start_server()


# 停止策略类
class StopCommandStrategy(CommandStrategy):
    def execute(self):
        stop_server()


# 重启策略类
class RestartCommandStrategy(CommandStrategy):
    def execute(self):
        restart_server()


# 策略上下文类
class CommandContext:
    def __init__(self, strategy):
        self.strategy = strategy

    def execute_command(self):
        self.strategy.execute()


if __name__ == "__main__":
    # python tornado_api.py stop > tornado_api.log 2>&1
    if len(sys.argv) != 2:
        print("用法: python tornado_api.py start | stop | restart")
        sys.exit(1)
    command = sys.argv[1]
    strategy_mapping = {
        'start': StartCommandStrategy(),
        'stop': StopCommandStrategy(),
        'restart': RestartCommandStrategy()
    }
    if command in strategy_mapping:
        context = CommandContext(strategy_mapping[command])
        context.execute_command()
    else:
        print("无效的命令，请使用 start、stop 或 restart。")
