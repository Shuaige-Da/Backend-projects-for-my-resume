# Backend Resume Projects

用于简历展示的 Python 后端开发与数据工程项目，覆盖 Web 应用、REST API、数据库设计、批量 ETL、数据质量控制、可视化分析、自动化测试和部署配置。

## 项目

### 1. [RainWave 个人博客内容管理系统](rainwave-personal-blog/)

- 使用 Flask 应用工厂和模块化路由组织公开站点、管理员后台、内容审核与 Hermes AI 服务。
- 管理 Markdown 文章、日记、图片、音乐、视频、留言和站点设置，支持 SQLite 本地开发与 MySQL 生产配置。
- 实现 CSRF、CSP nonce、可信主机、登录限流、安全 Cookie、上传文件真实类型校验和 Markdown 白名单净化。
- 提供 Gunicorn、Nginx、Systemd、Fail2ban 与日志配置，并包含单元、安全和性能回归测试。

### 2. [空气质量 ETL 与数据分析平台](air-quality-etl-api/)

- 面向台湾环境部 118 个月空气质量 CSV，按 50,000 行分块完成类型转换、县市标准化、质量检查与双语记录消重。
- 使用 PostgreSQL `COPY`、临时表和批量 `UPSERT` 导入 700 万级观测，以 SHA-256 和导入游标支持幂等执行与断点恢复。
- FastAPI 提供观测明细、县市/监测站排名、趋势、分布、相关性和导入审计接口。
- Vue 3 + ECharts 提供中文数据看板和中文 API 文档；项目包含 Docker Compose、自动化测试和生产构建配置。

## 使用说明

两个子项目相互独立，请进入对应目录阅读 README 并安装依赖。仓库不包含真实密钥、本地数据库、上传内容、运行日志、虚拟环境、Node.js 依赖和空气质量原始 CSV。

空气质量数据来自台湾环境部开放数据平台的 [AQX_P_488 空气品质指标历史资料](https://data.moenv.gov.tw/dataset/detail/AQX_P_488)。本仓库记录的规模和耗时来自特定数据快照及开发机实测，不代表生产环境 SLA。
