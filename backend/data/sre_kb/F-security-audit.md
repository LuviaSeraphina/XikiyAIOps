# 场景: 安全基线审计 (F-security-audit)

## 触发关键词
安全检查, 安全审计, 安全巡检, 安全扫描, 审计系统, 安全检查一下, security audit

## 意图
security_audit

## 策略
7 项安全基线审计: 用户权限→SUID→定时任务→内核模块→密码策略→认证失败→活跃会话

## 步骤模板
```json
{
  "intent": "security_audit",
  "strategy": "全面安全审计: 用户→SUID→crontab→内核模块→密码→认证→会话，7项检查一键报告",
  "steps": [
    {"id": 1, "description": "审计用户权限和sudo配置", "tool": "security_user_audit", "params": {}, "depends_on": []},
    {"id": 2, "description": "扫描SUID特权文件", "tool": "security_suid_scan", "params": {}, "depends_on": []},
    {"id": 3, "description": "审计定时任务风险", "tool": "security_crontab_audit", "params": {}, "depends_on": []},
    {"id": 4, "description": "检查内核模块安全性", "tool": "security_kernel_modules", "params": {}, "depends_on": []},
    {"id": 5, "description": "检查密码策略合规", "tool": "security_password_policy", "params": {}, "depends_on": []},
    {"id": 6, "description": "查看认证失败记录", "tool": "security_auth_failures", "params": {}, "depends_on": []},
    {"id": 7, "description": "检查活跃会话", "tool": "security_active_sessions", "params": {}, "depends_on": []}
  ]
}
```
