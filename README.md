# 智能旅行规划系统 Trip Planner

> 一个基于 HelloAgents 多智能体协作的智能行程规划 Web 应用。

## 📝 项目简介

本项目面向“旅行信息分散、规划耗时、个性化不足”的问题，提供从需求输入到完整行程生成、保存、编辑和回滚的一体化解决方案。

它的核心特点包括：
- 基于 HelloAgents 的多智能体协作架构，分别处理景点检索、酒店推荐、天气查询和最终行程编排
- 集成 MCP 地图工具链，可调用高德地图能力获取地点、天气与地理信息
- 支持异步生成任务、任务进度查询、行程版本管理和版本回滚
- 结合 Redis 与 FAISS 向量记忆，实现访客会话持久化、用户偏好记忆和历史行程召回
- 提供前后端分离体验，前端支持地图展示、行程编辑、导出等交互能力

适用场景包括：
- 想快速生成旅游计划的个人用户
- 需要保存、修改和比较多个行程版本的旅行规划场景
- 多智能体、MCP 工具调用、向量记忆相关的课程作业或实践项目

## ✨ 核心功能

- [x] 智能行程生成：根据目的地、日期、预算、偏好自动生成结构化多日行程
- [x] 多智能体协作规划：景点、酒店、天气、规划智能体分工协作，汇总为最终方案
- [x] 行程持久化管理：支持异步任务、访客会话、版本历史、冲突检测与回滚

## 🛠️ 技术栈

- HelloAgents 框架
- 智能体范式：多智能体协作 + 工具调用，整体偏 `Plan-and-Solve` 编排，单体执行支持类 `ReAct` 工具调用循环
- 工具和 API：
  - MCP 工具服务：`uvx amap-mcp-server`
  - 高德地图 API
  - OpenAI 兼容 LLM API（可配置 OpenAI / ModelScope / 其他兼容服务）
  - Unsplash API
- 其他依赖库：
  - 后端：FastAPI、Uvicorn、Redis、FAISS、Sentence-Transformers、PyJWT、bcrypt
  - 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router、Amap JS API

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 16+
- Redis 6+
- `uvx`，用于启动 MCP 地图工具服务

### 安装依赖

后端依赖：

```bash
cd backend
pip install -r requirements.txt
```

前端依赖：

```bash
cd frontend
npm install
```

### 配置 API 密钥

后端配置：

```bash
cd backend
cp .env.example .env
```

然后编辑 `backend/.env`，至少补充以下配置：

```env
LLM_API_KEY=your_api_key
LLM_MODEL_ID=your_model_name
LLM_BASE_URL=your_base_url
AMAP_API_KEY=your_amap_api_key
UNSPLASH_ACCESS_KEY=your_unsplash_access_key
REDIS_HOST=localhost
REDIS_PORT=6379
```

前端如需单独配置环境变量：

```bash
cd frontend
cp .env.example .env
```

### 运行项目

启动后端：

```bash
cd backend
python run.py
```

启动前端：

```bash
cd frontend
npm run dev
```

默认访问地址：
- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`

## 📖 使用示例

### 1. 通过接口生成行程

```bash
curl -X POST "http://localhost:8000/api/v1/trips/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "杭州",
    "start_date": "2026-04-03",
    "end_date": "2026-04-05",
    "preferences": ["自然", "美食", "休闲"],
    "hotel_preferences": ["舒适型", "地铁附近"],
    "budget": "中等"
  }'
```

返回结果会包含行程标题、每日景点安排、餐饮推荐、酒店建议、预算汇总，以及 `id`、`version`、`city_support_level` 等字段。

### 2. 异步生成并轮询任务进度

```bash
curl -X POST "http://localhost:8000/api/v1/trips/plan-async" \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "成都",
    "start_date": "2026-04-10",
    "end_date": "2026-04-13",
    "preferences": ["美食", "城市漫步"],
    "hotel_preferences": ["舒适型"],
    "budget": "宽裕"
  }'
```

拿到 `task_id` 后可继续查询：

```bash
curl "http://localhost:8000/api/v1/trips/tasks/{task_id}"
```

### 3. 编辑行程并使用版本控制

- 查询版本历史：`GET /api/v1/trips/{trip_id}/versions`
- 更新行程：`PUT /api/v1/trips/{trip_id}`
- 回滚版本：`POST /api/v1/trips/{trip_id}/rollback?target_version=2`

## 🎯 项目亮点

- 亮点1：多智能体分工明确，规划过程不是单次生成，而是景点、酒店、天气与总规划智能体协同完成
- 亮点2：将 MCP 工具调用、向量记忆、Redis 持久化整合进统一后端架构，工程化程度较高
- 亮点3：不仅能“生成”，还能“保存、编辑、比对、回滚”，更接近真实产品形态

## 🔮 未来计划

- [ ] 引入更细粒度的交通路径规划与日程时间优化
- [ ] 增加更多外部数据源，如点评、票价、实时营业信息
- [ ] 优化测试覆盖率与前后端部署文档，补齐生产环境配置说明

## 🤝 贡献指南

欢迎提出 Issue 和 Pull Request。

如果你准备参与开发，建议优先关注以下方向：
- 行程生成质量优化
- 前端交互体验与地图联动
- 工具调用稳定性与异常处理
- 测试补充与文档完善

## 📄 许可证

MIT License

## 🙏 致谢

感谢 Datawhale 社区和 Hello-Agents 项目。
