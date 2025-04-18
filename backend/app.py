import logging
import argparse
import uvicorn
from .routers import hello
from .routers import chat
from .config import CONFIG
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- 配置 CORS --- 
# 允许所有来源，所有方法，所有头，可以根据需要调整
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境中应指定允许的源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 包含路由 ---
app.include_router(hello.router, prefix="", tags=["greetings"])
app.include_router(chat.router, prefix="", tags=["chat"])

# --- 主程序入口 ---
if __name__ == '__main__':
    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description='启动 FastAPI 后端服务')
    parser.add_argument('-v', '--verbose', action='store_true', help='启用 DEBUG 级别的日志记录')
    # 使用导入的 CONFIG 获取默认值
    parser.add_argument('--host', type=str, default=CONFIG["FASTAPI_HOST"], help='服务监听的主机地址')
    parser.add_argument('--port', type=int, default=CONFIG["FASTAPI_PORT"], help='服务监听的端口')
    parser.add_argument('--reload', action='store_true', help='启用热重载模式 (用于开发)')
    args = parser.parse_args()

    # 根据参数配置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_level_str = 'debug' if log_level == logging.DEBUG else 'info'

    # 配置根日志记录器
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info(f"启动 FastAPI 服务器，监听地址 {args.host}:{args.port}, Debug 日志: {args.verbose}, 热重载: {args.reload}")

    # 使用 uvicorn 启动应用
    uvicorn.run(
        "backend.app:app", # 指向 FastAPI 应用实例 (模块路径:变量名)
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=log_level_str
    )