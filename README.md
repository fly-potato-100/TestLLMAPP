# AI聊天网页Demo项目

## 项目概述
基于React和Flask实现的AI聊天网页Demo，前端提供简洁聊天界面，后端作为百炼平台API代理。

## 技术栈
- 前端：React + Vite + Axios
- 后端：Flask + python-dotenv + requests
- 部署：开发模式运行

## 功能特性
1. 用户消息发送与显示
2. AI回复接收与显示
3. 简单的错误处理

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
python app.py
```

## 配置说明
1. 环境变量配置：
   - 复制示例文件并重命名：
     ```bash
     cp backend/.env.example backend/.env
     cp frontend/.env.example frontend/.env
     ```
   - 后端配置(`backend/.env`):
     - BAILIAN_API_URL: 百炼平台API地址
     - BAILIAN_API_KEY: 百炼平台API密钥
   - 前端配置(`frontend/.env`):
     - REACT_APP_API_BASE_URL: 后端服务地址(默认http://localhost:5000)

## 项目结构
```
project-root/
├── frontend/        # React前端
│   ├── src/        # 源代码
│   └── package.json # 依赖配置
├── backend/         # Flask后端
│   ├── app.py      # 主程序
│   └── .env        # 环境配置
└── README.md       # 项目文档
```

## 注意事项
1. 确保已安装Node.js和Python环境
2. 开发时需同时运行前后端服务
3. 生产环境需要额外配置