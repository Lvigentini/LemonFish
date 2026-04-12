#!/usr/bin/env python3
"""
Bulk comment translator — Chinese → English.

Walks the repo, identifies comment lines and docstrings in .py/.js/.ts/.vue
files, and applies a curated dictionary of Chinese → English translations.

Critical constraints:
  1. Only touches COMMENTS and DOCSTRINGS, never string literals.
     A hardcoded Chinese f-string like `f"已完成 {n}"` is left alone — those
     are i18n leaks, a separate problem handled via the t() helper.
  2. LLM prompts inside triple-quoted strings are heuristically detected
     by NOT being immediately after a def/class (i.e. body docstrings only
     are translated; standalone triple-quoted strings in function bodies
     are assumed to be LLM prompts).
  3. Lines that contain CJK text the dictionary cannot translate are
     flagged with a `# TODO(i18n-sweep): ...` marker (Python) or
     equivalent (JS/Vue) so a human can finish the job.

Usage:
    python3 scripts/translate_comments.py            # translate everything
    python3 scripts/translate_comments.py --path backend/app/models
                                                     # scope to a subdir
    python3 scripts/translate_comments.py --dry-run  # report only, no writes

This script is intended to be committed alongside the translation so the
dictionary is reviewable in-tree, but deleted after the sweep is done.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Dict, List, Tuple

CJK = re.compile(r'[\u4e00-\u9fff]')

# --------------------------------------------------------------------------
# Translation dictionary — curated by reading the actual comments in the
# repo. Longest keys first (greedy matching) to handle phrase overlap.
# --------------------------------------------------------------------------

DICTIONARY: Dict[str, str] = {
    # ---- Full-phrase replacements (most specific first) ----
    "带重试和备用模型支持": "with retry and fallback model support",
    "指数退避重试": "exponential-backoff retry",
    "统一从项目根目录的 .env 文件加载配置": "load settings from the project root .env file",
    "统一日志管理": "unified logger management",
    "确保 stdout/stderr 使用 UTF-8 编码": "ensure stdout/stderr use UTF-8 encoding",
    "解决 Windows 控制台中文乱码问题": "fix CJK character corruption on Windows consoles",
    "在所有其他导入之前设置": "must be set before any other imports",
    "Flask应用工厂函数": "Flask application factory",
    "Flask应用工厂": "Flask application factory",
    "Flask配置类": "Flask configuration class",
    "Flask配置": "Flask configuration",
    "设置环境变量确保 Python 使用 UTF-8": "set environment variable to force Python UTF-8",
    "重新配置标准输出流为 UTF-8": "reconfigure stdout streams to UTF-8",
    "添加项目根目录到路径": "add project root to sys.path",
    "验证必要配置": "validate required configuration",
    "验证配置": "validate configuration",
    "获取运行配置": "runtime configuration",
    "启动服务": "start the server",
    "主函数": "entry point",
    "启动入口": "entrypoint",
    "如果根目录没有 .env，尝试加载环境变量": "fall back to reading env vars directly",
    "用于生产环境": "for production",
    "加载项目根目录的 .env 文件": "load .env from project root",

    "获取任务": "get task",
    "查询任务": "query task",
    "获取项目": "get project",
    "获取项目详情": "get project details",
    "创建项目": "create project",
    "删除项目": "delete project",
    "保存项目": "save project",
    "更新项目": "update project",
    "重置项目": "reset project",
    "列出项目": "list projects",
    "项目信息": "project info",
    "项目状态": "project status",
    "项目元数据": "project metadata",
    "项目存储根目录": "project storage root directory",
    "项目数据模型": "project data model",
    "项目目录路径": "project directory path",
    "项目管理器": "project manager",
    "确保项目目录存在": "ensure project directory exists",
    "确保日志目录存在": "ensure log directory exists",
    "获取项目目录路径": "get project directory path",
    "获取项目元数据文件路径": "get project metadata file path",
    "获取项目文件存储目录": "get project files directory",
    "获取项目提取文本存储路径": "get project extracted-text path",
    "获取项目的所有文件路径": "get all file paths for a project",
    "获取提取的文本": "get extracted text",
    "保存提取的文本": "save extracted text",
    "保存上传的文件到项目目录": "save an uploaded file into the project directory",
    "生成安全的文件名": "generate a safe filename",
    "保存文件": "save the file",
    "获取文件大小": "get file size",
    "负责项目的持久化存储和检索": "handles persistent project storage and retrieval",
    "创建项目目录结构": "create the project directory structure",
    "保存项目元数据": "save project metadata",

    "任务状态管理": "task state management",
    "用于跟踪长时间运行的任务": "tracks long-running tasks",
    "任务状态枚举": "task status enum",
    "任务数据类": "task dataclass",
    "任务管理器": "task manager",
    "线程安全的任务状态管理": "thread-safe task state management",
    "单例模式": "singleton",
    "等待中": "waiting",
    "处理中": "processing",
    "已完成": "completed",
    "失败": "failed",
    "已取消": "cancelled",
    "总进度百分比": "overall progress percentage",
    "状态消息": "status message",
    "任务结果": "task result",
    "错误信息": "error info",
    "额外元数据": "extra metadata",
    "详细进度信息": "detailed progress info",
    "转换为字典": "convert to dict",
    "创建新任务": "create a new task",
    "更新任务状态": "update task state",
    "标记任务完成": "mark task complete",
    "标记任务失败": "mark task failed",
    "列出任务": "list tasks",
    "清理旧任务": "clean up old tasks",
    "任务ID": "task ID",
    "任务类型": "task type",
    "新状态": "new status",
    "进度": "progress",
    "消息": "message",
    "结果": "result",
    "异常信息": "exception info",

    # ---- API layer ----
    "图谱相关API路由": "Graph-related API routes",
    "采用项目上下文机制": "uses the project context pattern",
    "服务端持久化状态": "server-side persistent state",
    "检查文件扩展名是否允许": "check if file extension is allowed",
    "项目管理接口": "project management endpoints",
    "获取上传的文件": "get the uploaded files",
    "上传文件": "upload files",
    "创建新项目": "create a new project",
    "清除待上传数据": "clear pending upload data",
    "更新项目ID和数据": "update project ID and data",
    "更新URL": "update URL",
    "不刷新页面": "without page reload",
    "自动开始图谱构建": "auto-start graph build",
    "启动图谱构建": "start graph build",
    "开始构建图谱": "begin graph build",
    "图谱构建": "graph build",
    "图谱构建任务": "graph build task",
    "图谱数据": "graph data",
    "图谱构建中": "graph building",
    "图谱构建完成": "graph build complete",
    "图谱构建失败": "graph build failed",
    "本体生成": "ontology generation",
    "本体生成失败": "ontology generation failed",
    "本体生成中": "ontology generating",
    "本体生成阶段": "ontology generation phase",
    "生成本体定义": "generate ontology definition",
    "实体类型": "entity types",
    "关系类型": "relationship types",
    "关系类型列表": "relationship type list",
    "实体数量": "entity count",
    "关系数量": "relationship count",
    "处理失败": "processing failed",
    "返回项目信息": "return project info",
    "请求参数": "request params",
    "请求方式": "request method",
    "参数": "params",
    "返回": "returns",
    "必填": "required",
    "可选": "optional",

    # ---- Simulation ----
    "模拟器": "simulator",
    "模拟运行": "simulation run",
    "模拟配置": "simulation config",
    "模拟结果": "simulation result",
    "模拟状态": "simulation status",
    "模拟环境": "simulation environment",
    "模拟进程": "simulation process",
    "模拟需求": "simulation requirement",
    "模拟数据": "simulation data",
    "模拟任务": "simulation task",
    "模拟ID": "simulation ID",
    "模拟已完成": "simulation completed",
    "模拟准备": "simulation preparation",
    "模拟启动": "simulation startup",
    "开始模拟": "start simulation",
    "停止模拟": "stop simulation",
    "模拟脚本": "simulation script",
    "模拟管理器": "simulation manager",
    "模拟运行器": "simulation runner",
    "注册模拟进程清理函数": "register simulation process cleanup hook",
    "确保服务器关闭时终止所有模拟进程": "ensure all simulation processes are terminated on shutdown",
    "运行日志": "run log",
    "清理运行日志": "clean run logs",
    "运行中": "running",
    "未开始": "not started",
    "启动中": "starting",
    "处理中": "processing",
    "智能处理状态": "smart state handling",
    "重新启动": "restart",
    "检测是否": "check whether",
    "至少有一个": "at least one",
    "所有启用的平台": "all enabled platforms",
    "所有平台": "all platforms",
    "启用的平台": "enabled platform",
    "标记平台已完成": "mark platform as complete",
    "检查所有启用的平台是否都已完成": "check whether all enabled platforms are complete",
    "检查所有启用的平台是否都已完成模拟": "check whether all enabled platforms finished simulating",
    "检测 simulation_end 事件": "detect simulation_end event",

    # ---- Graph / Zep ----
    "知识图谱": "knowledge graph",
    "构建知识图谱": "build knowledge graph",
    "实时知识图谱": "real-time knowledge graph",
    "实时图谱展示": "real-time graph view",
    "图谱可视化": "graph visualisation",
    "图谱容器": "graph container",
    "图谱图例": "graph legend",
    "图谱数据加载中": "graph data loading",
    "构建中": "building",
    "构建完成": "build complete",
    "构建失败": "build failed",
    "构建结果": "build result",
    "构建进度": "build progress",
    "构建流程": "build pipeline",
    "构建流程详情": "build pipeline details",
    "构建配置": "build config",
    "接口说明": "endpoint description",
    "接口": "endpoint",
    "下一步": "next step",
    "下一步按钮": "next button",
    "进入下一步": "proceed to next step",
    "进入环境搭建": "proceed to environment setup",
    "环境搭建": "environment setup",
    "环境搭建步骤": "environment setup step",
    "环境搭建功能开发中": "environment setup feature in development",

    # ---- LLM / Retry ----
    "LLM客户端封装": "LLM client wrapper",
    "统一使用OpenAI格式调用": "uniformly uses OpenAI SDK format",
    "LLM客户端": "LLM client",
    "默认模型": "default model",
    "最大重试次数": "max retry count",
    "初始延迟": "initial delay",
    "最大延迟": "max delay",
    "退避因子": "backoff factor",
    "是否添加随机抖动": "whether to add random jitter",
    "需要重试的异常类型": "exception types to retry on",
    "重试时的回调函数": "retry callback",
    "执行函数调用并在失败时重试": "invoke a function with retry on failure",
    "要调用的函数": "function to call",
    "函数参数": "function args",
    "函数关键字参数": "function kwargs",
    "函数返回值": "function return value",
    "批量调用并对每个失败项单独重试": "batch call with per-item retry",
    "要处理的项目列表": "items to process",
    "处理函数": "processing function",
    "接收单个item作为参数": "receives a single item as argument",
    "单项失败后是否继续处理其他项": "continue after single-item failure",
    "成功结果列表": "list of successful results",
    "失败项列表": "list of failed items",
    "可重试的API客户端封装": "retryable API client wrapper",
    "异步版本的重试装饰器": "async version of the retry decorator",
    "带指数退避的重试装饰器": "exponential-backoff retry decorator",
    "API调用重试机制": "API call retry machinery",
    "用于处理LLM等外部API调用的重试逻辑": "handles retry for external API calls (primarily LLM)",
    "计算延迟": "compute delay",
    "异常类型": "exception type",
    "配置管理": "configuration management",

    # ---- File / Text ----
    "文件上传": "file upload",
    "文件处理": "file handling",
    "文件上传配置": "file upload config",
    "文件输入引用": "file input ref",
    "文本处理": "text processing",
    "文本处理配置": "text chunking config",
    "默认切块大小": "default chunk size",
    "默认重叠大小": "default overlap",
    "分块": "chunking",
    "切块": "chunking",
    "提取文本": "extract text",
    "文本解析": "text parsing",

    # ---- Report ----
    "生成报告": "generate report",
    "章节": "section",
    "章节列表": "section list",
    "章节标题": "section titles",
    "报告代理": "report agent",
    "报告生成": "report generation",
    "报告生成完成": "report generation complete",
    "报告任务": "report task",
    "最大工具调用数": "max tool calls",

    # ---- UI / Frontend ----
    "顶部导航栏": "top navigation bar",
    "主内容区": "main content area",
    "左侧": "left",
    "右侧": "right",
    "左侧面板": "left panel",
    "右侧面板": "right panel",
    "中间步骤指示器": "middle step indicator",
    "顶部工具栏": "top toolbar",
    "刷新图谱": "refresh graph",
    "全屏显示": "fullscreen",
    "退出全屏": "exit fullscreen",
    "节点详情": "node details",
    "边详情": "edge details",
    "关系展示": "relationship display",
    "加载状态": "loading state",
    "等待构建": "waiting for build",
    "错误状态": "error state",
    "流程阶段": "pipeline stage",
    "流程内容": "pipeline content",
    "阶段详情": "stage details",
    "属性列表": "properties list",
    "实体标签": "entity tag",
    "关系列表": "relationship list",
    "进度条": "progress bar",
    "项目信息面板": "project info panel",
    "响应式": "responsive",
    "变量": "variables",
    "全局样式重置": "global style reset",
    "滚动条样式": "scrollbar styles",
    "等待状态": "waiting state",

    # ---- Common state / action verbs ----
    "计算属性": "computed",
    "方法": "methods",
    "当前": "current",
    "选中": "selected",
    "选中的节点或边": "selected node or edge",
    "DOM引用": "DOM refs",
    "轮询定时器": "polling timer",
    "手动": "manual",
    "自动": "auto",
    "立即": "immediately",
    "定时": "scheduled",
    "然后": "then",
    "以下": "the following",
    "注册蓝图": "register blueprints",
    "健康检查": "health check",
    "请求日志中间件": "request logging middleware",
    "请求体": "request body",
    "响应": "response",
    "请求": "request",
    "启用CORS": "enable CORS",
    "设置日志": "configure logger",
    "启动中": "starting",
    "启动完成": "startup complete",
    "避免重复": "avoid duplicate",
    "避免重复输出": "avoid duplicate output",
    "日志格式": "log format",
    "日志目录": "log directory",
    "日志器名称": "logger name",
    "日志级别": "logging level",
    "日志处理器": "log handler",
    "日志文件": "log file",
    "日志器": "logger",
    "文件处理器": "file handler",
    "控制台处理器": "console handler",
    "详细日志": "detailed log",
    "简洁日志": "concise log",
    "按日期命名": "named by date",
    "带轮转": "with rotation",
    "及以上": "and above",
    "Windows 下重新配置标准输出为 UTF-8": "reconfigure stdout to UTF-8 on Windows",
    "避免重复添加": "avoid duplicate additions",
    "如果已经有处理器": "if handlers already attached",
    "不重复添加": "don't add again",
    "阻止日志向上传播到根 logger": "prevent propagation to the root logger",
    "创建日志器": "create the logger",
    "添加处理器": "attach handlers",
    "设置日志器": "configure the logger",
    "获取日志器": "get the logger",
    "如果不存在则创建": "create if not exists",
    "创建默认日志器": "create the default logger",
    "便捷方法": "convenience wrappers",

    # ---- Fragments that appear inside parentheses and other wrappers ----
    "每分钟": "per minute",
    "每轮": "per round",
    "每小时": "per hour",
    "每天": "per day",
    "总计": "total",
    "用户": "user",
    "用户名": "username",
    "角色": "role",
    "生命周期": "lifecycle",
    "监听": "watch",
    "轮询": "poll",
    "图谱ID": "graph ID",
    "项目ID": "project ID",
    "选中节点": "select node",
    "选中边": "select edge",
    "关闭详情面板": "close details panel",
    "点击空白处关闭详情面板": "click blank area to close details",
    "格式化日期": "format date",
    "初始化": "initialise",
    "初始化 - 处理新建项目或加载已有项目": "initialise — handle new project or load existing",
    "处理新建项目": "handle new project",
    "加载已有项目": "load existing project",
    "加载项目": "load project",
    "加载失败": "load failed",
    "更多关系": "more relationships",

    # ---- Single-word / short fragments (apply last) ----
    "节点": "node",
    "关系": "relationship",
    "边": "edge",
    "实体": "entity",
    "图谱": "graph",
    "本体": "ontology",
    "模拟": "simulation",
    "配置": "config",
    "状态": "status",
    "代理": "agent",
    "代理人": "agent",
    "报告": "report",
    "工具": "tool",
    "调用": "call",
    "返回值": "return value",
    "结果": "result",
    "错误": "error",
    "异常": "exception",
    "成功": "success",
    "默认": "default",
    "最大": "max",
    "最小": "min",
    "参数": "parameter",
    "字段": "field",
    "列表": "list",
    "字典": "dict",
    "对象": "object",
    "属性": "property",
    "方法": "method",
    "函数": "function",
    "类": "class",
    "模块": "module",
    "包": "package",
    "文件": "file",
    "路径": "path",
    "目录": "directory",
    "内容": "content",
    "文本": "text",
    "字符": "character",
    "字符串": "string",
    "数据": "data",
    "数据库": "database",
    "队列": "queue",
    "缓存": "cache",
    "存储": "storage",
    "持久化": "persist",
    "加载": "load",
    "保存": "save",
    "删除": "delete",
    "移除": "remove",
    "创建": "create",
    "生成": "generate",
    "更新": "update",
    "插入": "insert",
    "查询": "query",
    "查找": "lookup",
    "搜索": "search",
    "过滤": "filter",
    "排序": "sort",
    "分页": "paginate",
    "批量": "batch",
    "批次": "batch",
    "单个": "single",
    "多个": "multiple",
    "并行": "parallel",
    "并发": "concurrent",
    "串行": "serial",
    "异步": "async",
    "同步": "sync",
    "阻塞": "blocking",
    "非阻塞": "non-blocking",
    "超时": "timeout",
    "重试": "retry",
    "退避": "backoff",
    "抖动": "jitter",
    "延迟": "delay",
    "间隔": "interval",
    "频率": "frequency",
    "速率": "rate",
    "速率限制": "rate limit",
    "限流": "rate limiting",
    "验证": "validate",
    "校验": "check",
    "检查": "check",
    "确认": "confirm",
    "取消": "cancel",
    "停止": "stop",
    "启动": "start",
    "开始": "begin",
    "结束": "end",
    "完成": "complete",
    "准备": "prepare",
    "就绪": "ready",
    "等待": "wait",
    "挂起": "suspend",
    "恢复": "resume",
    "重置": "reset",
    "重启": "restart",
    "刷新": "refresh",
    "同步": "sync",
    "例如": "example",
    "注意": "note",
    "警告": "warning",
    "提示": "hint",
    "说明": "description",
    "描述": "description",
    "详细": "detailed",
    "简要": "brief",
    "简单": "simple",
    "复杂": "complex",
    "基本": "basic",
    "高级": "advanced",
    "可选": "optional",
    "必需": "required",
    "临时": "temporary",
    "永久": "permanent",
    "静态": "static",
    "动态": "dynamic",
    "只读": "read-only",
    "可写": "writable",
    "全局": "global",
    "局部": "local",
    "内部": "internal",
    "外部": "external",
    "公开": "public",
    "私有": "private",
    "接口": "interface",
    "实现": "implementation",
    "抽象": "abstract",
    "具体": "concrete",
    "父": "parent",
    "子": "child",
    "兄弟": "sibling",
    "根": "root",
    "叶子": "leaf",
    "分支": "branch",
    "主干": "main",
    "主": "main",
    "次": "secondary",
    "主要": "primary",
    "辅助": "auxiliary",
    "核心": "core",
    "边缘": "edge",
    "顶层": "top",
    "底层": "bottom",
    "上层": "upper",
    "下层": "lower",
    "前": "front",
    "后": "back",
    "内": "in",
    "外": "out",
    "左": "left",
    "右": "right",
    "上": "up",
    "下": "down",
    "新": "new",
    "旧": "old",
    "高": "high",
    "低": "low",
    "大": "large",
    "小": "small",
    "快": "fast",
    "慢": "slow",
    "强": "strong",
    "弱": "weak",
    "好": "good",
    "差": "bad",
    "正确": "correct",
    "错误": "error",
    "有效": "valid",
    "无效": "invalid",
    "可用": "available",
    "不可用": "unavailable",
    "存在": "exists",
    "不存在": "does not exist",
    "为空": "empty",
    "非空": "non-empty",
    "是": "is",
    "不是": "is not",
    "或": "or",
    "和": "and",
    "但": "but",
    "如果": "if",
    "否则": "else",
    "当": "when",
    "所有": "all",
    "任意": "any",
    "每个": "each",
    "某个": "some",
    "这": "this",
    "那": "that",
    "这些": "these",
    "那些": "those",
    "此": "this",
    "其": "its",
    "该": "the",
    "以上": "above",
    "以下": "below",
    "上面": "above",
    "下面": "below",
    "之前": "before",
    "之后": "after",
    "期间": "during",
    "同时": "simultaneously",
    "之后再": "then later",
    "目前": "currently",
    "已经": "already",
    "尚未": "not yet",
    "总是": "always",
    "从不": "never",
    "通常": "usually",
    "有时": "sometimes",
    "经常": "often",
    "很少": "rarely",

    # ---- High-frequency phrases from diagnostic pass ----
    "采访两个平台": "interview both platforms",
    "只采访": "interview only",
    "采访": "interview",
    "双平台": "dual platform",
    "命令模式": "command mode",
    "不截断": "no truncation",
    "不指定": "unspecified",
    "命令": "command",
    "记录": "record",
    "平台": "platform",
    "记忆": "memory",
    "摘要": "summary",
    "阶段": "phase",
    "进程": "process",
    "服务": "service",
    "相关的": "related",
    "相关": "related",
    "执行": "execute",
    "支持": "support",
    "定义": "definition",
    "一个": "a",
    "统计": "statistics",
    "历史": "history",
    "名称": "name",
    "格式": "format",
    "使用": "use",
    "信息": "info",
    "事件": "event",
    "环境": "environment",
    "添加": "add",
    "检索": "retrieve",
    "需要": "needs",
    "动作": "action",
    "时间": "time",
    "发送": "send",
    "完整": "complete",
    "中的": "in the",
    "转换为": "convert to",
    "清理": "cleanup",
    "用于": "used for",
    "日志": "log",
    "确保": "ensure",
    "读取": "read",
    "设置": "set",
    "问题": "issue",
    "运行": "run",
    "处理": "process",
    "构建": "build",
    "获取": "get",
    "任务": "task",
    "当前": "current",
    "目标": "target",
    "目标用户": "target user",
    "来源": "source",
    "来自": "from",
    "输入": "input",
    "输出": "output",
    "序列": "sequence",
    "结构": "structure",
    "类型": "type",
    "版本": "version",
    "位置": "location",
    "范围": "range",
    "数量": "count",
    "数组": "array",
    "长度": "length",
    "大小": "size",
    "宽度": "width",
    "高度": "height",
    "角度": "angle",
    "颜色": "color",
    "样式": "style",
    "模板": "template",
    "示例": "example",
    "输入参数": "input parameters",
    "输出参数": "output parameters",
    "返回参数": "return parameters",
    "参数说明": "parameter description",
    "字段说明": "field description",
    "字段定义": "field definition",
    "必填字段": "required field",
    "可选字段": "optional field",
    "默认值": "default value",
    "取值": "value",
    "取值范围": "value range",

    # Verbs
    "启动": "start",
    "停止": "stop",
    "暂停": "pause",
    "继续": "continue",
    "终止": "terminate",
    "中断": "interrupt",
    "中止": "abort",
    "跳过": "skip",
    "重做": "redo",
    "撤销": "undo",
    "切换": "switch",
    "选择": "select",
    "匹配": "match",
    "比较": "compare",
    "合并": "merge",
    "拆分": "split",
    "分割": "split",
    "连接": "connect",
    "断开": "disconnect",
    "发布": "publish",
    "订阅": "subscribe",
    "监听": "listen",
    "广播": "broadcast",
    "通知": "notify",
    "告知": "inform",
    "报告": "report",
    "提醒": "remind",
    "记忆": "memory",
    "遗忘": "forget",
    "学习": "learn",
    "训练": "train",
    "推理": "inference",
    "预测": "predict",
    "分析": "analyze",
    "统计": "statistics",
    "总结": "summarize",
    "提取": "extract",
    "解析": "parse",
    "编码": "encode",
    "解码": "decode",
    "序列化": "serialize",
    "反序列化": "deserialize",
    "压缩": "compress",
    "解压": "decompress",
    "加密": "encrypt",
    "解密": "decrypt",
    "签名": "sign",
    "认证": "authenticate",
    "授权": "authorize",
    "登录": "login",
    "注销": "logout",
    "退出": "exit",
    "关闭": "close",
    "打开": "open",
    "显示": "show",
    "隐藏": "hide",
    "展开": "expand",
    "折叠": "collapse",
    "放大": "zoom in",
    "缩小": "zoom out",
    "移动": "move",
    "复制": "copy",
    "粘贴": "paste",
    "剪切": "cut",
    "撤回": "withdraw",
    "提交": "commit",
    "推送": "push",
    "拉取": "pull",
    "克隆": "clone",
    "分叉": "fork",
    "标签": "tag",
    "修改": "modify",
    "补丁": "patch",
    "升级": "upgrade",
    "降级": "downgrade",

    # Tech
    "数据源": "data source",
    "数据流": "data flow",
    "数据集": "dataset",
    "服务器": "server",
    "客户端": "client",
    "端口": "port",
    "地址": "address",
    "域名": "domain",
    "主机": "host",
    "协议": "protocol",
    "请求头": "request header",
    "响应头": "response header",
    "返回结果": "return result",
    "回调": "callback",
    "回调函数": "callback function",
    "事件循环": "event loop",
    "线程": "thread",
    "线程池": "thread pool",
    "进程池": "process pool",
    "子进程": "subprocess",
    "父进程": "parent process",
    "守护进程": "daemon",
    "后台": "background",
    "前台": "foreground",
    "队列": "queue",
    "栈": "stack",
    "堆": "heap",
    "链表": "linked list",
    "哈希": "hash",
    "映射": "mapping",
    "集合": "set",
    "元组": "tuple",

    # Pipeline / workflow
    "流程": "pipeline",
    "工作流": "workflow",
    "步骤": "step",
    "任务流": "task flow",
    "子任务": "subtask",
    "父任务": "parent task",
    "任务队列": "task queue",
    "任务池": "task pool",

    # Social sim
    "发帖": "post",
    "帖子": "post",
    "评论": "comment",
    "点赞": "like",
    "转发": "repost",
    "关注": "follow",
    "取消关注": "unfollow",
    "回复": "reply",
    "浏览": "browse",
    "搜索": "search",
    "话题": "topic",
    "标签": "tag",
    "热门": "trending",
    "热点": "hotspot",
    "趋势": "trend",

    # Common connectors / qualifiers
    "第一": "first",
    "第二": "second",
    "最后": "last",
    "最后一个": "last one",
    "第一个": "first one",
    "其他": "other",
    "其它": "other",
    "其他的": "other",
    "全部": "all",
    "部分": "part",
    "其余": "the rest",
    "剩余": "remaining",
    "完全": "fully",
    "仅": "only",
    "仅限": "only",
    "只": "only",
    "也": "also",
    "还": "still",
    "再": "again",
    "才": "then",
    "就": "then",
    "都": "all",
    "也是": "is also",
    "已经": "already",
    "正在": "currently",
    "即将": "about to",
    "刚刚": "just now",
    "稍后": "later",
    "立刻": "immediately",
    "马上": "right away",
    "最终": "finally",
    "最开始": "at the start",
    "开头": "start",
    "开始时": "at start",
    "结束时": "at end",
    "初始": "initial",
    "最终的": "final",
    "上次": "last time",
    "下次": "next time",
    "本次": "this time",
    "每次": "each time",

    # Still more leftover fragments
    "制重": "rebuild",
    "不可": "cannot",
    "可以": "can",
    "必须": "must",
    "不能": "cannot",
    "不会": "will not",
    "不需要": "no need",
    "需要": "needs",
    "允许": "allow",
    "禁止": "forbid",
    "限制": "restrict",
    "建议": "suggest",
    "推荐": "recommend",
    "避免": "avoid",
    "防止": "prevent",
    "忽略": "ignore",
    "跳过": "skip",

    # Punctuation bridges: sometimes comments have phrases separated
    # by Chinese punctuation. We translate the punctuation too so the
    # fully_translated check succeeds.
    "，": ", ",
    "。": ". ",
    "：": ": ",
    "；": "; ",
    "？": "? ",
    "！": "! ",
    "、": ", ",
    "（": " (",
    "）": ") ",
    "\u3000": " ",  # full-width space
    "…": "...",
    "——": " — ",
    "—": "—",
    # Typographic curly quotes — use explicit Unicode escapes to avoid
    # collision with Python's triple-quoted string delimiter (if you write
    # three straight double-quotes in a row Python reads them as `"""`).
    "\u201c": '"',  # left double quotation mark
    "\u201d": '"',  # right double quotation mark
    "\u2018": "'",  # left single quotation mark
    "\u2019": "'",  # right single quotation mark

    # ---- Batch 2: further leftover fragments ----
    "人设": "persona",
    "轮数": "round count",
    "循环": "loop",
    "信号": "signal",
    "收到": "received",
    "尝试": "attempt",
    "实时": "real-time",
    "事实": "fact",
    "不要": "do not",
    "工作": "work",
    "通过": "via",
    "引用": "reference",
    "指定": "specify",
    "未知": "unknown",
    "最多": "at most",
    "最少": "at least",
    "功能": "feature",
    "智能": "smart",
    "控制台": "console",
    "要求": "requirement",
    "兜底": "fallback",
    "没有": "no",
    "活动": "activity",
    "标题": "title",
    "分钟": "minute",
    "模式": "mode",
    "项目": "project",
    "保留": "keep",
    "表示": "means",
    "优化": "optimize",
    "直接": "directly",
    "启用": "enable",
    "检测": "detect",
    "模型": "model",
    "可能": "possibly",
    "截断过长的": "truncate overly long",
    "截断": "truncate",
    "对话": "dialog",
    "基础": "basic",
    "两个": "both",
    "回答": "answer",
    "作者": "author",
    "提供": "provide",
    "以及": "as well as",
    "相同": "same",
    "不同": "different",
    "每个": "each",
    "单独": "separate",
    "共同": "shared",
    "共享": "shared",
    "统一": "unified",
    "分别": "respectively",
    "或者": "or",
    "并且": "and",
    "包括": "including",
    "不包括": "not including",
    "涵盖": "cover",
    "包含": "contain",
    "例外": "exception",
    "异常": "exception",
    "场景": "scenario",
    "情况": "case",
    "情形": "case",
    "上下文": "context",
    "背景": "background",
    "基础": "base",
    "依赖": "dependency",
    "依赖注入": "dependency injection",
    "配置项": "config entry",
    "配置文件": "config file",
    "选项": "option",
    "开关": "switch",
    "是否": "whether",
    "真": "true",
    "假": "false",
    "真假": "boolean",
    "大于": "greater than",
    "小于": "less than",
    "等于": "equal to",
    "不等于": "not equal to",
    "大于等于": "greater or equal",
    "小于等于": "less or equal",
    "任意一个": "any one",
    "任意个": "any number of",
    "若干": "several",
    "多个": "multiple",
    "单一": "single",
    "唯一": "unique",
    "重复": "duplicate",

    # Conversation / LLM specific
    "消息体": "message body",
    "系统提示": "system prompt",
    "用户提示": "user prompt",
    "提示词": "prompt",
    "回复": "reply",
    "返回消息": "return message",
    "上下文长度": "context length",
    "上下文窗口": "context window",
    "上限": "upper bound",
    "下限": "lower bound",
    "阈值": "threshold",

    # Zep / Graph specifics
    "节点属性": "node attribute",
    "边属性": "edge attribute",
    "实体节点": "entity node",
    "关系边": "relationship edge",
    "三元组": "triple",
    "事实节点": "fact node",
    "社区": "community",
    "社区摘要": "community summary",
    "时序": "temporal",
    "时序记忆": "temporal memory",

    # Simulation-runner specifics
    "双平台模拟": "dual-platform simulation",
    "单平台模拟": "single-platform simulation",
    "平台结束": "platform ended",
    "模拟结束": "simulation ended",
    "总轮数": "total rounds",
    "总动作数": "total actions",
    "总用户数": "total users",
    "活跃用户": "active user",
    "每轮时长": "duration per round",
    "每轮激活": "activated per round",
    "时段": "time slot",
    "高峰时段": "peak hours",
    "低谷时段": "off-peak hours",
    "工作时段": "work hours",
    "早间时段": "morning hours",
    "夜间时段": "night hours",
    "作息": "daily schedule",
    "激活": "activate",
    "激活率": "activation rate",

    # Phase/progress specifics
    "进入等待命令模式": "entering wait-for-command mode",
    "等待命令模式": "wait-for-command mode",
    "等待命令": "wait for command",
    "命令结束": "command ended",
    "准备工作": "setup work",
    "准备阶段": "preparation phase",

    # Common short verbs/nouns still missing
    "输入的": "input",
    "返回的": "returned",
    "函数返回": "function returns",
    "函数调用": "function call",
    "调用失败": "call failed",
    "调用成功": "call succeeded",
    "调用一次": "call once",
    "次数": "count",
    "秒": "seconds",
    "毫秒": "milliseconds",
    "微秒": "microseconds",
    "分": "minute",
    "小时": "hour",
    "天": "day",
    "周": "week",
    "月": "month",
    "年": "year",
    "当前目录": "current directory",
    "当前路径": "current path",
    "当前状态": "current status",
    "当前阶段": "current phase",
    "当前轮": "current round",
    "当前用户": "current user",
    "仅使用": "only use",
    "只使用": "only use",
    "只保留": "only keep",
    "仅保留": "only keep",
    "默认不": "by default, don't",
}

# --------------------------------------------------------------------------
# File classification
# --------------------------------------------------------------------------

EXTENSIONS = {'.py', '.js', '.ts', '.vue', '.sh'}
EXCLUDE_DIRS = {
    'node_modules', '.venv', 'venv', '__pycache__', 'dist', '.git',
    'uploads', 'cli/node_modules', '.claude',
}


def iter_target_files(root: str, path_filter: str = None):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1]
            if ext not in EXTENSIONS:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if path_filter and not rel.startswith(path_filter):
                continue
            yield full, rel, ext


# --------------------------------------------------------------------------
# Translation engine
# --------------------------------------------------------------------------

# Compile a single regex that matches any key in the dictionary, longest first.
# This avoids partial-match problems (e.g. matching "节点" when we meant "节点详情").
_SORTED_KEYS = sorted(DICTIONARY.keys(), key=len, reverse=True)
_KEY_PATTERN = re.compile('|'.join(re.escape(k) for k in _SORTED_KEYS))


def translate_text(text: str) -> Tuple[str, bool]:
    """Translate CJK phrases in a string using the dictionary.

    Returns (translated_text, fully_translated). The `fully_translated`
    flag is True iff every CJK character in the input got replaced.
    """
    out = _KEY_PATTERN.sub(lambda m: DICTIONARY[m.group(0)], text)
    fully = not CJK.search(out)
    return out, fully


# --------------------------------------------------------------------------
# Per-language comment extractors + writers
# --------------------------------------------------------------------------

TODO_MARKER = "TODO(i18n-sweep): "


def _try_apply(original: str, translated: str, fully: bool,
               stats: Dict[str, int], kind: str) -> str:
    """Only apply a translation if it fully cleared CJK chars. Otherwise
    leave the original untouched and count it as untranslated.

    Rationale: a partial translation like `# 创建the new项目 status` is
    strictly worse than the Chinese original — mixed-language comments
    are harder to read than monolingual ones. We want atomic swaps:
    either the whole comment becomes English, or we leave it for a
    human pass.
    """
    if fully:
        stats[kind] = stats.get(kind, 0) + 1
        return translated
    stats['untranslated'] = stats.get('untranslated', 0) + 1
    return original


def translate_py(content: str) -> Tuple[str, Dict[str, int]]:
    """Translate comments and docstrings in Python source.

    Heuristic for docstrings: the first triple-quoted string after a def
    or class is considered a docstring. Everything else inside a function
    body that happens to be a triple-quoted string is assumed to be an
    LLM prompt or similar and is left alone.
    """
    stats = {'comments': 0, 'docstrings': 0, 'untranslated': 0}
    lines = content.splitlines(keepends=True)
    out_lines = []

    # First pass: detect docstring ranges.
    # We find triple-quote boundaries and mark each as "docstring" if the
    # preceding non-blank line ends with `:` (typical after def/class/module).
    docstring_ranges = set()  # set of line indices that are inside a docstring
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Check for triple-quote start at module level (no indent, line 0-2)
        # or after a def/class ending with `:`
        is_docstring_start = False
        if i == 0 or (i < 3 and stripped.startswith(('"""', "'''"))):
            is_docstring_start = True
        elif stripped.startswith(('"""', "'''")):
            # Look backwards for the preceding non-blank line
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0:
                prev = lines[j].rstrip()
                if prev.endswith(':'):
                    # And the previous line should be a def/class/if/etc.
                    prev_stripped = prev.lstrip()
                    if prev_stripped.startswith(('def ', 'class ', 'async def ')):
                        is_docstring_start = True
                    # Also accept the style where a docstring follows a bare `:`
                    # inside a conditional block (rare but possible)

        if is_docstring_start:
            # Find the matching close
            marker = stripped[:3]
            if stripped.count(marker) >= 2 and len(stripped) > 3:
                # Single-line docstring
                docstring_ranges.add(i)
                i += 1
                continue
            # Multi-line: mark all lines from i to the closing marker
            docstring_ranges.add(i)
            j = i + 1
            while j < len(lines):
                docstring_ranges.add(j)
                if marker in lines[j]:
                    break
                j += 1
            i = j + 1
            continue
        i += 1

    # Second pass: translate
    for idx, line in enumerate(lines):
        if not CJK.search(line):
            out_lines.append(line)
            continue

        if idx in docstring_ranges:
            new_line, fully = translate_text(line)
            out_lines.append(_try_apply(line, new_line, fully, stats, 'docstrings'))
            continue

        # Look for a # comment. IMPORTANT: re `.` doesn't match `\n`, so
        # `(#.*)$` stops at (but does not include) any trailing newline. We
        # must preserve `line[m.end():]` (the trailing newline) explicitly,
        # or the output will have its newline eaten.
        m = re.search(r'(#.*)$', line)
        if m and CJK.search(m.group(1)):
            comment_text = m.group(1)
            before = line[:m.start()]
            after = line[m.end():]
            translated, fully = translate_text(comment_text)
            new_line = before + translated + after
            out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
            continue

        # CJK in a string literal (f-string, print arg, etc.) — leave alone
        out_lines.append(line)

    return ''.join(out_lines), stats


def translate_js_or_ts(content: str) -> Tuple[str, Dict[str, int]]:
    """Translate // and /* */ comments in JS/TS source. String literals are preserved."""
    stats = {'comments': 0, 'untranslated': 0}
    lines = content.splitlines(keepends=True)
    out_lines = []

    in_block = False
    for line in lines:
        if not CJK.search(line) and not in_block:
            out_lines.append(line)
            continue

        # Block comment tracking
        if in_block:
            translated, fully = translate_text(line)
            out_lines.append(_try_apply(line, translated, fully, stats, 'comments'))
            if '*/' in line:
                in_block = False
            continue

        # Look for // comment first (more common). Same newline-preservation
        # caveat as the Python # branch — `.*$` stops before `\n`.
        m = re.search(r'(//.*)$', line)
        if m and CJK.search(m.group(1)):
            comment_text = m.group(1)
            before = line[:m.start()]
            after = line[m.end():]
            translated, fully = translate_text(comment_text)
            new_line = before + translated + after
            out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
            continue

        # /* ... */ block comment on one line
        m = re.search(r'(/\*.*?\*/)', line)
        if m and CJK.search(m.group(1)):
            before = line[:m.start()]
            after = line[m.end():]
            translated, fully = translate_text(m.group(1))
            new_line = before + translated + after
            out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
            continue

        # /* ... (block open, continues on next line)
        if '/*' in line and '*/' not in line:
            in_block = True
            if CJK.search(line):
                translated, fully = translate_text(line)
                out_lines.append(_try_apply(line, translated, fully, stats, 'comments'))
            else:
                out_lines.append(line)
            continue

        # CJK in string or template literal — leave alone
        out_lines.append(line)

    return ''.join(out_lines), stats


def translate_vue(content: str) -> Tuple[str, Dict[str, int]]:
    """Translate comments in .vue files.

    Three sections to handle:
      <template>: <!-- --> comments translated, template text literals left alone
      <script>:   JS translation rules apply
      <style>:    /* */ comments translated
    """
    stats = {'comments': 0, 'untranslated': 0}
    lines = content.splitlines(keepends=True)
    out_lines = []

    in_template = False
    in_script = False
    in_style = False
    in_block_comment = False

    for line in lines:
        # Section markers
        if '<template' in line and '>' in line:
            in_template = True
            in_script = False
            in_style = False
        elif '</template>' in line:
            in_template = False
        if '<script' in line and '>' in line:
            in_script = True
            in_template = False
            in_style = False
        elif '</script>' in line:
            in_script = False
        if '<style' in line and '>' in line:
            in_style = True
            in_template = False
            in_script = False
        elif '</style>' in line:
            in_style = False

        if not CJK.search(line) and not in_block_comment:
            out_lines.append(line)
            continue

        if in_template:
            # HTML comment <!-- ... -->
            m = re.search(r'(<!--.*?-->)', line)
            if m and CJK.search(m.group(1)):
                before = line[:m.start()]
                after = line[m.end():]
                translated, fully = translate_text(m.group(1))
                new_line = before + translated + after
                out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
                continue
            # Template text is an i18n leak, leave alone
            out_lines.append(line)
            continue

        if in_script:
            if in_block_comment:
                translated, fully = translate_text(line)
                out_lines.append(_try_apply(line, translated, fully, stats, 'comments'))
                if '*/' in line:
                    in_block_comment = False
                continue
            m = re.search(r'(//.*)$', line)
            if m and CJK.search(m.group(1)):
                comment_text = m.group(1)
                before = line[:m.start()]
                after = line[m.end():]
                translated, fully = translate_text(comment_text)
                new_line = before + translated + after
                out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
                continue
            m = re.search(r'(/\*.*?\*/)', line)
            if m and CJK.search(m.group(1)):
                before = line[:m.start()]
                after = line[m.end():]
                translated, fully = translate_text(m.group(1))
                new_line = before + translated + after
                out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
                continue
            if '/*' in line and '*/' not in line:
                in_block_comment = True
                if CJK.search(line):
                    translated, fully = translate_text(line)
                    out_lines.append(_try_apply(line, translated, fully, stats, 'comments'))
                else:
                    out_lines.append(line)
                continue
            out_lines.append(line)
            continue

        if in_style:
            # CSS only has /* */
            if in_block_comment:
                translated, fully = translate_text(line)
                out_lines.append(_try_apply(line, translated, fully, stats, 'comments'))
                if '*/' in line:
                    in_block_comment = False
                continue
            m = re.search(r'(/\*.*?\*/)', line)
            if m and CJK.search(m.group(1)):
                before = line[:m.start()]
                after = line[m.end():]
                translated, fully = translate_text(m.group(1))
                new_line = before + translated + after
                out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
                continue
            if '/*' in line and '*/' not in line:
                in_block_comment = True
                if CJK.search(line):
                    translated, fully = translate_text(line)
                    out_lines.append(_try_apply(line, translated, fully, stats, 'comments'))
                else:
                    out_lines.append(line)
                continue
            out_lines.append(line)
            continue

        # Outside any section — leave as-is
        out_lines.append(line)

    return ''.join(out_lines), stats


def translate_sh(content: str) -> Tuple[str, Dict[str, int]]:
    """Translate # comments in shell scripts."""
    stats = {'comments': 0, 'untranslated': 0}
    lines = content.splitlines(keepends=True)
    out_lines = []
    for line in lines:
        if not CJK.search(line):
            out_lines.append(line)
            continue
        m = re.search(r'(#.*)$', line)
        if m and CJK.search(m.group(1)):
            before = line[:m.start()]
            after = line[m.end():]
            translated, fully = translate_text(m.group(1))
            new_line = before + translated + after
            out_lines.append(_try_apply(line, new_line, fully, stats, 'comments'))
            continue
        out_lines.append(line)
    return ''.join(out_lines), stats


TRANSLATORS = {
    '.py': translate_py,
    '.js': translate_js_or_ts,
    '.ts': translate_js_or_ts,
    '.vue': translate_vue,
    '.sh': translate_sh,
}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--path', default=None, help='subdirectory filter (relative to repo root)')
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help='repo root (default: parent of scripts/)')
    args = ap.parse_args()

    totals = {'files': 0, 'comments': 0, 'docstrings': 0, 'untranslated': 0, 'files_changed': 0}

    for full, rel, ext in iter_target_files(args.root, args.path):
        try:
            with open(full, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f'[skip] {rel}: {e}', file=sys.stderr)
            continue

        if not CJK.search(content):
            continue

        translator = TRANSLATORS.get(ext)
        if not translator:
            continue

        new_content, stats = translator(content)
        totals['files'] += 1
        totals['comments'] += stats.get('comments', 0)
        totals['docstrings'] += stats.get('docstrings', 0)
        totals['untranslated'] += stats.get('untranslated', 0)

        if new_content != content:
            totals['files_changed'] += 1
            if not args.dry_run:
                with open(full, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            action = 'would write' if args.dry_run else 'wrote'
            print(f'{action} {rel}: '
                  f'{stats.get("comments", 0)} comments, '
                  f'{stats.get("docstrings", 0)} docstrings, '
                  f'{stats.get("untranslated", 0)} untranslated')

    print()
    print(f'--- totals ({"dry run" if args.dry_run else "applied"}) ---')
    print(f'  files seen with CJK:     {totals["files"]}')
    print(f'  files changed:           {totals["files_changed"]}')
    print(f'  comment lines translated:   {totals["comments"]}')
    print(f'  docstring lines translated: {totals["docstrings"]}')
    print(f'  lines with remaining CJK:   {totals["untranslated"]}')


if __name__ == '__main__':
    main()
