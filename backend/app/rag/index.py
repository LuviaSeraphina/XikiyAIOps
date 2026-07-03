"""
文件索引 — 按 MD5 追踪文档变更, 支持增量判断
"""
import os
import json
import logging
import hashlib
from typing import Dict, List
from . import config as _cfg

_logger=logging.getLogger("xikiy_aiops.rag")

_INDEX_PATH=os.path.join(_cfg.RAG_DB_DIR, "file_index.json")


"""
方法: load(), 读取已索引文件的 MD5 快照, 返回 {source: md5}

"""

def load()->Dict[str,str]:
    if not os.path.exists(_INDEX_PATH):
        return {}
    try:
        with open(_INDEX_PATH,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

"""
方法: save(index), 持久化文件索引

"""

def save(index:Dict[str,str]):
    os.makedirs(os.path.dirname(_INDEX_PATH),exist_ok=True)
    with open(_INDEX_PATH,"w",encoding="utf-8") as f:
        json.dump(index,f,ensure_ascii=False,indent=2)

"""
方法: clear(), 删除索引 (force 重建时调用)

"""

def clear():
    if os.path.exists(_INDEX_PATH):
        os.remove(_INDEX_PATH)

"""
方法: file_md5(fpath), 计算文件 MD5 哈希

"""

def file_md5(fpath:str)->str:
    with open(fpath,"rb") as f:
        return hashlib.md5(f.read()).hexdigest()

"""
方法: build_from_chunks(chunks, docs_dir), 从已加载的 chunks 反推文件索引 (force 模式用)

"""

def build_from_chunks(chunks:List[Dict[str,str]], docs_dir:str)->Dict[str,str]:
    index={}
    for c in chunks:
        src=c.get("source","")
        if src and src!="mcp_tools" and not src.startswith("sre_kb/"):
            fpath=os.path.join(docs_dir, src.replace("docs/",""))
            if os.path.exists(fpath):
                index[src]=file_md5(fpath)
    #MCP tools 标记
    tool_names=sorted(set(
        c.get("title","") for c in chunks if c.get("source")=="mcp_tools"
    ))
    index["__mcp_tools__"]=hashlib.md5(",".join(tool_names).encode()).hexdigest()
    return index
