// ============================================================
// SRE-agent 全局类型定义
// 严格对齐后端 API 契约与 SSE 事件流
// ============================================================

// ========== 枚举字面量 ==========

/** MCP 工具风险等级 */
export type RiskLevel = 'read_only' | 'restricted' | 'dangerous'

/** 对话消息角色 */
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

/** 工具调用状态 */
export type ToolCallStatus = 'pending' | 'running' | 'done' | 'error'

/** 安全决策 */
export type SecurityDecision = 'allowed' | 'blocked' | 'confirmed'

/** 威胁等级 */
export type ThreatLevel = 'SAFE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

/** 意图分类 */
export type IntentCategory =
  | 'jailbreak'
  | 'dangerous_action'
  | 'ops_action'
  | 'safe_query'
  | 'unknown'

/** SSE 事件类型（严格对齐后端 chat_stream yield） */
export type SSEEventType =
  | 'token'
  | 'tool_call'
  | 'tool_result'
  | 'security_check'
  | 'rca_analysis'
  | 'done'
  | 'error'

// ========== API 统一响应 ==========

export interface ApiResponse<T> {
  code: number
  data: T | null
  message: string
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ========== 对话模型（对齐 Conversation + Message） ==========

/** 对话会话 */
export interface Conversation {
  id: string
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

/** 单条消息 */
export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: string
  tool_calls?: ToolCall[]
}

/** MCP 工具调用（对齐 Message.tool_calls JSON 列） */
export interface ToolCall {
  id: string
  tool_name: string
  arguments: Record<string, unknown>
  status: ToolCallStatus
  risk_level: RiskLevel
  result?: unknown
}

// ========== 审计日志模型（对齐 AuditLog 5 阶段） ==========

/** 审计日志 */
export interface AuditLog {
  id: string
  timestamp: string
  user: string
  session_id: string
  risk_level: RiskLevel
  stages: [
    StageInput,
    StagePerception,
    StageReasoning,
    StageValidation,
    StageExecution,
  ]
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
  decision: SecurityDecision
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

// ========== SSE 事件载荷 ==========

export interface SSETokenData {
  text: string
}

export interface SSEToolCallData {
  tool_name: string
  arguments: Record<string, unknown>
  risk_level: RiskLevel
}

export interface SSEToolResultData {
  tool_name: string
  result: unknown
  status: ToolCallStatus
}

export interface SSESecurityCheckData {
  tool_name: string
  summary: string
  details: string
  risk_level: RiskLevel
}

export interface SSERcaAnalysisData {
  score: number
  grade: string
  alerts: string[]
}

export interface SSEErrorData {
  message: string
}

// ========== 确认操作 ==========

export interface PendingConfirm {
  tool_name: string
  summary: string
  details: string
  risk_level: RiskLevel
}

// ========== 仪表盘辅助类型 ==========

export interface ChartDataPoint {
  label: string
  value: number
  color?: string
}

