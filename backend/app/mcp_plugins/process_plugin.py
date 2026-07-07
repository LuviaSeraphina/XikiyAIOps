"""
MCP 进程巡检与控制工具

功能:
- process_inspect: 按状态/CPU/内存过滤 Top N 进程
- process_detail: 单进程详细信息
- process_tree: 进程树 (PID 1 为根)
- process_zombie_scan: 扫描僵尸进程
- process_top_cpu/top_memory: 资源占用排行
- process_kill: 安全终止进程 (SIGTERM/SIGKILL)
- process_smaps: 内存映射分析 (RSS/PSS/Swap)
- process_zombie_cleanup: 清理僵尸进程 (SIGCHLD)
- process_renice: 调整 CPU nice 值
- process_ionice: 调整 I/O 调度优先级
- process_io_top: I/O 读写速率 Top N

使用 psutil.process_iter() 遍历进程, 返回结构化 dict 列表,
每次调用前自动预热 CPU 采样, 避免首次返回全 0。
"""

import psutil
import time
import os
import signal
from app.mcp_plugins._common import (
    make_response as _make_response,
    error_response as _error_response,
    run_command as _run_command,
    _cmd_ok,
)

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
"""
方法: process_smaps_handler(pid), 进程内存映射分析: PSS/RSS/共享/私有/Swap 使用量

"""
def process_smaps_handler(pid):
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


# ── 5. process_zombie_cleanup ──

"""
方法: process_zombie_cleanup(), 清理僵尸进程 — 向其父进程发送 SIGCHLD 信号促其收割子进程

"""
def process_zombie_cleanup(parent_pid=0):
    try:
        if not parent_pid:
            return _error_response("process_zombie_cleanup", ValueError("参数 parent_pid 不能为空"))

        if not psutil.pid_exists(parent_pid):
            return _error_response("process_zombie_cleanup", ValueError(f"PID {parent_pid} 不存在"))

        #验证该进程确实有僵尸子进程
        try:
            parent_proc=psutil.Process(parent_pid)
            parent_name=parent_proc.name()
            children=parent_proc.children()
            zombies=[c for c in children if c.status()==psutil.STATUS_ZOMBIE]
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return _error_response("process_zombie_cleanup", e)

        if not zombies:
            return _make_response("process_zombie_cleanup",
                data={"parent_pid":parent_pid,"parent_name":parent_name,"zombie_count":0,"cleaned":False},
                summary={"info":f"PID {parent_pid} ({parent_name}) 没有僵尸子进程, 无需清理"},
                risk_level="restricted",
            )

        zombie_count=len(zombies)
        zombie_pids=[c.pid for c in zombies]

        #发送 SIGCHLD 信号给父进程
        try:
            os.kill(parent_pid, signal.SIGCHLD)
        except (PermissionError, ProcessLookupError) as e:
            return _error_response("process_zombie_cleanup", e)

        #等待短暂时间让父进程处理信号
        time.sleep(0.5)

        #验证僵尸是否已清理
        remaining=0
        try:
            parent_proc=psutil.Process(parent_pid)
            for c in parent_proc.children():
                try:
                    if c.status()==psutil.STATUS_ZOMBIE:
                        remaining+=1
                except (psutil.NoSuchProcess, psutil.ZombieProcess):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        cleaned=zombie_count - remaining

        return _make_response("process_zombie_cleanup",
            data={
                "parent_pid":parent_pid,
                "parent_name":parent_name,
                "zombie_pids":zombie_pids,
                "zombie_count_before":zombie_count,
                "zombie_count_after":remaining,
                "cleaned":cleaned,
                "success":cleaned>0,
            },
            summary={
                "parent_pid":parent_pid,
                "cleaned":cleaned,
                "remaining":remaining,
                "success":cleaned>0,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("process_zombie_cleanup", e)


# ── 6. process_renice ──

"""
方法: process_renice(), 调整进程 CPU 调度优先级 (nice 值, -20~19)

"""
def process_renice(pid=0, nice=0):
    try:
        if not pid:
            return _error_response("process_renice", ValueError("参数 pid 不能为空"))

        #nice 范围校验: -20 到 19, 禁止 -20 (最高优先级)
        if nice<-19 or nice>19:
            return _make_response("process_renice",
                data={"pid":pid,"nice":nice,"blocked":True},
                summary={"error":"nice 值必须在 -19 到 19 之间"},
                risk_level="restricted",
            )
        if nice==-20:
            return _make_response("process_renice",
                data={"pid":pid,"nice":nice,"blocked":True},
                summary={"error":"禁止设置 nice=-20 (最高优先级), 可能影响系统稳定性"},
                risk_level="restricted",
            )

        if not psutil.pid_exists(pid):
            return _error_response("process_renice", ValueError(f"PID {pid} 不存在"))

        try:
            proc=psutil.Process(pid)
            proc_name=proc.name()
            old_nice=proc.nice()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return _error_response("process_renice", e)

        #设置新 nice 值
        try:
            proc.nice(nice)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return _error_response("process_renice", e)

        #验证
        try:
            new_nice=psutil.Process(pid).nice()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            new_nice="unknown"

        return _make_response("process_renice",
            data={
                "pid":pid,
                "process":proc_name,
                "old_nice":old_nice,
                "new_nice":new_nice,
                "success":new_nice==nice,
            },
            summary={
                "pid":pid,
                "process":proc_name,
                "old_nice":old_nice,
                "new_nice":new_nice,
                "success":new_nice==nice,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("process_renice", e)


# ── 7. process_ionice ──

#ionice class 映射
_IONICE_CLASS={"idle":3,"best-effort":2,"realtime":1}
_IONICE_CLASS_REV={3:"idle",2:"best-effort",1:"realtime",0:"none"}

"""
方法: process_ionice(), 调整进程 I/O 调度优先级

"""
def process_ionice(pid=0, ionice_class="idle", ionice_level=4):
    try:
        if not pid:
            return _error_response("process_ionice", ValueError("参数 pid 不能为空"))

        #安全检查: 禁止 realtime (class=1), 可能导致 I/O 饥饿
        if ionice_class=="realtime" or ionice_class==1:
            return _make_response("process_ionice",
                data={"pid":pid,"class":ionice_class,"blocked":True},
                summary={"error":"禁止设置 ionice class=realtime, 可能导致其他进程 I/O 饥饿"},
                risk_level="restricted",
            )

        if ionice_class not in _IONICE_CLASS:
            return _make_response("process_ionice",
                data={"pid":pid,"class":ionice_class,"blocked":True},
                summary={"error":f"不支持的 ionice class: {ionice_class}, 仅允许: idle, best-effort"},
                risk_level="restricted",
            )

        #ionice_level 范围: 0-7 (best-effort), idle 忽略此参数
        if ionice_level<0 or ionice_level>7:
            ionice_level=4

        if not psutil.pid_exists(pid):
            return _error_response("process_ionice", ValueError(f"PID {pid} 不存在"))

        try:
            proc=psutil.Process(pid)
            proc_name=proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return _error_response("process_ionice", e)

        #获取当前 ionice
        try:
            old_ionice=proc.ionice()
            old_class=_IONICE_CLASS_REV.get(old_ionice.ioclass, str(old_ionice.ioclass))
            old_value=old_ionice.value
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            old_class="unknown"
            old_value=0

        #设置新 ionice
        class_num=_IONICE_CLASS[ionice_class]
        try:
            if ionice_class=="idle":
                proc.ionice(psutil.IOPRIO_CLASS_IDLE)
            else:
                proc.ionice(psutil.IOPRIO_CLASS_BE, ionice_level)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return _error_response("process_ionice", e)
        except AttributeError:
            #psutil 版本不支持 IOPRIO_CLASS 常量, 回退到 ionice 命令
            r=_run_command(["ionice","-c",str(class_num),"-n",str(ionice_level),"-p",str(pid)], timeout=5)
            if not _cmd_ok(r):
                return _make_response("process_ionice",
                    data={"pid":pid,"failed":True},
                    summary={"error":r["stderr"] or "ionice 命令执行失败"},
                    risk_level="restricted",
                )

        return _make_response("process_ionice",
            data={
                "pid":pid,
                "process":proc_name,
                "old_class":old_class,
                "old_value":old_value,
                "new_class":ionice_class,
                "new_value":ionice_level if ionice_class!="idle" else 0,
                "success":True,
            },
            summary={
                "pid":pid,
                "process":proc_name,
                "old_class":old_class,
                "new_class":ionice_class,
                "success":True,
            },
            risk_level="restricted",
        )
    except Exception as e:
        return _error_response("process_ionice", e)


# ── 8. process_io_top ──

"""
方法: process_io_top(), I/O 读写速率 Top N (读取 /proc/PID/io)

"""
def process_io_top(top_n=10):
    try:
        if top_n<1:
            top_n=1
        if top_n>50:
            top_n=50

        #第一次采样
        sample1={}
        for proc in psutil.process_iter(['pid','name','status']):
            try:
                io_path=f"/proc/{proc.pid}/io"
                if not os.path.isfile(io_path):
                    continue
                with open(io_path,"r") as f:
                    data={}
                    for line in f:
                        parts=line.split(":")
                        if len(parts)==2:
                            key=parts[0].strip()
                            val=parts[1].strip()
                            try:
                                data[key]=int(val)
                            except ValueError:
                                pass
                sample1[proc.pid]={
                    "name":proc.info['name'],
                    "read_bytes":data.get("read_bytes",0),
                    "write_bytes":data.get("write_bytes",0),
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError, FileNotFoundError):
                continue

        #等待 1 秒
        time.sleep(1)

        #第二次采样, 计算速率
        results=[]
        for proc in psutil.process_iter(['pid','name','status']):
            try:
                io_path=f"/proc/{proc.pid}/io"
                if not os.path.isfile(io_path):
                    continue
                with open(io_path,"r") as f:
                    data={}
                    for line in f:
                        parts=line.split(":")
                        if len(parts)==2:
                            key=parts[0].strip()
                            val=parts[1].strip()
                            try:
                                data[key]=int(val)
                            except ValueError:
                                pass

                prev=sample1.get(proc.pid)
                if not prev:
                    continue

                read_delta=data.get("read_bytes",0) - prev["read_bytes"]
                write_delta=data.get("write_bytes",0) - prev["write_bytes"]

                if read_delta<0:
                    read_delta=0
                if write_delta<0:
                    write_delta=0

                total_delta=read_delta + write_delta
                if total_delta>0:
                    results.append({
                        "pid":proc.pid,
                        "name":proc.info['name'],
                        "read_bytes_per_sec":read_delta,
                        "write_bytes_per_sec":write_delta,
                        "total_bytes_per_sec":total_delta,
                        "read_mb_per_sec":round(read_delta/1048576, 2),
                        "write_mb_per_sec":round(write_delta/1048576, 2),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError, FileNotFoundError):
                continue

        #排序
        results.sort(key=lambda x: x["total_bytes_per_sec"], reverse=True)
        top_results=results[:top_n]

        return _make_response("process_io_top",
            data={
                "sample_interval_sec":1,
                "total_processes_sampled":len(sample1),
                "processes_with_io":len(results),
                "top_n":len(top_results),
                "processes":top_results,
            },
            summary={
                "sampled":len(sample1),
                "with_io":len(results),
                "top_process":top_results[0]["name"] if top_results else "none",
                "top_io_mb":round(top_results[0]["total_bytes_per_sec"]/1048576, 2) if top_results else 0,
            },
            risk_level="read_only",
        )
    except Exception as e:
        return _error_response("process_io_top", e)