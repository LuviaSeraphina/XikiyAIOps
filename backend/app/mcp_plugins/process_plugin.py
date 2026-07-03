"""
MCP 进程巡检工具

功能：
- 获取系统当前进程列表
- 支持按进程状态过滤(running / sleeping / zombie / disk-sleep 等)
- 支持按 CPU 或内存使用率排序
- 返回 Top N 进程(默认 10 个，可配置 1~100)

使用 psutil.process_iter() 遍历进程，返回结构化 dict 列表，
每次调用前自动预热 CPU 采样，避免首次返回全 0。

用于 MCP Agent 进行系统负载分析、僵尸进程排查、异常进程检测等场景。

"""

import psutil
import time
import os
import signal
from app.mcp_plugins._common import make_response as _make_response, error_response as _error_response

process_inspect_schema={
    "name": "process_inspect",
    "description": "获取系统进程信息",
    "inputSchema": {
        "type": "object",
        "properties": {
            "filter_state": {"type": "string","default": "","enum": ["running","sleeping","stopped","zombie","disk-sleep"]},
            "sort_by": {"type": "string","default": "cpu","enum": ["cpu","mem"]},
            "top_n": {"type": "integer","default": 10,"minimum": 1,"maximum": 100}
        }
    },
    "risk_level": "read_only"
}

"""
方法: process_inspect_handler(), 返回进程列表，支持按状态过滤、按 CPU/内存(mem)排序

"""
def process_inspect_handler(filter_state="", sort_by="cpu", top_n=10):
    try:
        # 预热: 触发所有进程的第一次采样
        try:
            for _ in psutil.process_iter(['cpu_percent']):
                _=_.info['cpu_percent']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        time.sleep(0.5)
        
        # 正式采样
        all_process=[]
        for process in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']):
            try:
                if filter_state and process.info['status']!=filter_state:
                    continue
                
                all_process.append({
                    'pid': process.info.get('pid'),
                    'name': process.info.get('name'),
                    'cpu_percent': process.info.get('cpu_percent') or 0.0,
                    'memory_percent': process.info.get('memory_percent') or 0.0,
                    'status': process.info.get('status')
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 按CPU/内存排序
        if sort_by=="cpu":
            all_process.sort(key=lambda x:x['cpu_percent'],reverse=True)
        elif sort_by=="mem":
            all_process.sort(key=lambda x:x['memory_percent'],reverse=True)

        return _make_response("process_inspect_handler",
            data={"processes": all_process[:top_n]},
            summary={"total": len(all_process), "shown": min(top_n, len(all_process))},
        )
    except Exception as e:
        return _error_response("process_inspect_handler", e)


"""
方法: process_detail_handler(pid), 单进程详情 — 线程数/fd数/OOM score/cgroup/CWD/RSS内存
"""
def process_detail_handler(pid):
    try:
        proc=psutil.Process(pid)
        info=proc.as_dict(attrs=[
            'pid','name','status','cpu_percent','memory_percent',
            'num_threads','create_time','cwd','exe','username','nice',
        ])

        #num_fds: 可能因权限失败
        try:
            info['num_fds']=proc.num_fds()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            info['num_fds']=None

        #RSS 转 MB
        try:
            info['memory_info_rss_mb']=round(proc.memory_info().rss / (1024*1024), 2)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            info['memory_info_rss_mb']=None

        #格式化启动时间
        if info.get('create_time'):
            info['create_time_formatted']=time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(info['create_time']))

        return _make_response("process_detail_handler",
            data={"process": info},
            summary={"pid": info.get('pid'), "name": info.get('name'), "status": info.get('status')},
        )
    except psutil.NoSuchProcess:
        return _error_response("process_detail_handler", f"进程 PID={pid} 不存在")
    except psutil.AccessDenied:
        return _error_response("process_detail_handler", f"无权限访问进程 PID={pid}")
    except Exception as e:
        return _error_response("process_detail_handler", e)


"""
方法: process_tree_handler(), 进程树 — 按 ppid 构建父子关系, 返回以 PID 1 为根的进程树
"""
def process_tree_handler():
    try:
        procs={}
        for p in psutil.process_iter(['pid','name','ppid','status']):
            try:
                info=p.info
                procs[info['pid']]={
                    'pid': info['pid'],
                    'name': info['name'],
                    'ppid': info['ppid'],
                    'status': info['status'],
                    'children': [],
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        #构建父子关系
        for pid, node in procs.items():
            ppid=node['ppid']
            if ppid in procs:
                procs[ppid].setdefault('children', []).append(node)

        #清理空 children
        def _clean(node):
            if 'children' in node and len(node['children'])==0:
                del node['children']
            elif 'children' in node:
                for child in node['children']:
                    _clean(child)
            return node

        #找根节点
        root_pid=1 if 1 in procs else None
        if root_pid is None:
            for pid, node in procs.items():
                if node['ppid']==0:
                    root_pid=pid
                    break

        if root_pid is None:
            return _make_response("process_tree_handler",
                data={"tree": None},
                summary={"total_processes": len(procs), "error": "未找到根进程"},
            )

        root=_clean(procs[root_pid])
        return _make_response("process_tree_handler",
            data={"tree": root},
            summary={"total_processes": len(procs), "root_pid": root_pid, "root_name": root.get('name','unknown')},
        )
    except Exception as e:
        return _error_response("process_tree_handler", e)


"""
方法: process_zombie_scan_handler(), 僵尸进程检测 — 筛选 status=zombie 并解析父进程名
"""
def process_zombie_scan_handler():
    try:
        zombies=[]
        for p in psutil.process_iter(['pid','name','ppid','status']):
            try:
                if p.info['status']=='zombie':
                    z={
                        'pid': p.info['pid'],
                        'name': p.info['name'],
                        'ppid': p.info['ppid'],
                    }
                    #尝试获取父进程名
                    try:
                        parent=psutil.Process(z['ppid'])
                        z['parent_name']=parent.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        z['parent_name']='unknown'
                    zombies.append(z)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        alert=len(zombies)>0
        return _make_response("process_zombie_scan_handler",
            data={"zombies": zombies},
            summary={
                "total_zombies": len(zombies),
                "alert": alert,
                "alert_reason": f"发现 {len(zombies)} 个僵尸进程" if alert else "",
            },
        )
    except Exception as e:
        return _error_response("process_zombie_scan_handler", e)


"""
方法: process_top_cpu_handler(top_n=5), Top N CPU 消耗进程 — 快速 CPU 热点快照
"""
def process_top_cpu_handler(top_n=5):
    try:
        top_n=max(1, min(top_n, 20))

        #预热 CPU 采样
        try:
            for _ in psutil.process_iter(['cpu_percent']):
                _=_.info['cpu_percent']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        time.sleep(0.5)

        procs=[]
        for p in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']):
            try:
                procs.append({
                    'pid': p.info.get('pid'),
                    'name': p.info.get('name'),
                    'cpu_percent': p.info.get('cpu_percent') or 0.0,
                    'memory_percent': p.info.get('memory_percent') or 0.0,
                    'status': p.info.get('status'),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x['cpu_percent'], reverse=True)

        return _make_response("process_top_cpu_handler",
            data={"processes": procs[:top_n]},
            summary={"total": len(procs), "shown": min(top_n, len(procs)), "sort_by": "cpu"},
        )
    except Exception as e:
        return _error_response("process_top_cpu_handler", e)


"""
方法: process_top_memory_handler(top_n=5), Top N 内存消耗进程 — 含 RSS MB
"""
def process_top_memory_handler(top_n=5):
    try:
        top_n=max(1, min(top_n, 20))

        procs=[]
        for p in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']):
            try:
                info={
                    'pid': p.info.get('pid'),
                    'name': p.info.get('name'),
                    'cpu_percent': p.info.get('cpu_percent') or 0.0,
                    'memory_percent': p.info.get('memory_percent') or 0.0,
                    'status': p.info.get('status'),
                }
                #RSS 内存
                try:
                    info['memory_info_rss_mb']=round(p.memory_info().rss / (1024*1024), 2)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    info['memory_info_rss_mb']=None
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x['memory_percent'], reverse=True)

        return _make_response("process_top_memory_handler",
            data={"processes": procs[:top_n]},
            summary={"total": len(procs), "shown": min(top_n, len(procs)), "sort_by": "memory"},
        )
    except Exception as e:
        return _error_response("process_top_memory_handler", e)


"""
方法: process_kill_handler(pid, signal_name="SIGTERM"), 终止进程 ⚠ dangerous
  signal_name 仅允许 SIGTERM/SIGKILL
  安全护栏: ①禁杀 PID 1 ②禁杀自身 ③禁杀关键系统进程黑名单
"""
#系统关键进程黑名单
_PROC_BLACKLIST={'systemd','sshd','kernel','dbus-daemon','journald','auditd','rsyslogd','cron'}

def process_kill_handler(pid, signal_name="SIGTERM"):
    try:
        #校验信号
        if signal_name not in ("SIGTERM", "SIGKILL"):
            return _error_response("process_kill_handler",
                f"无效信号: {signal_name}, 仅支持 SIGTERM / SIGKILL")

        sig=getattr(signal, signal_name)

        #禁杀 PID 1
        if pid==1:
            return _make_response("process_kill_handler",
                data={"pid": pid, "signal": signal_name, "blocked": True},
                summary={"action": "blocked", "reason": "禁止终止 PID 1 (init)"},
                risk_level="dangerous",
            )

        #禁杀自身
        if pid==os.getpid():
            return _make_response("process_kill_handler",
                data={"pid": pid, "signal": signal_name, "blocked": True},
                summary={"action": "blocked", "reason": "禁止终止自身进程"},
                risk_level="dangerous",
            )

        #获取进程名, 检查黑名单
        try:
            proc=psutil.Process(pid)
            pname=proc.name()
        except psutil.NoSuchProcess:
            return _make_response("process_kill_handler",
                data={"pid": pid, "signal": signal_name, "already_dead": True},
                summary={"action": "already_dead", "process": f"PID={pid}", "signal": signal_name},
                risk_level="dangerous",
            )

        if pname in _PROC_BLACKLIST:
            return _make_response("process_kill_handler",
                data={"pid": pid, "name": pname, "signal": signal_name, "blocked": True},
                summary={"action": "blocked", "reason": f"禁止终止关键系统进程: {pname}"},
                risk_level="dangerous",
            )

        #发送信号
        os.kill(pid, sig)
        return _make_response("process_kill_handler",
            data={"pid": pid, "name": pname, "signal": signal_name, "killed": True},
            summary={"action": "killed", "process": f"{pname}({pid})", "signal": signal_name},
            risk_level="dangerous",
        )
    except ProcessLookupError:
        return _make_response("process_kill_handler",
            data={"pid": pid, "signal": signal_name, "already_dead": True},
            summary={"action": "already_dead", "process": f"PID={pid}", "signal": signal_name},
            risk_level="dangerous",
        )
    except psutil.AccessDenied:
        return _error_response("process_kill_handler", f"无权限访问进程 PID={pid}")
    except PermissionError:
        return _error_response("process_kill_handler", f"无权限发送 {signal_name} 到 PID={pid}")
    except Exception as e:
        return _error_response("process_kill_handler", e)


# ── process_smaps: 进程内存映射分析 ──

def process_smaps_handler(pid):
    """
    方法: process_smaps_handler(pid), 进程内存映射分析: PSS/RSS/共享/私有/Swap 使用量

    """
    try:
        pid=int(pid)
        rollup_path=f"/proc/{pid}/smaps_rollup"
        smaps_path=f"/proc/{pid}/smaps"
        import os
        if os.path.exists(rollup_path):
            with open(rollup_path) as f:
                raw=f.read()
        elif os.path.exists(smaps_path):
            with open(smaps_path) as f:
                raw=f.read()
        else:
            return _error_response("process_smaps",f"进程 PID={pid} 不存在或无权限")
        #解析关键字段 (单位 kB)
        keys=["Rss","Pss","Shared_Clean","Shared_Dirty","Private_Clean","Private_Dirty",
              "Referenced","Anonymous","Swap"]
        totals={k:0 for k in keys}
        for line in raw.split("\n"):
            for k in keys:
                if line.startswith(f"{k}:"):
                    parts=line.split()
                    if len(parts)>=2:
                        try:
                            totals[k]+=int(parts[1])
                        except ValueError:
                            pass
        #获取进程名
        proc_name=""
        try:
            with open(f"/proc/{pid}/comm") as f:
                proc_name=f.read().strip()
        except Exception:
            pass
        #告警判断
        alerts=[]
        shared_total=totals["Shared_Clean"]+totals["Shared_Dirty"]
        private_total=totals["Private_Clean"]+totals["Private_Dirty"]
        if totals["Swap"]>0:
            alerts.append(f"进程使用了 Swap: {totals['Swap']} kB")
        if totals["Pss"]>500000:
            alerts.append(f"实际物理内存占用较高: PSS={totals['Pss']} kB ({totals['Pss']//1024} MB)")
        return _make_response("process_smaps",
            data={
                "pid":pid,"process_name":proc_name,
                "rss_kb":totals["Rss"],"pss_kb":totals["Pss"],
                "shared_kb":shared_total,"private_kb":private_total,
                "anonymous_kb":totals["Anonymous"],"swap_kb":totals["Swap"],
                "referenced_kb":totals["Referenced"],
            },
            summary={
                "pid":pid,"process":proc_name,
                "rss_mb":round(totals["Rss"]/1024,1),
                "pss_mb":round(totals["Pss"]/1024,1),
                "swap_kb":totals["Swap"],
                "alerts":alerts,
            },
        )
    except FileNotFoundError:
        return _error_response("process_smaps",f"进程 PID={pid} 不存在")
    except PermissionError:
        return _error_response("process_smaps",f"无权限读取 PID={pid} 的内存映射 (需要 root)")
    except Exception as e:
        return _error_response("process_smaps",e)