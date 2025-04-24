# AI聊天网页Demo项目

## 项目概述
基于React和FastAPI实现的AI聊天网页Demo，前端提供简洁聊天界面，后端作为百炼、coze、火山方舟等平台API代理。

## 技术栈
- 前端：React + Vite + Axios
- 后端：FastAPI + Uvicorn + Pydantic + python-dotenv + httpx
- 部署：开发模式运行

## 功能特性
1. 用户消息发送与显示
2. AI回复接收与显示
3. 简单的错误处理

## 配置说明
1. 环境变量配置：
   - 复制示例文件并重命名：
     ```bash
     cp backend/.env.example backend/.env
     cp frontend/.env.example frontend/.env
     ```
   - 后端配置(`backend/.env`):
     - BAILIAN_BASE_API_URL: 百炼平台API地址
     - BAILIAN_API_KEY: 百炼平台API密钥
     - COZE_BASE_URL: Coze平台API基础地址
     - COZE_API_KEY: Coze平台API密钥
     - COZE_WORKFLOW_ID: Coze平台要运行的工作流ID
     - 根据 backend/.env.example 补充其他平台
   - 前端配置(`frontend/.env`):
     - REACT_APP_API_BASE_URL: 后端服务地址(默认http://localhost:8000/api)

## 快速开始

### 前端启动
```bash
cd frontend
npm install
npm start
```

### 后端启动
```bash
cd backend
pip install -r requirements.txt
cd ..
python -m backend.app -v

## 项目结构
```
project-root/
├── frontend/        # React前端
│   ├── public/
│   ├── src/        # 源代码
│   ├── .env.example
│   ├── index.html
│   ├── package.json # 依赖配置
│   └── vite.config.js
├── backend/         # FastAPI后端
│   ├── __init__.py
│   ├── main.py     # FastAPI 应用入口 (替代 app.py)
│   ├── config.py   # 配置加载
│   ├── models/     # Pydantic模型
│   │   ├── __init__.py
│   │   ├── bailian.py
│   │   ├── chat.py
│   │   └── coze.py    # Coze 模型文件
│   ├── routers/    # API路由
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   └── hello.py
│   ├── services/   # 外部服务调用逻辑
│   │   ├── __init__.py
│   │   ├── bailian.py
│   │   └── coze.py    # Coze API 调用实现
│   ├── .env.example # 环境变量示例
│   ├── .env        # 环境配置 (gitignored)
│   └── requirements.txt # 依赖文件
└── README.md       # 项目文档
```

## 注意事项
1. 确保已安装Node.js (>=16) 和 Python (>=3.8) 环境。
2. 开发时需同时运行前后端服务。
3. 生产环境部署需要考虑使用 Gunicorn + Uvicorn worker，并配置反向代理（如 Nginx）。
4. 请务必在 `.env` 文件中配置好所需的 API Key 和 URL。