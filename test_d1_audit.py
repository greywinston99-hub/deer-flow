import sys
import os
import logging
import traceback
import shutil

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

REPO_ROOT = "/Users/winstonwei/Documents/Playground/deer-flow"
HARNES_PATH = os.path.join(REPO_ROOT, "backend", "packages", "harness")
if HARNES_PATH not in sys.path:
    sys.path.insert(0, HARNES_PATH)

from deerflow.runtime.cer_review import CERReviewRunner

workflow_path = os.path.join(REPO_ROOT, "backend", "workflows", "cer_review_workflow_v1.yaml")
project_profile_path = os.path.join(REPO_ROOT, "examples", "cer_review", "project_profile_smoke_precheck.yaml")

try:
    runner = CERReviewRunner(
        repo_root=REPO_ROOT,
        workflow_path=workflow_path,
        project_profile_path=project_profile_path,
        run_mode="smoke-run",
    )
    result = runner.run()
    print("\n========== RUN COMPLETED ==========")
    print("Run ID:", result.run_id)
    print("Thread ID:", result.thread_id)
    print("Artifact Root Actual:", result.artifact_root_actual)
    print("Executed steps:", result.executed_steps)
    print("===================================\n")
except Exception as e:
    print("Run failed with exception:", type(e).__name__, str(e))
    traceback.print_exc()
    sys.exit(1)
