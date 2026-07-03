"""
RAG 模型封装 — 双后端自适应架构

嵌入模型:
  x86_64/ARM:  sentence-transformers 本地推理 (优先) → numpy TF-IDF (回落)
  LoongArch:  numpy TF-IDF (直接启用, 跳过无意义的本地模型加载)

向量存储:
  x86_64/ARM:  ChromaDB (优先) → sqlite3+numpy (回落)
  LoongArch:  sqlite3+numpy (直接启用)
"""
import os as _os
import json as _json
import struct
import logging
import re as _re
import pickle as _pickle
import platform as _platform
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

try:
    import sqlite3
except ImportError:
    import sqlite3

_logger=logging.getLogger("xikiy_aiops.rag")

# CPU 架构检测
_IS_LOONGARCH=_platform.machine() in ("loongarch64",)


@dataclass
class Document:
    content:str
    metadata:Dict[str,str]=field(default_factory=dict)
    score:float=0.0

    def to_context(self)->str:
        source=self.metadata.get("source","未知")
        title=self.metadata.get("title","")
        header=f"[来源: {source}]"
        if title: header+=f" {title}"
        return f"{header}\n{self.content}"


# ═══════════ 嵌入模型 — 双后端自适应 ═══════════

class EmbeddingModel:
    _instance=None
    _DIMENSION=384
    _MAX_FEATURES=768  # TF-IDF 最大特征数

    def __new__(cls):
        if cls._instance is None:
            cls._instance=super().__new__(cls)
            cls._instance._backend=None
            cls._instance._model=None
        return cls._instance

    # ── 1. sentence-transformers (x86_64) ──

    def _try_local(self)->bool:
        try:
            from sentence_transformers import SentenceTransformer
            from . import config as _cfg
            _logger.info(f"加载本地嵌入: {_cfg.EMBEDDING_MODEL}")
            self._model=SentenceTransformer(_cfg.EMBEDDING_MODEL, device=_cfg.EMBEDDING_DEVICE)
            self._DIMENSION=self._model.get_embedding_dimension()
            self._backend="local"
            _logger.info(f"嵌入后端: 本地 ({self._DIMENSION}维)")
            return True
        except ImportError:
            return False
        except Exception as e:
            _logger.warning(f"本地模型加载失败: {e}")
            return False

    # ── 2. 纯 numpy TF-IDF (全平台, 默认回落) ──

    def _use_numpy_tfidf(self):
        self._backend="numpy_tfidf"
        self._vocab={}        # token → index
        self._idf=None        # [vocab_size]
        self._fitted=False
        self._DIMENSION=self._MAX_FEATURES
        _logger.info("嵌入后端: 纯 numpy TF-IDF (零依赖, 毫秒级)")

    # ── 初始化逻辑 ──

    def _ensure_init(self):
        if self._backend is not None: return
        # LoongArch: 直接走 numpy TF-IDF, 不尝试加载 sentence-transformers
        if _IS_LOONGARCH:
            self._use_numpy_tfidf()
            return
        # 用户显式指定后端
        backend_env=_os.getenv("RAG_EMBEDDING_BACKEND","")
        if backend_env=="sentence_transformers":
            if self._try_local(): return
            _logger.warning("sentence-transformers 不可用, 回落 numpy TF-IDF")
            self._use_numpy_tfidf()
            return
        # 自动检测: 本地 → numpy TF-IDF
        if self._try_local(): return
        self._use_numpy_tfidf()

    # ── TF-IDF 分词 (中文 char n-gram + 英文/数字词) ──

    @staticmethod
    def _tokenize(text:str)->List[str]:
        return tokenize_for_tfidf(text)

    # ── TF-IDF 拟合 (仅在 numpy_tfidf 后端调用) ──

    # 在全部语料上构建词汇表 + 计算 IDF, 持久化到磁盘
    def fit(self, texts:List[str]):
        if self._backend!="numpy_tfidf":
            _logger.info(f"后端 {self._backend} 无需 fit, 跳过")
            return
        n_docs=len(texts)
        df={}
        for text in texts:
            seen=set()
            for tok in self._tokenize(text):
                if tok not in seen:
                    df[tok]=df.get(tok,0)+1
                    seen.add(tok)
        # 按 DF 降序取 top MAX_FEATURES
        sorted_toks=sorted(df.items(), key=lambda x:-x[1])[:self._MAX_FEATURES]
        self._vocab={tok:i for i,(tok,_) in enumerate(sorted_toks)}
        vocab_size=len(self._vocab)
        self._DIMENSION=vocab_size
        self._idf=np.zeros(vocab_size)
        for tok,idx in self._vocab.items():
            self._idf[idx]=np.log((n_docs+1)/(df.get(tok,1)+1))+1
        self._fitted=True
        # 持久化到 RAG_DB_DIR
        self._save_vocab()
        _logger.info(f"TF-IDF 拟合完成: vocab={vocab_size}, dim={vocab_size}")

    def _vocab_path(self)->Path:
        from . import config as _cfg
        return Path(_cfg.RAG_DB_DIR)/"tfidf_vocab.pkl"

    # 持久化到磁盘
    def _save_vocab(self):
        assert self._idf is not None  # 仅 fit() 后调用, 此时 _idf 已赋值
        p=self._vocab_path()
        _os.makedirs(p.parent,exist_ok=True)
        data={"vocab":self._vocab,"idf":self._idf.tolist(),"_DIMENSION":self._DIMENSION}
        with open(self._vocab_path(),"wb") as f:
            _pickle.dump(data,f)

    # 从磁盘加载 TF-IDF 词汇表与 IDF, 供查询时复用
    def _load_vocab(self)->bool:
        p=self._vocab_path()
        if not p.exists(): return False
        try:
            with open(p,"rb") as f:
                data=_pickle.load(f)
            self._vocab=data["vocab"]
            self._idf=np.array(data["idf"])
            self._DIMENSION=data["_DIMENSION"]
            self._fitted=True
            self._backend="numpy_tfidf"
            _logger.info(f"TF-IDF 词汇表已加载: vocab={len(self._vocab)}, dim={self._DIMENSION}")
            return True
        except Exception as e:
            _logger.warning(f"TF-IDF 词汇表加载失败: {e}")
            return False

    # ── 编码 ──

    def _tfidf_encode(self, texts:List[str])->List[List[float]]:
        if not self._fitted:
            raise RuntimeError("TF-IDF 未拟合, 请先运行 build_knowledge_base()")
        if not self._vocab:
            return [[0.0] for _ in texts]  #空词汇表, 返回零向量
        assert self._idf is not None
        result=np.zeros((len(texts), len(self._vocab)))
        for i,text in enumerate(texts):
            tf={}
            for tok in self._tokenize(text):
                tf[tok]=tf.get(tok,0)+1
            for tok,count in tf.items():
                if tok in self._vocab:
                    result[i,self._vocab[tok]]=count*self._idf[self._vocab[tok]]
        # L2 归一化
        norms=np.linalg.norm(result,axis=1,keepdims=True)
        norms[norms==0]=1
        return (result/norms).tolist()

    def encode(self, texts:List[str])->List[List[float]]:
        self._ensure_init()
        if self._backend=="local":
            return self._model.encode(texts, normalize_embeddings=True).tolist()
        # numpy_tfidf: 查询时自动加载词汇表
        if not self._fitted:
            self._load_vocab()
        return self._tfidf_encode(texts)

    def encode_single(self, text:str)->List[float]: return self.encode([text])[0]

    @property
    def dimension(self)->int:
        self._ensure_init()
        return int(self._DIMENSION) if self._DIMENSION is not None else 0

    @property
    def backend(self)->str: self._ensure_init(); return self._backend


# ═══════════ 向量存储 — 自适应 ═══════════

class VectorStore:
    _instance=None
    def __new__(cls):
        if cls._instance is None:
            cls._instance=super().__new__(cls)
            cls._instance._backend=None
            cls._instance._client=None
        return cls._instance

    def _try_chromadb(self)->bool:
        try:
            import chromadb
            from . import config as _cfg
            _os.makedirs(_cfg.RAG_DB_DIR,exist_ok=True)
            self._client=chromadb.PersistentClient(path=_cfg.RAG_DB_DIR)
            self._backend="chromadb"
            _logger.info(f"向量存储: ChromaDB ({_cfg.RAG_DB_DIR})")
            return True
        except ImportError: return False
        except Exception as e: _logger.warning(f"ChromaDB失败: {e}"); return False

    def _use_native(self):
        from . import config as _cfg
        _os.makedirs(_cfg.RAG_DB_DIR,exist_ok=True)
        db_path=_os.path.join(_cfg.RAG_DB_DIR,"vectors.db")
        self._client=sqlite3.connect(db_path)
        self._client.executescript("""
            CREATE TABLE IF NOT EXISTS collections(name TEXT PRIMARY KEY,dim INTEGER);
            CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,collection TEXT,embedding BLOB,document TEXT,metadata_json TEXT DEFAULT '{}');
            CREATE INDEX IF NOT EXISTS idx_coll ON chunks(collection);
        """)
        self._client.commit()
        self._backend="native"
        _logger.info(f"向量存储: sqlite3+numpy ({db_path})")

    def _ensure_init(self):
        if self._backend is not None: return
        # LoongArch: 跳过 ChromaDB, 直接 sqlite3+numpy
        if _IS_LOONGARCH:
            self._use_native()
            return
        # 其他架构: ChromaDB → sqlite3+numpy
        if not self._try_chromadb(): self._use_native()

    def get_or_create_collection(self, name:str="sre_knowledge"):
        self._ensure_init()
        if self._backend=="chromadb":
            try: return self._client.get_collection(name)  # type: ignore[union-attr]
            except: return self._client.create_collection(name,metadata={"hnsw:space":"cosine"})  # type: ignore[union-attr]
        # native 后端 (sqlite3)
        dim=embedding_model.dimension
        cur=self._client.execute("SELECT dim FROM collections WHERE name=?",(name,))  # type: ignore[union-attr]
        if not cur.fetchone():
            self._client.execute("INSERT INTO collections VALUES(?,?)",(name,dim))  # type: ignore[union-attr]
            self._client.commit()  # type: ignore[union-attr]
        return _NativeCol(self._client,name,dim)

    def delete_collection(self, name:str="sre_knowledge"):
        self._ensure_init()
        if self._backend=="chromadb":
            try: self._client.delete_collection(name)  # type: ignore[union-attr]
            except: pass
        else:
            self._client.execute("DELETE FROM chunks WHERE collection=?",(name,))  # type: ignore[union-attr]
            self._client.execute("DELETE FROM collections WHERE name=?",(name,))  # type: ignore[union-attr]
            self._client.commit()  # type: ignore[union-attr]

    @property
    def db(self): self._ensure_init(); return self._client if self._backend=="native" else None


class _NativeCol:
    def __init__(self,conn,name,dim):
        self._c=conn; self.name=name; self.dim=dim

    def count(self)->int:
        return self._c.execute("SELECT COUNT(*) FROM chunks WHERE collection=?",(self.name,)).fetchone()[0]

    def add(self,ids,embeddings,documents,metadatas):
        rows=[(ids[i],self.name,_enc(embeddings[i]),documents[i] if i<len(documents) else "",
              _json.dumps(metadatas[i] if i<len(metadatas) else {},ensure_ascii=False))
              for i in range(len(ids))]
        self._c.executemany("INSERT OR REPLACE INTO chunks VALUES(?,?,?,?,?)",rows)
        self._c.commit()

    def query(self,query_embeddings,n_results=5,include=None,**kw)->Dict:
        if include is None: include=["documents","metadatas","distances"]
        rows=self._c.execute("SELECT id,embedding,document,metadata_json FROM chunks WHERE collection=?",(self.name,)).fetchall()
        if not rows: return {"ids":[[]],"documents":[[]],"metadatas":[[]],"distances":[[]]}
        ids=[r[0] for r in rows]; embs=np.array([_dec(r[1],self.dim) for r in rows])
        docs=[r[2] for r in rows]; metas=[_json.loads(r[3]) for r in rows]
        qv=np.array(query_embeddings[0] if query_embeddings else [0]*self.dim)
        scores=np.dot(embs,qv)
        top=np.argsort(-scores)[:n_results]
        r={"ids":[[ids[i] for i in top]]}
        if "documents" in include: r["documents"]=[[docs[i] for i in top]]
        if "metadatas" in include: r["metadatas"]=[[metas[i] for i in top]]
        if "distances" in include: r["distances"]=[[float(1-scores[i]) for i in top]]
        return r

    def get(self,include=None,**kw)->Dict:
        if include is None: include=["documents","metadatas"]
        rows=self._c.execute("SELECT document,metadata_json FROM chunks WHERE collection=?",(self.name,)).fetchall()
        r={}
        if "documents" in include: r["documents"]=[row[0] for row in rows]
        if "metadatas" in include: r["metadatas"]=[_json.loads(row[1]) for row in rows]
        return r

def _enc(v): return struct.pack(f"<{len(v)}f",*v)
def _dec(b,dim): return np.frombuffer(b,dtype=np.float32)

embedding_model=EmbeddingModel()
vector_store=VectorStore()


# ── 统一分词 (供 retrieval BM25 和 TF-IDF 共用) ──

"""
方法: tokenize_for_tfidf(text), TF-IDF 分词: 中文 char bigram + 英文/数字词, 用于 EmbeddingModel._tokenize

"""

def tokenize_for_tfidf(text:str)->List[str]:
    tokens=[]
    for m in _re.finditer(r'[\u4e00-\u9fff]+', text):
        seg=m.group()
        for i,ch in enumerate(seg):
            tokens.append(ch)
            if i+1<len(seg):
                tokens.append(seg[i:i+2])
    for w in _re.findall(r'[a-zA-Z0-9_]+', text.lower()):
        tokens.append(w)
    return tokens


"""
方法: tokenize_for_bm25(text), BM25 分词: 中文单字 + 英文按空白/标点切, 过滤短词, 用于检索管道

"""

def tokenize_for_bm25(text:str)->List[str]:
    tokens=[]
    buf=""
    for ch in text:
        if '\u4e00'<=ch<='\u9fff' or '\u3400'<=ch<='\u4dbf':
            if buf:
                tokens.append(buf.lower())
                buf=""
            tokens.append(ch)
        elif ch.isalnum():
            buf+=ch
        else:
            if buf:
                tokens.append(buf.lower())
                buf=""
    if buf:
        tokens.append(buf.lower())
    return [t for t in tokens if len(t)>=2 or '\u4e00'<=t<='\u9fff']
