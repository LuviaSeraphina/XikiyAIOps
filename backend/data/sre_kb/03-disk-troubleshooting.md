# Linux 磁盘空间不足排查指南

## 快速检查

```bash
df -h                    # 查看各分区使用率
df -i                    # 查看 inode 使用率（大量小文件也会导致磁盘满）
du -sh /* 2>/dev/null | sort -rh | head -10  # 找出根目录下最占空间的目录
```

## 排查步骤

### 1. 定位大目录
```bash
du -h --max-depth=1 /home | sort -rh    # 查看 /home 下各子目录大小
ncdu /path/to/dir                        # 交互式磁盘使用分析（推荐）
```

### 2. 定位大文件
```bash
find / -type f -size +100M -exec ls -lh {} \; 2>/dev/null | sort -k5 -rh | head -20
find / -type f -size +100M -printf '%s %p\n' 2>/dev/null | sort -rn | head -20
```

### 3. 检查已删除但未释放的文件
进程打开的文件被删除后，磁盘空间不会立即释放：
```bash
lsof | grep deleted | awk '{print $1, $2, $7}' | sort -u   # 列出所有已删除仍占用的文件
lsof +L1                                                    # 列出被删除但仍链接的文件
```

释放方法：重启占用进程或清空文件描述符：
```bash
# 清空已删除的文件内容而不杀死进程
> /proc/<PID>/fd/<FD>
# 例如 lsof 显示 PID 1234 的 fd 5 指向已删除日志：
> /proc/1234/fd/5
```

### 4. 日志文件清理
```bash
journalctl --disk-usage              # systemd 日志大小
journalctl --vacuum-size=500M        # 清理 systemd 日志到 500M
journalctl --vacuum-time=7d          # 只保留 7 天日志

# 查找大于 50M 的日志文件
find /var/log -type f -size +50M -exec ls -lh {} \;

# 安全清理日志
truncate -s 0 /var/log/large.log     # 清空文件内容（不删除文件）
logrotate -f /etc/logrotate.conf     # 强制执行日志轮转
```

### 5. 检查 inode 耗尽
大量小文件会导致 inode 耗尽（即使还有磁盘空间）：
```bash
df -i                    # 查看 inode 使用率
# 找出含大量文件的目录
for d in /*; do echo "$(find $d -xdev -type f 2>/dev/null | wc -l) $d"; done | sort -rn | head -10
```

## 常见清理方法

```bash
# 清理 apt/dnf 缓存（Debian/Ubuntu）
sudo apt clean && sudo apt autoremove
# 清理 dnf 缓存（RHEL/麒麟）
sudo dnf clean all

# 清理 Docker
docker system prune -a -f    # 删除所有未使用的镜像、容器、网络
docker volume prune -f       # 删除未使用的卷

# 清理 pip 缓存
pip cache purge

# 清理 npm 缓存
npm cache clean --force

# 清理临时文件
rm -rf /tmp/*
find /tmp -type f -mtime +7 -delete  # 删除 7 天前的临时文件

# 清理旧内核（Debian/Ubuntu）
dpkg -l | grep linux-image | awk '{print $2}' | sort -V | head -n -1 | xargs sudo apt purge -y
```

## 磁盘预警阈值

| 使用率 | 状态 | 操作 |
|--------|------|------|
| < 60% | 🟢 正常 | 无需处理 |
| 60-80% | 🟡 关注 | 检查增长趋势 |
| 80-90% | 🟠 警告 | 清理或扩容 |
| > 90% | 🔴 紧急 | 立即处理 |

磁盘使用率超过 80% 时，应在 24 小时内采取行动。