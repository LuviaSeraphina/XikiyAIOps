# 内核参数调优 (Kernel Tuning)

## sysctl 性能优化参数

### 内存管理 (vm)
```bash
# 控制 swap 倾向 (0=尽量不用swap, 100=积极使用)
# 对于数据库/缓存服务器, 建议 0~10
vm.swappiness = 10

# 脏页比例 — 达到此比例开始异步写回
vm.dirty_ratio = 15
# 后台写回触发比例
vm.dirty_background_ratio = 5

# 最小保留内存 (防止系统完全无内存可用)
# 公式: min_free_kbytes = sqrt(总内存GB) * 64 * 1024
vm.min_free_kbytes = 65536

# 内存过量分配: 0=保守, 1=允许, 2=不允许
vm.overcommit_memory = 1
vm.overcommit_ratio = 50
```

### 文件系统 (fs)
```bash
# 最大打开文件数
fs.file-max = 2097152

# inotify 用户监控数 (CI/CD/IDE 需大量监控)
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024

# aio 最大请求数 (数据库需要)
fs.aio-max-nr = 1048576
```

### 网络优化 (net)
```bash
# Socket 队列
net.core.somaxconn = 4096              # 最大监听队列长度
net.core.netdev_max_backlog = 5000     # 网络设备积压队列

# TCP 缓冲区 (调整到适合 10Gbps 网络)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# TCP 连接优化
net.ipv4.tcp_max_syn_backlog = 8192    # SYN 积压
net.ipv4.tcp_fin_timeout = 15          # FIN_WAIT 超时 (秒)
net.ipv4.tcp_tw_reuse = 1              # TIME_WAIT 复用
net.ipv4.tcp_keepalive_time = 300      # Keepalive 首次探测时间
net.ipv4.tcp_keepalive_intvl = 30      # 探测间隔
net.ipv4.tcp_keepalive_probes = 5      # 探测次数

# TCP Fast Open (3=客户端+服务端)
net.ipv4.tcp_fastopen = 3

# 启用 BBR 拥塞控制
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
```

### 内核调度 (kernel)
```bash
# 进程 PID 上限 (大量容器场景)
kernel.pid_max = 4194304

# 消息队列
kernel.msgmax = 65536
kernel.msgmnb = 65536

# 共享内存 (数据库需要)
kernel.shmmax = 68719476736      # 64GB
kernel.shmall = 16777216         # 页面数
```

## NUMA 感知

```bash
# 启用 NUMA 自动平衡 (多 socket 服务器)
kernel.numa_balancing = 1
# 限制 NUMA 迁移带宽
kernel.numa_balancing_promote_rate_limit_MBps = 100
```

## 验证调优效果

```bash
# 查看当前所有 sysctl 值
sysctl -a
# 临时设置 (重启失效)
sysctl -w vm.swappiness=10
# 永久设置
echo "vm.swappiness=10" >> /etc/sysctl.d/99-sre-tuning.conf
sysctl -p /etc/sysctl.d/99-sre-tuning.conf
```

## 不同场景调优建议

| 场景 | vm.swappiness | tcp_keepalive | somaxconn | fs.file-max |
|------|:---:|:--:|:--:|:--:|
| Web 服务器 | 10 | 120 | 4096 | 65536 |
| 数据库 | 0 | 300 | 8192 | 2097152 |
| 缓存 (Redis) | 0 | 180 | 1024 | 65536 |
| 消息队列 | 5 | 60 | 8192 | 2097152 |
| 通用服务器 | 30 | 300 | 1024 | 65536 |

## 注意事项

1. **不要盲目调优**: 先测量, 后修改, 再验证
2. **记录基线**: 修改前后对比性能指标
3. **逐项修改**: 每次只改一个参数, 方便回滚
4. **生产环境先在 staging 验证**
5. **内核版本兼容**: 某些参数仅在特定内核版本可用 (如 BBR 需 >=4.9)
