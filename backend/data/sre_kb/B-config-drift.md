# 场景: 配置漂移检测 (B-config-drift)

## 触发关键词
配置漂移, 配置对比, 配置恢复, nginx配置, ssh配置, 配置被改, config diff

## 意图
config_drift

## 策略
对比配置差异，备份当前配置，恢复原始配置，重载服务

## 步骤模板
```json
{
  "intent": "config_drift",
  "strategy": "对比配置差异，备份当前配置，恢复原始配置，重载服务",
  "steps": [
    {"id": 1, "description": "对比当前配置与原始配置", "tool": "config_diff", "params": {"path": "${用户指定配置路径}", "compare_to": "${原始配置路径}"}, "depends_on": []},
    {"id": 2, "description": "备份当前漂移配置", "tool": "config_backup", "params": {"path": "${用户指定配置路径}", "tag": "drift_backup"}, "depends_on": [1]},
    {"id": 3, "description": "恢复原始配置", "tool": "config_restore", "params": {"backup_path": "${step2.data.backup_path}"}, "depends_on": [2]},
    {"id": 4, "description": "重载服务", "tool": "service_control", "params": {"service": "${用户指定服务名}", "action": "reload"}, "depends_on": [3]}
  ]
}
```
