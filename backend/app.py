from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 统一配置环境变量默认值
CONFIG = {
    "BAILIAN_API_KEY": os.getenv("BAILIAN_API_KEY", "test-api-key"),
    "BAILIAN_API_URL": os.getenv("BAILIAN_API_URL", "https://api.bailian.openai.example/v1/chat")
}

app = Flask(__name__)

@app.route('/chat', methods=['POST'])
def chat_proxy():
    try:
        # 获取前端消息
        data = request.get_json()
        user_message = data.get('message', '')
        
        # 构造百炼平台请求
        headers = {
            "Authorization": f"Bearer {CONFIG['BAILIAN_API_KEY']}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": user_message,
            "parameters": {
                "temperature": 0.7,
                "top_p": 0.9
            }
        }
        
        # 调用百炼平台API
        response = requests.post(
            CONFIG['BAILIAN_API_URL'],
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        
        # 返回AI回复
        return jsonify({
            "response": response.json().get("output", "未收到有效回复")
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)