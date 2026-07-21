# 场景: 清理系统垃圾 (A-clean-garbage)

## 触发关键词
清理垃圾, 磁盘满, 空间不足, 释放空间, 清理磁盘, tmp文件, 日志太大, /var/log

## 意图
clean_system_garbage

## 策略
先感知磁盘状态，定位大文件，识别性质，逐个安全清理，最后验证

## 步骤模板
```json
{
  "intent": "clean_system_garbage",
  "strategy": "先感知磁盘状态，定位大文件，识别性质，逐个安全清理，最后验证",
  "steps": [
    {"id": 1, "description": "检查磁盘使用率", "tool": "disk_inspect", "params": {}, "depends_on": []},
    {"id": 2, "description": "定位大文件 (>100MB)", "tool": "disk_large_files", "params": {"min_size_mb": 100, "top_n": 5}, "depends_on": [1]},
    {"id": 3, "description": "识别大文件的性质", "tool": "file_identify", "params": {"path": "${step2.data.files[0].path}"}, "depends_on": [2], "max_retries": 2},
    {"id": 4, "description": "安全清理非关键文件", "tool": "file_truncate", "params": {"path": "${step3.data.path}"}, "depends_on": [3], "fallback_tool": "disk_cleanup"},
    {"id": 5, "description": "验证清理效果", "tool": "disk_inspect", "params": {}, "depends_on": [4]}
  ]
}
```
