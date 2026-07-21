# Linux 进程管理指南

## 查看进程

```bash
ps aux                          # 所有进程详细列表
ps auxf                         # 树形显示进程关系
ps -eo pid,ppid,user,%cpu,%mem,cmd --sort=-%cpu | head -20  # 自定义格式
pstree -p                       # 进程树
pgrep -f "pattern"              # 按模式查找进程 PID
pidof <进程名>                   # 快速获取 PID
```

## 进程状态

| 状态 | 含义 |
|------|------|
| R | Running/可运行 |
| S | Sleeping（可中断睡眠） |
| D | Disk sleep（不可中断睡眠，IO 等待） |
| Z | Zombie（僵尸进程，已退出但父进程未回收） |
| T | Stopped（被暂停） |

## 僵尸进程处理

```bash
ps aux | awk '$8=="Z" {print $2, $11}'    # 找到僵尸进程
# 查看是谁的父进程
ps -o ppid= -p <僵尸PID>
# 如果父进程不回收，杀死父进程
kill <父进程PID>
# 僵尸进程会被 init (PID 1) 收养并回收
```

僵尸进程本身不消耗资源，但大量积累可能耗尽 PID 池。

## 资源限制

```bash
cat /proc/<PID>/limits                     # 查看进程的资源限制
ulimit -a                                   # 当前 shell 的资源限制
prlimit --pid <PID>                         # 查看运行中进程的限制

# 调整限制（临时）
ulimit -n 65536                              # 最大文件描述符
ulimit -u 65536                              # 最大进程数

# 永久调整 — /etc/security/limits.conf
* soft nofile 65536
* hard nofile 65536
* soft nproc 65536
* hard nproc 65536
```

## 进程优先级

```bash
nice -n 10 <命令>                           # 以较低优先级启动
renice -n -5 -p <PID>                       # 调整运行中进程的优先级
```

nice 值范围 -20（最高优先级）到 19（最低优先级），普通用户只能增加 nice 值（降低优先级）。

## 进程诊断

### strace — 系统调用跟踪
```bash
strace -p <PID>                              # 跟踪运行中的进程
strace -c -p <PID>                           # 统计系统调用频率
strace -e trace=network -p <PID>             # 只跟踪网络相关调用
strace -ff -o /tmp/trace <命令>              # 跟踪所有子进程
```

### lsof — 打开文件列表
```bash
lsof -p <PID>                                # 进程打开的所有文件
lsof -i :<端口>                               # 占用端口的进程
lsof /var/log/app.log                        # 正在使用某文件的进程
```

### /proc 文件系统
```bash
cat /proc/<PID>/cmdline | tr '\0' ' '        # 进程的完整启动命令
cat /proc/<PID>/environ | tr '\0' '\n'       # 进程环境变量
cat /proc/<PID>/cwd                          # 进程当前工作目录
ls -la /proc/<PID>/fd/                       # 进程打开的文件描述符
```

## 信号处理

| 信号 | 编号 | 效果 |
|------|------|------|
| SIGHUP | 1 | 挂起（常用于重载配置） |
| SIGINT | 2 | 中断（Ctrl+C） |
| SIGKILL | 9 | 强制终止（不可捕获） |
| SIGTERM | 15 | 优雅终止（默认 kill） |
| SIGSTOP | 19 | 暂停进程 |

```bash
kill -15 <PID>          # 优雅终止
kill -9 <PID>           # 强制终止（非必要不要用）
kill -HUP <PID>         # 重载配置
killall -15 <进程名>     # 按名称终止所有匹配进程
```
