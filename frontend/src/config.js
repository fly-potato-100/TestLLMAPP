// 集中管理前端环境变量默认值
const CONFIG = {
  API_BASE_URL: process.env.REACT_APP_API_BASE_URL || "http://localhost:5000"
};

export default CONFIG;