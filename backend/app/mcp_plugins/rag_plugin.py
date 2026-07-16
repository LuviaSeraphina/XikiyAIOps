"""
MCP RAG 知识库插件

提供两个 Tool:
- rag_search: 检索运维知识库, 返回相关文档片段
- rag_stats:  查看知识库统计信息
"""
from app.mcp_plugins._common import make_response as _make_response, error_response as _error_response

#延迟导入 — LoongArch 上 numpy 可能缺少 Fortran 运行时, 不阻塞插件注册
_search_fn=None
_stats_fn=None

def _lazy_import():
    global _search_fn, _stats_fn
    if _search_fn is not None: return True
    try:
        from app.rag import search as _s, get_stats as _g
        _search_fn=_s; _stats_fn=_g
        return True
    except ImportError as e:
        return False
    except Exception as e:
        return False


"""
方法: rag_search_handler(query, top_k), 从运维知识库检索相关文档片段, 含赛题文档/MCP Tool/SRE 最佳实践

"""
def rag_search_handler(query:str="", top_k:int=5):
    if not query or not query.strip():
        return _make_response("rag_search",
            data={"query":"","results":[],"count":0},
            summary={"count":0,"error":"查询为空"},
        )

    try:
        if not _lazy_import():
            return _error_response("rag_search", "RAG 知识库不可用 (numpy/Fortran 运行时缺失)")
        results=_search_fn(query.strip(), top_k=min(top_k, 10))

        if not results:
            return _make_response("rag_search",
                data={"query":query,"results":[],"count":0},
                summary={"count":0,"hint":"未找到相关知识, 建议换个关键词或补充 SRE 知识库"},
            )

        items=[]
        for i, doc in enumerate(results):
            items.append({
                "rank":i+1,
                "title":doc.metadata.get("title",""),
                "source":doc.metadata.get("source","未知"),
                "content":doc.content,
                "score":round(doc.score,4),
            })

        return _make_response("rag_search",
            data={"query":query,"results":items,"count":len(items)},
            summary={
                "count":len(items),
                "top_source":items[0]["source"] if items else "",
                "top_score":round(items[0]["score"],2) if items else 0,
            },
        )
    except Exception as e:
        return _error_response("rag_search", f"检索失败: {e}")


"""
方法: rag_stats_handler(), 查看知识库统计信息

"""
def rag_stats_handler():
    try:
        if not _lazy_import():
            return _error_response("rag_stats", "RAG 知识库不可用")
        stats=_stats_fn()
        return _make_response("rag_stats",
            data=stats,
            summary={
                "total_chunks":stats.get("total_chunks",0),
                "status":stats.get("status","unknown"),
            },
        )
    except Exception as e:
        return _error_response("rag_stats", f"查询失败: {e}")


"""
方法: doc_sync_handler(), 扫描 docs/ 目录, 增量索引到 RAG 知识库

"""
def doc_sync_handler(path:str=""):
    """同步文档到 RAG 知识库 — 扫描指定目录的 .md/.txt 文件并重建索引"""
    import os
    from pathlib import Path
    
    #默认扫描路径
    if not path:
        backend_root=Path(__file__).resolve().parent.parent.parent
        docs_dir=backend_root / ".." / "docs"
    else:
        docs_dir=Path(path)
    
    if not docs_dir.exists():
        return _error_response("doc_sync", f"目录不存在: {docs_dir}")
    
    #收集文档
    synced=[]
    failed=[]
    total_size=0
    
    for ext in ["*.md","*.txt","*.rst"]:
        for f in docs_dir.rglob(ext):
            try:
                content=f.read_text(encoding="utf-8",errors="replace")
                if len(content.strip())<10:
                    continue
                synced.append({
                    "file":str(f.relative_to(docs_dir)),
                    "size":len(content),
                    "lines":content.count("\n")+1,
                })
                total_size+=len(content)
            except Exception:
                failed.append(str(f.relative_to(docs_dir)))
    
    #尝试重建 RAG 索引
    rag_note=""
    try:
        if _lazy_import():
            from app.rag import rebuild_index
            rebuild_index([str(docs_dir)])
            rag_note="RAG 索引已更新"
    except Exception as e:
        rag_note=f"RAG 索引更新跳过: {e}"
    
    return _make_response("doc_sync",
        data={
            "docs_dir":str(docs_dir),
            "synced":synced,
            "failed":failed,
            "total_files":len(synced),
            "total_size_kb":round(total_size/1024,1),
        },
        summary={
            "synced":len(synced),
            "failed":len(failed),
            "rag_status":rag_note,
        },
    )
