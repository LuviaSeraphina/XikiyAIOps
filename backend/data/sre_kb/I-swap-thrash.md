# 场景: Swap 抖动诊断 (I-swap-thrash)

## 触发关键词
swap高, 换页频繁, 机器卡, 系统变慢, 卡顿, swap抖动, 交换分区

## 意图
swap_diagnosis

## 策略
交换分区状态 → 内存压力 → 内存TOP进程 → 虚拟内存统计 → 定位元凶

## 步骤模板
```json
{
  "intent": "swap_diagnosis",
  "strategy": "Swap使用率→内存压力→TOP进程→VMstat→定位谁在疯狂换页",
  "steps": [
    {"id": 1, "description": "查看Swap使用情况", "tool": "swap_info", "params": {}, "depends_on": []},
    {"id": 2, "description": "查看内存整体状态", "tool": "memory_info", "params": {}, "depends_on": []},
    {"id": 3, "description": "查看内存TOP10进程", "tool": "process_top_memory", "params": {"top_n": 10}, "depends_on": []},
    {"id": 4, "description": "查看虚拟内存统计(vmstat)", "tool": "vmstat_stats", "params": {}, "depends_on": []},
    {"id": 5, "description": "查看OOM历史", "tool": "memory_oom_history", "params": {}, "depends_on": []}
  ]
}
```
