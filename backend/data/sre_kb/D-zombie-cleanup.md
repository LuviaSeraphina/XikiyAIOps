# 场景: 僵尸进程清理 (D-zombie-cleanup)

## 触发关键词
僵尸进程, zombie, 僵尸, defunct, 进程异常

## 意图
zombie_cleanup

## 策略
扫描僵尸进程，清理父进程，验证结果

## 步骤模板
```json
{
  "intent": "zombie_cleanup",
  "strategy": "扫描僵尸进程，清理父进程，验证结果",
  "steps": [
    {"id": 1, "description": "扫描僵尸进程", "tool": "process_zombie_scan", "params": {}, "depends_on": []},
    {"id": 2, "description": "清理僵尸进程", "tool": "process_zombie_cleanup", "params": {"pid": "${step1.data.zombies[0].pid}"}, "depends_on": [1]},
    {"id": 3, "description": "验证清理结果", "tool": "process_zombie_scan", "params": {}, "depends_on": [2]}
  ]
}
```
