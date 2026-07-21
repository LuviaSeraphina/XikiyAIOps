# 场景: FD 文件描述符泄漏排查 (J-fd-leak)

## 触发关键词
文件句柄, FD泄漏, 打开文件太多, too many open files, ulimit

## 意图
fd_leak

## 策略
检查打开文件分布 → 定位进程 → 查看进程详情 → 系统限制检查

## 步骤模板
```json
{
  "intent": "fd_leak",
  "strategy": "打开文件分布→定位进程→进程详情→系统FD上限→判断泄漏",
  "steps": [
    {"id": 1, "description": "检查系统打开文件情况", "tool": "security_open_files", "params": {}, "depends_on": []},
    {"id": 2, "description": "查看系统整体信息", "tool": "system_info", "params": {}, "depends_on": []},
    {"id": 3, "description": "查看TOP CPU进程", "tool": "process_top_cpu", "params": {"top_n": 10}, "depends_on": []}
  ]
}
```
