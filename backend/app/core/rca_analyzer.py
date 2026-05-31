"""
根因分析引擎

1. 异常检测 — 3-Sigma / IQR / 移动平均 / 孤立森林 (无需训练数据, 适合现场部署)
2. 日志关联 — 多源系统日志时间线对齐 + 因果关系推断
3. 根因链推断 — 事件排序 + 依赖图 + 最近共同祖先
4. 系统健康评分 — 多维度加权综合评分 (0~100)
"""

import re
import math
import json
import os
from datetime import datetime
from collections import defaultdict, Counter


# 1. 异常检测算法 — 类架构: fit()→detect()→get_anomalies()→summary()

# 3-Sigma 动态阈值异常检测
class ThreeSigmaDetector:
    def __init__(self, values, threshold=3.0):
        self.values=list(values)
        self.threshold=threshold
        self._indices=None
        self.mean=None
        self.std=None
        self.upper=None
        self.lower=None
        
    # 计算均值、标准差、上界、下界
    def fit(self):
        n=len(self.values)
        if n < 3:
            return self
        self.mean=sum(self.values) / n
        variance=sum((x - self.mean) ** 2 for x in self.values) / n
        self.std=math.sqrt(variance) if variance > 0 else 0
        if self.std == 0:
            return self
        self.upper=self.mean + self.threshold * self.std
        self.lower=max(0, self.mean - self.threshold * self.std)
        self._indices=self.detect()
        return self
    
    # 返回异常点索引列表
    def detect(self):
        if self.upper is None:
            return []
        return [i for i, v in enumerate(self.values) if v > self.upper or v < self.lower]
    
    # 返回只包含异常值的列表
    def get_anomalies(self):
        if self._indices is None:
            return []
        return [self.values[i] for i in self._indices]
    
    # 返回结构化摘要 dict
    def summary(self):
        n=len(self.values)
        return {
            "anomaly_indices": self._indices if self._indices else [],
            "anomaly_count": len(self._indices) if self._indices else 0,
            "mean": round(self.mean, 2) if self.mean else 0,
            "std": round(self.std, 2) if self.std else 0,
            "upper_bound": round(self.upper, 2) if self.upper else 0,
            "lower_bound": round(self.lower, 2) if self.lower else 0,
            "threshold": self.threshold,
            "detail": "3σ 检测: {} / {} 个异常点".format(
                len(self._indices) if self._indices else 0, n),
        }

# IQR 箱线图异常检测
class IQRDetector:
    def __init__(self, values, multiplier=1.5):
        self.values=list(values)
        self.multiplier=multiplier
        self._indices=None
        self.q1=None
        self.q3=None
        self.iqr=None
        self.upper=None
        self.lower=None
        
    # 计算四分位数、上下界
    def fit(self):
        n=len(self.values)
        if n < 4:
            return self
        sorted_vals=sorted(self.values)
        q1_idx=n // 4
        q3_idx=(3 * n) // 4
        self.q1=sorted_vals[q1_idx]
        self.q3=sorted_vals[q3_idx]
        self.iqr=self.q3 - self.q1
        if self.iqr == 0:
            return self
        self.lower=self.q1 - self.multiplier * self.iqr
        self.upper=self.q3 + self.multiplier * self.iqr
        self._indices=self.detect()
        return self
    
    # 返回异常点索引列表
    def detect(self):
        if self.upper is None:
            return []
        return [i for i, v in enumerate(self.values) if v < self.lower or v > self.upper]
    
    # 返回只包含异常值的列表
    def get_anomalies(self):
        if self._indices is None:
            return []
        return [self.values[i] for i in self._indices]
    
    # 返回结构化摘要 dict
    def summary(self):
        n=len(self.values)
        return {
            "anomaly_indices": self._indices if self._indices else [],
            "anomaly_count": len(self._indices) if self._indices else 0,
            "Q1": self.q1,
            "Q3": self.q3,
            "IQR": round(self.iqr, 2) if self.iqr else 0,
            "lower_bound": round(self.lower, 2) if self.lower else 0,
            "upper_bound": round(self.upper, 2) if self.upper else 0,
            "multiplier": self.multiplier,
            "detail": "IQR 检测: {} / {} 个异常点".format(
                len(self._indices) if self._indices else 0, n),
        }

# 移动平均异常检测
class MovingAverageDetector:
    def __init__(self, values, window=5, threshold_factor=2.0):
        self.values=list(values)
        self.window=window
        self.threshold_factor=threshold_factor
        self._points=None
        
    # 计算滑动窗口偏离
    def fit(self):
        n=len(self.values)
        self._points=[]
        if n < self.window + 1:
            return self
        for i in range(self.window, n):
            window_vals=self.values[i - self.window:i]
            avg=sum(window_vals) / self.window
            if avg == 0:
                continue
            deviation=abs(self.values[i] - avg) / avg
            if deviation > self.threshold_factor:
                self._points.append({
                    "index": i,
                    "value": self.values[i],
                    "moving_avg": round(avg, 2),
                    "deviation_pct": round(deviation * 100, 1),
                })
        return self
    
    # 返回偏离点索引列表
    def detect(self):
        if self._points is None:
            return []
        return [p["index"] for p in self._points]
    
    # 返回只包含偏离值的列表
    def get_anomalies(self):
        if self._points is None:
            return []
        return [p["value"] for p in self._points]
    
    # 返回结构化摘要 dict
    def summary(self):
        n=len(self._points) if self._points else 0
        return {
            "anomaly_indices": self.detect(),
            "anomaly_points": self._points if self._points else [],
            "anomaly_count": n,
            "window": self.window,
            "threshold_factor": self.threshold_factor,
            "detail": "移动平均检测: {} 个偏离点 (窗口={}, 阈值={}x)".format(
                n, self.window, self.threshold_factor),
        }

# 孤立森林多维联合检测 (需 sklearn, 不可用时自动降级)
class IsolationForestDetector:
    def __init__(self, values, contamination=0.05):
        self._raw=values
        self.contamination=contamination
        self.values=None
        self.dim=0
        self.labels=None
        self.scores=None
        
    # 多维数据标准化 + 模型拟合
    def fit(self):
        # 标准化输入: 支持 [[a,b,c],...] 和 [a,b,c,...]
        flat=[list(v) if hasattr(v, '__iter__') and not isinstance(v, str) else [v] for v in self._raw]
        self.values=flat
        self.dim=len(flat[0]) if flat else 1
        try:
            from sklearn.ensemble import IsolationForest
            model=IsolationForest(contamination=self.contamination, random_state=42)
            self.labels=model.fit_predict(self.values)
            self.scores=model.decision_function(self.values)  # type: ignore
        except ImportError:
            self.labels=[1] * len(self.values)
        return self
    
    # 返回异常点索引列表
    def detect(self):
        if self.labels is None:
            return []
        return [i for i, v in enumerate(self.labels) if v == -1]
    
    # 返回只包含异常点的列表
    def get_anomalies(self):
        indices=self.detect()
        return [self.values[i] for i in indices] if self.values else []
    
    # 返回结构化摘要 dict
    def summary(self):
        anomaly_count=len(self.detect())
        has_sklearn=self.labels is not None
        return {
            "anomaly_indices": self.detect(),
            "anomaly_count": anomaly_count,
            "total": len(self.values) if self.values else 0,
            "dimensions": self.dim,
            "contamination": self.contamination,
            "sklearn_available": has_sklearn,
            "detail": "孤立森林: {} / {} 个异常点 (contamination={}, {}维)".format(
                anomaly_count, len(self.values) if self.values else 0, self.contamination, self.dim),
        }


# 组合异常检测: 多算法投票 (含孤立森林)
def detect_anomaly_combined(values, methods=None, multi_dim=None):
    if methods is None:
        methods=["3sigma", "iqr", "moving_avg"]
    results={}
    anomaly_sets=[]
    if "3sigma" in methods:
        d=ThreeSigmaDetector(values).fit()
        results["3sigma"]=d.summary()
        anomaly_sets.append(set(d.detect()))
    if "iqr" in methods:
        d=IQRDetector(values).fit()
        results["iqr"]=d.summary()
        anomaly_sets.append(set(d.detect()))
    if "moving_avg" in methods:
        d=MovingAverageDetector(values).fit()
        results["moving_avg"]=d.summary()
        anomaly_sets.append(set(d.detect()))
    if "isolation_forest" in methods and multi_dim is not None:
        d=IsolationForestDetector(multi_dim).fit()
        results["isolation_forest"]=d.summary()
        anomaly_sets.append(set(d.detect()))
        
    # 共识: 至少 2 种算法标记
    if len(anomaly_sets) >= 2:
        consensus=anomaly_sets[0].intersection(*anomaly_sets[1:])
    else:
        consensus=anomaly_sets[0] if anomaly_sets else set()
    return {
        "consensus_anomalies": sorted(consensus),
        "consensus_count": len(consensus),
        "confidence": "HIGH" if len(consensus) > 0 else "LOW",
        "method_results": results,
        "detail": "组合检测: {} 个高置信度异常点 (由 {} 种方法共识)".format(
            len(consensus), len(anomaly_sets)),
    }


""" 2. 日志关联引擎 """

# 事件严重程度定义
SEVERITY_ORDER={
    "EMERG": 0, "ALERT": 1, "CRIT": 2, "ERR": 3,
    "ERROR": 3, "WARN": 4, "WARNING": 4, "NOTICE": 5,
    "INFO": 6, "DEBUG": 7,
}

# 因果关联模式: (前因正则, 后果正则, 关联描述, 置信度)
_CAUSAL_PATTERNS=[
    # OOM 相关
    (re.compile(r"Out of memory|oom-killer|invoked oom-killer", re.IGNORECASE),
    re.compile(r"Killed process|Memory cgroup out of memory", re.IGNORECASE),
    "OOM Killer → 进程被终止", 0.95),
    # 磁盘满
    (re.compile(r"No space left on device|Disk quota exceeded", re.IGNORECASE),
    re.compile(r"(?:write|create|open).*?(?:failed|error)", re.IGNORECASE),
    "磁盘空间耗尽 → 写入失败", 0.90),
    # 网络故障
    (re.compile(r"Network (?:unreachable|is down|link down)|No route to host", re.IGNORECASE),
    re.compile(r"(?:connection|connect).*?(?:refused|timeout|failed|reset)", re.IGNORECASE),
    "网络中断 → 连接失败", 0.85),
    # CPU 过载
    (re.compile(r"CPU.*?(?:throttle|soft lockup|hard LOCKUP|rcu_sched)", re.IGNORECASE),
    re.compile(r"(?:task|process).*?(?:blocked|hung|stuck).*?(?:more than|for) \d+ seconds", re.IGNORECASE),
    "CPU 锁死 → 任务阻塞", 0.90),
    # 服务崩溃
    (re.compile(r"(?:segfault|SIGSEGV|SIGABRT|core dumped)", re.IGNORECASE),
    re.compile(r"(?:service|daemon).*?(?:stop|exit|terminated|inactive)", re.IGNORECASE),
    "进程崩溃 → 服务停止", 0.88),
    # 认证攻击
    (re.compile(r"(?:Failed password|authentication failure).*?(?:from|for).*?(\d+\.\d+\.\d+\.\d+)", re.IGNORECASE),
    re.compile(r"pam_tally2?.*?(?:account|user).*?(?:locked|denied)", re.IGNORECASE),
    "暴力破解 → 账户锁定", 0.82),
    # DNS 故障
    (re.compile(r"(?:Name or service not known|Temporary failure in name resolution|DNS.*?fail)", re.IGNORECASE),
    re.compile(r"(?:resolve|lookup|gethostbyname).*?(?:fail|error|timeout)", re.IGNORECASE),
    "DNS 解析失败 → 服务访问异常", 0.80),
]


"""
方法: extract_log_events(), 从日志行中提取结构化事件
"""
def extract_log_events(log_lines, source="syslog"):
    events=[]

    # 通用 syslog 格式解析: MMM DD HH:MM:SS host process[pid]: message
    syslog_re=re.compile(
        r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)$'
    )
    journal_re=re.compile(
        r'^(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)$'
    )

    for line in log_lines:
        if not line.strip():
            continue

        event={
            "raw": line[:200],
            "source": source,
            "severity": "INFO",
            "keywords": [],
        }

        # 尝试 syslog 格式
        m=syslog_re.match(line)
        if m:
            event["timestamp_raw"]=m.group(1)
            event["host"]=m.group(2)
            event["process"]=m.group(3)
            event["pid"]=m.group(4)
            event["message"]=m.group(5)
        else:
            m=journal_re.match(line)
            if m:
                event["process"]=m.group(1)
                event["pid"]=m.group(2)
                event["message"]=m.group(3)
            else:
                event["message"]=line

        # 提取严重程度
        for sev in SEVERITY_ORDER:
            if sev in line.upper():
                event["severity"]=sev if sev != "ERROR" else "ERR"
                break

        # 提取关键词
        event["keywords"]=_extract_log_keywords(event.get("message", line))
        events.append(event)

    return events


#方法: 从日志消息中提取关键术语
def _extract_log_keywords(message):
    keywords=[]

    patterns=[
        (r'\b(?:OOM|out of memory|memory pressure)\b', 'memory_pressure'),
        (r'\b(?:segfault|SIGSEGV|SIGABRT|core dump)\b', 'process_crash'),
        (r'\b(?:No space left|disk full|quota exceed)\b', 'disk_full'),
        (r'\b(?:timeout|timed out|T/O)\b', 'timeout'),
        (r'\b(?:connection refused|connection reset|no route)\b', 'network_error'),
        (r'\b(?:permission denied|access denied|not authorized)\b', 'permission_error'),
        (r'\b(?:Failed password|auth fail|invalid user)\b', 'auth_failure'),
        (r'\b(?:CPU|soft lockup|hard LOCKUP|rcu_sched)\b', 'cpu_lockup'),
        (r'\b(?:killed|terminated by signal|exit code)\b', 'process_killed'),
        (r'\b(?:stuck|hung|blocked)\s+(?:for|more than)\s+\d+\s*(?:s|sec|second)', 'task_hung'),
    ]

    for pattern, tag in patterns:
        if re.search(pattern, message, re.IGNORECASE):
            keywords.append(tag)

    return list(set(keywords))


""" 3. 因果链推断 """

"""
方法: build_event_timeline(), 构建事件时间线
"""
def build_event_timeline(events):
    timeline=defaultdict(list)

    for event in events:
        severity=SEVERITY_ORDER.get(event.get("severity", "INFO"), 6)
        timeline[event.get("source", "unknown")].append({
            **event,
            "severity_rank": severity,
        })

    return dict(timeline)


"""
方法: infer_causal_chain(), 从事件序列推断因果链
"""
def infer_causal_chain(events, min_confidence=0.7):
    sorted_events=sorted(
        events,
        key=lambda e: SEVERITY_ORDER.get(e.get("severity", "INFO"), 99)
    )

    causal_links=[]
    matched_sources=set()
    matched_targets=set()

    for i, event_a in enumerate(sorted_events):
        msg_a=event_a.get("message", "")
        for j, event_b in enumerate(sorted_events):
            if i == j:
                continue
            msg_b=event_b.get("message", "")

            for cause_re, effect_re, description, confidence in _CAUSAL_PATTERNS:
                if confidence < min_confidence:
                    continue
                if cause_re.search(msg_a) and effect_re.search(msg_b):
                    link={
                        "cause": {
                            "process": event_a.get("process", "unknown"),
                            "message": msg_a[:100],
                            "keywords": event_a.get("keywords", []),
                        },
                        "effect": {
                            "process": event_b.get("process", "unknown"),
                            "message": msg_b[:100],
                            "keywords": event_b.get("keywords", []),
                        },
                        "relation": description,
                        "confidence": confidence,
                    }
                    link_key=(msg_a[:50], msg_b[:50], description)
                    existing_keys=[(l["cause"]["message"][:50], l["effect"]["message"][:50], l["relation"]) for l in causal_links]
                    if link_key not in existing_keys:
                        causal_links.append(link)
                        matched_sources.add(i)
                        matched_targets.add(j)

    # 根因: 是其他事件的前因但不是任何事件的后果
    root_cause_indices=matched_sources - matched_targets
    root_causes=[sorted_events[i] for i in root_cause_indices if i < len(sorted_events)]

    # 受影响: 是后果但不是前因
    affected_indices=matched_targets - matched_sources
    affected=[sorted_events[i] for i in affected_indices if i < len(sorted_events)]

    return {
        "causal_links": causal_links,
        "link_count": len(causal_links),
        "root_causes": [
            {
                "process": e.get("process", "unknown"),
                "message": e.get("message", "")[:120],
                "severity": e.get("severity", "INFO"),
                "keywords": e.get("keywords", []),
            }
            for e in root_causes[:5]
        ],
        "affected_services": [
            {
                "process": e.get("process", "unknown"),
                "message": e.get("message", "")[:120],
                "severity": e.get("severity", "INFO"),
            }
            for e in affected[:5]
        ],
        "detail": "因果链推断: {} 条关联, {} 个根因候选, {} 个受影响服务".format(
            len(causal_links), len(root_causes), len(affected)),
    }


""" 4. 系统健康评分 — 权重和阈值从配置文件读取 """

# 默认配置文件路径 (backend/config/ 下, 与代码分离)
_CONFIG_DIR=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
_DEFAULT_CONFIG_PATH=os.path.join(_CONFIG_DIR, "health_score_config.json")

# 内置默认值 (配置文件不存在或损坏时的兜底)
_BUILTIN_CONFIG={
    "weights": {"cpu": 0.25, "memory": 0.25, "disk": 0.20, "load": 0.15, "swap": 0.15},
    "thresholds": {
        "cpu": [{"max": 50, "score": 100}, {"max": 70, "score": 80}, {"max": 85, "score": 60}, {"max": 95, "score": 30}, {"max": 101, "score": 10}],
        "memory": [{"max": 60, "score": 100}, {"max": 80, "score": 80}, {"max": 90, "score": 50}, {"max": 95, "score": 25}, {"max": 101, "score": 5}],
        "disk": [{"max": 60, "score": 100}, {"max": 80, "score": 80}, {"max": 90, "score": 50}, {"max": 95, "score": 20}, {"max": 101, "score": 5}],
        "load": [{"max": 0.7, "score": 100}, {"max": 1.0, "score": 80}, {"max": 2.0, "score": 50}, {"max": 5.0, "score": 20}, {"max": 999, "score": 5}],
        "swap": [{"max": 20, "score": 100}, {"max": 50, "score": 70}, {"max": 80, "score": 40}, {"max": 101, "score": 10}],
    },
    "alerts": {
        "cpu": [{"max_score": 30, "message": "CPU 使用率偏高: {}%"}, {"max_score": 10, "message": "CPU 使用率危险: {}%"}],
        "memory": [{"max_score": 50, "message": "内存使用率偏高: {}%"}, {"max_score": 25, "message": "内存不足: {}%"}, {"max_score": 5, "message": "内存耗尽: {}%"}],
        "disk": [{"max_score": 50, "message": "磁盘使用率偏高: {}%"}, {"max_score": 20, "message": "磁盘空间不足: {}%"}, {"max_score": 5, "message": "磁盘空间耗尽: {}%"}],
        "load": [{"max_score": 50, "message": "系统负载偏高: {}x CPU核心数"}, {"max_score": 20, "message": "系统过载: {}x CPU核心数"}, {"max_score": 5, "message": "系统严重过载: {}x CPU核心数"}],
        "swap": [{"max_score": 40, "message": "Swap 使用率偏高: {}% (可能发生内存抖动)"}, {"max_score": 10, "message": "Swap 使用率危险: {}% (内存严重不足)"}],
    },
    "grades": [{"min": 90, "label": "A (优秀)"}, {"min": 75, "label": "B (良好)"}, {"min": 60, "label": "C (一般)"}, {"min": 40, "label": "D (警告)"}, {"min": 0, "label": "F (严重)"}],
}


# 从配置文件读取健康评分配置
def load_health_config(path=None):
    """读取健康评分 JSON 配置文件, 返回 dict; 文件不存在或损坏时返回内置默认值"""
    target=path or _DEFAULT_CONFIG_PATH
    try:
        with open(target, "r", encoding="utf-8") as f:
            config=json.load(f)
        # 校验必要字段
        for key in ("weights", "thresholds"):
            if key not in config:
                raise ValueError("配置文件缺少必要字段: {}".format(key))
        return config
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        return dict(_BUILTIN_CONFIG)  # 返回副本, 避免修改内置默认值


# 将配置写回 JSON 文件
def save_health_config(config, path=None):
    """校验并保存健康评分配置到 JSON 文件; 返回 (success: bool, message: str)"""
    target=path or _DEFAULT_CONFIG_PATH
    # 校验必要字段
    for key in ("weights", "thresholds"):
        if key not in config:
            return False, "配置缺少必要字段: {}".format(key)
    weight_sum=sum(config["weights"].get(k, 0) for k in ("cpu", "memory", "disk", "load", "swap"))
    if abs(weight_sum - 1.0) > 0.01:
        return False, "权重之和必须为 1.0, 当前: {:.2f}".format(weight_sum)
    # 校验阈值结构
    for dim in ("cpu", "memory", "disk", "load", "swap"):
        thresholds=config["thresholds"].get(dim)
        if not thresholds or not isinstance(thresholds, list):
            return False, "thresholds.{} 必须是非空列表".format(dim)
    try:
        config.setdefault("version", "1.0")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True, "配置已保存到 {}".format(target)
    except (PermissionError, OSError) as e:
        return False, "写入配置文件失败: {}".format(str(e))


# 根据阈值表计算单项得分
def _score_by_thresholds(value, thresholds):
    for tier in thresholds:
        if value < tier["max"]:
            return tier["score"]
    return thresholds[-1]["score"] if thresholds else 0

# 根据告警表生成告警消息
def _alerts_by_score(score, alert_rules, fmt_value):
    messages=[]
    for rule in alert_rules:
        if score <= rule.get("max_score", 0):
            messages.append(rule["message"].format(fmt_value))
    return messages


"""
方法: compute_health_score(), 综合系统健康评分 (0~100) — 权重和阈值从配置文件读取
"""
def compute_health_score(metrics, config=None):
    if config is None:
        config=load_health_config()
    weights=config.get("weights", _BUILTIN_CONFIG["weights"])
    thresholds=config.get("thresholds", _BUILTIN_CONFIG["thresholds"])
    alert_rules=config.get("alerts", _BUILTIN_CONFIG["alerts"])
    grade_rules=config.get("grades", _BUILTIN_CONFIG["grades"])

    scores={}
    alerts=[]

    # CPU
    cpu=metrics.get("cpu_percent", 0)
    scores["cpu"]=_score_by_thresholds(cpu, thresholds.get("cpu", []))
    alerts.extend(_alerts_by_score(scores["cpu"], alert_rules.get("cpu", []), cpu))

    # 内存
    mem=metrics.get("memory_percent", 0)
    scores["memory"]=_score_by_thresholds(mem, thresholds.get("memory", []))
    alerts.extend(_alerts_by_score(scores["memory"], alert_rules.get("memory", []), mem))

    # 磁盘
    disk=metrics.get("disk_percent", 0)
    scores["disk"]=_score_by_thresholds(disk, thresholds.get("disk", []))
    alerts.extend(_alerts_by_score(scores["disk"], alert_rules.get("disk", []), disk))

    # 负载
    load_ratio=metrics.get("load_ratio", 0)
    scores["load"]=_score_by_thresholds(load_ratio, thresholds.get("load", []))
    alerts.extend(_alerts_by_score(scores["load"], alert_rules.get("load", []), round(load_ratio, 1)))

    # Swap
    swap=metrics.get("swap_percent", 0)
    scores["swap"]=_score_by_thresholds(swap, thresholds.get("swap", []))
    alerts.extend(_alerts_by_score(scores["swap"], alert_rules.get("swap", []), swap))

    # 加权总分
    total=sum(scores[k] * weights.get(k, 0) for k in weights)

    # 评级
    grade="F (严重)"
    for rule in grade_rules:
        if total >= rule["min"]:
            grade=rule["label"]
            break

    return {
        "score": round(total, 1),
        "grade": grade,
        "dimension_scores": scores,
        "alerts": alerts,
        "alert_count": len(alerts),
        "detail": "健康评分 {} ({}), {} 项告警".format(round(total, 1), grade, len(alerts)),
    }


""" 5. RCA 综合分析入口 """

"""
方法: run_rca_analysis(), RCA 综合分析入口 — 整合异常检测+日志关联+因果推断+健康评分
"""
def run_rca_analysis(plugin_data):
    report={
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sections": {},
        "overall_conclusion": "",
    }

    # 1. 异常检测
    anomaly_results={}
    if "load" in plugin_data and len(plugin_data["load"]) >= 3:
        anomaly_results["load_3sigma"]=ThreeSigmaDetector(plugin_data["load"]).fit().summary()
        anomaly_results["load_iqr"]=IQRDetector(plugin_data["load"]).fit().summary()
        anomaly_results["load_ma"]=MovingAverageDetector(plugin_data["load"]).fit().summary()
        anomaly_results["load_combined"]=detect_anomaly_combined(plugin_data["load"])
    if "memory_history" in plugin_data and len(plugin_data["memory_history"]) >= 3:
        anomaly_results["memory"]=ThreeSigmaDetector(
            plugin_data["memory_history"], threshold=2.5
        ).fit().summary()
    # 孤立森林: 多维联合检测 (CPU+内存+磁盘)
    if "metrics_multi" in plugin_data and len(plugin_data["metrics_multi"]) >= 10:
        anomaly_results["isolation_forest"]=IsolationForestDetector(
            plugin_data["metrics_multi"]
        ).fit().summary()

    report["sections"]["anomaly_detection"]={
        "title": "异常检测",
        "results": anomaly_results,
        "summary": "检测到 {} 个维度的异常".format(len(anomaly_results)),
    }

    # 2. 日志关联
    log_events=plugin_data.get("log_events", [])
    if log_events:
        structured_events=extract_log_events(log_events)
        timeline=build_event_timeline(structured_events)
        report["sections"]["log_correlation"]={
            "title": "日志关联分析",
            "total_events": len(structured_events),
            "event_sources": list(timeline.keys()),
            "severity_distribution": dict(Counter(
                e.get("severity", "INFO") for e in structured_events
            )),
            "timeline": {
                k: len(v) for k, v in timeline.items()
            },
        }

    # 3. 因果推断
    if log_events:
        structured_events=extract_log_events(log_events)
        causal=infer_causal_chain(structured_events)
        report["sections"]["causal_analysis"]={
            "title": "因果链推断",
            **causal,
        }

    # 4. 健康评分
    health_config=load_health_config()
    health_input={
        "cpu_percent": plugin_data.get("cpu_percent", 0),
        "memory_percent": plugin_data.get("memory_percent", 0),
        "disk_percent": plugin_data.get("disk_percent", 0),
        "load_ratio": plugin_data.get("load_ratio", 0),
        "swap_percent": plugin_data.get("swap_percent", 0),
    }
    health=compute_health_score(health_input, config=health_config)
    report["sections"]["health_score"]={
        "title": "健康度评分",
        **health,
    }

    # 5. 综合结论
    conclusions=[]

    # 从异常检测总结
    combined=anomaly_results.get("load_combined", {})
    if combined.get("consensus_count", 0) > 0:
        conclusions.append("负载异常: {} 个时间点被多算法共识标记".format(combined["consensus_count"]))
    # 孤立森林总结
    iso_forest=anomaly_results.get("isolation_forest", {})
    if iso_forest.get("anomaly_count", 0) > 0:
        conclusions.append("多维联合异常: 孤立森林检测到 {} 个异常点 ({}维)".format(
            iso_forest["anomaly_count"], iso_forest.get("dimensions", 1)))

    # 从健康评分总结
    if health["score"] < 60:
        conclusions.append("系统健康度 {} ({}) — 需立即关注".format(health["score"], health["grade"]))
    elif health["score"] < 75:
        conclusions.append("系统健康度 {} ({}) — 建议排查".format(health["score"], health["grade"]))

    # 从因果分析总结
    causal_section=report["sections"].get("causal_analysis", {})
    root_causes=causal_section.get("root_causes", [])
    if root_causes:
        conclusions.append("可能的根因: {} (关键字: {})".format(
            root_causes[0].get("process", "unknown"),
            ", ".join(root_causes[0].get("keywords", ["未知"])),
        ))

    if not conclusions:
        conclusions.append("未检测到明显异常, 系统运行正常")

    report["overall_conclusion"] = " | ".join(conclusions)

    return report
