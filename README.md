# ninehub-mcp

通用 **PostgreSQL MCP Server**，供 **Hermes** 通过 **streamable-http** 调用。

独立项目：**不修改、不依赖 [NineHub](https://github.com/)**；NineHub 的 PG 仅作为可连接数据源之一。

设计文档：[docs/DESIGN-v3-confirmed.md](docs/DESIGN-v3-confirmed.md) · Admin UI：[docs/UI-DESIGN.md](docs/UI-DESIGN.md)

---

## 架构概览

```
Hermes ──streamable-http + MCP_API_KEY──► ninehub-mcp serve (:8000)
                                              │
                                              │ GET /api/v1/mcp/config
                                              ▼
                                         ninehub-mcp admin (:8899)
                                         SQLite 配置中心
                                              │
                                              ▼
                                         PostgreSQL (只读)
```

- **配置通道**：Admin REST API 为主；`export-config` JSON 为离线兜底
- **Catalog 优先**：`browse_{schema}_{table}` → 复杂分析再用 `execute_sql`（暂缓实现）
- **双层交付**：`list_tools` 短描述 + 关键词；详情读 `catalog://{schema}.{table}`（v1 JSON）
- **样例**：scan 10 条 build 样例 → 两阶段 LLM 构建 Rich Manifest；Hermes Resource 3 条 + catalog

生成向导说明：[docs/MCP-BUILD-WIZARD.md](docs/MCP-BUILD-WIZARD.md)

---

## 快速开始

```bash
cd D:\PycharmProjects\ninehub-mcp
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
cp examples/.env.example .env   # 编辑 DATABASE_URL、密钥
```

### 1. 启动 Admin（配置中心）

```bash
set ADMIN_API_TOKEN=dev-token
set MCP_API_KEY=dev-mcp-key
ninehub-mcp admin --port 8899
```

### 2. 创建连接并扫描

```bash
# 创建连接（Basic Auth 可选，127.0.0.1 开发环境可不设）
curl -X POST http://127.0.0.1:8899/api/v1/connections ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"local\",\"database_url\":\"postgresql://readonly:pass@127.0.0.1:5432/mydb\",\"include_table_patterns\":[\"public.*\"]}"

# 记下返回的 id，然后 scan
curl -X POST http://127.0.0.1:8899/api/v1/connections/<CONNECTION_ID>/scan

# （可选）MCP 生成：两阶段 LLM 构建 Rich Manifest
curl -X POST http://127.0.0.1:8899/api/v1/mcp/build-jobs ^
  -H "Content-Type: application/json" ^
  -d "{\"connection_id\":\"<CONNECTION_ID>\",\"options\":{\"mode\":\"quick\"}}"
```

### 3. 启动 MCP serve

```bash
set MCP_API_KEY=dev-mcp-key
set ADMIN_API_TOKEN=dev-token
ninehub-mcp serve ^
  --transport streamable-http ^
  --admin-url http://127.0.0.1:8899 ^
  --connection-id <CONNECTION_ID> ^
  --profile all
```

### 4. Hermes 配置

见 [examples/cursor.mcp.json](examples/cursor.mcp.json)（streamable-http + Bearer）。

### 离线模式（无 Admin）

```bash
ninehub-mcp export-config --connection-id <CONNECTION_ID> -o mcp-config.json
ninehub-mcp serve --config mcp-config.json --transport streamable-http
```

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `admin` | 启动 Admin API + SQLite 配置中心 |
| `serve` | MCP Server（streamable-http 或 stdio） |
| `export-config` | 从 Admin 导出 JSON 配置 |
| `scan` | 仅输出 Schema IR JSON（调试） |
| `serve --legacy-stdio` | Phase0 通用 5 tools（遗留） |

---

## MCP Tools（v3）

| 类型 | Tools |
|------|-------|
| Catalog | `browse_{schema}_{table}`、`list_schemas`、`list_tables`、`describe_table` |
| Query | `list_exposed_tables`、`execute_sql`（**stub，暂缓**） |
| Resources | `schema://`、`sample://`（3 条）、**`catalog://`**（join/keywords/示例 v1） |

### Agent 推荐流程

1. `list_tools` — 读短 description + 关键词选表  
2. `read catalog://schema.table` — join_hints / filter_hints / usage_examples  
3. `browse_{schema}_{table}` — 参数化查询  

### MCP 构建（Admin UI 或 API）

| 模式 | 说明 |
|------|------|
| 快速 | 选连接 → 一键重建（Pass1 图谱 + Pass2 逐表 LLM，失败自动规则降级） |
| 高级 | 审视 Pack → 配置 domain_hint / skip_pass1 → 质量预览 |

Pass1 失败时 `fallback_to_rule`：物理 FK + 推断 join 继续构建，不中断。

---

## 安全

| 项 | 约定 |
|----|------|
| serve (HTTP) | 强制 `MCP_API_KEY` |
| Admin | 非 `127.0.0.1` 须 `ADMIN_USERNAME` / `ADMIN_PASSWORD` |
| serve → Admin | `ADMIN_API_TOKEN`（Bearer） |
| 数据库 | 只读角色；browse 走参数化 SafeQueryEngine |
| 表过滤 | Admin 通配符 include/exclude；预置排除 `pg_catalog.*` 等 |

---

## 项目结构

```
ninehub_mcp/
├── admin/           # FastAPI 配置中心
├── collector/       # SampleCollector（10 条样例）
├── context/         # ContextPack、McpRuntimeConfig
├── llm/             # Pass1 graph + Pass2 table builder、prompt 模板
├── planner/         # ToolPlanner、join_infer、filter_infer
├── runtime/         # catalog_runtime、config_loader、热重载
├── scanner/         # PostgresScanner
├── wildcard.py      # 通配符过滤
└── cli.py
docs/                # DESIGN-v3-confirmed.md
examples/            # .env、Hermes 配置、filter_patterns
tests/
```

---

## 开发

```bash
pytest -p no:pytest_postgresql
black .
ruff check .
```

Agent 约定见 [AGENTS.md](AGENTS.md)。

---

## 实施状态（摘要）

| 阶段 | 状态 |
|------|------|
| P0–P1c | ✅ 扫描、Admin 配置 API、streamable-http、热重载轮询 |
| P2 部分 | ✅ browse tools、filter 推断、软告警 |
| P2b | ✅ 两阶段 LLM + catalog:// v1 + 生成向导 |
| P3 | ⏳ execute_sql（LIMIT 策略单独设计） |
| P4–P5 | ✅ 大部分（Admin CRUD、Vue UI，见 [UI-DESIGN.md](docs/UI-DESIGN.md)） |

详见设计文档 §12。
