# 场景: OOM 内存溢出排查 (G-oom-diagnosis)

## 触发关键词
OOM, 内存不足, 内存溢出, 内存爆了, 内存满了, out of memory, 内存耗尽

## 意图
oom_diagnosis

## 策略
查看历史OOM记录 → 定位内存TOP进程 → 查看进程详情 → 检查Swap

## 步骤模板
```json
{
  "intent": "oom_diagnosis",
  "strategy": "查看OOM历史→定位内存大户→查进程详情→Swap状态→给出建议",
  "steps": [
    {"id": 1, "description": "查看历史OOM事件", "tool": "memory_oom_history", "params": {}, "depends_on": []},
    {"id": 2, "description": "查看当前内存使用TOP进程", "tool": "process_top_memory", "params": {"top_n": 10}, "depends_on": []},
    {"id": 3, "description": "查看Swap使用情况", "tool": "swap_info", "params": {}, "depends_on": []},
    {"id": 4, "description": "查看内存整体状态", "tool": "memory_info", "params": {}, "depends_on": []}
  ]
}
```
