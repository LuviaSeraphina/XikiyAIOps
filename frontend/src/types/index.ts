// ========== 基础类型 ==========

/** 风险等级：只读 | 受限 | 危险 */
export type RiskLevel = 'read_only' | 'restricted' | 'dangerous'

/** 对话消息角色 */
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

/** 工具调用状态 */
export type ToolCallStatus = 'pending' | 'running' | 'done' | 'error'

// ========== 系统状态 ==========

/** 系统概览（CPU/内存/Swap/运行时间） */
export interface SystemSummary {
  cpu_percent: number
  cpu_cores: number
  load_avg: [number, number, number]   // 1min / 5min / 15min
  memory_total_gb: number
  memory_used_gb: number
  memory_percent: number
  swap_total_gb: number
  swap_used_gb: number
  uptime_seconds: number
}

/** 单个磁盘/挂载点信息 */
export interface DiskInfo {
  mount_point: string
  total_gb: number
  used_gb: number
  free_gb: number
  usage_percent: number
  inode_percent: number
  filesystem: string
}

/** 进程信息 */
export interface ProcessInfo {
  pid: number
  name: string
  cpu_percent: number
  memory_percent: number
  status: string
}

/** 网络连接统计 */
export interface NetworkStats {
  tcp_established: number
  tcp_time_wait: number
  tcp_close_wait: number
  listening_ports: number
}

/** 登录失败来源 */
export interface AuthFailure {
  ip: string
  count: number
  user: string
}

// ========== 对话 ==========

/** 对话消息 */
export interface ChatMessage {
  id: string
  role: MessageRole
  content: string               // Markdown 文本
  timestamp: string
  tool_calls?: ToolCall[]       // 该消息包含的工具调用
}

/** MCP 工具调用 */
export interface ToolCall {
  id: string
  tool_name: string
  arguments: Record<string, unknown>
  status: ToolCallStatus
  result?: unknown
  risk_level?: RiskLevel
}

/** 待确认的危险操作 */
export interface PendingConfirm {
  message_id: string
  tool_name: string
  summary: string
  details: string
  risk_level: RiskLevel
}

// ========== 审计日志 ==========

/** 审计日志 — 完整五阶段闭环 */
export interface AuditLog {
  id: string
  timestamp: string
  user: string
  session_id: string
  risk_level: RiskLevel
  stages: [StageInput, StagePerception, StageReasoning, StageValidation, StageExecution]
}

/** 阶段 1 — 接收指令 */
export interface StageInput {
  raw_input: string
  timestamp: string
  user: string
}

/** 阶段 2 — 感知环境 */
export interface StagePerception {
  tools_called: string[]
  snapshot_summary: string
}

/** 阶段 3 — 推理决策 */
export interface StageReasoning {
  llm_model: string
  llm_raw_output: string
  tool_calls_planned: string[]
}

/** 阶段 4 — 安全校验 */
export interface StageValidation {
  rules_hit: string[]
  risk_score: number
  decision: 'allowed' | 'blocked' | 'confirmed'
  reason: string
}

/** 阶段 5 — 执行结果 */
export interface StageExecution {
  action_taken: string
  exit_code: number | null
  stdout: string
  stderr: string
  duration_ms: number
}

// ========== SSE 事件 ==========

/** SSE 事件类型 */
export type SSEEventType =
  | 'token'
  | 'tool_call'
  | 'tool_result'
  | 'security_check'
  | 'done'
  | 'error'

/** SSE 事件联合体 */
export interface SSEEvent {
  event: SSEEventType
  data: SSETokenData | SSEToolCallData | SSEToolResultData | SSESecurityCheckData | SSEDoneData | SSEErrorData
}

/** token — 流式文本片段 */
export interface SSETokenData { text: string }

/** tool_call — LLM 决定调用工具 */
export interface SSEToolCallData {
  tool_name: string
  arguments: Record<string, unknown>
  risk_level: RiskLevel
}

/** tool_result — 工具执行完毕 */
export interface SSEToolResultData {
  tool_name: string
  result: unknown
  status: ToolCallStatus
}

/** security_check — 危险操作需二次确认 */
export interface SSESecurityCheckData {
  tool_name: string
  summary: string
  details: string
  risk_level: RiskLevel
  require_confirmation: boolean
}

/** done — 对话结束 */
export interface SSEDoneData { message_id: string }

/** error — 异常 */
export interface SSEErrorData { code: string; message: string }
