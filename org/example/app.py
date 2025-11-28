from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "你好，我是首页"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888)
