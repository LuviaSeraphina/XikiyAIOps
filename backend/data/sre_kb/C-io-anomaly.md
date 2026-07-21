# 场景: I/O 磁盘异常 (C-io-anomaly)

## 触发关键词
IO高, iowait, 磁盘慢, 读写慢, 卡IO, IO异常, 磁盘IO, 磁盘读写

## 意图
io_anomaly

## 策略
确认 I/O 异常，定位元凶进程，降低优先级，验证效果

## 步骤模板
```json
{
  "intent": "io_anomaly",
  "strategy": "确认 I/O 异常，定位元凶进程，降低优先级，验证效果",
  "steps": [
    {"id": 1, "description": "检查磁盘 I/O 统计", "tool": "disk_io_stats", "params": {}, "depends_on": []},
    {"id": 2, "description": "定位 I/O 最高的进程", "tool": "process_io_top", "params": {"top_n": 5}, "depends_on": [1]},
    {"id": 3, "description": "降低进程 I/O 优先级", "tool": "process_ionice", "params": {"pid": "${step2.data.processes[0].pid}", "class": "idle"}, "depends_on": [2]},
    {"id": 4, "description": "验证 I/O 改善", "tool": "disk_io_stats", "params": {}, "depends_on": [3]}
  ]
}
```
