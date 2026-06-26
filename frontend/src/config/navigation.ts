export type NavItem = {
  to: string;
  label: string;
  hint?: string;
};

export type NavGroup = {
  section: string;
  items: NavItem[];
};

export const NAV_GROUPS: NavGroup[] = [
  {
    section: "平台",
    items: [{ to: "/", label: "概览", hint: "KPI 与推荐流程" }],
  },
  {
    section: "连接",
    items: [{ to: "/connections", label: "数据源", hint: "PostgreSQL 连接配置" }],
  },
  {
    section: "MCP",
    items: [
      { to: "/mcp/build", label: "生成向导", hint: "构建 tool manifest" },
      { to: "/mcp/tools", label: "接口清单", hint: "浏览 catalog tools" },
      { to: "/mcp/test", label: "接口测试", hint: "Admin 内调用" },
      { to: "/mcp/serve", label: "服务管控", hint: "启停 MCP Serve" },
      { to: "/mcp/logs", label: "监控日志", hint: "SSE 实时日志" },
    ],
  },
  {
    section: "系统",
    items: [
      { to: "/settings", label: "设置", hint: "LLM 与密钥" },
      { to: "/settings/account", label: "账户", hint: "登录凭据" },
    ],
  },
];
