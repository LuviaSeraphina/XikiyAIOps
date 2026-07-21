# Linux 内存与 OOM 排查指南

## 内存使用指标

使用 `free -h` 查看：
- **total** — 物理内存总量
- **used** — 已使用（含 buffers/cache）
- **available** — 实际可用（内核估算，比 free 准确）
- **buff/cache** — 内核缓存，可在内存紧张时释放

关键判断：`available` 低于 10% 总内存时，系统即将 OOM。

## OOM Killer 排查

### 1. 查看 OOM 历史
```bash
dmesg | grep -i "out of memory"     # 内核日志中的 OOM 记录
dmesg | grep -i "killed process"    # 被杀的进程
journalctl -k | grep -i oom          # systemd 系统日志
```

### 2. 查看当前 OOM 评分
```bash
cat /proc/<PID>/oom_score            # 当前进程的 OOM 分数（越高越容易被杀）
cat /proc/<PID>/oom_score_adj        # 手动调整的 OOM 分数
cat /proc/<PID>/oom_adj              # 旧版 OOM 调整值（-17 表示禁止被 OOM）
```

### 3. 找出内存占用最高的进程
```bash
ps aux --sort=-%mem | head -10       # 按内存占用排序
top -b -n1 -o %MEM | head -20        # top 按内存排序
smem -rs size | head -10             # 含 PSS（实际物理内存）
```

### 4. 检查内存泄漏
```bash
# 持续监控某进程的内存增长
while true; do ps -p <PID> -o rss= >> mem.log; sleep 5; done

# 查看进程内存映射
cat /proc/<PID>/smaps | grep -E '^(Rss|Pss|Swap)'   # 详细内存使用
pmap -x <PID>                                        # 进程内存映射表
```

### 5. 检查 HugePages
```bash
cat /proc/meminfo | grep -i huge   # 大页内存使用情况
```

## 常见场景与处理

### 内存泄漏
- 应用代码未释放内存 → 使用 valgrind / heaptrack 分析
- Java 堆内存溢出 → `-XX:+HeapDumpOnOutOfMemoryError` 配置
- Python 内存增长 → `tracemalloc` 模块追踪

### Buff/Cache 过高
- 正常现象，内核会在需要时释放
- 手动释放: `echo 3 > /proc/sys/vm/drop_caches`（谨慎，影响性能）

### Swap 使用率高
```bash
# 查看 Swap 使用详情
cat /proc/swaps
swapon --show
# 找出使用 Swap 最多的进程
for f in /proc/*/status; do
  awk '/^Name:|^VmSwap:/' $f | paste - - 2>/dev/null
done | sort -k4 -nr | head -10
```

降低 swappiness:
```bash
sysctl vm.swappiness=10    # 临时
echo "vm.swappiness=10" >> /etc/sysctl.conf  # 永久
```
