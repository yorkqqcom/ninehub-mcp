# ninehub-mcp Admin UI

设计规范：`../docs/UI-DESIGN.md`

## 开发

```bash
npm install
npm run dev   # http://127.0.0.1:5173，代理 /api → :8899
```

另开终端启动 Admin API：

```bash
ninehub-mcp admin --host 127.0.0.1 --port 8899
```

本地开发（无 Admin 密码）可直接登录，空密码即可获取 session token。

## 构建

```bash
npm run build   # 输出 frontend/dist/
```

## 已实现（P5）

- I1：登录页、路由守卫、全局 toast、AppShell + 导航
- I2：概览 KPI、Skeleton、EmptyState、dashboard/summary API
- I3：连接 CRUD、Verify/Scan、通配符页、preview-exposure API
- I4：Scan 页（job 轮询、Context Pack 预览、exposure banner）
- I5：系统设置（LLM + 密钥）与账户页
- I6：MCP 生成向导 + 接口清单
- I7：Serve 启停 + 日志监控（SSE）
- I8：接口测试、tool 锁定编辑、404、UI-DESIGN 定稿
