"""
Docker 沙箱插件 — 高危命令隔离执行

提供:
- sandbox_exec: 在 Docker 容器中执行命令 (网络隔离/只读文件系统/资源限制)
- sandbox_status: 检查 Docker 沙箱健康状态
"""
import subprocess
import shlex
from app.mcp_plugins._common import make_response, error_response

# 沙箱默认配置
_SANDBOX_IMAGE="alpine:latest"
_SANDBOX_TIMEOUT=30          #默认超时秒
_SANDBOX_MAX_TIMEOUT=120     #最大超时
_SANDBOX_MEMORY="256m"       #内存限制
_SANDBOX_CPUS="0.5"          #CPU 限制
_SANDBOX_READONLY=True       #只读根文件系统

#只读模式下允许写入的目录 (tmpfs)
_SANDBOX_TMPFS=["/tmp","/var/tmp"]


def sandbox_exec_handler(command, timeout=None, image=None, read_only=None):
    """
    Docker 沙箱执行 — 在隔离容器中运行命令
    安全特性: 网络隔离/只读根文件系统/CPU+内存限制/超时保护
    """
    cmd=command.strip()
    if not cmd:
        return error_response("sandbox_exec", "命令不能为空")
    
    #安全校验: 禁止容器逃逸关键字
    _forbidden=["--privileged","--pid=host","--net=host","--ipc=host",
                "--volume","-v","/var/run/docker.sock","/proc","/sys",
                "nsenter","unshare"]
    for kw in _forbidden:
        if kw in cmd:
            return make_response("sandbox_exec",
                data={"command":cmd,"output":"","exit_code":-1},
                summary={"error":f"禁止的沙箱逃逸关键字: {kw}","blocked":True})
    
    t=int(timeout or _SANDBOX_TIMEOUT)
    if t<1 or t>_SANDBOX_MAX_TIMEOUT:
        t=_SANDBOX_TIMEOUT
    
    img=image or _SANDBOX_IMAGE
    ro=read_only if read_only is not None else _SANDBOX_READONLY
    
    #构建 docker run 参数
    docker_args=[
        "docker","run","--rm",
        "--network=none",               #网络隔离
        f"--memory={_SANDBOX_MEMORY}",
        f"--cpus={_SANDBOX_CPUS}",
        "--pids-limit=100",             #限制进程数
        "--security-opt=no-new-privileges",  #禁止提权
    ]
    
    if ro:
        docker_args.append("--read-only")
        for tmpfs in _SANDBOX_TMPFS:
            docker_args.extend(["--tmpfs",f"{tmpfs}:exec"])
    
    docker_args.append(img)
    docker_args.extend(["sh","-c",cmd])
    
    try:
        result=subprocess.run(
            docker_args,
            capture_output=True,text=True,
            timeout=t+5,  #docker 自身开销给5秒余量
        )
        return make_response("sandbox_exec",
            data={
                "command":cmd,
                "image":img,
                "read_only":ro,
                "timeout_sec":t,
                "exit_code":result.returncode,
                "stdout":result.stdout[-8000:],  #截断过长输出
                "stderr":result.stderr[-4000:],
            },
            summary={
                "exit_code":result.returncode,
                "output":(result.stdout+result.stderr)[:500],
                "sandbox":"Docker (network=none, ro)" if ro else "Docker (network=none)",
            },
        )
    except subprocess.TimeoutExpired:
        return make_response("sandbox_exec",
            data={"command":cmd,"exit_code":-1,"timeout_sec":t},
            summary={"error":f"沙箱执行超时 ({t}s)","exit_code":-1})
    except FileNotFoundError:
        return error_response("sandbox_exec", "Docker 未安装或 docker 命令不可用")
    except Exception as e:
        return error_response("sandbox_exec", str(e))


def sandbox_status_handler():
    """检查 Docker 沙箱健康状态"""
    status={"docker_available":False,"image_available":False,"version":""}
    
    #检查 Docker
    try:
        r=subprocess.run(["docker","version","--format","{{.Server.Version}}"],
            capture_output=True,text=True,timeout=5)
        if r.returncode==0:
            status["docker_available"]=True
            status["version"]=r.stdout.strip()
    except Exception:
        pass
    
    #检查镜像
    if status["docker_available"]:
        try:
            r=subprocess.run(["docker","image","inspect",_SANDBOX_IMAGE],
                capture_output=True,text=True,timeout=5)
            status["image_available"]=r.returncode==0
        except Exception:
            pass
    
    return make_response("sandbox_status",
        data=status,
        summary={
            "healthy":status["docker_available"] and status["image_available"],
            "image":_SANDBOX_IMAGE,
            "limits":f"memory={_SANDBOX_MEMORY}, cpus={_SANDBOX_CPUS}, timeout={_SANDBOX_TIMEOUT}s",
        },
    )
