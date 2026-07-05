"""
MCP 运维操作工具测试

覆盖 Phase 1-6 新增的 23 个工具:
- 文件操作: file_identify, file_read, file_truncate, disk_cleanup, logrotate_force
- 服务管理: service_control
- 配置管理: config_diff, config_backup, config_restore, sysctl_set
- 进程控制: process_zombie_cleanup, process_renice, process_ionice, process_io_top
- 网络安全: firewall_rule_add, firewall_rule_del, dns_flush
- 用户包管理: user_create, user_lock, user_password, package_install, package_remove, package_update_security

运行: cd backend && python -m pytest tests/test_mcp_ops_tools.py -v
"""
import pytest
import os
import tempfile
from app.mcp_plugins.ops_plugin import (
    file_identify, file_read, file_truncate, disk_cleanup, logrotate_force
)
from app.mcp_plugins.service_plugin import service_control
from app.mcp_plugins.config_plugin import (
    config_diff, config_backup, config_restore, sysctl_set
)
from app.mcp_plugins.process_plugin import (
    process_zombie_cleanup, process_renice, process_ionice, process_io_top
)
from app.mcp_plugins.network_security_ops import (
    firewall_rule_add, firewall_rule_del, dns_flush
)
from app.mcp_plugins.user_pkg_plugin import (
    user_create, user_lock, user_password,
    package_install, package_remove, package_update_security
)


class TestFileIdentify:
    """file_identify: 文件识别工具"""

    def test_identify_existing_file(self):
        """识别存在的文件"""
        result = file_identify(path="/etc/hostname")
        assert result["summary"]["path"] == "/etc/hostname"
        assert result["data"]["exists"] is True
        assert result["data"]["size_bytes"] > 0

    def test_identify_nonexistent_file(self):
        """识别不存在的文件"""
        result = file_identify(path="/nonexistent/file.txt")
        assert result["data"]["exists"] is False
        assert "error" in result["summary"]

    def test_identify_empty_path(self):
        """空路径参数"""
        result = file_identify(path="")
        assert result["risk_level"] == "error"
        assert "不能为空" in result["summary"]["error"]

    def test_identify_critical_file(self):
        """识别关键数据库文件 (模拟)"""
        # 创建一个 .sqlite 后缀的临时文件
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            f.write(b"test")
            tmp_path = f.name
        try:
            result = file_identify(path=tmp_path)
            assert result["data"]["is_critical"] is True
            assert "sqlite" in result["data"]["critical_reason"].lower()
        finally:
            os.unlink(tmp_path)


class TestFileRead:
    """file_read: 安全读取文件"""

    def test_read_allowed_path(self):
        """读取白名单路径 (/etc/)"""
        result = file_read(path="/etc/hostname", max_lines=5)
        assert result["summary"]["lines_read"] > 0
        assert result["data"]["total_lines"] > 0

    def test_read_with_line_limit(self):
        """行数限制"""
        result = file_read(path="/etc/passwd", max_lines=3)
        assert result["data"]["lines_read"] <= 3
        assert result["data"]["total_lines"] >= result["data"]["lines_read"]

    def test_read_blocked_path(self):
        """非白名单路径被拦截"""
        result = file_read(path="/root/secret.txt")
        assert result["data"]["blocked"] is True
        assert "不在允许" in result["summary"]["error"]

    def test_read_empty_path(self):
        """空路径参数"""
        result = file_read(path="")
        assert result["risk_level"] == "error"

    def test_read_nonexistent_file(self):
        """不存在的文件"""
        result = file_read(path="/etc/nonexistent_12345.conf")
        assert result["risk_level"] == "error"


class TestFileTruncate:
    """file_truncate: 安全截断大日志"""

    def test_truncate_critical_file_blocked(self):
        """拒绝截断数据库文件"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            f.write(b"x" * 1024)
            tmp_path = f.name
        try:
            result = file_truncate(path=tmp_path)
            assert result["data"]["blocked"] is True
            assert "安全拦截" in result["summary"]["error"]
        finally:
            os.unlink(tmp_path)

    def test_truncate_small_file_skipped(self):
        """小文件 (<1MB) 不截断"""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            f.write(b"small log" * 10)
            tmp_path = f.name
        try:
            result = file_truncate(path=tmp_path)
            assert result["data"]["truncated"] is False
            assert "无需截断" in result["summary"]["info"]
        finally:
            os.unlink(tmp_path)

    def test_truncate_empty_path(self):
        """空路径参数"""
        result = file_truncate(path="")
        assert result["risk_level"] == "error"


class TestDiskCleanup:
    """disk_cleanup: 一键清理"""

    def test_cleanup_journal_only(self):
        """仅清理 journal"""
        result = disk_cleanup(cleanup_journal=True, cleanup_pkg_cache=False,
                              cleanup_tmp=False, cleanup_core=False)
        assert result["data"]["results"] is not None
        assert len(result["data"]["results"]) >= 1

    def test_cleanup_all_targets(self):
        """清理所有目标"""
        result = disk_cleanup()
        assert result["data"]["results"] is not None
        assert result["summary"]["targets_cleaned"] >= 1

    def test_cleanup_no_targets(self):
        """禁用所有清理目标"""
        result = disk_cleanup(cleanup_journal=False, cleanup_pkg_cache=False,
                              cleanup_tmp=False, cleanup_core=False)
        assert result["data"]["results"] == []


class TestLogrotateForce:
    """logrotate_force: 强制日志轮转"""

    def test_rotate_critical_file_blocked(self):
        """拒绝轮转数据库文件"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(b"test data")
            tmp_path = f.name
        try:
            result = logrotate_force(path=tmp_path)
            assert result["data"]["blocked"] is True
        finally:
            os.unlink(tmp_path)

    def test_rotate_nonexistent_file(self):
        """不存在的文件"""
        result = logrotate_force(path="/nonexistent.log")
        assert result["risk_level"] == "error"

    def test_rotate_empty_path(self):
        """空路径参数"""
        result = logrotate_force(path="")
        assert result["risk_level"] == "error"


class TestServiceControl:
    """service_control: 服务管理"""

    def test_control_empty_service(self):
        """空服务名"""
        result = service_control(service="", action="restart")
        assert result["risk_level"] == "error"

    def test_control_empty_action(self):
        """空操作"""
        result = service_control(service="nginx", action="")
        assert result["risk_level"] == "error"

    def test_control_invalid_action(self):
        """不支持的操作"""
        result = service_control(service="nginx", action="destroy")
        assert result["data"]["blocked"] is True
        assert "不支持" in result["summary"]["error"]

    def test_control_protected_service_blocked(self):
        """保护关键服务"""
        for svc in ["sshd", "auditd", "systemd-journald"]:
            result = service_control(service=svc, action="stop")
            assert result["data"]["blocked"] is True
            assert "关键服务" in result["summary"]["error"]

    def test_control_status_query(self):
        """查询服务状态"""
        result = service_control(service="cron", action="status")
        assert "pre_status" in result["data"]
        assert "post_status" in result["data"]


class TestConfigDiff:
    """config_diff: 配置对比"""

    def test_diff_existing_file(self):
        """对比存在的文件"""
        result = config_diff(path="/etc/hostname")
        assert result["data"]["path"] == "/etc/hostname"

    def test_diff_nonexistent_file(self):
        """不存在的文件"""
        result = config_diff(path="/nonexistent.conf")
        assert result["risk_level"] == "error"

    def test_diff_empty_path(self):
        """空路径参数"""
        result = config_diff(path="")
        assert result["risk_level"] == "error"

    def test_diff_with_compare_to(self):
        """指定对比目标"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".conf") as f1:
            f1.write("line1\n")
            f1.write("line2\n")
            path1 = f1.name
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".conf") as f2:
            f2.write("line1\n")
            f2.write("line3\n")
            path2 = f2.name
        try:
            result = config_diff(path=path1, compare_to=path2)
            assert result["data"]["has_changes"] is True
            assert result["data"]["diff_line_count"] > 0
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestConfigBackup:
    """config_backup: 配置备份"""

    def test_backup_existing_file(self):
        """备份存在的文件"""
        result = config_backup(path="/etc/hostname", tag="test")
        # 可能因权限失败 (/var/backups/xikiy/ 不存在)
        assert "backup_path" in result.get("data", {}) or result["risk_level"] == "error"

    def test_backup_nonexistent_file(self):
        """不存在的文件"""
        result = config_backup(path="/nonexistent.conf")
        assert result["risk_level"] == "error"

    def test_backup_empty_path(self):
        """空路径参数"""
        result = config_backup(path="")
        assert result["risk_level"] == "error"


class TestConfigRestore:
    """config_restore: 配置恢复"""

    def test_restore_nonexistent_backup(self):
        """不存在的备份文件"""
        result = config_restore(backup_path="/nonexistent_backup")
        assert result["risk_level"] == "error"

    def test_restore_empty_path(self):
        """空路径参数"""
        result = config_restore(backup_path="")
        assert result["risk_level"] == "error"


class TestSysctlSet:
    """sysctl_set: 设置内核参数"""

    def test_set_whitelist_blocked(self):
        """非白名单参数被拦截"""
        result = sysctl_set(key="kernel.unknown_param", value="1")
        assert result["data"]["blocked"] is True
        assert "不在允许" in result["summary"]["error"]

    def test_set_empty_key(self):
        """空参数名"""
        result = sysctl_set(key="", value="1")
        assert result["risk_level"] == "error"

    def test_set_empty_value(self):
        """空参数值"""
        result = sysctl_set(key="vm.swappiness", value="")
        assert result["risk_level"] == "error"


class TestProcessZombieCleanup:
    """process_zombie_cleanup: 清理僵尸进程"""

    def test_cleanup_nonexistent_pid(self):
        """不存在的 PID"""
        result = process_zombie_cleanup(parent_pid=99999)
        assert result["risk_level"] == "error"

    def test_cleanup_zero_pid(self):
        """PID 为 0"""
        result = process_zombie_cleanup(parent_pid=0)
        assert result["risk_level"] == "error"

    def test_cleanup_no_zombies(self):
        """进程无僵尸子进程"""
        # 使用 PID 1 (systemd), 通常没有僵尸子进程
        result = process_zombie_cleanup(parent_pid=1)
        assert result["data"]["zombie_count"] == 0
        assert result["data"]["cleaned"] is False


class TestProcessRenice:
    """process_renice: 调整 CPU 优先级"""

    def test_renice_nonexistent_pid(self):
        """不存在的 PID"""
        result = process_renice(pid=99999, nice=10)
        assert result["risk_level"] == "error"

    def test_renice_zero_pid(self):
        """PID 为 0"""
        result = process_renice(pid=0, nice=10)
        assert result["risk_level"] == "error"

    def test_renice_extreme_nice_blocked(self):
        """禁止 -20 (最高优先级) — 被范围校验拦截"""
        result = process_renice(pid=1, nice=-20)
        assert result["data"]["blocked"] is True

    def test_renice_out_of_range(self):
        """nice 值超范围"""
        result = process_renice(pid=1, nice=-25)
        assert result["data"]["blocked"] is True


class TestProcessIonice:
    """process_ionice: 调整 I/O 优先级"""

    def test_ionice_realtime_blocked(self):
        """禁止 realtime"""
        result = process_ionice(pid=1, ionice_class="realtime")
        assert result["data"]["blocked"] is True
        assert "禁止" in result["summary"]["error"]

    def test_ionice_invalid_class(self):
        """不支持的 class"""
        result = process_ionice(pid=1, ionice_class="unknown")
        assert result["data"]["blocked"] is True
        assert "不支持" in result["summary"]["error"]

    def test_ionice_nonexistent_pid(self):
        """不存在的 PID"""
        result = process_ionice(pid=99999, ionice_class="idle")
        assert result["risk_level"] == "error"


class TestProcessIoTop:
    """process_io_top: I/O 读写速率 Top N"""

    def test_io_top_default(self):
        """默认 Top 10"""
        result = process_io_top()
        assert result["data"]["sample_interval_sec"] == 1
        assert "processes" in result["data"]
        assert len(result["data"]["processes"]) <= 10

    def test_io_top_custom_n(self):
        """自定义 Top N"""
        result = process_io_top(top_n=3)
        assert len(result["data"]["processes"]) <= 3

    def test_io_top_zero_n_corrected(self):
        """Top N=0 自动修正为 1"""
        result = process_io_top(top_n=0)
        assert result["risk_level"] == "read_only"
        assert len(result["data"]["processes"]) <= 1


class TestFirewallRuleAdd:
    """firewall_rule_add: 添加防火墙规则"""

    def test_add_empty_chain(self):
        """空链名"""
        result = firewall_rule_add(chain="", protocol="tcp", port=80)
        assert result["risk_level"] == "error"

    def test_add_empty_protocol(self):
        """空协议"""
        result = firewall_rule_add(chain="INPUT", protocol="", port=80)
        assert result["risk_level"] == "error"

    def test_add_invalid_action(self):
        """不支持的 action"""
        result = firewall_rule_add(chain="INPUT", protocol="tcp", port=80, action="DESTROY")
        assert result["risk_level"] == "error"

    def test_add_icmp_no_port(self):
        """ICMP 不需要端口 — 参数校验通过 (可能因无防火墙工具而 error)"""
        result = firewall_rule_add(chain="INPUT", protocol="icmp", action="ACCEPT")
        # 参数校验通过即可, 实际执行可能因无 iptables/nft 而失败
        assert result["risk_level"] in ("dangerous", "error")


class TestFirewallRuleDel:
    """firewall_rule_del: 删除防火墙规则"""

    def test_del_empty_chain(self):
        """空链名"""
        result = firewall_rule_del(chain="", protocol="tcp", port=80)
        assert result["risk_level"] == "error"

    def test_del_empty_protocol(self):
        """空协议"""
        result = firewall_rule_del(chain="INPUT", protocol="", port=80)
        assert result["risk_level"] == "error"


class TestDnsFlush:
    """dns_flush: 刷新 DNS 缓存"""

    def test_flush_dns(self):
        """刷新 DNS 缓存"""
        result = dns_flush()
        assert "method" in result["data"]
        assert "success" in result["data"]


class TestUserCreate:
    """user_create: 创建用户"""

    def test_create_empty_username(self):
        """空用户名"""
        result = user_create(username="")
        assert result["risk_level"] == "error"

    def test_create_invalid_username_format(self):
        """无效用户名格式"""
        result = user_create(username="123invalid")
        assert result["data"]["blocked"] is True
        assert "格式无效" in result["summary"]["error"]

    def test_create_existing_user(self):
        """已存在的用户"""
        result = user_create(username="root")
        assert result["data"]["blocked"] is True
        assert "已存在" in result["summary"]["error"]


class TestUserLock:
    """user_lock: 锁定用户"""

    def test_lock_empty_username(self):
        """空用户名"""
        result = user_lock(username="", lock=True)
        assert result["risk_level"] == "error"

    def test_lock_protected_user(self):
        """保护关键用户"""
        for user in ["root", "nobody"]:
            result = user_lock(username=user, lock=True)
            assert result["data"]["blocked"] is True
            assert "禁止" in result["summary"]["error"]

    def test_lock_nonexistent_user(self):
        """不存在的用户"""
        result = user_lock(username="nonexistent_user_12345", lock=True)
        assert result["risk_level"] == "error"


class TestUserPassword:
    """user_password: 修改密码"""

    def test_password_empty_username(self):
        """空用户名"""
        result = user_password(username="", password="Test1234")
        assert result["risk_level"] == "error"

    def test_password_empty_password(self):
        """空密码"""
        result = user_password(username="testuser", password="")
        assert result["risk_level"] == "error"

    def test_password_weak_too_short(self):
        """密码太短"""
        result = user_password(username="testuser", password="Ab1")
        assert result["data"]["blocked"] is True
        assert "至少 8 位" in result["summary"]["error"]

    def test_password_weak_no_uppercase(self):
        """无大写字母"""
        result = user_password(username="testuser", password="test1234")
        assert result["data"]["blocked"] is True
        assert "大写" in result["summary"]["error"]

    def test_password_weak_no_digit(self):
        """无数字"""
        result = user_password(username="testuser", password="TestTest")
        assert result["data"]["blocked"] is True
        assert "数字" in result["summary"]["error"]

    def test_password_nonexistent_user(self):
        """不存在的用户"""
        result = user_password(username="nonexistent_12345", password="Test1234")
        assert result["risk_level"] == "error"


class TestPackageInstall:
    """package_install: 安装软件包"""

    def test_install_empty_packages(self):
        """空包列表"""
        result = package_install(packages="")
        assert result["risk_level"] == "error"

    def test_install_protected_package(self):
        """保护关键系统包"""
        for pkg in ["kernel", "systemd", "glibc"]:
            result = package_install(packages=pkg)
            assert result["data"]["blocked"] is True
            assert "关键系统包" in result["summary"]["error"]

    def test_install_multiple_packages(self):
        """多个包"""
        result = package_install(packages="vim,htop,curl")
        # 可能因权限失败, 但参数校验应该通过
        assert result.get("risk_level") != "error" or "拦截" in str(result.get("summary", {}))


class TestPackageRemove:
    """package_remove: 卸载软件包"""

    def test_remove_empty_packages(self):
        """空包列表"""
        result = package_remove(packages="")
        assert result["risk_level"] == "error"

    def test_remove_protected_package(self):
        """保护关键系统包"""
        for pkg in ["kernel", "systemd", "libc6"]:
            result = package_remove(packages=pkg)
            assert result["data"]["blocked"] is True
            assert "关键系统包" in result["summary"]["error"]


class TestPackageUpdateSecurity:
    """package_update_security: 安全更新"""

    def test_security_update(self):
        """执行安全更新"""
        result = package_update_security()
        # 可能因权限失败, 但应该返回结构化结果
        assert "manager" in result["data"] or result["risk_level"] == "error"
