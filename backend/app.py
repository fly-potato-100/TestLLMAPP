import logging
import os
import argparse
import requests
import json
from fastapi import FastAPI, HTTPException  # 修改: 引入 FastAPI 和 HTTPException
from fastapi.middleware.cors import CORSMiddleware # 新增: 引入 CORSMiddleware
from pydantic import BaseModel             # 新增: 引入 Pydantic 用于数据验证
from dotenv import load_dotenv
from typing import Optional, Dict, List     # 新增: 引入 List

# 加载环境变量
load_dotenv()

# --- Pydantic 模型定义 ---
# 新增: 单个消息模型
class BailianPayloadInputMessage(BaseModel):
    role: str
    content: str

# 修改: Bailian API 请求体中的 input 结构
class BailianPayloadInput(BaseModel):
    messages: Optional[List[BailianPayloadInputMessage]] = None
    prompt: Optional[str] = None
    session_id: Optional[str] = None
    biz_params: Dict = {}

class BailianPayload(BaseModel):
    input: BailianPayloadInput
    parameters: Dict = {}
    debug: Dict = {}

# 修改: 前端请求体结构
class ChatInputData(BaseModel):
    conversation: List[BailianPayloadInputMessage]
    session_id: Optional[str] = None
    biz_params: Optional[Dict] = None
class ChatRequest(BaseModel):
    input: ChatInputData 
class ChatOutput(BaseModel):
    text: str
    session_id: Optional[str] = None

# 新增: 符合百炼 API 文档的单个模型使用情况
class BailianModelUsage(BaseModel):
    model_id: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

# 修改: BailianUsage 模型结构以符合文档
class BailianUsage(BaseModel):
    models: Optional[List[BailianModelUsage]] = None

class BailianResponse(BaseModel):
    output: ChatOutput
    usage: Optional[BailianUsage] = None
    request_id: Optional[str] = None # 假设 API 可能返回 request_id

class ChatResponse(BaseModel):
    response_text: str
    session_id: Optional[str] = None
    usage: Optional[BailianUsage] = None

# --- 新增: Hello 端点 ---
class HelloResponse(BaseModel):
    message: str

# --- 配置 ---
# 配置日志记录 (稍后在 main 中根据参数设置级别)

# 统一配置环境变量默认值
CONFIG = {
    "BAILIAN_API_KEY": os.getenv("BAILIAN_API_KEY", "YOUR_API_KEY"),
    "BAILIAN_APP_ID": os.getenv("BAILIAN_APP_ID", "YOUR_APP_ID"),
    "BAILIAN_BASE_API_URL": os.getenv("BAILIAN_API_URL", "https://dashscope.aliyuncs.com/api/v1/apps")
}

# 检查必要的环境变量是否已设置
if CONFIG["BAILIAN_API_KEY"] == "YOUR_API_KEY" or CONFIG["BAILIAN_APP_ID"] == "YOUR_APP_ID":
    logging.warning("请在 .env 文件中设置 BAILIAN_API_KEY 和 BAILIAN_APP_ID")

# --- FastAPI 应用实例 ---
app = FastAPI()

# 配置 CORS
# 允许所有来源，所有方法，所有头，可以根据需要调整
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境中应指定允许的源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 新增: Hello 端点 ---
@app.get("/hello/{name}", response_model=HelloResponse)
async def say_hello(name: str):
    """接收路径参数 name 并返回问候消息。"""
    logging.info(f"接收到 /hello/{name} 请求")
    return {"message": f"Hello, {name}"}

# --- API 端点 ---
@app.post("/chat", response_model=ChatResponse) # 修改: 使用 FastAPI 装饰器和响应模型
async def chat_proxy(chat_request: ChatRequest): # 修改: 使用 Pydantic 模型接收请求体，改为 async
    logging.info("===========chat_proxy===========")
    try:
        # 修改: 从 chat_request.input 中提取数据
        messages_history = chat_request.input.conversation
        session_id = chat_request.input.session_id
        biz_params_from_request = chat_request.input.biz_params # 新增: 提取 biz_params

        logging.info(f"接收到 /chat 请求: session_id='{session_id}', messages_count={len(messages_history)}, biz_params={biz_params_from_request}") # 修改: 添加 biz_params 日志
        logging.debug(f"Messages history: {messages_history}")

        if not messages_history:
            logging.warning("请求 input 中缺少 'messages' 字段或为空")
            raise HTTPException(status_code=400, detail="Messages are required in input")

        # 构造百炼平台请求 URL
        api_url = f"{CONFIG['BAILIAN_BASE_API_URL']}/{CONFIG['BAILIAN_APP_ID']}/completion"
        logging.debug(f"构造百炼 API URL: {api_url}")

        # 构造请求头
        headers = {
            "Authorization": f"Bearer {CONFIG['BAILIAN_API_KEY']}",
            "Content-Type": "application/json"
        }

        # 构造请求体 (使用 Pydantic 模型)
        payload_input = BailianPayloadInput()
        if True:
            payload_input.prompt = json.dumps([msg.model_dump() for msg in messages_history], ensure_ascii=False) # 添加 ensure_ascii=False 以正确处理中文
        else:
            payload_input.messages = messages_history
        if session_id and False:
            payload_input.session_id = session_id
        if biz_params_from_request:
            payload_input.biz_params = biz_params_from_request
        else:
            raise HTTPException(status_code=400, detail="biz_params is required")
        payload = BailianPayload(input=payload_input)

        # 将 Pydantic 模型转为字典用于 requests
        payload_dict = payload.model_dump(exclude_none=True) # exclude_none 确保可选字段不传 null

        logging.debug(f"构造百炼请求体: {json.dumps(payload_dict, indent=2, ensure_ascii=False)}")

        # 调用百炼平台API (仍然使用同步 requests，未来可换成 httpx)
        logging.info("开始调用百炼 API")
        # 在异步函数中调用同步代码需要注意，对于 requests 这种 IO 密集操作通常还好
        # 但更优的方式是使用异步 http 客户端如 httpx
        response = requests.post(
            api_url,
            json=payload_dict, # 发送字典
            headers=headers,
            stream=False
        )
        logging.debug(f"收到百炼 API 响应状态码: {response.status_code}")
        response.raise_for_status() # 如果请求失败 (非 2xx 状态码)，requests 会抛出 HTTPError

        response_data = response.json()
        logging.debug(
            "收到百炼 API 响应内容: %s\n", 
            json.dumps(response_data, indent=2, ensure_ascii=False)
        )

        # 使用 Pydantic 解析和验证响应
        try:
            bailian_response = BailianResponse.model_validate(response_data)
        except Exception as pydantic_error: # 更具体的 Pydantic ValidationError
            logging.error(f"解析百炼 API 响应失败: {pydantic_error}, 原始数据: {response_data}")
            raise HTTPException(status_code=500, detail="解析 AI 服务响应时出错。")

        # 从验证后的模型中提取数据
        ai_response_text = bailian_response.output.text if bailian_response.output else "抱歉，未能获取到回复。"
        next_session_id = bailian_response.output.session_id if bailian_response.output else None
        usage_details = bailian_response.usage

        logging.info(f"提取到 AI 回复和 next_session_id: '{next_session_id}'")

        # 返回验证后的数据模型，FastAPI 自动序列化为 JSON
        return ChatResponse(
            response_text=ai_response_text,
            session_id=next_session_id,
            usage=usage_details
        )

    except requests.exceptions.HTTPError as http_err:
        # 处理 HTTP 错误 (由 raise_for_status 抛出)
        status_code = http_err.response.status_code
        error_detail = "未知 API 错误"
        try:
            error_detail = http_err.response.json() # 尝试获取 JSON 错误详情
        except ValueError:
            error_detail = http_err.response.text # 否则获取文本内容
        error_message = f"API 请求失败 (状态码 {status_code}): {error_detail}"
        logging.error(f"调用百炼 API 时发生 HTTP 错误: {error_message}")
        raise HTTPException(status_code=status_code, detail="调用 AI 服务时出错。") # 转发错误

    except requests.exceptions.RequestException as req_err:
        # 处理其他请求相关的错误 (如网络问题)
        error_message = f"API 请求连接失败: {req_err}"
        logging.error(error_message)
        raise HTTPException(status_code=503, detail="无法连接到 AI 服务。") # Service Unavailable

    except HTTPException as e:
        # 重新抛出已知的 HTTPException
        raise e
    except Exception as e:
        logging.exception("处理 /chat 请求时发生未预料的错误")
        raise HTTPException(status_code=500, detail="服务器内部错误。") # Internal Server Error

# --- 主程序入口 ---
if __name__ == '__main__':
    import uvicorn # 修改: 引入 uvicorn

    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description='启动 FastAPI 后端服务') # 修改描述
    parser.add_argument('-v', '--verbose', action='store_true', help='启用 DEBUG 级别的日志记录')
    parser.add_argument('--host', type=str, default=os.getenv("FASTAPI_HOST", "0.0.0.0"), help='服务监听的主机地址') # 新增 host 参数
    parser.add_argument('--port', type=int, default=int(os.getenv("FASTAPI_PORT", 8000)), help='服务监听的端口') # 修改默认端口为 8000
    parser.add_argument('--reload', action='store_true', help='启用热重载模式 (用于开发)') # 新增 reload 参数
    args = parser.parse_args()

    # 根据参数配置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO

    # 手动配置根日志记录器以捕获我们自己的日志
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info(f"启动 FastAPI 服务器，监听地址 {args.host}:{args.port}, Debug 日志: {args.verbose}, 热重载: {args.reload}")

    # 使用 uvicorn 启动应用
    uvicorn.run(
        "app:app",              # 指向 FastAPI 应用实例 (文件名:变量名)
        host=args.host,
        port=args.port,
        reload=args.reload,     # 控制是否启用热重载
        log_level='debug' if log_level == logging.DEBUG else 'info' # 修改: 传递字符串形式的日志级别
    )