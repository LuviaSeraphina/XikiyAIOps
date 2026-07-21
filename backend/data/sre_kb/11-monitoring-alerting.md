# 监控与告警 (Monitoring & Alerting)

## Prometheus Alert Rules

### 高优先级告警 (CRITICAL)
```yaml
# 节点宕机
- alert: NodeDown
  expr: up == 0
  for: 1m
  labels: { severity: critical }
  annotations:
    summary: "节点 {{ $labels.instance }} 宕机"

# 磁盘空间不足 (预测)
- alert: NodeFilesystemSpaceFillingUp
  expr: |
    node_filesystem_avail_bytes / node_filesystem_size_bytes * 100 < 15
    and predict_linear(node_filesystem_avail_bytes[6h], 4*60*60) < 0
  for: 1h
  labels: { severity: critical }
  annotations:
    summary: "磁盘 {{ $labels.mountpoint }} 预计 4h 内满"

# 内存耗尽 (OOM 风险)
- alert: NodeMemoryPressure
  expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 95
  for: 5m
  labels: { severity: critical }
```

### 中优先级告警 (WARNING)
```yaml
# CPU 高负载
- alert: NodeCPUHigh
  expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
  for: 15m
  labels: { severity: warning }

# 磁盘 Inode 不足
- alert: NodeInodePressure
  expr: node_filesystem_files_free / node_filesystem_files * 100 < 20
  for: 10m
  labels: { severity: warning }

# 网络错误率
- alert: NodeNetworkErrors
  expr: rate(node_network_receive_errors_total[5m]) > 0.01
  for: 5m
  labels: { severity: warning }
```

### 低优先级告警 (INFO)
```yaml
# 磁盘空间使用 >80%
- alert: NodeDiskSpaceHigh
  expr: node_filesystem_avail_bytes / node_filesystem_size_bytes * 100 < 20
  for: 30m
  labels: { severity: info }

# Swap 使用
- alert: NodeSwapUsage
  expr: (1 - node_memory_SwapFree_bytes / node_memory_SwapTotal_bytes) * 100 > 50
  for: 10m
  labels: { severity: info }

# 僵尸进程
- alert: NodeZombieProcesses
  expr: node_procs_blocked > 5
  for: 10m
  labels: { severity: info }
```

## 监控四大黄金信号

1. **延迟 (Latency)**: 请求处理时间 — p50/p95/p99
2. **流量 (Traffic)**: 请求速率 — QPS/RPS
3. **错误 (Errors)**: 错误率 — 5xx 百分比
4. **饱和度 (Saturation)**: 资源使用率 — CPU/内存/磁盘/网络

## USE 方法 (资源监控)

- **U**tilization: 资源使用率 (如 CPU=85%)
- **S**aturation: 资源饱和度 (如 队列长度 / run queue)
- **E**rrors: 错误计数 (如 网卡丢包 / 磁盘 I/O 错误)

## RED 方法 (服务监控)

- **R**ate: 请求速率 (请求/秒)
- **E**rrors: 错误率 (失败请求占比)
- **D**uration: 请求延迟 (响应时间分布)

## Alertmanager 配置

```yaml
route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 4h
  routes:
    - match: { severity: critical }
      receiver: 'oncall-pager'
    - match: { severity: warning }
      receiver: 'sre-slack'
receivers:
  - name: 'oncall-pager'
    webhook_configs:
      - url: 'http://xikiy-aiops:8001/api/alerts'
  - name: 'sre-slack'
    slack_configs:
      - channel: '#sre-alerts'
```

## 告警降噪策略

1. **分组**: 同类告警合并为一条通知
2. **抑制**: 高优先级抑制低优先级 (NodeDown 抑制所有该节点告警)
3. **静默**: 维护窗口期间暂停告警
4. **重复间隔**: repeat_interval 设为 4h, 避免告警风暴

## 常用 Exporter

| Exporter | 用途 |
|----------|------|
| node_exporter | 主机 CPU/内存/磁盘/网络 |
| process_exporter | 进程级别监控 |
| mysqld_exporter | MySQL 指标 |
| nginx-prometheus-exporter | Nginx 连接/请求统计 |
| blackbox_exporter | HTTP/TCP/ICMP 探活 |
