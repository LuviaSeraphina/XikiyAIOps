import type {
  SystemSummary,
  DiskInfo,
  ProcessInfo,
  NetworkStats,
  AuditLog,
} from '../types'

/** 切换此开关：true = 前端独立开发，false = 连接后端 */
export const USE_MOCK = true

// ========== 仪表盘 Mock ==========

export const MOCK_SYSTEM_SUMMARY: SystemSummary = {
  cpu_percent: 12.5,
  cpu_cores: 4,
  load_avg: [0.8, 0.6, 0.5],
  memory_total_gb: 14.0,
  memory_used_gb: 6.3,
  memory_percent: 45.0,
  swap_total_gb: 2.0,
  swap_used_gb: 0.0,
  uptime_seconds: 86400,
}

export const MOCK_DISKS: DiskInfo[] = [
  {
    mount_point: '/',
    total_gb: 100,
    used_gb: 48.5,
    free_gb: 51.5,
    usage_percent: 48.5,
    inode_percent: 12.3,
    filesystem: '/dev/sda1',
  },
  {
    mount_point: '/home',
    total_gb: 200,
    used_gb: 145.2,
    free_gb: 54.8,
    usage_percent: 72.6,
    inode_percent: 45.1,
    filesystem: '/dev/sda2',
  },
  {
    mount_point: '/var/log',
    total_gb: 50,
    used_gb: 46.8,
    free_gb: 3.2,
    usage_percent: 93.6,
    inode_percent: 88.7,
    filesystem: '/dev/sda3',
  },
]

export const MOCK_PROCESSES: ProcessInfo[] = [
  { pid: 1, name: 'systemd', cpu_percent: 0.0, memory_percent: 0.5, status: 'sleeping' },
  { pid: 1234, name: 'mysql', cpu_percent: 8.2, memory_percent: 12.3, status: 'running' },
  { pid: 2345, name: 'nginx', cpu_percent: 2.1, memory_percent: 3.8, status: 'running' },
  { pid: 3456, name: 'java', cpu_percent: 15.7, memory_percent: 28.4, status: 'running' },
  { pid: 4567, name: 'sshd', cpu_percent: 0.3, memory_percent: 0.2, status: 'sleeping' },
  { pid: 5678, name: 'python3', cpu_percent: 4.5, memory_percent: 2.1, status: 'running' },
  { pid: 6789, name: 'node', cpu_percent: 1.8, memory_percent: 1.6, status: 'running' },
  { pid: 7890, name: 'redis-server', cpu_percent: 0.6, memory_percent: 0.8, status: 'sleeping' },
  { pid: 8901, name: 'cron', cpu_percent: 0.0, memory_percent: 0.1, status: 'sleeping' },
  { pid: 9012, name: 'bash', cpu_percent: 0.1, memory_percent: 0.1, status: 'sleeping' },
]

export const MOCK_NETWORK: NetworkStats = {
  tcp_established: 3,
  tcp_time_wait: 12,
  tcp_close_wait: 0,
  listening_ports: 8,
}

export const MOCK_AUTH_FAILURES = {
  failed_ips: {
    '192.168.1.100': 15,
    '10.0.0.55': 8,
    '172.16.0.23': 5,
    '192.168.1.200': 3,
    '10.0.0.99': 2,
  },
  total: 33,
}

// ========== 审计日志 Mock ==========

export const MOCK_AUDIT_LOGS: AuditLog[] = [
  {
    id: 'audit-001',
    timestamp: '2026-05-28T14:32:00Z',
    user: 'admin',
    session_id: 'sess-001',
    risk_level: 'dangerous',
    stages: [
      { raw_input: '清理 /var/log 下的旧日志', timestamp: '2026-05-28T14:32:00Z', user: 'admin' },
      { tools_called: ['disk_usage', 'file_inspect'], snapshot_summary: '/var/log 占用 93.6%，发现大量 WAL 日志' },
      { llm_model: 'DeepSeek-V3', llm_raw_output: '建议执行 rm -rf /var/log/app/*.log', tool_calls_planned: ['file_delete'] },
      { rules_hit: ['rm_rf_detected', 'critical_path_access'], risk_score: 85, decision: 'blocked', reason: '目标路径为数据库关键日志目录，建议使用 logrotate' },
      { action_taken: '操作被拦截，未执行', exit_code: null, stdout: '', stderr: 'BLOCKED: dangerous operation', duration_ms: 120 },
    ],
  },
  {
    id: 'audit-002',
    timestamp: '2026-05-28T13:15:00Z',
    user: 'admin',
    session_id: 'sess-001',
    risk_level: 'read_only',
    stages: [
      { raw_input: '系统状态', timestamp: '2026-05-28T13:15:00Z', user: 'admin' },
      { tools_called: ['process_list', 'system_info'], snapshot_summary: 'CPU 12.5%，内存 45%，各项指标正常' },
      { llm_model: 'DeepSeek-V3', llm_raw_output: '系统运行正常，无需干预', tool_calls_planned: [] },
      { rules_hit: [], risk_score: 0, decision: 'allowed', reason: '只读查询，无风险' },
      { action_taken: '返回系统状态摘要', exit_code: 0, stdout: 'CPU: 12.5%, MEM: 45.0%', stderr: '', duration_ms: 850 },
    ],
  },
  {
    id: 'audit-003',
    timestamp: '2026-05-28T11:05:00Z',
    user: 'operator',
    session_id: 'sess-002',
    risk_level: 'restricted',
    stages: [
      { raw_input: '重启 nginx 服务', timestamp: '2026-05-28T11:05:00Z', user: 'operator' },
      { tools_called: ['service_status'], snapshot_summary: 'nginx 运行中，已连接 3 个活跃客户端' },
      { llm_model: 'DeepSeek-V3', llm_raw_output: '调用 service_restart 重启 nginx', tool_calls_planned: ['service_restart'] },
      { rules_hit: ['service_restart_requires_confirm'], risk_score: 40, decision: 'confirmed', reason: '用户已确认重启操作' },
      { action_taken: 'nginx 已成功重启', exit_code: 0, stdout: 'nginx restarted successfully', stderr: '', duration_ms: 2300 },
    ],
  },
]
