# 日志管理 (Log Management)

## journald 配置

### 持久化日志
```bash
# 创建持久化存储目录
mkdir -p /var/log/journal
systemctl restart systemd-journald
```

### journald.conf 关键配置 (/etc/systemd/journald.conf)
```
Storage=persistent          # 日志写入磁盘
SystemMaxUse=500M           # 日志最大使用量
SystemKeepFree=1G           # 为其他应用保留磁盘
SystemMaxFileSize=50M       # 单文件最大 50M
RuntimeMaxUse=200M          # 运行时最大使用量
Compress=yes                # 启用压缩
```

### 清理旧日志
```bash
# 保留最近 3 天日志
journalctl --vacuum-time=3d
# 限制日志大小不超过 500M
journalctl --vacuum-size=500M
# 保留最近 2 个日志文件
journalctl --vacuum-files=2
```

## journalctl 常用查询

```bash
# 查看指定服务日志
journalctl -u nginx -n 50
# 按时间范围查询
journalctl --since "2024-01-01" --until "2024-01-02"
# 按优先级过滤 (emerg/alert/crit/err/warning/notice/info/debug)
journalctl -p err -n 50
# 查看内核日志
journalctl -k
# 实时跟踪 (-f)
journalctl -u sshd -f
```

## logrotate 日志轮转

### 配置示例 (/etc/logrotate.d/nginx)
```
/var/log/nginx/*.log {
    daily                   # 每天轮转
    rotate 7                # 保留 7 份
    missingok               # 文件不存在不报错
    notifempty              # 空文件不轮转
    compress                # 压缩旧日志
    delaycompress           # 延迟一次压缩
    copytruncate            # 复制后截断 (不中断服务写入)
    postrotate
        /usr/sbin/nginx -s reopen >/dev/null 2>&1 || true
    endscript
}
```

### 手动轮转
```bash
# 强制执行指定配置的轮转
logrotate -f /etc/logrotate.d/nginx
# 调试模式 (不实际执行)
logrotate -d /etc/logrotate.d/nginx
```

### 轮转策略选择
- `copytruncate`: 适用于持续写入的日志 (nginx/数据库), 不丢失条目但可能截断一行
- `create`: 适用于可短暂停止写入的服务, 原子性好但需要服务支持 reopen

## 大日志文件处理

### 查找大日志
```bash
# 查找 >100MB 的日志文件
find /var/log -type f -size +100M -exec ls -lh {} \;
# 按大小排序
du -sh /var/log/* | sort -rh | head -10
```

### 安全截断大日志
```bash
# 方法1: truncate 保留 inode，不影响正在写入的进程
truncate -s 0 /var/log/nginx/access.log
# 方法2: 清空但不删除 (> vs rm)
: > /var/log/nginx/access.log
# ⚠️ 警告: 不要用 rm + touch 替换，会导致日志写入丢失
```

## 日志分析技巧

```bash
# 统计 Top 10 访问 IP
journalctl -u nginx | grep -oP '\d+\.\d+\.\d+\.\d+' | sort | uniq -c | sort -rn | head -10
# 统计错误频率
journalctl -p err --since "1 hour ago" | cut -d' ' -f5- | sort | uniq -c | sort -rn
```

## 最佳实践

1. **持久化日志**: 确保 journald 日志写入磁盘而非仅内存
2. **限制大小**: 设置 SystemMaxUse 防止磁盘被日志占满
3. **定时清理**: crontab 定时 vacuum 或 logrotate
4. **远程备份**: 关键日志发送到远程 syslog 服务器
5. **敏感信息脱敏**: logs 中避免记录密码/token/密钥
