# 备份与恢复策略 (Backup & Recovery)

## 分层备份策略

### 第 1 层: 配置文件备份
```bash
# 备份关键配置目录
tar -czf /var/backups/etc-backup-$(date +%Y%m%d).tar.gz /etc/
# 使用 etckeeper 自动版本控制
apt install etckeeper
etckeeper init
```

### 第 2 层: 数据库备份
```bash
# MySQL/MariaDB 逻辑备份
mysqldump --all-databases --single-transaction | gzip > /var/backups/mysql-all-$(date +%Y%m%d).sql.gz
# PostgreSQL 逻辑备份
pg_dumpall | gzip > /var/backups/pgsql-all-$(date +%Y%m%d).sql.gz
```

### 第 3 层: 文件系统快照
```bash
# LVM 快照
lvcreate -L 10G -s -n snap-root /dev/vg0/root
# 挂载快照备份
mount /dev/vg0/snap-root /mnt/snap
tar -czf /backup/root-snapshot.tar.gz -C /mnt/snap .
umount /mnt/snap
lvremove -f /dev/vg0/snap-root
```

## 恢复测试流程

### 全量恢复验证
```bash
# 1. 准备临时环境 (容器/KVM)
# 2. 恢复配置文件
tar -xzf /backup/etc-backup-YYYYMMDD.tar.gz -C /tmp/restore/
# 3. 恢复数据库
gunzip < mysql-all-YYYYMMDD.sql.gz | mysql -h 127.0.0.1 -u restore_user
# 4. 应用健康检查
curl -s http://localhost/health
# 5. 验证关键数据完整性
mysql -e "SELECT COUNT(*) FROM critical_table;"
```

### 增量备份策略
```bash
# rsync 增量同步到远程
rsync -avz --delete /var/backups/ backup-server:/backups/$(hostname)/
# rsnapshot 时间点快照 (基于 rsync+硬链接)
rsnapshot daily    # 保留 7 天
rsnapshot weekly   # 保留 4 周
rsnapshot monthly  # 保留 6 月
```

## 备份 3-2-1 原则

1. **3 份**数据副本 (原始 + 2 份备份)
2. **2 种**不同存储介质 (本地磁盘 + 远程/云)
3. **1 份**异地备份 (不同物理位置)

## RTO/RPO 定义

- **RTO** (Recovery Time Objective): 恢复时间目标 — 从故障到服务恢复的最大可接受时间
  - 核心数据库: < 1 小时
  - Web 服务: < 4 小时
  - 分析系统: < 24 小时
- **RPO** (Recovery Point Objective): 恢复点目标 — 可接受的最大数据丢失时间
  - 交易数据库: < 5 分钟
  - 日志系统: < 1 小时
  - 归档数据: < 24 小时

## 备份完整性验证

```bash
# 校验备份文件 checksum
sha256sum /var/backups/*.tar.gz > /var/backups/checksums.txt
# 定期验证
sha256sum -c /var/backups/checksums.txt
# 每周测试恢复一个随机备份到沙箱环境
```

## 灾难恢复清单

1. **独立存储恢复手册**: 恢复 runbook 不能存在要恢复的系统上
2. **优先恢复顺序**: 网络 → 数据库 → 应用 → 前端
3. **DNS 切换预案**: 预先准备 TTL 降低和 DNS 切换步骤
4. **通讯计划**: 故障期间团队通讯方式 (不依赖公司内网)
5. **年度恢复演练**: 每年至少一次全流程恢复演练
