"""
系统快照 API — 仪表盘实时数据源

GET /api/system/snapshot  — 返回 CPU/内存/磁盘/网络/系统信息
"""
from fastapi import APIRouter, Request
import psutil
import os
import platform
import time
import json
from pathlib import Path

router=APIRouter()


@router.get("/snapshot")
async def system_snapshot():
    """返回系统实时快照，供仪表盘直接展示"""
    #CPU
    cpu_percent=psutil.cpu_percent(interval=0.3)
    cpu_count=psutil.cpu_count(logical=True)
    cpu_physical=psutil.cpu_count(logical=False)
    load=psutil.getloadavg()

    #内存
    mem=psutil.virtual_memory()
    swap=psutil.swap_memory()

    #磁盘
    disk=psutil.disk_usage("/")

    #网络
    net_io=psutil.net_io_counters()
    connections=len(psutil.net_connections(kind="inet"))

    #启动时间
    boot_time=psutil.boot_time()
    uptime_seconds=int(time.time()-boot_time)

    #进程
    proc_count=len(psutil.pids())

    return {
        "code": 0,
        "data": {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "kernel": platform.version(),
            "architecture": platform.machine(),
            "boot_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot_time)),
            "uptime_seconds": uptime_seconds,

            "cpu": {
                "cores_logical": cpu_count,
                "cores_physical": cpu_physical or cpu_count,
                "percent": round(cpu_percent, 1),
                "load_1m": round(load[0], 2),
                "load_5m": round(load[1], 2),
                "load_15m": round(load[2], 2),
            },

            "memory": {
                "total_gb": round(mem.total/(1024**3), 1),
                "used_gb": round(mem.used/(1024**3), 1),
                "available_gb": round(mem.available/(1024**3), 1),
                "percent": mem.percent,
                "swap_total_gb": round(swap.total/(1024**3), 1) if swap.total>0 else 0,
                "swap_used_gb": round(swap.used/(1024**3), 1) if swap.total>0 else 0,
                "swap_percent": swap.percent,
            },

            "disk": {
                "total_gb": round(disk.total/(1024**3), 1),
                "used_gb": round(disk.used/(1024**3), 1),
                "free_gb": round(disk.free/(1024**3), 1),
                "percent": disk.percent,
            },

            "network": {
                "bytes_sent_mb": round(net_io.bytes_sent/(1024**2), 1),
                "bytes_recv_mb": round(net_io.bytes_recv/(1024**2), 1),
                "connections": connections,
            },

            "process_count": proc_count,
        },
        "message": "ok",
    }


#── LLM 配置 API ─────────────────────────

from app.llm.config import get_llm_config, save_preset_config, PRESET_MODELS

# 内置预设 ID 集合 (不可删除)
BUILTIN_IDS={p["id"] for p in PRESET_MODELS}

@router.get("/llm-config")
async def llm_config_get():
    """读取当前 LLM 配置 + 预设模型列表"""
    config=get_llm_config()
    active_preset=config.get("active_preset","deepseek")
    presets=config.get("presets",{})
    preset=presets.get(active_preset,{})
    # 收集自定义预设 (不在 BUILTIN_IDS 中的)
    custom_ids=[pid for pid in presets.keys() if pid not in BUILTIN_IDS]
    return {
        "code":0,
        "data":{
            "active_preset":active_preset,
            "current":{
                "provider":preset.get("provider",""),
                "base_url":preset.get("base_url",""),
                "model":preset.get("model",""),
                "api_key_set":bool(preset.get("api_key","")),
            },
            "preset_configs":{pid: {"api_key_set": bool(p.get("api_key","")), "model": p.get("model",""), "base_url": p.get("base_url",""), "provider": p.get("provider",""), "label": p.get("label",pid)} for pid, p in presets.items()},
            "custom_presets":[{"id":pid,"label":presets[pid].get("label",pid),"provider":presets[pid].get("provider",""),"base_url":presets[pid].get("base_url","")} for pid in custom_ids],
            "presets":PRESET_MODELS,
        },
    }


@router.post("/llm-config/preset")
async def llm_config_add_preset(request: Request):
    """新增自定义预设"""
    body=await request.json()
    preset_id=body.get("id","").strip().lower().replace(" ","_")
    label=body.get("label",preset_id)
    provider=body.get("provider","openai")
    base_url=body.get("base_url","")

    if not preset_id:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400,content={"code":400,"data":None,"message":"预设 ID 不能为空"})
    if preset_id in BUILTIN_IDS:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400,content={"code":400,"data":None,"message":"该 ID 与内置预设冲突"})

    config=get_llm_config()
    if "presets" not in config:
        config["presets"]={}
    if preset_id in config["presets"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400,content={"code":400,"data":None,"message":"该预设已存在"})

    config["presets"][preset_id]={"provider":provider,"base_url":base_url,"model":"","api_key":"","label":label}
    # 新建预设不自动激活，仅加入预设列表
    LLM_CONFIG_PATH=Path(__file__).resolve().parent.parent.parent / "llm_config.json"
    LLM_CONFIG_PATH.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"code":0,"data":None,"message":f"已添加预设: {label}"}


@router.delete("/llm-config/preset/{preset_id}")
async def llm_config_delete_preset(preset_id: str):
    """删除自定义预设"""
    if preset_id in BUILTIN_IDS:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400,content={"code":400,"data":None,"message":"内置预设不可删除"})
    config=get_llm_config()
    if preset_id not in config.get("presets",{}):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404,content={"code":404,"data":None,"message":"预设不存在"})
    del config["presets"][preset_id]
    if config.get("active_preset")==preset_id:
        config["active_preset"]="deepseek"
    LLM_CONFIG_PATH=Path(__file__).resolve().parent.parent.parent / "llm_config.json"
    LLM_CONFIG_PATH.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"code":0,"data":None,"message":"预设已删除"}


@router.post("/llm-config")
async def llm_config_save(request: Request):
    """保存 LLM 配置 (provider/base_url/model/api_key/label)"""
    body=await request.json()
    preset_id=body.get("preset_id","")
    provider=body.get("provider","")
    model=body.get("model","")
    base_url=body.get("base_url","")
    api_key=body.get("api_key","")
    label=body.get("label","")

    if not preset_id:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"code":400,"data":None,"message":"preset_id 不能为空"},
        )

    if not provider:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"code":400,"data":None,"message":"provider 不能为空"},
        )

    save_preset_config(preset_id, {
        "provider":provider,
        "base_url":base_url,
        "model":model,
        "api_key":api_key,
        "label":label,
    })
    return {
        "code":0,
        "data":None,
        "message":"LLM 配置已保存, 下次对话生效",
    }


@router.post("/llm-config/test")
async def llm_config_test(request: Request):
    """连通测试 — 用提交的配置调一次 /models 验证可达性"""
    import httpx
    body=await request.json()
    base_url=body.get("base_url","")
    api_key=body.get("api_key","")

    # 如果前端未提供 API Key，从已保存的配置中读取
    if not api_key:
        saved=get_llm_config()
        active_preset=saved.get("active_preset","deepseek")
        preset=saved.get("presets",{}).get(active_preset,{})
        api_key=preset.get("api_key","")

    if not base_url:
        return {"code":1,"data":{"ok":False,"detail":"base_url 为空"}}

    headers={}
    if api_key:
        headers["Authorization"]=f"Bearer {api_key}"

    test_url=f"{base_url.rstrip('/')}/v1/models"

    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            resp=await cli.get(test_url, headers=headers)
            ok=resp.status_code in (200,401,403)
            return {
                "code":0,
                "data":{
                    "ok":ok,
                    "status_code":resp.status_code,
                    "detail":f"HTTP {resp.status_code}" if ok else resp.text[:200],
                },
            }
    except httpx.ConnectError:
        return {"code":0,"data":{"ok":False,"detail":f"无法连接 {base_url}"}}
    except httpx.ReadTimeout:
        return {"code":0,"data":{"ok":False,"detail":"连接超时 (10s)"}}
    except Exception as e:
        return {"code":0,"data":{"ok":False,"detail":str(e)[:200]}}


@router.post("/llm-config/models")
async def llm_config_models(request: Request):
    """从 base_url 拉取可用模型列表"""
    import httpx
    body=await request.json()
    base_url=body.get("base_url","")
    api_key=body.get("api_key","")

    # 如果前端未提供 API Key，从已保存的配置中读取
    if not api_key:
        saved=get_llm_config()
        active_preset=saved.get("active_preset","deepseek")
        preset=saved.get("presets",{}).get(active_preset,{})
        api_key=preset.get("api_key","")

    if not base_url:
        return {"code":0,"data":{"models":[],"detail":"base_url 为空"}}

    headers={}
    if api_key:
        headers["Authorization"]=f"Bearer {api_key}"

    models_url=f"{base_url.rstrip('/')}/v1/models"

    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            resp=await cli.get(models_url, headers=headers)
            if resp.status_code==401:
                return {"code":0,"data":{"models":[],"detail":"需要正确的API Key"}}
            elif resp.status_code==403:
                return {"code":0,"data":{"models":[],"detail":"API Key 无效或无权限访问"}}
            elif resp.status_code!=200:
                return {"code":0,"data":{"models":[],"detail":f"HTTP {resp.status_code}"}}
            data=resp.json()
            # OpenAI 兼容格式: {"data":[{"id":"model-name",...}]}
            raw_models=data.get("data",[])
            model_ids=[m.get("id","") for m in raw_models if m.get("id")]
            model_ids.sort()
            return {
                "code":0,
                "data":{
                    "models":model_ids,
                    "detail":f"获取到 {len(model_ids)} 个模型",
                },
            }
    except httpx.ConnectError:
        return {"code":0,"data":{"models":[],"detail":f"无法连接 {base_url}"}}
    except httpx.ReadTimeout:
        return {"code":0,"data":{"models":[],"detail":"连接超时 (15s)"}}
    except Exception as e:
        return {"code":0,"data":{"models":[],"detail":str(e)[:200]}}
