"""
知识库构建 — 文档加载 → 分块 → 向量化 → 入库

增量策略: 按文件 MD5 追踪变更, force=False 只处理新增/修改的文件
"""
import os
import json
import logging
import hashlib
from typing import List, Dict, Optional
from . import config as _cfg
from .models import embedding_model, vector_store, Document
from .chunker import chunk_markdown_file
from .index import load as _load_file_index, save as _save_file_index, clear as _clear_file_index
from .index import file_md5 as _file_md5, build_from_chunks as _build_index_from_chunks

_logger=logging.getLogger("xikiy_aiops.rag")

COLLECTION_NAME="sre_knowledge"


# ── 文档加载 (支持增量) ──────────────────────────

"""
方法: _load_project_docs(docs_dir, file_index), 加载 docs/ 目录 Markdown, 增量模式跳过未改文件

"""
def _load_project_docs(docs_dir:str, file_index:Dict[str,str]=None)->List[Dict[str,str]]:
    chunks=[]
    if not os.path.isdir(docs_dir):
        _logger.warning(f"文档目录不存在: {docs_dir}")
        return chunks

    for fname in sorted(os.listdir(docs_dir)):
        if not fname.endswith(".md"):
            continue
        fpath=os.path.join(docs_dir, fname)
        source=f"docs/{fname}"
        new_hash=_file_md5(fpath)

        #增量模式: 未变更则跳过
        if file_index is not None and file_index.get(source)==new_hash:
            _logger.info(f"  {fname}: 未变更, 跳过")
            continue

        try:
            file_chunks=chunk_markdown_file(
                fpath,
                chunk_size=_cfg.CHUNK_SIZE,
                overlap=_cfg.CHUNK_OVERLAP,
            )
            for c in file_chunks:
                c["source"]=source
            chunks.extend(file_chunks)
            if file_index is not None:
                file_index[source]=new_hash
            _logger.info(f"  {fname}: {len(file_chunks)} 块")
        except Exception as e:
            _logger.warning(f"  跳过 {fname}: {e}")

    return chunks


"""
方法: _load_tool_schemas(file_index), 加载 MCP Tool Schema, 增量模式跳过

"""
def _load_tool_schemas(file_index:Dict[str,str]=None)->List[Dict[str,str]]:
    #增量模式: MCP Tools 不变则不重索引
    if file_index is not None and file_index.get("__mcp_tools__"):
        _logger.info("  MCP Tools: 未变更, 跳过")
        return []

    try:
        from app.mcp_plugins.base import registry
        tools=registry.list_all()
    except Exception:
        _logger.warning("无法加载 MCP Tool Schema")
        return []

    chunks=[]
    for t in tools:
        name=t.get("name","")
        desc=t.get("description","")
        risk=t.get("risk_level","")
        schema=json.dumps(t.get("inputSchema",{}), ensure_ascii=False)

        content=f"""工具: {name}
风险等级: {risk}
描述: {desc}
参数: {schema}"""

        chunks.append({
            "title":f"MCP Tool: {name}",
            "content":content,
            "source":"mcp_tools",
        })

    if file_index is not None:
        #用工具名列表的 hash 标记是否变更
        tool_names=sorted(t.get("name","") for t in tools)
        file_index["__mcp_tools__"]=hashlib.md5(",".join(tool_names).encode()).hexdigest()

    _logger.info(f"  MCP Tools: {len(chunks)} 个")
    return chunks


"""
方法: _load_sre_knowledge(kb_dir, file_index), 加载 sre_kb/ 目录, 增量模式跳过未改文件

"""
def _load_sre_knowledge(kb_dir:Optional[str]=None, file_index:Dict[str,str]=None)->List[Dict[str,str]]:
    if kb_dir is None:
        #与 config.py 一致: backend/app/rag/ → ../../data/sre_kb = backend/data/sre_kb
        _here=os.path.dirname(os.path.abspath(__file__))
        kb_dir=os.path.join(_here, "..", "..", "data", "sre_kb")

    chunks=[]
    if not os.path.isdir(kb_dir):
        return chunks

    for fname in sorted(os.listdir(kb_dir)):
        if not fname.endswith(".md"):
            continue
        fpath=os.path.join(kb_dir, fname)
        source=f"sre_kb/{fname}"
        new_hash=_file_md5(fpath)

        if file_index is not None and file_index.get(source)==new_hash:
            _logger.info(f"  sre_kb/{fname}: 未变更, 跳过")
            continue

        try:
            file_chunks=chunk_markdown_file(
                fpath, _cfg.CHUNK_SIZE, _cfg.CHUNK_OVERLAP)
            for c in file_chunks:
                c["source"]=source
            chunks.extend(file_chunks)
            if file_index is not None:
                file_index[source]=new_hash
            _logger.info(f"  sre_kb/{fname}: {len(file_chunks)} 块")
        except Exception as e:
            _logger.warning(f"  跳过 {fname}: {e}")

    return chunks


"""
方法: build_knowledge_base(docs_dir, kb_dir, force), 知识库构建 — force=True 全量重建, force=False 增量更新

"""
def build_knowledge_base(
    docs_dir:Optional[str]=None,
    kb_dir:Optional[str]=None,
    force:bool=False,
)->Dict[str,int]:
    if docs_dir is None:
        project_root=os.path.join(os.path.dirname(__file__), "..", "..", "..")
        docs_dir=os.path.join(project_root, "docs")

    _logger.info("="*50)
    mode="全量重建" if force else "增量更新"
    _logger.info(f"开始构建 RAG 知识库 ({mode})")

    #1. 准备集合
    if force:
        vector_store.delete_collection(COLLECTION_NAME)
        #清除文件索引
        _clear_file_index()

    collection=vector_store.get_or_create_collection(COLLECTION_NAME)
    existing_count=collection.count()
    _logger.info(f"集合 '{COLLECTION_NAME}' 现有 {existing_count} 条")

    #2. 加载文档 — 增量模式下传入文件索引
    file_index=None if force else _load_file_index()

    all_chunks=[]
    # all_chunks.extend(_load_project_docs(docs_dir, file_index))
    all_chunks.extend(_load_tool_schemas(file_index))
    all_chunks.extend(_load_sre_knowledge(kb_dir, file_index))

    #6. 保存文件索引 (force 模式也保存, 作为下次增量的基线)
    _save_file_index(file_index if file_index is not None else _build_index_from_chunks(all_chunks, docs_dir))

    if not all_chunks:
        _logger.info("无新增/变更文档, 知识库已是最新")
        return {"chunks_added":0, "tool_chunks":0, "sre_chunks":0, "doc_chunks":0, "total_chunks":existing_count}

    #3. 清理旧块 — 增量模式下删除被更新文件的旧向量
    if not force and existing_count>0:
        changed_sources=set(c["source"] for c in all_chunks)
        if changed_sources:
            _delete_chunks_by_sources(collection, changed_sources)

    _logger.info(f"总计 {len(all_chunks)} 个块需要索引, 开始向量化...")

    #4. 拟合嵌入模型 (TF-IDF 需先构建词汇表; 其他后端自动跳过)
    texts=[c["content"] for c in all_chunks]
    metadatas=[{"title":c.get("title",""), "source":c.get("source","")} for c in all_chunks]
    embedding_model.fit(texts)

    #5. 批量向量化 + 入库
    embeddings=embedding_model.encode(texts)

    #生成唯一 ID: 用 source+内容 hash 避免重复
    ids=[f"chunk_{hashlib.md5((c['source']+c['content'][:100]).encode()).hexdigest()[:12]}" for c in all_chunks]

    collection.add(
        ids=ids,
        embeddings=embeddings,  # type: ignore[arg-type]
        documents=texts,
        metadatas=metadatas,  # type: ignore[arg-type]
    )

    #统计
    doc_chunks=sum(1 for c in all_chunks if c.get("source","").startswith("docs/"))
    tool_chunks=sum(1 for c in all_chunks if c.get("source")=="mcp_tools")
    kb_chunks=sum(1 for c in all_chunks if c.get("source","").startswith("sre_kb/"))
    total=collection.count()

    _logger.info("="*50)
    _logger.info(f"知识库构建完成: {total} 条 (本次新增 {len(all_chunks)})")
    _logger.info(f"  项目文档: {doc_chunks}")
    _logger.info(f"  MCP 工具: {tool_chunks}")
    _logger.info(f"  SRE 知识: {kb_chunks}")

    return {
        "chunks_added":len(all_chunks),
        "doc_chunks":doc_chunks,
        "tool_chunks":tool_chunks,
        "sre_chunks":kb_chunks,
        "total_chunks":total,
    }


# ── 辅助: 按 source 删除旧块 ──────────────────────

"""
方法: _delete_chunks_by_sources(collection, sources), 增量更新前删除将被替换的旧向量块

"""

def _delete_chunks_by_sources(collection, sources:set):
    try:
        if hasattr(collection,'_c'):
            #native 后端: sqlite DELETE
            for src in sources:
                collection._c.execute(
                    "DELETE FROM chunks WHERE collection=? AND json_extract(metadata_json,'$.source')=?",
                    (collection.name, src))
            collection._c.commit()
        else:
            #ChromaDB: 通过 get+where 找到 ids 再 delete
            for src in sources:
                try:
                    result=collection.get(where={"source":src})
                    if result and result.get("ids"):
                        collection.delete(ids=result["ids"])
                except Exception:
                    pass  #ChromaDB where 过滤可能不支持, 忽略
    except Exception as e:
        _logger.warning(f"清理旧块失败 (非致命): {e}")
