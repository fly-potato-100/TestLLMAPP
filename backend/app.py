import logging # 新增
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import argparse # 新增

# 加载环境变量
load_dotenv()

# 配置日志记录 (移到 main 块中)
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s') # 修改

# 统一配置环境变量默认值
CONFIG = {
    "BAILIAN_API_KEY": os.getenv("BAILIAN_API_KEY", "YOUR_API_KEY"), # 只使用 BAILIAN_API_KEY
    "BAILIAN_APP_ID": os.getenv("BAILIAN_APP_ID", "YOUR_APP_ID"), # 新增 App ID 配置
    # 基础 API URL，需要拼接 app_id 和 /completion
    "BAILIAN_BASE_API_URL": os.getenv("BAILIAN_API_URL", "https://dashscope.aliyuncs.com/api/v1/apps")
}

# 检查必要的环境变量是否已设置
if CONFIG["BAILIAN_API_KEY"] == "YOUR_API_KEY" or CONFIG["BAILIAN_APP_ID"] == "YOUR_APP_ID":
    # 使用日志记录器打印警告
    logging.warning("请在 .env 文件中设置 BAILIAN_API_KEY 和 BAILIAN_APP_ID") # 修改

app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "http://localhost:3000"}})

@app.route('/chat', methods=['POST'])
def chat_proxy():
    logging.info("===========chat_proxy===========")
    try:
        # 获取前端消息
        data = request.get_json()
        user_message = data.get('message', '')
        # 从前端获取 session_id (如果存在)
        session_id = data.get('session_id', None)

        logging.info(f"接收到 /chat 请求: session_id='{session_id}'")
        logging.debug(f"user_message='{user_message}'") 

        if not user_message:
            logging.warning("请求缺少 'message' 字段") # 新增
            return jsonify({"error": "Message is required"}), 400

        # 构造百炼平台请求 URL
        api_url = f"{CONFIG['BAILIAN_BASE_API_URL']}/{CONFIG['BAILIAN_APP_ID']}/completion"
        logging.debug(f"构造百炼 API URL: {api_url}") # 新增

        # 构造请求头
        headers = {
            "Authorization": f"Bearer {CONFIG['BAILIAN_API_KEY']}",
            "Content-Type": "application/json"
        }
        # 注意：出于安全考虑，不在日志中记录完整的 headers (包含 API Key)

        # 构造请求体 (根据文档调整)
        payload = {
            "input": {
                "prompt": user_message,
            },
            "parameters": {},
            "debug": {}
        }

        # 如果前端传入了 session_id，则添加到 parameters 中
        if session_id:
            payload["input"]["session_id"] = session_id

        logging.debug(f"构造百炼请求体: {payload}") # 新增

        # 调用百炼平台API
        logging.info("开始调用百炼 API") # 新增
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            stream=False # 通常聊天接口不需要流式输出，除非明确需要
        )
        logging.debug(f"收到百炼 API 响应状态码: {response.status_code}") # 新增
        response.raise_for_status() # 如果请求失败 (非 2xx 状态码)，抛出异常

        response_data = response.json()
        # 可以考虑记录部分响应数据，但避免记录过多内容
        # logging.debug(f"收到百炼 API 响应内容: {response_data}")

        # 从响应中提取模型回复 (根据文档调整)
        ai_response = response_data.get("output", {}).get("text", "抱歉，未能获取到回复。")
        # 从响应中提取 session_id 用于下一轮对话
        next_session_id = response_data.get("output", {}).get("session_id")
        logging.info(f"提取到 AI 回复和 next_session_id: '{next_session_id}'")
        logging.debug(f"AI 回复: '{ai_response}'")

        # 返回AI回复和 session_id
        return jsonify({
            "response": ai_response,
            "session_id": next_session_id # 将 session_id 返回给前端
        })

    except requests.exceptions.RequestException as e:
        # 更具体的网络或 HTTP 错误处理
        error_message = f"API 请求失败: {e}"
        status_code = 500
        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_detail = e.response.json()
                error_message = f"API 请求失败 (状态码 {status_code}): {error_detail}"
            except ValueError: # 如果响应不是 JSON
                 error_message = f"API 请求失败 (状态码 {status_code}): {e.response.text}"

        logging.error(f"调用百炼 API 时发生请求错误: {error_message}") # 修改
        # print(f"错误: {error_message}") # 在后端打印详细错误 (logging 替代)
        return jsonify({"error": "调用 AI 服务时出错。"}), status_code # 返回给前端通用错误

    except Exception as e:
        logging.exception("处理 /chat 请求时发生未预料的错误") # 修改，使用 exception 记录堆栈信息
        # print(f"内部服务器错误: {e}") # 在后端打印详细错误 (logging 替代)
        return jsonify({"error": "服务器内部错误。"}), 500

if __name__ == '__main__':
    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description='启动 Flask 后端服务') # 新增
    parser.add_argument('-v', '--verbose', action='store_true', help='启用 DEBUG 级别的日志记录') # 新增
    args = parser.parse_args() # 新增

    # 根据参数配置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO # 新增
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s') # 新增

    # 建议从环境变量获取端口和调试模式
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    logging.info(f"启动 Flask 服务器，监听地址 0.0.0.0:{port}, Debug 模式: {debug_mode}") # 新增
    app.run(host='0.0.0.0', port=port, debug=debug_mode) # 监听所有接口，方便容器化部署