# Linux CPU 高负载排查指南

## 判断 CPU 负载类型

使用 `top` 命令查看 CPU 使用分布：
- **%us (user)** — 用户态进程消耗 CPU。过高说明应用程序计算密集
- **%sy (system)** — 内核态消耗 CPU。过高说明大量系统调用或内核操作
- **%wa (iowait)** — CPU 等待 IO 完成。过高说明磁盘 IO 瓶颈
- **%id (idle)** — CPU 空闲。低于 20% 需要关注
- **%hi/%si** — 硬中断/软中断。过高说明网络或外设中断频繁

## 排查步骤

### 1. 快速查看整体负载
```bash
top -bn1 | head -20    # 批量模式查看一次
uptime                  # 查看 1/5/15 分钟平均负载
```

负载值 > CPU 核心数 = 系统过载。例如 8 核机器，load average > 8 表示过载。

### 2. 找出 CPU 占用最高的进程
```bash
ps aux --sort=-%cpu | head -10    # 按 CPU 排序
top -b -n1 -o %CPU | head -20     # top 按 CPU 排序
```

### 3. 分析进程内部线程
```bash
top -H -p <PID>          # 查看指定进程的所有线程
ps -Lf -p <PID>          # 列出线程
```

### 4. 检查 IO 等待
```bash
iostat -x 1 5            # 查看磁盘 IO 详情（%util 接近 100% = 磁盘瓶颈）
iotop -o                 # 查看 IO 最高的进程
```

### 5. 分析 CPU 上下文切换
```bash
vmstat 1 5               # cs 列 = 上下文切换次数/秒，过高（>10万）需要关注
pidstat -w -p <PID> 1    # 查看指定进程的上下文切换
```

### 6. 使用 perf 深入分析
```bash
perf top                  # 实时查看热点函数
perf record -p <PID> -g sleep 30 && perf report  # 记录 30 秒后分析
```

## 常见场景与处理

### CPU %wa 高（IO 等待）
- 磁盘性能瓶颈 → 升级 SSD，或迁移数据到更快存储
- 大量日志写入 → 减少日志级别，使用 logrotate
- 检查是否有进程频繁 fsync: `strace -e trace=fsync -p <PID>`

### CPU %sy 高（内核态）
- 大量系统调用 → `strace -c -p <PID>` 统计调用频率
- 上下文切换过多 → 减少线程数，增大线程池
- 网络中断 → 检查网卡队列: `ethtool -l eth0`

### CPU %us 高（用户态）
- 应用代码死循环或计算密集 → 使用 profiling 工具
- Java/Python 程序 → 使用 jstack/py-spy 查看线程状态
- Node.js → 使用 `node --inspect` 或 clinic.js
