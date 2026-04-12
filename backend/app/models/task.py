"""
task state management
用于跟踪长时间运行的任务（如图谱构建）
"""

import uuid
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..utils.locale import t


class TaskStatus(str, Enum):
    """task status enum"""
    PENDING = "pending"          # waiting
    PROCESSING = "processing"    # processing
    COMPLETED = "completed"      # completed
    FAILED = "failed"            # failed
    CANCELLED = "cancelled"      # cancelled (Phase 7)


@dataclass
class Task:
    """task dataclass"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # overall progress percentage 0-100
    message: str = ""              # status message
    result: Optional[Dict] = None  # task result
    error: Optional[str] = None    # error info
    metadata: Dict = field(default_factory=dict)  # extra metadata
    progress_detail: Dict = field(default_factory=dict)  # detailed progress info
    
    def to_dict(self) -> Dict[str, Any]:
        """convert to dict"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskManager:
    """
    task manager
    thread-safe task state management
    """
    
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """singleton"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
                    cls._instance._cancel_events: Dict[str, threading.Event] = {}
        return cls._instance
    
    def create_task(self, task_type: str, metadata: Optional[Dict] = None) -> str:
        """
        create a new task
        
        Args:
            task_type: task type
            metadata: extra metadata
            
        Returns:
            task ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """get task"""
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None
    ):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度
            message: 消息
            result: 结果
            error: 错误信息
            progress_detail: 详细进度信息
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                task.updated_at = datetime.now()
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message is not None:
                    task.message = message
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress_detail is not None:
                    task.progress_detail = progress_detail
    
    def complete_task(self, task_id: str, result: Dict):
        """mark task complete"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message=t('progress.taskComplete'),
            result=result
        )
    
    def fail_task(self, task_id: str, error: str):
        """mark task failed"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message=t('progress.taskFailed'),
            error=error
        )

    # --- Phase 7: cancellation support ---
    def request_cancel(self, task_id: str) -> bool:
        """Request cancellation of a running task.

        Returns True if a cancel event was set, False if task not found or already done.
        The worker thread must call `is_cancelled(task_id)` at safe checkpoints
        (e.g., batch boundaries) to observe the cancellation.
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            event = self._cancel_events.get(task_id)
            if event is None:
                event = threading.Event()
                self._cancel_events[task_id] = event
            event.set()
            return True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been asked to cancel."""
        with self._task_lock:
            event = self._cancel_events.get(task_id)
            return bool(event and event.is_set())

    def cancel_task(self, task_id: str, reason: str = ""):
        """Mark a task as cancelled (worker thread calls this when it observes the cancel flag)."""
        self.update_task(
            task_id,
            status=TaskStatus.CANCELLED,
            message=reason or "Cancelled by user",
        )
    
    def list_tasks(self, task_type: Optional[str] = None) -> list:
        """list tasks"""
        with self._task_lock:
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """clean up old tasks"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            for tid in old_ids:
                del self._tasks[tid]

