# Linux 安全加固 (SRE Security Hardening)

## SSH 加固

### 基本配置 (/etc/ssh/sshd_config)
```
# 禁用 root 登录
PermitRootLogin no
# 仅允许密钥认证
PasswordAuthentication no
PubkeyAuthentication yes
# 限制认证时限
LoginGraceTime 60
# 限制最大会话数
MaxSessions 5
# 限制并发未认证连接
MaxStartups 10:30:60
```

### 白名单用户
```bash
# 仅允许特定用户通过 SSH 登录
echo "AllowUsers admin sre-operator" >> /etc/ssh/sshd_config
systemctl restart sshd
```

### SSH 加密算法加固
```
# 禁用弱加密算法
Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com
KexAlgorithms curve25519-sha256,diffie-hellman-group16-sha512
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
```

### 换端口 + Fail2Ban
```bash
# 修改 SSH 默认端口 (避免自动扫描)
sed -i 's/#Port 22/Port 2200/' /etc/ssh/sshd_config
# fail2ban 配置
cat > /etc/fail2ban/jail.local << EOF
[sshd]
enabled = true
port = 2200
maxretry = 3
bantime = 3600
findtime = 600
EOF
```

## 内核安全参数 (sysctl)

```bash
# 网络层安全
net.ipv4.tcp_syncookies = 1          # SYN flood 防护
net.ipv4.conf.all.rp_filter = 1      # 反 IP 欺骗
net.ipv4.conf.all.accept_source_route = 0  # 禁用源路由
net.ipv4.conf.all.accept_redirects = 0     # 禁用 ICMP 重定向
net.ipv4.icmp_echo_ignore_broadcasts = 1   # 禁用广播 ping
net.ipv6.conf.all.accept_redirects = 0

# 内核安全
kernel.randomize_va_space = 2        # 完整 ASLR
kernel.kptr_restrict = 2             # 内核指针隐藏
kernel.dmesg_restrict = 1            # 限制 dmesg 访问
kernel.perf_event_paranoid = 2       # 限制性能事件访问
fs.protected_symlinks = 1            # 防止符号链接攻击
fs.protected_hardlinks = 1           # 防止硬链接攻击
```

## iptables/nftables 防火墙基线

```bash
# iptables 默认策略
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT
# 允许已建立连接
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
# 允许本地回环
iptables -A INPUT -i lo -j ACCEPT
# 允许 SSH (端口 2200)
iptables -A INPUT -p tcp --dport 2200 -j ACCEPT
# 速率限制 ICMP
iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/s -j ACCEPT
```

## 用户权限审计

```bash
# 检查空密码用户
awk -F: '($2 == "" || $2 == "!") && $3 >= 1000' /etc/shadow
# 检查 UID=0 用户 (非 root)
awk -F: '($3 == 0 && $1 != "root")' /etc/passwd
# 检查无密码 sudo 用户
grep -r "NOPASSWD" /etc/sudoers /etc/sudoers.d/
```

## SELinux/AppArmor

```bash
# 检查 SELinux 状态
getenforce
# 临时切换到 permissive (排错用)
setenforce 0
# 永久启用
sed -i 's/SELINUX=disabled/SELINUX=enforcing/' /etc/selinux/config
# AppArmor 状态
aa-status
```

## 最佳实践总结

1. **最小权限**: 每个服务使用专用用户运行, 避免 root
2. **端口最小化**: 仅暴露必要的端口, 使用 iptables/nftables 严格限制
3. **定期审计**: crontab 定时检查 SUID 文件、异常用户、SSH 登录失败
4. **补丁管理**: 通过 apt update && apt upgrade --only-upgrade 仅安装安全更新
5. **日志外发**: 关键日志 (auth.log/syslog) 发送到远程 syslog 服务器, 防止被篡改
