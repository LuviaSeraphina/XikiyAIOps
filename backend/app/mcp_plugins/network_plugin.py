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
    _cmd_ok,
    make_response as _make_response,
    error_response as _error_response
)
from collections import Counter
import re
import os

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
        if not _cmd_ok(result):
            return _error_response("network_listening_ports","ss -tlnp 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("network_listening_ports",
                                data={"ports":[]},
                                summary={"total":0}
                                )
        
        ports=_get_info(output)
            
        return _make_response("network_listening_ports",
                            data={"port":ports},
                            summary={"total":len(ports)}
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
        reasons.append(f"CLOSE_WAIT({close_wait})过高, 疑似应用层 socket 未正确 close")
    if syn_sent>20:
        reasons.append(f"SYN_SENT({syn_sent})过高, 可能存在大量对外连接失败或扫描")
    if fin_wait1>20:
        reasons.append(f"FIN_WAIT1({fin_wait1})过高, 远端主动断开后本地未及时确认")
    return alert, "; ".join(reasons) if reasons else ""


"""
方法: network_connections_summary(), 监控和分析服务器网络连接状态

"""    
def network_connections_summary():
    try:
        result=_run_command(["ss", "-tan"])
        if not _cmd_ok(result):
            return _error_response("network_connections_summary","ss -tan 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("network_connections_summary",
                data={"established":0,"time_wait":0,"close_wait":0,"listen":0},
                summary={"total":0,"alert":False},
            )

        #统计各状态连接数
        states=_count_tcp_states(output)
        #提取关键状态
        data=_extract_key_states(states)
        #告警判断
        alert, reason=_check_connection_alert(states)

        return _make_response("network_connections_summary",
            data=data,
            summary={
                "total":sum(states.values()),
                "alert":alert,
                "alert_reason":reason,
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
        if not _cmd_ok(result):
            return _error_response("network_interface_stats","ip -s link 执行失败")
        output=result["stdout"]
        if not output:
            return _make_response("network_interface_stats",
                data={"interfaces":[]},
                summary={"total_interfaces":0,"active":0,"alert":False},
            )

        #解析网卡数据
        interfaces=_parse_ip_stats(output)
        #统计活跃网卡
        active=[iface for iface in interfaces if iface["state"]=="UP"]
        #检查是否有错误或丢包
        has_error=any(
            iface.get("rx_errors", 0)>0 or iface.get("tx_errors", 0)>0 or
            iface.get("rx_dropped", 0)>0 or iface.get("tx_dropped", 0)>0
            for iface in interfaces
        )

        return _make_response("network_interface_stats",
            data={"interfaces":interfaces},
            summary={
                "total_interfaces":len(interfaces),
                "active":len(active),
                "alert":has_error,
                "alert_reason":"检测到网卡错误或丢包, 请检查" if has_error else "",
            },
        )
    except Exception as e:
        return _error_response("network_interface_stats", e)


"""
方法: network_firewall_audit(), 防火墙规则审计 — iptables/nftables 规则统计

"""
def network_firewall_audit():
    try:
        #检测防火墙类型 — which + 绝对路径双重检查
        nft_exists=_run_command(["which", "nft"])
        ipt_exists=_run_command(["which", "iptables"])
        #补充绝对路径检测 (nft/iptables 通常在 /usr/sbin, 普通用户 which 可能找不到)
        nft_found=_cmd_ok(nft_exists) and "nft" in nft_exists["stdout"]
        if not nft_found and os.path.exists("/usr/sbin/nft"):
            nft_found=True
        ipt_found=_cmd_ok(ipt_exists) and "iptables" in ipt_exists["stdout"]
        if not ipt_found and os.path.exists("/usr/sbin/iptables"):
            ipt_found=True

        fw_type="unknown"
        rule_count=0
        rules=[]

        if nft_found:
            fw_type="nftables"
            result=_run_command(["nft", "list", "ruleset"], timeout=10)
            if not _cmd_ok(result):
                return _error_response("network_firewall_audit","nft list ruleset 执行失败")
            output=result["stdout"]
            lines=output.split("\n") if output else []
            rule_count=len([l for l in lines if l.strip()])

        elif ipt_found:
            fw_type="iptables"
            for table in ["filter", "nat", "mangle"]:
                result=_run_command(["iptables", "-t", table, "-L", "-n"], timeout=5)
                if not _cmd_ok(result):
                    return _error_response("network_firewall_audit",f"iptables -t {table} -L -n 执行失败")
                output=result["stdout"]
                if output:
                    lines=[l for l in output.split("\n") if l.strip().startswith(("ACCEPT", "DROP", "REJECT", "Chain"))]
                    rules.extend(lines)
            rule_count=len(rules)

        return _make_response("network_firewall_audit",
            data={
                "firewall_type":fw_type,
                "rule_count":rule_count,
            },
            summary={
                "type":fw_type,
                "rules":rule_count,
                "alert":fw_type=="unknown",
                "alert_reason":"未检测到防火墙" if fw_type=="unknown" else "",
            },
        )
    except Exception as e:
        return _error_response("network_firewall_audit", e)


"""
方法: network_tcp_retrans(), TCP 重传率 — 从 ss -ti 解析 retrans 计数, >2% 表示网络异常

"""
def network_tcp_retrans():
    try:
        retrans_total=0
        conn_count=0
        result=_run_command(["ss", "-ti"], timeout=5)
        if not _cmd_ok(result):
            return _error_response("network_tcp_retrans","ss -ti 执行失败")
        output=result["stdout"]
        if output:
            for line in output.split("\n"):
                if "retrans:" in line:
                    conn_count+=1
                    m=re.search(r"retrans:(\d+)", line)
                    if m:
                        retrans_total+=int(m.group(1))

        retrans_rate=round(retrans_total / conn_count * 100, 1) if conn_count > 0 else 0.0

        return _make_response("network_tcp_retrans",
            data={
                "connections_checked":conn_count if output else 0,
                "retransmissions":retrans_total if output else 0,
                "retrans_rate_percent":retrans_rate,
            },
            summary={
                "rate":retrans_rate,
                "alert":retrans_rate>2.0,
                "alert_reason":f"TCP 重传率 {retrans_rate}% > 2%, 网络可能异常" if retrans_rate>2.0 else "",
            },
        )
    except Exception as e:
        return _error_response("network_tcp_retrans", e)


"""
方法: network_dns_check(domain, dns_server=""), DNS 解析测试 — dig 优先, getent 兜底

"""
def network_dns_check(domain, dns_server=""):
    try:
        #dig 可用?
        dig_ok=False
        try:
            which_out=_run_command(["which", "dig"], timeout=3)
            dig_ok=bool(which_out and "/dig" in which_out)
        except Exception:
            dig_ok=False

        ips=[]
        if dig_ok:
            cmd=["dig", "+short", domain]
            if dns_server:
                cmd.append(f"@{dns_server}")
            out=_run_command(cmd, timeout=5)
            if out:
                for line in out.split("\n"):
                    line=line.strip()
                    if line and not line.startswith(";"):
                        ips.append(line)

        #dig 无结果, 兜底 getent
        if not ips:
            try:
                out=_run_command(["getent", "hosts", domain], timeout=5)
                if out:
                    for line in out.split("\n"):
                        line=line.strip()
                        if line:
                            ip=line.split()[0] if line.split() else ""
                            if ip and ip not in ips:
                                ips.append(ip)
            except Exception:
                pass

        resolved=len(ips)>0
        return _make_response("network_dns_check",
            data={
                "domain": domain,
                "dns_server": dns_server if dns_server else "system-default",
                "resolved_ips": ips,
                "count": len(ips),
            },
            summary={
                "resolved": resolved,
                "ip_count": len(ips),
                "dns_server": dns_server if dns_server else "system-default",
            },
        )
    except Exception as e:
        return _error_response("network_dns_check", e)