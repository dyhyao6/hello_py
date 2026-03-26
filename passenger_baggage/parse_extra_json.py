import json

# 读取完整的 event.json 文件
with open('event.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 提取 extra 字段
extra_str = data.get("_source", {}).get("extra", "")

print("=== Extra 字段解析结果 ===\n")

try:
    extra_data = json.loads(extra_str)
    print(json.dumps(extra_data, indent=2, ensure_ascii=False))
    
except json.JSONDecodeError as e:
    print(f"JSON 解析错误: {e}")
    print(f"错误位置: {e.pos}")
    print(f"\n原始 extra 字段内容（前2000字符）:")
    print(extra_str[:2000])