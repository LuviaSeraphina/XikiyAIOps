"""
_common.py 工具函数测试 — _sdk_call

覆盖本次重构合并的 _sdk_call 函数:
- 正常方法调用
- 方法不存在 → None
- 方法抛异常 → None
- 带参数调用
"""
import pytest
from app.mcp_plugins._common import _sdk_call


class FakeSDK:
    """模拟 KYSDK 对象"""
    def get_name(self):
        return "kylin"

    def get_info(self, version=0):
        return "v{}".format(version)

    def raise_error(self):
        raise RuntimeError("SDK internal error")


class TestSdkCall:
    """_sdk_call: 安全调用 KYSDK 对象方法"""

    def test_normal_call_no_args(self):
        obj = FakeSDK()
        result = _sdk_call(obj, "get_name")
        assert result == "kylin"

    def test_normal_call_with_args(self):
        obj = FakeSDK()
        result = _sdk_call(obj, "get_info", 2)
        assert result == "v2"

    def test_method_not_found_returns_none(self):
        obj = FakeSDK()
        result = _sdk_call(obj, "non_existent_method")
        assert result is None

    def test_method_raises_returns_none(self):
        obj = FakeSDK()
        result = _sdk_call(obj, "raise_error")
        assert result is None

    def test_none_object_attr_fallback(self):
        """对象有属性但为 None 的边界情况 — getattr 返回 None, method is None → None"""
        obj = FakeSDK()
        obj.get_name = None
        result = _sdk_call(obj, "get_name")
        assert result is None
