# Linux 网络故障排查指南

## 快速检查

```bash
ip addr show                          # 查看网卡和IP
ss -tlnp                              # 查看 TCP 监听端口（比 netstat 快）
ss -s                                 # 网络统计摘要
```

## 排查步骤

### 1. 检查连通性
```bash
ping -c 4 <目标IP>                    # ICMP 连通性
traceroute <目标IP>                   # 路由追踪
mtr -r <目标IP>                       # 持续追踪 + 丢包统计
curl -sS -o /dev/null -w '%{time_total}s %{http_code}\n' <URL>  # HTTP 响应时间
```

### 2. 检查 DNS
```bash
nslookup <域名>                        # DNS 解析
dig +short <域名>                       # 简洁查询
cat /etc/resolv.conf                    # 查看 DNS 配置
```

### 3. 查看网络连接状态
```bash
ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn   # 连接状态统计
ss -tan state time-wait | wc -l        # TIME_WAIT 连接数
ss -tan state established | wc -l      # ESTABLISHED 连接数
```

TIME_WAIT 过多（>1000）表示短连接过多，需要优化内核参数。

### 4. 网络性能检查
```bash
ethtool eth0                           # 网卡速率和双工模式
sar -n DEV 1 5                         # 每秒网络流量统计
iftop -i eth0                          # 实时流量监控（类似 top）
iperf3 -s                              # 带宽测试（服务端）
iperf3 -c <服务端IP>                    # 带宽测试（客户端）
```

### 5. 网络错误诊断
```bash
ip -s link show eth0                   # 网卡错误统计（errors/dropped）
netstat -i                             # 网卡接口错误
dmesg | grep -i eth                    # 网卡驱动日志
```

## TCP 重传问题

```bash
cat /proc/net/snmp | grep Tcp          # TCP 统计（含重传）
# 查看具体连接的重传
ss -ti | grep -E 'retrans|segs_out'
```

## 防火墙排查
```bash
sudo iptables -L -n -v                 # IPv4 防火墙规则
sudo nft list ruleset                  # nftables 规则
sudo firewall-cmd --list-all           # firewalld 规则（CentOS/RHEL/麒麟）
```

## 关键内核参数优化

```bash
# 增大 TIME_WAIT 连接复用
sysctl net.ipv4.tcp_tw_reuse=1
# TCP 连接队列
sysctl net.core.somaxconn=4096
# 网络缓冲区
sysctl net.core.rmem_max=134217728
sysctl net.core.wmem_max=134217728
```
