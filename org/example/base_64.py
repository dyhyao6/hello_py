import base64
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == '__main__':

    password = "bigdata@123"
    # 确保密钥长度达到 32 字节
    if len(password) < 32:
        # 用密码本身填充到 32 字节
        while len(password) < 32:
            password += password
        password = password[:32]
    print("生成的 Nacos 密钥（Base64 编码）:", password)
    # 对填充后的密码进行 Base64 编码
    encoded_key = base64.b64encode(password.encode('utf-8')).decode('utf-8')
    # 打印 Base64 编码后的密钥
    print("生成的 Nacos 密钥（Base64 编码）:", encoded_key)

