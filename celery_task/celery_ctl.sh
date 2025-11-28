#!/bin/bash

# ============================
# Global Config
# ============================
HOME_DIR="/Users/duyonghui/pycharm_workpsace/hello_py"   # 项目根目录
APP="celery_task.celery_app"

APP_DIR="$HOME_DIR/celery_task"
LOG_DIR="$APP_DIR/logs"
PID_FILE="$APP_DIR/celery_worker.pid"

mkdir -p "$LOG_DIR"

# 设置 PYTHONPATH 为项目根目录
export PYTHONPATH="$HOME_DIR:$PYTHONPATH"

# ============================
# Utility: check if PID is running
# ============================
is_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# ============================
# Start worker
# ============================
start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if is_running "$PID"; then
            echo "⚠️ Celery worker already running (PID: $PID)"
            exit 0
        else
            echo "⚠️ Old PID file found but process not running. Cleaning..."
            rm -f "$PID_FILE"
        fi
    fi

    echo "🚀 Starting Celery worker..."
    cd "$HOME_DIR" || exit 1   # 必须在项目根目录

    nohup celery -A "$APP" worker --loglevel=info \
        >> "$LOG_DIR/celery_worker.log" 2>&1 &

    NEW_PID=$!
    echo $NEW_PID > "$PID_FILE"

    # 等待几秒确认是否启动成功
    sleep 3
    if is_running "$NEW_PID"; then
        echo "✅ Celery worker started (PID: $NEW_PID)"
    else
        echo "❌ Celery worker failed to start!"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# ============================
# Stop worker
# ============================
stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "⚠️ No PID file found — worker not running?"
        exit 1
    fi

    PID=$(cat "$PID_FILE")
    if ! is_running "$PID"; then
        echo "⚠️ PID file exists but process not running. Cleaning..."
        rm -f "$PID_FILE"
        exit 0
    fi

    echo "🛑 Stopping Celery worker (PID: $PID)..."
    kill "$PID" 2>/dev/null

    # 等待进程退出
    sleep 2
    if ! is_running "$PID"; then
        rm -f "$PID_FILE"
        echo "✅ Celery worker stopped."
    else
        echo "❌ Failed to stop Celery worker."
        exit 1
    fi
}

# ============================
# Restart worker
# ============================
restart() {
    echo "🔄 Restarting Celery worker..."
    stop
    sleep 1
    start
}

# ============================
# Status
# ============================
status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if is_running "$PID"; then
            echo "🟢 Celery worker running (PID: $PID)"
            exit 0
        else
            echo "⚠️ PID file exists but worker not running. Cleaning..."
            rm -f "$PID_FILE"
        fi
    fi
    echo "🔴 Celery worker is NOT running."
}

# ============================
# Main Entry
# ============================
case "$1" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
esac