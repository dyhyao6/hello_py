import asyncio

from fastapi import FastAPI, WebSocket, APIRouter
from fastapi.responses import HTMLResponse

app = FastAPI(title="WebSocket Demo")

router = APIRouter()

html = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Chat</title>
</head>
<body>
    <h1>WebSocket Chat</h1>
    <form onsubmit="sendMessage(event)">
        <input type="text" id="messageText" autocomplete="off"/>
        <button>Send</button>
    </form>
    <ul id="messages"></ul>

    <script>
        let ws;

        function connect() {
            ws = new WebSocket("ws://localhost:8888/ws");

            ws.onopen = () => console.log("WebSocket connected");

            ws.onmessage = (event) => {
                const messages = document.getElementById('messages');
                const message = document.createElement('li');
                message.textContent = event.data;
                messages.appendChild(message);
            };

            ws.onclose = () => {
                console.log("WebSocket closed. Reconnecting in 2s...");
                setTimeout(connect, 2000); // 自动重连
            };

            ws.onerror = (err) => {
                console.error("WebSocket error:", err);
                ws.close();
            };
        }

        function sendMessage(event) {
            event.preventDefault();
            const input = document.getElementById("messageText");
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(input.value);
            } else {
                console.warn("WebSocket not open. ReadyState:", ws.readyState);
                alert("WebSocket未连接，请稍等或刷新页面");
            }
            input.value = '';
        }

        // 页面加载后立即连接
        window.onload = connect;
    </script>
</body>
</html>
"""


stream_html = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Chat</title>
</head>
<body>
    <h1>WebSocket Chat</h1>
    <form onsubmit="sendMessage(event)">
        <input type="text" id="messageText" autocomplete="off"/>
        <button>Send</button>
    </form>
    <ul id="messages"></ul>

    <script>
        let ws;

        function connect() {
            ws = new WebSocket("ws://127.0.0.1:8888/ws-stream");
        
            ws.onopen = () => console.log("WebSocket connected");
        
            ws.onmessage = (event) => {
                const messages = document.getElementById('messages');
                let li = messages.lastElementChild;
                if (!li || li.className !== 'streaming') {
                    li = document.createElement('li');
                    li.className = 'streaming';
                    messages.appendChild(li);
                }
                li.textContent += event.data;
            };

        
            ws.onclose = () => {
                console.log("WebSocket closed. Reconnecting in 2s...");
                setTimeout(connect, 2000);
            };
        
            ws.onerror = (err) => {
                console.error("WebSocket error:", err);
                // 不要在这里立即 close，交给 onclose 处理重连
                // ws.close();
            };
        }
        
        function sendMessage(event) {
            event.preventDefault();
            const input = document.getElementById("messageText");
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(input.value);
            } else {
                console.warn("WebSocket not open. ReadyState:", ws ? ws.readyState : "undefined");
                alert("WebSocket未连接，请稍等或刷新页面");
            }
            input.value = '';
        }
        
        window.onload = () => {
            connect();
        };
    </script>
</body>
</html>
"""

@router.get("/html", response_class=HTMLResponse)
async def get():
    return html


@router.get("/html_stream", response_class=HTMLResponse)
async def get():
    return stream_html

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Server received: {data}")
    except Exception as e:
        print("WebSocket closed:", e)

@router.websocket("/ws-stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # 等待客户端发来一次完整的请求（例如要生成的文本）
            req_text = await websocket.receive_text()
            # 示例：把 req_text 逐字符发送回去（你也可以按 token 或按 chunk 发送）
            for ch in req_text:
                try:
                    await websocket.send_text(ch)
                except Exception:
                    # 客户端可能断开，直接退出循环
                    raise
                # 控制发送速率（可根据需要调整或去掉）
                await asyncio.sleep(0.12)
            # 发送结束标记（可选），前端收到后可做结束处理
            try:
                await websocket.send_text("[DONE]")
            except Exception:
                raise
    except Exception as e:
        print("WebSocket closed:", e)

app.include_router(router)