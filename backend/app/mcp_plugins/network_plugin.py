"""
MCP 网络态势感知插件

提供三项主机网络审计能力:
1. network_listening_ports       - TCP/UDP 监听端口枚举, 识别未授权服务
2. network_connections_summary   - TCP 连接状态统计与异常告警 (CLOSE_WAIT/SYN_SENT/FIN_WAIT1)
3. network_interface_stats       - 网卡流量与错误统计, 识别丢包/错误异常

数据来源:
- ss -tlnp (监听端口)
- ss -tan  (TCP 连接状态)
- ip -s link (网卡统计)

底层命令通过 run_command() 统一执行, 超时或失败自动降级返回空数据。
所有工具均为 read_only, 不会修改系统状态。

"""

from app.mcp_plugins._common import(
    run_command as _run_command,
    make_response as _make_response,
    error_response as _error_response
)
from collections import Counter
import re

#方法: 正则解析name和pid
def _parse_info(raw):
    if not raw:
        return {"name": "","pid": ""}
    
    pattern=re.search(r'users:\(\(\"(?P<name>.*?)\",pid=(?P<pid>.*?),',raw)
    if pattern:
        return {"name": pattern.group("name"),"pid": pattern.group("pid")}
    return {"name": "","pid": ""}

#方法: 提取关键信息
def _get_info(result):
#裁切res
    ports=[]
    for line in result.split("\n")[1:]:
        line=line.split()
        if len(line)<5 or line[0]!="LISTEN":
            continue
        local=line[3]
        process=line[5] if len(line)>=6 else ""
        
        #裁切与正则提取, 兼容Ipv6地址
        address,port=local.rsplit(":",1)
        
        if address.startswith("[") and address.endswith("]"):
            address=address[1:-1]
        
        res=_parse_info(process)
        
        ports.append({
            "port": int(port),
            "proto": "tcp",
            "bind": address,
            "process": res.get("name"),
            "pid": res.get("pid")
        })
        
    return ports

"""
方法: network_listening_ports(), 解析ss返回所有 TCP/UDP 监听端口, 端口号/协议/绑定IP/关联进程

"""
def network_listening_ports():
    try:
        result=_run_command(["ss","-tlnp"])
        if not result:
            return _make_response("network_listening_ports",
                                data={"ports": []},
                                summary={"total": 0}
                                )
        
        ports=_get_info(result)
            
        return _make_response("network_listening_ports",
                            data={"port": ports},
                            summary={"total": len(ports)}
                            )
    except Exception as e:
        return _error_response("network_listening_ports", e)

#方法: 解析 ss -tan 输出, 统计各 TCP 状态数量
def _count_tcp_states(result):
    states=Counter()
    for line in result.split("\n")[1:]:
        parts=line.split()
        if not parts:
            continue
        #统一大写, 兼容 TIME_WAIT / TIME-WAIT / timewait 等写法
        state=parts[0].upper().replace("-", "_")
        states[state]+=1
    return states

# 需要重点关注的状态
_KEY_TCP_STATES=["ESTAB", "TIME_WAIT", "CLOSE_WAIT", "LISTEN", "SYN_SENT", "FIN_WAIT1", "FIN_WAIT2"]

#方法: 从状态计数器中提取关键状态的 data 字典
def _extract_key_states(states):
    data={}
    for s in _KEY_TCP_STATES:
        data[s.lower()]=states.get(s, 0)
    data["all_states"]=dict(states)
    return data

#方法: 根据异常计数器判断是否告警
def _check_connection_alert(states):
    close_wait=states.get("CLOSE_WAIT", 0)
    syn_sent=states.get("SYN_SENT", 0)
    fin_wait1=states.get("FIN_WAIT1", 0)
    alert=close_wait>10 or syn_sent>20 or fin_wait1>20
    reasons=[]
    if close_wait>10:
        reasons.append("CLOSE_WAIT({})过高, 疑似应用层 socket 未正确 close".format(close_wait))
    if syn_sent>20:
        reasons.append("SYN_SENT({})过高, 可能存在大量对外连接失败或扫描".format(syn_sent))
    if fin_wait1>20:
        reasons.append("FIN_WAIT1({})过高, 远端主动断开后本地未及时确认".format(fin_wait1))
    return alert, "; ".join(reasons) if reasons else ""


"""
方法: network_connections_summary(), 监控和分析服务器网络连接状态

"""    
def network_connections_summary():
    try:
        result=_run_command(["ss", "-tan"])
        if not result:
            return _make_response("network_connections_summary",
                data={"established": 0, "time_wait": 0, "close_wait": 0, "listen": 0},
                summary={"total": 0, "alert": False},
            )

        #统计各状态连接数
        states=_count_tcp_states(result)
        #提取关键状态
        data=_extract_key_states(states)
        #告警判断
        alert, reason=_check_connection_alert(states)

        return _make_response("network_connections_summary",
            data=data,
            summary={
                "total": sum(states.values()),
                "alert": alert,
                "alert_reason": reason,
            },
        )
    except Exception as e:
        return _error_response("network_connections_summary", e)


#方法: 解析 ip -s link 输出, 返回每个网卡的流量统计
def _parse_ip_stats(result):
    interfaces=[]
    current=None
    lines=result.split("\n")
    i=0
    while i<len(lines):
        line=lines[i]
        #匹配网卡头: "1: ens33: <UP,...>"
        if line and line[0].isdigit() and ":" in line[:6]:
            current={
                "name": line.split(":")[1].strip(),
                "state": "UP" if "UP" in line else "DOWN",
            }
            i+=1
            continue
        #RX 数据行 (表头的下一行)
        if current is not None and line.strip().startswith("RX:"):
            i+=1
            if i<len(lines):
                nums=lines[i].split()
                if len(nums)>=6:
                    current["rx_bytes"]=int(nums[0])
                    current["rx_packets"]=int(nums[1])
                    current["rx_errors"]=int(nums[2])
                    current["rx_dropped"]=int(nums[3])
            i+=1
            continue
        #TX 数据行
        if current is not None and line.strip().startswith("TX:"):
            i+=1
            if i<len(lines):
                nums=lines[i].split()
                if len(nums)>=6:
                    current["tx_bytes"]=int(nums[0])
                    current["tx_packets"]=int(nums[1])
                    current["tx_errors"]=int(nums[2])
                    current["tx_dropped"]=int(nums[3])
            #TX 是最后一组数据, 存入列表
            if current:
                interfaces.append(current)
                current=None
            i+=1
            continue
        i+=1
    return interfaces


"""
方法: network_interface_stats(), 网卡流量与错误统计, 识别丢包/错误异常

"""
def network_interface_stats():
    try:
        result=_run_command(["ip", "-s", "link"])
        if not result:
            return _make_response("network_interface_stats",
                data={"interfaces": []},
                summary={"total_interfaces": 0, "active": 0, "alert": False},
            )

        #解析网卡数据
        interfaces=_parse_ip_stats(result)
        #统计活跃网卡
        active=[iface for iface in interfaces if iface["state"]=="UP"]
        #检查是否有错误或丢包
        has_error=any(
            iface.get("rx_errors", 0)>0 or iface.get("tx_errors", 0)>0 or
            iface.get("rx_dropped", 0)>0 or iface.get("tx_dropped", 0)>0
            for iface in interfaces
        )

        return _make_response("network_interface_stats",
            data={"interfaces": interfaces},
            summary={
                "total_interfaces": len(interfaces),
                "active": len(active),
                "alert": has_error,
                "alert_reason": "检测到网卡错误或丢包, 请检查" if has_error else "",
            },
        )
    except Exception as e:
        return _error_response("network_interface_stats", e)