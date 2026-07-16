"""
敏感规则库管理插件 — 运行时热加载自定义规则

提供:
- sensitive_rules_get: 获取当前规则配置
- sensitive_rules_set: 更新指定分类的规则
- sensitive_rules_reload: 重新加载规则文件
"""
import json
import re
from pathlib import Path
from app.mcp_plugins._common import make_response, error_response

_RULES_FILE=Path(__file__).resolve().parent.parent.parent / "config" / "sensitive_rules.json"

#运行时缓存
_cached_rules=None
_cache_mtime=0


def _load_rules(force=False):
    """加载规则文件 (带缓存)"""
    global _cached_rules, _cache_mtime
    if not force and _cached_rules is not None:
        mtime=_RULES_FILE.stat().st_mtime if _RULES_FILE.exists() else 0
        if mtime<=_cache_mtime:
            return _cached_rules
    
    if not _RULES_FILE.exists():
        return {}
    
    with open(_RULES_FILE, "r", encoding="utf-8") as f:
        _cached_rules=json.load(f)
        _cache_mtime=_RULES_FILE.stat().st_mtime
        return _cached_rules


def sensitive_rules_get_handler(category=None):
    """获取敏感规则配置"""
    rules=_load_rules()
    if category and category in rules:
        return make_response("sensitive_rules_get",
            data={category: rules[category]},
            summary={"category":category,"version":rules.get("version","")})
    return make_response("sensitive_rules_get",
        data=rules,
        summary={"categories":list(rules.keys()),"version":rules.get("version","")})


def sensitive_rules_set_handler(category, data):
    """
    更新指定分类的敏感规则
    
    category: data_sanitize | intent_filter | intent_audit | protected_lists
    data: JSON 对象 (替换整个分类)
    """
    valid_categories=["data_sanitize","intent_filter","intent_audit","protected_lists"]
    if category not in valid_categories:
        return error_response("sensitive_rules_set", f"无效分类: {category}, 允许: {valid_categories}")
    
    rules=_load_rules(force=True)
    
    #验证 data 结构
    if not isinstance(data, dict):
        return error_response("sensitive_rules_set", "data 必须是 JSON 对象")
    
    #特殊验证
    if category=="data_sanitize":
        for p in data.get("patterns",[]):
            if not isinstance(p,dict) or "regex" not in p:
                return error_response("sensitive_rules_set", "data_sanitize.patterns 需含 regex 字段")
            #验证正则有效性
            try:
                re.compile(p["regex"])
            except re.error as e:
                return error_response("sensitive_rules_set", f"无效正则 '{p['regex'][:30]}': {e}")
    
    #更新规则
    rules[category]=data
    rules["version"]=f"{float(rules.get('version','1.0').split('.')[0])+0.1:.1f}"
    
    #写回文件
    with open(_RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    
    #刷新缓存
    global _cached_rules
    _cached_rules=rules
    _cache_mtime=_RULES_FILE.stat().st_mtime
    
    return make_response("sensitive_rules_set",
        data={"category":category,"version":rules["version"]},
        summary={"updated":category,"version":rules["version"]})


def sensitive_rules_reload_handler():
    """强制重新加载规则文件"""
    rules=_load_rules(force=True)
    return make_response("sensitive_rules_reload",
        data={"version":rules.get("version","")},
        summary={"reloaded":len(rules),"version":rules.get("version","")})
