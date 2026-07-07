"""
MCP 健康评分配置插件 — AI 可读写健康评分权重和阈值

提供两项能力:
1. health_config_get — 读取当前配置 (read_only)
2. health_config_set — 修改单个配置项 (restricted, 需确认)
"""
from app.core.rca_analyzer import load_health_config, save_health_config
from app.mcp_plugins._common import make_response as _make_response, error_response as _error_response


"""
方法: health_config_get_handler(), 读取当前健康评分配置

"""
def health_config_get_handler():
    try:
        config=load_health_config()
        return _make_response("health_config_get",
            data={"config": config},
            summary={
                "weights": config.get("weights", {}),
                "dimensions": list(config.get("thresholds", {}).keys()),
                "version": config.get("version", "unknown"),
            },
        )
    except Exception as e:
        return _error_response("health_config_get", e)


"""
方法: health_config_set_handler(), 按 dot-path 修改单个配置项

"""
def health_config_set_handler(key_path="", value=0.0):
    try:
        if not key_path:
            return _error_response("health_config_set", "key_path 不能为空")
        config=load_health_config()
        # 按 . 分隔的路径逐层定位并修改
        keys=key_path.split(".")
        target=config
        for _, key in enumerate(keys[:-1]):
            # 处理数组索引: 如 thresholds.cpu.1 → 定位到 thresholds["cpu"][1]
            if isinstance(target, list):
                idx=int(key)
                if idx < 0 or idx >= len(target):
                    return _error_response("health_config_set",
                        "索引 {} 超出范围 (0~{})".format(idx, len(target) - 1))
                target=target[idx]
            elif isinstance(target, dict):
                if key not in target:
                    return _error_response("health_config_set",
                        "配置路径不存在: '{}' (可用: {})".format(key, list(target.keys())))
                target=target[key]
            else:
                return _error_response("health_config_set", "无法在非容器类型中查找 '{}'".format(key))
        # 最后一个 key — 设置值
        last_key=keys[-1]
        if isinstance(target, list):
            idx=int(last_key)
            if idx < 0 or idx >= len(target):
                return _error_response("health_config_set",
                    "索引 {} 超出范围 (0~{})".format(idx, len(target) - 1))
            old_value=target[idx]
            target[idx]=value
        elif isinstance(target, dict):
            if last_key not in target:
                return _error_response("health_config_set",
                    "配置键不存在: '{}' (可用: {})".format(last_key, list(target.keys())))
            old_value=target[last_key]
            target[last_key]=value
        else:
            return _error_response("health_config_set", "无法设置非容器类型的值")
        # 保存
        ok, msg=save_health_config(config)
        if not ok:
            return _error_response("health_config_set", msg)
        return _make_response("health_config_set",
            data={
                "key_path": key_path,
                "old_value": old_value,
                "new_value": value,
            },
            summary={
                "updated": key_path,
                "old": old_value,
                "new": value,
                "message": msg,
            },
        )
    except (ValueError, TypeError) as e:
        return _error_response("health_config_set",
            "参数错误: {} (key_path='{}', value={})".format(str(e), key_path, value))
    except Exception as e:
        return _error_response("health_config_set", e)
