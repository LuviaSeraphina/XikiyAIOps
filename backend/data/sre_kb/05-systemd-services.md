# systemd 服务管理指南

## 基础命令

```bash
systemctl status <服务名>              # 查看服务状态
systemctl start <服务名>               # 启动服务
systemctl stop <服务名>                # 停止服务
systemctl restart <服务名>             # 重启服务
systemctl enable <服务名>              # 开机自启
systemctl disable <服务名>             # 取消开机自启
systemctl is-active <服务名>           # 是否运行中
systemctl is-enabled <服务名>          # 是否自启
systemctl daemon-reload               # 重载 systemd 配置
```

## 排查服务故障

### 1. 查看服务日志
```bash
journalctl -u <服务名> --no-pager -n 50     # 查看最近 50 行日志
journalctl -u <服务名> -f                    # 实时跟踪日志
journalctl -u <服务名> --since "10min ago"   # 查看最近 10 分钟
journalctl -u <服务名> -p err                # 只看错误级别
```

### 2. 列出所有服务状态
```bash
systemctl list-units --type=service          # 所有服务
systemctl list-units --type=service --state=failed  # 失败的服务
systemctl list-units --type=service --state=running # 运行中的服务
```

### 3. 分析服务启动失败原因
```bash
systemctl status <服务名> -l                 # 完整输出
# 检查服务文件
systemctl cat <服务名>                       # 查看服务的 Unit 文件
```

常见的服务失败原因：
- **ExecStart 路径错误** — 二进制不存在或无执行权限
- **WorkingDirectory 不存在** — 工作目录被删除
- **User 不存在** — 指定的用户不存在
- **依赖服务未启动** — After/Requires 的条件不满足
- **端口被占用** — 服务绑定的端口已被使用

### 4. 查看服务依赖
```bash
systemctl list-dependencies <服务名>         # 列出依赖
systemctl list-dependencies <服务名> --reverse # 列出被依赖
```

## 编写 systemd 服务

```ini
[Unit]
Description=My Service Description
After=network.target
Requires=network.target

[Service]
Type=simple                      # simple | forking | oneshot | notify
User=root
WorkingDirectory=/opt/myapp
ExecStart=/usr/bin/myapp --config /etc/myapp.conf
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Type 类型说明
- **simple** — 默认，ExecStart 启动的进程即主进程
- **forking** — 父进程 fork 后退出，子进程成为主进程（适合传统守护进程）
- **oneshot** — 一次性任务，完成后退出
- **notify** — 服务启动后通过 sd_notify 通知 systemd

### Restart 策略
- **no** — 不自动重启
- **on-failure** — 异常退出时重启（推荐）
- **on-abnormal** — 信号导致退出时重启
- **always** — 总是重启

## 定时器（Timer）

systemd 定时器是 crontab 的替代方案：

```ini
# /etc/systemd/system/mytask.timer
[Unit]
Description=Run mytask daily

[Timer]
OnCalendar=daily          # 每天一次
Persistent=true           # 错过执行时间后补执行

[Install]
WantedBy=timers.target
```

查看定时器：
```bash
systemctl list-timers --all
```
