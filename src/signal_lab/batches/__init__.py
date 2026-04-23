from .config import load_workflow_batch_config
from .models import BatchRunMode, WorkflowBatchConfig, WorkflowBatchEntry

__all__ = [
    "BatchRunMode",
    "WorkflowBatchConfig",
    "WorkflowBatchEntry",
    "WorkflowBatchRunner",
    "load_workflow_batch_config",
]


def __getattr__(name: str):
    if name == "WorkflowBatchRunner":
        from .runner import WorkflowBatchRunner

        return WorkflowBatchRunner
    raise AttributeError(name)
