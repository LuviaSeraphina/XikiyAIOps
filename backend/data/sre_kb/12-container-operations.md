# 容器运维 (Container Operations)

## Docker/Podman 故障排查

### 常见问题诊断
```bash
# 查看容器资源使用
docker stats --no-stream        # Docker
podman stats --no-stream        # Podman

# 查看容器日志 (含时间戳)
docker logs --tail 100 -t <container>
podman logs --tail 100 -t <container>

# 进入运行中的容器
docker exec -it <container> /bin/bash
podman exec -it <container> /bin/bash

# 查看容器详细信息 (环境变量/挂载/端口)
docker inspect <container>
podman inspect <container>
```

### 磁盘空间问题
```bash
# 查看 Docker 磁盘使用
docker system df
# 清理未使用的资源
docker system prune -a --volumes
# Podman 清理
podman system prune -a --volumes
# 查看 overlay2 层占用
du -sh /var/lib/docker/overlay2/
du -sh /var/lib/containers/storage/
```

### 网络故障排查
```bash
# 查看容器网络设置
docker network ls
docker network inspect bridge
# DNS 问题
docker exec <container> nslookup google.com
# 端口绑定检查
ss -tlnp | grep docker-proxy
```

## Rootless Podman (推荐生产配置)

```bash
# 启用 rootless Podman (用户级运行, 无需 root)
# 优点: 容器内的 root = 宿主机的普通用户, 安全隔离
systemctl --user enable podman.socket
systemctl --user start podman.socket
# 配置 lingering (用户注销后容器继续运行)
loginctl enable-linger $USER
```

## Quadlet 生产配置 (Podman systemd)

```ini
# ~/.config/containers/systemd/nginx.container
[Container]
Image=docker.io/library/nginx:stable
PublishPort=8080:80
Volume=/var/www/html:/usr/share/nginx/html:Z
Network=host

[Service]
Restart=always
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=default.target
```
```bash
# 加载并启动
systemctl --user daemon-reload
systemctl --user start nginx
```

## 安全最佳实践

1. **Rootless 优先**: 生产环境优先使用 rootless 容器
2. **最小镜像**: 使用 distroless 或 alpine 基础镜像, 减少攻击面
3. **只读根文件系统**: `--read-only` 标志, 需要写入的目录用 tmpfs
4. **资源限制**: 设置 MemoryMax/CPUQuota 防止资源耗尽
5. **Secret 管理**: 敏感信息通过环境变量注入, 不写在 Dockerfile
6. **体积清理**: 定期 `podman system prune` 清理悬空镜像和卷

## 常见错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `no space left on device` | overlay2 层耗尽 | `docker system prune -a` 清理 |
| `port already in use` | 端口冲突 | `ss -tlnp` 查占用, 换端口 |
| `permission denied` | SELinux 阻止 | `chcon -Rt svirt_sandbox_file_t` 或 `:Z` 标签 |
| `Cannot connect to the Docker daemon` | dockerd 未运行 | `systemctl start docker`, 检查 `DOCKER_HOST` |
| `container keeps restarting` | 应用启动失败 | `docker logs <container>` 查看原因, 检查健康检查 |
