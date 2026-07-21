# 场景: 网络连通性诊断 (H-network-diagnosis)

## 触发关键词
连不上, 网络不通, 网络异常, 网络诊断, 网络排查, ping不通, 端口不通, DNS解析

## 意图
network_diagnosis

## 策略
持续连通性 → DNS解析 → 端口监听 → 防火墙规则 → 网卡状态

## 步骤模板
```json
{
  "intent": "network_diagnosis",
  "strategy": "ping→DNS→端口→防火墙→网卡，5步定位网络问题根因",
  "steps": [
    {"id": 1, "description": "检测网络连通性", "tool": "network_ping", "params": {}, "depends_on": []},
    {"id": 2, "description": "检查DNS解析", "tool": "network_dns_check", "params": {"domain": "baidu.com"}, "depends_on": []},
    {"id": 3, "description": "查看监听端口和服务", "tool": "network_listening_ports", "params": {}, "depends_on": []},
    {"id": 4, "description": "检查TCP重传率(丢包)", "tool": "network_tcp_retrans", "params": {}, "depends_on": []},
    {"id": 5, "description": "查看网卡状态和丢包", "tool": "network_interface_stats", "params": {}, "depends_on": []}
  ]
}
```
