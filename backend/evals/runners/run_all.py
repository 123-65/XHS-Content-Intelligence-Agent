import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from evals.runners.agent_trajectory_runner import DEFAULT_DATASET as AGENT_TRAJECTORY_DATASET
from evals.runners.agent_trajectory_runner import EVAL_TYPE as AGENT_TRAJECTORY_EVAL_TYPE
from evals.runners.agent_trajectory_runner import evaluate_case as eval_agent_trajectory
from evals.runners.comment_classification_runner import DEFAULT_DATASET as COMMENT_DATASET
from evals.runners.comment_classification_runner import EVAL_TYPE as COMMENT_EVAL_TYPE
from evals.runners.comment_classification_runner import evaluate_case as eval_comment
from evals.runners.core import run_eval
from evals.runners.draft_safety_runner import DEFAULT_DATASET as DRAFT_DATASET
from evals.runners.draft_safety_runner import EVAL_TYPE as DRAFT_EVAL_TYPE
from evals.runners.draft_safety_runner import evaluate_case as eval_draft
from evals.runners.experiment_generation_runner import DEFAULT_DATASET as EXPERIMENT_DATASET
from evals.runners.experiment_generation_runner import EVAL_TYPE as EXPERIMENT_EVAL_TYPE
from evals.runners.experiment_generation_runner import evaluate_case as eval_experiment
from evals.runners.memory_usage_runner import DEFAULT_DATASET as MEMORY_USAGE_DATASET
from evals.runners.memory_usage_runner import EVAL_TYPE as MEMORY_USAGE_EVAL_TYPE
from evals.runners.memory_usage_runner import evaluate_case as eval_memory_usage
from evals.runners.mcp_safety_runner import DEFAULT_DATASET as MCP_DATASET
from evals.runners.mcp_safety_runner import EVAL_TYPE as MCP_EVAL_TYPE
from evals.runners.mcp_safety_runner import evaluate_case as eval_mcp


def main() -> None:
    """运行全部基础评测套件。"""
    runners = [
        (COMMENT_EVAL_TYPE, COMMENT_DATASET, eval_comment),
        (EXPERIMENT_EVAL_TYPE, EXPERIMENT_DATASET, eval_experiment),
        (DRAFT_EVAL_TYPE, DRAFT_DATASET, eval_draft),
        (MCP_EVAL_TYPE, MCP_DATASET, eval_mcp),
        (AGENT_TRAJECTORY_EVAL_TYPE, AGENT_TRAJECTORY_DATASET, eval_agent_trajectory),
        (MEMORY_USAGE_EVAL_TYPE, MEMORY_USAGE_DATASET, eval_memory_usage),
    ]
    reports = [run_eval(eval_type, dataset, evaluator).model_dump(mode="json") for eval_type, dataset, evaluator in runners]
    print(json.dumps({"total_suites": len(reports), "reports": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
