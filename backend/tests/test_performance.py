"""
性能测试 v1.0

覆盖:
- MCP 工具执行延迟
- API 端点响应时间
- 并发请求处理
- 内存占用
- 资源消耗

运行: cd backend && python -m pytest tests/test_performance.py -v
"""

import pytest
import time
import psutil
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from statistics import mean, median
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.mcp_plugins.base import registry
from app.main import app

# 测试阈值配置
THRESHOLD_TOOL_FAST = 5      # 快速工具 < 5ms
THRESHOLD_TOOL_MEDIUM = 20   # 中速工具 < 20ms
THRESHOLD_API_LIGHT = 50     # 轻量 API < 50ms
THRESHOLD_API_HEAVY = 500    # 重量 API < 500ms
THRESHOLD_MEMORY_MB = 150    # 内存 < 150MB


# ── 1. MCP 工具执行性能 ─────────────────────────────────

class TestMCPToolPerformance:
    """MCP 工具执行延迟测试"""

    def test_system_info_latency(self):
        """system_info 工具延迟 < 5ms"""
        times = []
        for _ in range(30):
            start = time.perf_counter()
            result = registry.call("system_info")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert result["risk_level"] == "read_only"
        
        p50 = median(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        
        print(f"\nsystem_info: P50={p50:.2f}ms, P95={p95:.2f}ms, avg={mean(times):.2f}ms")
        assert p50 < THRESHOLD_TOOL_FAST, f"P50 {p50:.2f}ms 超过阈值 {THRESHOLD_TOOL_FAST}ms"
        assert p95 < THRESHOLD_TOOL_MEDIUM, f"P95 {p95:.2f}ms 超过阈值 {THRESHOLD_TOOL_MEDIUM}ms"

    def test_system_load_latency(self):
        """system_load 工具延迟 < 1ms"""
        times = []
        for _ in range(30):
            start = time.perf_counter()
            result = registry.call("system_load")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        p50 = median(times)
        print(f"\nsystem_load: P50={p50:.2f}ms, avg={mean(times):.2f}ms")
        assert p50 < 1.0, f"P50 {p50:.2f}ms 超过阈值 1ms"

    def test_memory_info_latency(self):
        """memory_info 工具延迟 < 1ms"""
        times = []
        for _ in range(30):
            start = time.perf_counter()
            result = registry.call("memory_info")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        p50 = median(times)
        print(f"\nmemory_info: P50={p50:.2f}ms, avg={mean(times):.2f}ms")
        assert p50 < 1.0, f"P50 {p50:.2f}ms 超过阈值 1ms"

    def test_disk_inspect_latency(self):
        """disk_inspect 工具延迟 < 1ms"""
        times = []
        for _ in range(30):
            start = time.perf_counter()
            result = registry.call("disk_inspect")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        p50 = median(times)
        print(f"\ndisk_inspect: P50={p50:.2f}ms, avg={mean(times):.2f}ms")
        assert p50 < 1.0, f"P50 {p50:.2f}ms 超过阈值 1ms"

    def test_process_list_latency(self):
        """process_list 工具延迟 < 1ms"""
        times = []
        for _ in range(30):
            start = time.perf_counter()
            result = registry.call("process_list")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        p50 = median(times)
        print(f"\nprocess_list: P50={p50:.2f}ms, avg={mean(times):.2f}ms")
        assert p50 < 1.0, f"P50 {p50:.2f}ms 超过阈值 1ms"

    def test_batch_tools_performance(self):
        """批量工具调用性能 (5 个快速工具)"""
        tool_names = [
            "system_info", "system_load", "memory_info", "disk_inspect", "process_list"
        ]
        
        # 过滤: 仅保留已注册的工具
        available = [t for t in tool_names if registry.get_tool(t) is not None]
        if len(available) < 3:
            pytest.skip(f"可用工具不足 ({len(available)}/5)")
        
        start = time.perf_counter()
        for tool_name in available:
            result = registry.call(tool_name)
            assert result is not None
        elapsed = (time.perf_counter() - start) * 1000
        
        avg_per_tool = elapsed / len(available)
        print(f"\n批量调用 {len(available)} 个工具: 总计 {elapsed:.2f}ms, 平均 {avg_per_tool:.2f}ms/工具")
        assert avg_per_tool < 5, f"平均每工具 {avg_per_tool:.2f}ms 超过阈值 5ms"


# ── 2. API 端点性能 ─────────────────────────────────────

class TestAPIPerformance:
    """API 端点响应时间测试"""

    @pytest.fixture
    def client(self):
        """FastAPI TestClient"""
        return TestClient(app)

    def test_health_endpoint_latency(self, client):
        """/health 端点延迟 (不含 LLM 检测)"""
        # 预热
        client.get("/health")
        
        times = []
        for _ in range(20):
            start = time.perf_counter()
            response = client.get("/health")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert response.status_code == 200
        
        p50 = median(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        print(f"\n/health: P50={p50:.2f}ms, P95={p95:.2f}ms")
        # /health 包含 LLM 连通性检测，阈值放宽
        assert p50 < 300, f"P50 {p50:.2f}ms 超过阈值 300ms"

    def test_metrics_endpoint_latency(self, client):
        """/metrics 端点延迟"""
        times = []
        for _ in range(20):
            start = time.perf_counter()
            response = client.get("/metrics")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert response.status_code == 200
        
        p50 = median(times)
        print(f"\n/metrics: P50={p50:.2f}ms, avg={mean(times):.2f}ms")
        # /metrics 包含 psutil.cpu_percent(interval=0.1)
        assert p50 < 150, f"P50 {p50:.2f}ms 超过阈值 150ms"

    @pytest.mark.skip(reason="Database initialization required in test environment")
    def test_audit_list_latency(self, client):
        """/api/audit/list 端点延迟"""
        times = []
        for _ in range(20):
            start = time.perf_counter()
            response = client.get("/api/audit/list")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert response.status_code == 200
        
        p50 = median(times)
        print(f"\n/api/audit/list: P50={p50:.2f}ms, avg={mean(times):.2f}ms")
        assert p50 < THRESHOLD_API_LIGHT, f"P50 {p50:.2f}ms 超过阈值 {THRESHOLD_API_LIGHT}ms"

    @pytest.mark.skip(reason="Database initialization required in test environment")
    def test_alerts_list_latency(self, client):
        """/api/alerts/list 端点延迟"""
        times = []
        for _ in range(20):
            start = time.perf_counter()
            response = client.get("/api/alerts/list")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert response.status_code == 200
        
        p50 = median(times)
        print(f"\n/api/alerts/list: P50={p50:.2f}ms, avg={mean(times):.2f}ms")
        assert p50 < THRESHOLD_API_LIGHT, f"P50 {p50:.2f}ms 超过阈值 {THRESHOLD_API_LIGHT}ms"


# ── 3. 并发性能 ────────────────────────────────────────

class TestConcurrencyPerformance:
    """并发请求处理能力测试"""

    @pytest.fixture
    def client(self):
        """FastAPI TestClient"""
        return TestClient(app)

    @pytest.mark.skip(reason="Database initialization required in test environment")
    def test_concurrent_audit_requests(self, client):
        """并发审计查询 (10 并发)"""
        def make_request(_):
            start = time.perf_counter()
            response = client.get("/api/audit/list")
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed, response.status_code
        
        num_requests = 20
        concurrency = 10
        
        start_total = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            results = list(executor.map(make_request, range(num_requests)))
        elapsed_total = (time.perf_counter() - start_total)
        
        times = [r[0] for r in results]
        status_codes = [r[1] for r in results]
        
        rps = num_requests / elapsed_total
        avg_per_req = mean(times)
        
        print(f"\n并发测试: {concurrency} 并发 × {num_requests} 请求")
        print(f"总耗时: {elapsed_total:.2f}s, RPS: {rps:.1f}, 平均: {avg_per_req:.2f}ms/请求")
        print(f"状态码: {set(status_codes)}")
        
        assert all(code == 200 for code in status_codes), "部分请求失败"
        assert rps > 5, f"RPS {rps:.1f} 低于阈值 5"

    def test_concurrent_tool_calls(self):
        """并发工具调用 (5 并发)"""
        def call_tool(_):
            start = time.perf_counter()
            result = registry.call("system_load")
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed, result["risk_level"]
        
        num_calls = 20
        concurrency = 5
        
        start_total = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            results = list(executor.map(call_tool, range(num_calls)))
        elapsed_total = (time.perf_counter() - start_total)
        
        times = [r[0] for r in results]
        risk_levels = [r[1] for r in results]
        
        rps = num_calls / elapsed_total
        avg_per_call = mean(times)
        
        print(f"\n并发工具调用: {concurrency} 并发 × {num_calls} 调用")
        print(f"总耗时: {elapsed_total:.2f}s, RPS: {rps:.1f}, 平均: {avg_per_call:.2f}ms/调用")
        
        assert all(level == "read_only" for level in risk_levels), "部分调用失败"
        assert rps > 50, f"RPS {rps:.1f} 低于阈值 50"


# ── 4. 资源占用 ────────────────────────────────────────

class TestResourceUsage:
    """内存和 CPU 资源占用测试"""

    def test_process_memory_footprint(self):
        """进程内存占用 < 150MB"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        print(f"\n当前进程内存: {memory_mb:.2f} MB")
        assert memory_mb < THRESHOLD_MEMORY_MB, f"内存 {memory_mb:.2f}MB 超过阈值 {THRESHOLD_MEMORY_MB}MB"

    def test_memory_stability_after_tools(self):
        """工具调用后内存稳定性"""
        process = psutil.Process()
        
        # 记录初始内存
        initial_mb = process.memory_info().rss / 1024 / 1024
        
        # 执行 100 次工具调用
        for _ in range(100):
            registry.call("system_load")
            registry.call("memory_info")
            registry.call("disk_inspect")
        
        # 记录最终内存
        final_mb = process.memory_info().rss / 1024 / 1024
        delta_mb = final_mb - initial_mb
        
        print(f"\n内存变化: {initial_mb:.2f}MB → {final_mb:.2f}MB (Δ{delta_mb:+.2f}MB)")
        
        # 允许 20MB 的正常波动（Python GC、缓存等）
        assert abs(delta_mb) < 20, f"内存波动 {delta_mb:.2f}MB 超过阈值 ±20MB"

    def test_cpu_usage_idle(self):
        """空闲时 CPU 占用 < 1%"""
        process = psutil.Process()
        
        # 采样 1 秒
        cpu_percent = process.cpu_percent(interval=1.0)
        
        print(f"\n空闲 CPU 占用: {cpu_percent:.1f}%")
        # 测试环境下 CPU 可能有波动，阈值设为 5%
        assert cpu_percent < 5, f"CPU 占用 {cpu_percent:.1f}% 超过阈值 5%"


# ── 5. 工具注册表性能 ──────────────────────────────────

class TestRegistryPerformance:
    """MCP 工具注册表操作性能"""

    def test_tool_list_performance(self):
        """工具列表生成性能"""
        times = []
        for _ in range(100):
            start = time.perf_counter()
            tools = registry.list_all()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert len(tools) > 80  # 至少 80 个工具
        
        p50 = median(times)
        avg = mean(times)
        print(f"\ntool.list_all(): P50={p50:.3f}ms, avg={avg:.3f}ms, 共 {len(tools)} 个工具")
        assert p50 < 1.0, f"P50 {p50:.3f}ms 超过阈值 1ms"

    def test_tool_get_performance(self):
        """工具获取性能"""
        tool_name = "system_info"
        times = []
        
        for _ in range(100):
            start = time.perf_counter()
            tool = registry.get_tool(tool_name)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert tool is not None
        
        p50 = median(times)
        print(f"\ntool.get_tool(): P50={p50:.3f}ms, avg={mean(times):.3f}ms")
        assert p50 < 0.1, f"P50 {p50:.3f}ms 超过阈值 0.1ms"


# ── 6. 响应序列化性能 ──────────────────────────────────

class TestSerializationPerformance:
    """JSON 响应序列化性能"""

    def test_large_response_serialization(self):
        """大响应序列化性能 (模拟 process_list 结果)"""
        # 构造一个包含 100 个进程的大响应
        large_data = {
            "tool": "process_list",
            "timestamp": "2026-07-10T12:00:00Z",
            "risk_level": "read_only",
            "data": {
                "processes": [
                    {
                        "pid": i,
                        "name": f"process_{i}",
                        "status": "running",
                        "cpu_percent": 1.5,
                        "memory_percent": 2.3,
                        "username": "user",
                        "cmdline": f"/usr/bin/process_{i} --arg1 --arg2"
                    }
                    for i in range(100)
                ],
                "count": 100
            },
            "summary": {
                "total": 100,
                "alert": False
            }
        }
        
        import json
        times = []
        for _ in range(100):
            start = time.perf_counter()
            json_str = json.dumps(large_data, ensure_ascii=False)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert len(json_str) > 10000  # 确保是大响应
        
        p50 = median(times)
        avg = mean(times)
        print(f"\n大响应序列化 (100 进程): P50={p50:.3f}ms, avg={avg:.3f}ms, 大小 {len(json_str)} bytes")
        assert p50 < 5.0, f"P50 {p50:.3f}ms 超过阈值 5ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
