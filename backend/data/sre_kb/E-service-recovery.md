# 场景: 服务故障自愈 (E-service-recovery)

## 触发关键词
服务挂了, 服务宕机, 服务异常, 服务死了, nginx挂了, 服务启动不了, 服务停止, service down

## 意图
service_recovery

## 策略
确认当前服务状态 → 查看服务崩溃日志 → 重启服务 → 验证服务恢复

## 步骤模板
```json
{
  "intent": "service_recovery",
  "strategy": "确认服务状态，查看崩溃日志，重启服务，验证恢复",
  "steps": [
    {"id": 1, "description": "检查服务运行状态", "tool": "service_control", "params": {"service": "${用户指定服务名}", "action": "status"}, "depends_on": []},
    {"id": 2, "description": "查看服务最近日志", "tool": "system_journal_tail", "params": {"service": "${用户指定服务名}", "lines": 50}, "depends_on": [1]},
    {"id": 3, "description": "重启服务", "tool": "service_control", "params": {"service": "${用户指定服务名}", "action": "restart"}, "depends_on": [2]},
    {"id": 4, "description": "检查服务恢复状态", "tool": "service_control", "params": {"service": "${用户指定服务名}", "action": "status"}, "depends_on": [3]},
    {"id": 5, "description": "验证监听端口", "tool": "network_listening_ports", "params": {}, "depends_on": [4]}
  ]
}
```
