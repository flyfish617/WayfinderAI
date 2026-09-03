"""
健壮的日志系统
提供结构化日志、请求ID追踪、日志轮转等功能
"""
import json
import logging
import logging.handlers
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 请求ID上下文变量
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

SENSITIVE_FIELD_MARKERS = {
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "access_key",
    "refresh_token",
    "cookie",
}

STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def _extract_log_context(record: logging.LogRecord) -> Dict[str, Any]:
    context: Dict[str, Any] = {}

    extra_context = getattr(record, "extra_context", None)
    if isinstance(extra_context, dict):
        context.update(extra_context)

    for key, value in record.__dict__.items():
        if key in STANDARD_LOG_RECORD_FIELDS or key == "extra_context":
            continue
        context[key] = value

    return context


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(marker in normalized for marker in SENSITIVE_FIELD_MARKERS)


def _sanitize_value(value: Any, *, key: Optional[str] = None) -> Any:
    if key and _is_sensitive_key(key):
        return "***REDACTED***"

    if isinstance(value, dict):
        return {str(k): _sanitize_value(v, key=str(k)) for k, v in value.items()}

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)

    if isinstance(value, str):
        compact = value.strip()
        if len(compact) > 2000:
            return f"{compact[:2000]}...<truncated>"
        return compact

    return value


class StructuredFormatter(logging.Formatter):
    """
    结构化日志格式化器
    将日志输出为JSON格式，便于日志收集和分析
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录为JSON格式
        """
        # 获取请求ID
        request_id = request_id_var.get()
        
        # 构建基础日志数据
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加请求ID（如果存在）
        if request_id:
            log_data["request_id"] = request_id
        
        # 添加异常信息（如果存在）
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info) if record.exc_info else None
            }
        
        context = _sanitize_value(_extract_log_context(record))
        if context:
            log_data["context"] = context
        
        # 添加线程和进程信息
        log_data["thread"] = record.thread
        log_data["process"] = record.process
        
        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """
    人类可读的日志格式化器
    用于控制台输出，格式更友好
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录为人类可读格式
        """
        # 获取请求ID
        request_id = request_id_var.get()
        
        # 基础格式
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        logger_name = record.name
        message = record.getMessage()
        
        # 构建日志行
        log_line = f"[{timestamp}] {level} [{logger_name}] {message}"
        
        # 添加请求ID
        if request_id:
            log_line = f"[{timestamp}] {level} [{logger_name}] [RequestID: {request_id}] {message}"
        
        # 添加位置信息
        log_line += f" | {record.module}.{record.funcName}:{record.lineno}"
        
        # 添加异常信息
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"
        
        context = _sanitize_value(_extract_log_context(record))
        if context:
            context_str = json.dumps(context, ensure_ascii=False, indent=2)
            log_line += f"\n上下文信息:\n{context_str}"
        
        return log_line


def setup_logger(
    name: str = "trip_planner",
    log_level: str = "INFO",
    log_dir: str = "logs",
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    设置并配置日志记录器
    
    Args:
        name: 日志记录器名称
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件目录
        enable_file_logging: 是否启用文件日志
        enable_console_logging: 是否启用控制台日志
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建日志目录
    if enable_file_logging:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
    
    # 控制台处理器（人类可读格式）
    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = HumanReadableFormatter()
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器 - 所有日志（JSON格式）
    if enable_file_logging:
        all_log_file = log_path / "app.log"
        file_handler = logging.handlers.RotatingFileHandler(
            all_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = StructuredFormatter()
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # 错误日志文件 - 只记录ERROR及以上级别
    if enable_file_logging:
        error_log_file = log_path / "error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = StructuredFormatter()
        error_handler.setFormatter(error_formatter)
        logger.addHandler(error_handler)
    
    return logger


def set_request_id(request_id: str):
    """
    设置当前请求的ID
    
    Args:
        request_id: 请求ID
    """
    return request_id_var.set(request_id)


def clear_request_id(token=None) -> None:
    if token is not None:
        request_id_var.reset(token)
    else:
        request_id_var.set(None)


def get_request_id() -> Optional[str]:
    """
    获取当前请求的ID
    
    Returns:
        请求ID，如果不存在则返回None
    """
    return request_id_var.get()


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context
) -> None:
    """
    记录带上下文的日志
    
    Args:
        logger: 日志记录器
        level: 日志级别
        message: 日志消息
        **context: 额外的上下文信息
    """
    extra = {'extra_context': _sanitize_value(context)}
    logger.log(level, message, extra=extra)


# 创建默认的日志记录器实例
default_logger = setup_logger()

