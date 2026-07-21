# Linux 性能调优速查

## 性能瓶颈快速定位

| 现象 | 查看命令 | 可能原因 |
|------|---------|---------|
| 负载高但 CPU 空闲 | `top`, `iostat` | IO 瓶颈（进程在 D 状态） |
| CPU %wa 高 | `iostat -x 1` | 磁盘 IO 瓶颈 |
| CPU %sy 高 | `vmstat 1`, `perf top` | 内核态消耗：系统调用、上下文切换 |
| 内存 available 低 | `free -h` | 内存不足，即将 OOM |
| Swap 使用增长 | `vmstat 1` 的 si/so 列 | 内存不足触发交换 |
| 网络丢包 | `netstat -s`, `ip -s link` | 网卡错误或缓冲区不足 |

## CPU 调优

```bash
# 查看 CPU 信息
lscpu                     # CPU 架构和特性
cat /proc/cpuinfo | grep "model name" | head -1

# 设置 CPU 调度器
echo "performance" > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# 可选: performance | powersave | ondemand | schedutil

# 中断绑核（把网卡中断绑定到特定 CPU）
cat /proc/interrupts                    # 查看中断分布
echo 2 > /proc/irq/<IRQ号>/smp_affinity # 绑定到 CPU1
```

## 内存调优

```bash
# vm.swappiness — 控制换出倾向 (0-100, 越低越少使用 Swap)
sysctl vm.swappiness=10

# vm.vfs_cache_pressure — 控制内核回收 dentry/inode 缓存的倾向
sysctl vm.vfs_cache_pressure=50   # 默认 100, 小于 100 减少回收

# 透明大页 — 推荐 always 用于数据库
echo always > /sys/kernel/mm/transparent_hugepage/enabled
# 或 madvise — 应用按需使用
```

## 磁盘 IO 调优

```bash
# IO 调度器
cat /sys/block/sda/queue/scheduler         # 查看当前调度器
echo mq-deadline > /sys/block/sda/queue/scheduler
# 可选: none (NVMe推荐) | mq-deadline (HDD推荐) | kyber | bfq

# 读取预读大小（KB）
blockdev --getra /dev/sda                   # 查看
blockdev --setra 4096 /dev/sda              # 设置 4MB 预读

# 文件系统挂载选项
# /etc/fstab 中:
# noatime — 不记录访问时间（减少写操作）
# data=ordered — ext4 数据安全模式
```

## 内核参数速查

```bash
# TCP 调优
net.core.somaxconn=4096                     # 监听队列
net.ipv4.tcp_tw_reuse=1                     # TIME_WAIT 复用
net.ipv4.tcp_fin_timeout=15                 # FIN_WAIT2 超时
net.ipv4.tcp_max_syn_backlog=8192           # SYN 队列
net.ipv4.tcp_keepalive_time=300             # Keepalive 时间

# 文件系统
fs.file-max=655360                          # 系统全局最大文件句柄数
fs.inotify.max_user_watches=524288          # inotify 监控数量

# 内核
kernel.pid_max=4194304                      # 最大 PID
vm.max_map_count=262144                     # 进程最大内存映射数
```

## 性能监控工具速查

| 工具 | 用途 | 命令示例 |
|------|------|---------|
| `top` / `htop` | 实时进程和资源 | `htop` |
| `vmstat` | 虚拟内存统计 | `vmstat 1` |
| `iostat` | 磁盘 IO 统计 | `iostat -x 1` |
| `sar` | 历史性能数据 | `sar -u -r -n DEV 1 10` |
| `pidstat` | 进程级性能 | `pidstat -u -r -d 1` |
| `mpstat` | CPU 统计 | `mpstat -P ALL 1` |
| `dstat` | 综合指标 | `dstat -c -d -m -n` |
| `perf` | 性能分析 | `perf top`, `perf stat` |
| `bpftrace` | eBPF 动态追踪 | `bpftrace -e 'k:vfs_read { @[comm] = count(); }'` |

## 快速诊断清单

当系统响应变慢时，依次检查：
1. `uptime` — 负载是否超过 CPU 核心数
2. `dmesg | tail` — 内核是否有 OOM/错误
3. `vmstat 1` — CPU、内存、IO、交换活动
4. `iostat -x 1` — 磁盘 IO 是否饱和
5. `free -h` — 内存 available 是否充足
6. `ss -s` — 网络连接是否异常
7. `top -bn1 | head -20` — 最消耗资源的进程
