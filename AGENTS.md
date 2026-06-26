# AGENTS.md — ninehub-mcp

本文件供 Cursor / Hermes Agent 与协作者快速理解仓库约定。

## 项目定位

- **通用 PostgreSQL MCP Server**，Hermes 通过 **streamable-http** 调用
- **独立仓库**：不修改、不依赖 NineHub 项目代码
- 设计真源：`docs/DESIGN-v3-confirmed.md`

## 架构要点

| 进程 | 职责 |
|------|------|
| `ninehub-mcp admin` | 唯一写入 SQLite；scan、manifest、export-config |
| `ninehub-mcp serve` | 读 Admin API 或 `--config` JSON；**禁止直接读 SQLite** |

配置同步：`GET /api/v1/mcp/config` + 轮询 `config/version`（默认 60s）。

## Agent 调用策略

1. 优先 `list_tools` — 读短 description + 关键词选表
2. `read catalog://{schema}.{table}` — 获取 join_hints / filter_hints / usage_examples（hint_format v1）
3. `read sample://` / `schema://` — 样例与列元数据
4. 使用 `browse_{schema}_{table}` 参数化查询；复杂 JOIN → `execute_sql`（暂缓）

## CLI

```bash
ninehub-mcp admin [--port 8899]
ninehub-mcp serve --transport streamable-http --admin-url ... --connection-id ...
ninehub-mcp serve --config mcp-config.json --transport streamable-http
ninehub-mcp export-config --connection-id <uuid> -o mcp-config.json
ninehub-mcp scan --url $DATABASE_URL --out schema.json
ninehub-mcp serve --legacy-stdio   # 仅调试 Phase0
```

## 文档

- 产品设计：`docs/DESIGN-v3-confirmed.md`
- **Admin UI**：`docs/UI-DESIGN.md`（配色、组件、页面、NineHub 复制清单）
- 示例：`examples/.env.example`、`examples/cursor.mcp.json`

## 模块职责

| 路径 | 说明 |
|------|------|
| `admin/` | FastAPI、SQLite、scan、MCP config API |
| `collector/` | 每表 10 条样例 |
| `context/` | ContextPack、McpRuntimeConfig、ToolManifest |
| `planner/` | `browse_{schema}_{table}` manifest |
| `runtime/catalog_runtime.py` | **主 MCP 运行时**（HTTP/stdio） |
| `runtime/server.py` | **遗留** Phase0 generic tools |
| `runtime/config_loader.py` | Admin API / JSON 配置加载 |
| `wildcard.py` | 表暴露通配符 |
| `scanner/ninehub.py` | **已废弃 stub**，v3 不使用 |

## 编码规范

- Python ≥3.10，pydantic-settings，black **100** 字符，ruff
- 新 API 分页对齐 `{items, total, page, size}`（逐步补齐 page/size）
- 测试：`pytest`；优先 mock PG，集成测后续补
- 日志：structlog（新代码优先使用）
- **不**在运行时让 LLM 拼 SQL
- **不**静默向复杂 SQL 追加 LIMIT（execute_sql 单独设计）

## 环境变量

见 `examples/.env.example`。

## 明确不做

- NineHub 模式 / `tia_overrides`
- serve 直读 Admin SQLite
- 静态 generate（首版）
- 修改 NineHub 仓库

## 当前缺口（实现时优先）

- P2b：DeepSeek LLM manifest 构建
- P3：`execute_sql` + LIMIT 分流设计
- P4–P5：Admin CRUD 完善、Vue UI
- CI：`.github/workflows` 待补
