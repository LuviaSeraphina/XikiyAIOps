"""
自动备份与回滚插件 — 数据安全最后防线

提供:
- backup_create: 创建完整备份快照 (SQLite + 配置 + RAG 向量)
- backup_list: 列出所有备份
- backup_restore: 从指定快照恢复
- backup_cleanup: 清理过期备份 (保留最近 N 个)
"""
import os
import shutil
import tarfile
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from app.mcp_plugins._common import make_response, error_response

#备份根目录
_BACKUP_ROOT=Path(__file__).resolve().parent.parent.parent / "data" / "backups"
#备份保留数量
_MAX_BACKUPS=20

#需备份的路径 (相对于 backend/)
_BACKUP_PATHS=[
    "data/xikiy_aiops.db",       #SQLite 数据库
    "config/health_score_config.json",
    "data/rag_index/",            #RAG 向量索引 (如果存在)
]

def backup_create_handler(label=""):
    """
    创建完整备份快照
    
    备份内容: SQLite 数据库 + 配置文件 + RAG 索引
    快照格式: tar.gz, 文件名含时间戳 + MD5 校验
    """
    backend_root=Path(__file__).resolve().parent.parent.parent
    _BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    
    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label=label.replace("/","_").replace(" ","_")[:30] if label else "auto"
    archive_name=f"backup_{timestamp}_{safe_label}.tar.gz"
    archive_path=_BACKUP_ROOT / archive_name
    
    #收集备份文件列表
    files_to_backup=[]
    total_size=0
    for rel_path in _BACKUP_PATHS:
        abs_path=backend_root / rel_path
        if not abs_path.exists():
            continue
        if abs_path.is_file():
            files_to_backup.append((rel_path, abs_path))
            total_size+=abs_path.stat().st_size
        elif abs_path.is_dir():
            for f in abs_path.rglob("*"):
                if f.is_file():
                    rel=str(f.relative_to(backend_root))
                    files_to_backup.append((rel, f))
                    total_size+=f.stat().st_size
    
    if not files_to_backup:
        return error_response("backup_create", "没有可备份的文件")
    
    try:
        #创建 tar.gz
        with tarfile.open(archive_path, "w:gz") as tar:
            for rel_path, abs_path in files_to_backup:
                tar.add(abs_path, arcname=rel_path)
        
        #计算 MD5
        md5=hashlib.md5()
        with open(archive_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        
        file_size=archive_path.stat().st_size
        
        return make_response("backup_create",
            data={
                "archive":archive_name,
                "path":str(archive_path),
                "size_bytes":file_size,
                "size_mb":round(file_size/1024/1024, 2),
                "files_count":len(files_to_backup),
                "total_size_bytes":total_size,
                "md5":md5.hexdigest(),
                "timestamp":timestamp,
                "label":safe_label,
            },
            summary={
                "backup":archive_name,
                "size":f"{file_size/1024/1024:.1f}MB",
                "files":len(files_to_backup),
                "md5":md5.hexdigest()[:12],
            },
        )
    except Exception as e:
        #清理失败的归档
        if archive_path.exists():
            archive_path.unlink()
        return error_response("backup_create", str(e))


def backup_list_handler():
    """列出所有备份快照, 按时间倒序"""
    _BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    
    backups=[]
    for f in sorted(_BACKUP_ROOT.glob("backup_*.tar.gz"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat=f.stat()
        #解析时间戳和标签
        name=f.stem  # backup_20260716_120000_auto
        parts=name.split("_",2)
        ts_str=f"{parts[1]}_{parts[2]}" if len(parts)>=3 else name
        label=parts[3] if len(parts)>=4 else ""
        
        backups.append({
            "name":f.name,
            "path":str(f),
            "size_mb":round(stat.st_size/1024/1024, 2),
            "created":datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "label":label,
        })
    
    return make_response("backup_list",
        data={"backups":backups,"count":len(backups),"max_keep":_MAX_BACKUPS},
        summary={"total":len(backups),"latest":backups[0]["name"] if backups else "无"},
    )


def backup_restore_handler(archive_name):
    """
    从备份快照恢复
    
    恢复前自动创建"恢复前备份", 确保可回滚。
    恢复后提示重启服务。
    """
    archive_path=_BACKUP_ROOT / archive_name
    if not archive_path.exists():
        return error_response("backup_restore", f"备份不存在: {archive_name}")
    
    backend_root=Path(__file__).resolve().parent.parent.parent
    
    #恢复前自动备份当前状态
    pre_restore_result=backup_create_handler(label="pre_restore")
    pre_backup=pre_restore_result.get("data",{}).get("archive","无")
    
    try:
        restored_files=[]
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                #安全检查: 防止路径穿越
                target_path=backend_root / member.name
                if not str(target_path.resolve()).startswith(str(backend_root.resolve())):
                    continue  #跳过越界路径
                
                tar.extract(member, backend_root)
                restored_files.append(member.name)
        
        return make_response("backup_restore",
            data={
                "archive":archive_name,
                "restored_files":restored_files[:50],
                "files_count":len(restored_files),
                "pre_restore_backup":pre_backup,
            },
            summary={
                "restored":len(restored_files),
                "pre_restore":pre_backup,
                "hint":"还原完成, 建议重启服务以应用配置变更",
            },
        )
    except Exception as e:
        return error_response("backup_restore", f"恢复失败: {e}")


def backup_cleanup_handler(keep=10):
    """
    清理旧备份, 保留最近 N 个
    
    安全: 至少保留 3 个备份, 防止误删
    """
    keep=max(keep, 3)
    _BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    
    all_backups=sorted(
        _BACKUP_ROOT.glob("backup_*.tar.gz"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    
    deleted=[]
    for old in all_backups[keep:]:
        old.unlink()
        deleted.append(old.name)
    
    kept=[b.name for b in all_backups[:keep]]
    
    return make_response("backup_cleanup",
        data={"deleted":deleted,"deleted_count":len(deleted),"kept":kept,"kept_count":len(kept)},
        summary={"deleted":len(deleted),"kept":len(kept)},
    )
