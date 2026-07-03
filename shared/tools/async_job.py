"""
AsyncJobTool: start any long-running job and poll it later.

Agents use this whenever a task would otherwise block for minutes:
  - type="gh_actions"  fire a GitHub Actions workflow_dispatch
  - type="shell"       run a shell command in the background (BDD, test suites, builds)
  - type="ecs"         trigger an ECS service update and wait for stabilisation

All three return the same handle dict. The REPL (or the agent on a follow-up tool call)
passes the handle back via operation="poll" to check status without blocking.

Typical agent usage
-------------------
Step 1 — start the job:
  async_job(operation="start", type="shell",
            params={"command": "npm run test:bdd -- --tags @smoke",
                    "label": "BDD smoke suite", "cwd": "/app"})
  → {"handle": {"type": "shell", "job_id": "a1b2c3d4", "log_file": "...", "status_file": "..."}}

Step 2 — emit the handle so the REPL can poll:
  RUN_HANDLE: {"type": "shell", "job_id": "a1b2c3d4", ...}

Or poll inline (short tasks):
  async_job(operation="poll", handle={"type": "shell", ...})
  → {"status": "running" | "success" | "failure", "log_tail": "..."}
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Literal, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class _AsyncJobInput(BaseModel):
    operation: Literal["start", "poll"] = Field(
        description=(
            "'start' kicks off a job and returns a handle dict. "
            "'poll' checks a handle returned by a previous start."
        )
    )
    type: str = Field(
        default="",
        description=(
            "Job backend — required for start, ignored for poll. "
            "  gh_actions — trigger a GitHub Actions workflow_dispatch. "
            "  shell      — run any shell command in the background (BDD, test suites, builds, etc.). "
            "  ecs        — trigger an ECS service update and wait for stabilisation."
        ),
    )
    params: dict = Field(
        default_factory=dict,
        description=(
            "Backend-specific parameters for start. "
            "gh_actions: {workflow, ref, inputs, repo}. "
            "shell:      {command, label, cwd}. "
            "ecs:        {cluster, service, image, region}."
        ),
    )
    handle: dict = Field(
        default_factory=dict,
        description="Handle dict returned by a previous start call. Required for poll.",
    )


class AsyncJobTool(BaseTool):
    name: str = "async_job"
    description: str = (
        "Start or poll a long-running background job. Use this whenever a task would "
        "block for minutes — CI deploys, BDD test suites, ECS updates, etc.\n\n"
        "operation='start'  — kick off the job; returns a handle dict.\n"
        "operation='poll'   — check status of a handle; returns "
        "{status, conclusion, url, log_tail}.\n\n"
        "status values: pending | running | success | failure | unknown.\n\n"
        "After start, output the handle on its own line so the REPL can poll it:\n"
        "  RUN_HANDLE: {<handle dict>}\n\n"
        "Type guide:\n"
        "  gh_actions — params: {workflow, ref?, inputs?, repo?}\n"
        "  shell      — params: {command, label?, cwd?}  "
        "(use for BDD suites, npm test, go test, any shell command)\n"
        "  ecs        — params: {cluster, service, image?, region?}"
    )
    args_schema: type[BaseModel] = _AsyncJobInput

    def _run(
        self,
        operation: str,
        type: str = "",
        params: dict | None = None,
        handle: dict | None = None,
    ) -> str:
        params = params or {}
        handle = handle or {}

        if operation == "start":
            if type == "gh_actions":
                return self._start_gh(params)
            if type == "shell":
                return self._start_shell(params)
            if type == "ecs":
                return self._start_ecs(params)
            return json.dumps({"error": f"unknown type {type!r} — use gh_actions, shell, or ecs"})

        if operation == "poll":
            if not handle:
                return json.dumps({"error": "handle is required for poll"})
            htype = handle.get("type", "")
            if htype == "gh_actions":
                return self._poll_gh(handle)
            if htype == "shell":
                return self._poll_shell(handle)
            if htype == "ecs":
                return self._poll_ecs(handle)
            return json.dumps({"error": f"unknown handle type {htype!r}"})

        return json.dumps({"error": f"unknown operation {operation!r} — use start or poll"})

    # ------------------------------------------------------------------
    # gh_actions backend
    # ------------------------------------------------------------------

    def _start_gh(self, params: dict) -> str:
        workflow = params.get("workflow", "")
        if not workflow:
            return json.dumps({"error": "params.workflow is required for gh_actions"})

        ref = params.get("ref", "")
        repo = params.get("repo", "")
        inputs = params.get("inputs", {})

        cmd = ["gh", "workflow", "run", workflow]
        if ref:
            cmd += ["--ref", ref]
        if repo:
            cmd += ["--repo", repo]
        for k, v in inputs.items():
            cmd += ["--field", f"{k}={v}"]

        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return json.dumps({"error": r.stderr.strip()[:300]})

        # gh workflow run outputs nothing on success — fetch the newest run
        list_cmd = ["gh", "run", "list", "--workflow", workflow,
                    "--limit", "1", "--json", "databaseId,status,url"]
        if repo:
            list_cmd += ["--repo", repo]
        lr = subprocess.run(list_cmd, capture_output=True, text=True)
        if lr.returncode != 0:
            return json.dumps({"error": lr.stderr.strip()[:300]})

        runs = json.loads(lr.stdout or "[]")
        if not runs:
            return json.dumps({"error": "workflow triggered but no run found"})

        run = runs[0]
        handle = {
            "type": "gh_actions",
            "run_id": run["databaseId"],
            "workflow": workflow,
            "repo": repo,
        }
        return json.dumps({"handle": handle, "status": run.get("status", "queued"),
                           "url": run.get("url", "")})

    def _poll_gh(self, handle: dict) -> str:
        run_id = handle.get("run_id")
        repo = handle.get("repo", "")
        if not run_id:
            return json.dumps({"status": "unknown", "error": "no run_id in handle"})

        cmd = ["gh", "run", "view", str(run_id),
               "--json", "status,conclusion,url,workflowName"]
        if repo:
            cmd += ["--repo", repo]

        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return json.dumps({"status": "unknown", "error": r.stderr.strip()[:200]})

        info = json.loads(r.stdout)
        return json.dumps(_normalize_gh(info))

    # ------------------------------------------------------------------
    # shell backend
    # ------------------------------------------------------------------

    def _start_shell(self, params: dict) -> str:
        import shlex
        import uuid

        command = params.get("command", "")
        if not command:
            return json.dumps({"error": "params.command is required for shell"})

        label = params.get("label", "job")
        cwd = params.get("cwd", "") or str(Path.cwd())

        job_id = str(uuid.uuid4())[:8]
        job_dir = Path.cwd() / ".code-crew" / "jobs"
        job_dir.mkdir(parents=True, exist_ok=True)

        log_file = str(job_dir / f"{job_id}.log")
        status_file = str(job_dir / f"{job_id}.status")
        # Script writes exit code to status_file when done — survives REPL restarts
        script = (
            f"#!/bin/bash\n"
            f"cd {shlex.quote(cwd)}\n"
            f"{command}\n"
            f"echo $? > {shlex.quote(status_file)}\n"
        )
        script_path = str(job_dir / f"{job_id}.sh")
        Path(script_path).write_text(script, encoding="utf-8")
        os.chmod(script_path, 0o755)

        with open(log_file, "w") as lf:
            proc = subprocess.Popen(
                ["bash", script_path],
                stdout=lf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )

        handle = {
            "type": "shell",
            "job_id": job_id,
            "pid": proc.pid,
            "label": label,
            "log_file": log_file,
            "status_file": status_file,
        }
        return json.dumps({"handle": handle, "status": "running",
                           "message": f"Started '{label}' (pid {proc.pid})"})

    def _poll_shell(self, handle: dict) -> str:
        status_file = handle.get("status_file", "")
        log_file = handle.get("log_file", "")
        pid = handle.get("pid")

        # Status file written by the wrapper script when the command exits
        if status_file and Path(status_file).exists():
            try:
                exit_code = int(Path(status_file).read_text().strip())
            except ValueError:
                exit_code = 1
            status = "success" if exit_code == 0 else "failure"
            log_tail = _read_tail(log_file)
            return json.dumps({"status": status, "conclusion": status,
                               "exit_code": exit_code, "log_tail": log_tail})

        # No status file yet — check if the process is still alive
        if pid:
            try:
                os.kill(pid, 0)
                running = True
            except ProcessLookupError:
                running = False
            except PermissionError:
                running = True
        else:
            running = False

        if running:
            log_tail = _read_tail(log_file, lines=5)
            return json.dumps({"status": "running", "conclusion": "", "log_tail": log_tail})

        # Process gone and no status file — it was killed or crashed
        log_tail = _read_tail(log_file)
        return json.dumps({"status": "failure", "conclusion": "failure",
                           "error": "process exited without writing status file",
                           "log_tail": log_tail})

    # ------------------------------------------------------------------
    # ecs backend
    # ------------------------------------------------------------------

    def _start_ecs(self, params: dict) -> str:
        cluster = params.get("cluster", "")
        service = params.get("service", "")
        image = params.get("image", "")
        region = params.get("region", "")

        if not cluster or not service:
            return json.dumps({"error": "params.cluster and params.service are required for ecs"})

        cmd = ["aws", "ecs", "update-service",
               "--cluster", cluster, "--service", service,
               "--force-new-deployment"]
        if image:
            # In practice image updates go through task-def registration; keep simple for now
            cmd += ["--task-definition", image]
        if region:
            cmd += ["--region", region]

        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return json.dumps({"error": r.stderr.strip()[:300]})

        handle = {
            "type": "ecs",
            "cluster": cluster,
            "service": service,
            "region": region,
        }
        return json.dumps({"handle": handle, "status": "pending",
                           "message": f"ECS service update triggered for {service}"})

    def _poll_ecs(self, handle: dict) -> str:
        cluster = handle.get("cluster", "")
        service = handle.get("service", "")
        region = handle.get("region", "")

        if not cluster or not service:
            return json.dumps({"status": "unknown", "error": "missing cluster or service"})

        cmd = ["aws", "ecs", "describe-services",
               "--cluster", cluster, "--services", service,
               "--query", "services[0].{status:status,running:runningCount,desired:desiredCount}",
               "--output", "json"]
        if region:
            cmd += ["--region", region]

        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return json.dumps({"status": "unknown", "error": r.stderr.strip()[:200]})

        info = json.loads(r.stdout)
        if not info:
            return json.dumps({"status": "unknown", "error": "no service found"})

        svc_status = info.get("status", "").upper()
        running = info.get("running", 0)
        desired = info.get("desired", 0)

        if svc_status == "ACTIVE" and desired > 0 and running == desired:
            status = "success"
            conclusion = "success"
        elif svc_status in ("DRAINING", "INACTIVE"):
            status = "failure"
            conclusion = "failure"
        else:
            status = "running"
            conclusion = ""

        return json.dumps({"status": status, "conclusion": conclusion,
                           "running": running, "desired": desired})


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def _normalize_gh(info: dict) -> dict:
    raw = info.get("status", "unknown")
    conclusion = info.get("conclusion") or ""
    if raw == "completed":
        status = conclusion if conclusion in ("success", "failure", "timed_out", "cancelled") else "failure"
    elif raw == "in_progress":
        status = "running"
    elif raw in ("queued", "waiting", "pending"):
        status = "pending"
    else:
        status = raw
    return {"status": status, "conclusion": conclusion,
            "url": info.get("url", ""), "name": info.get("workflowName", "")}


def _read_tail(log_file: str, lines: int = 20) -> str:
    if not log_file or not Path(log_file).exists():
        return ""
    try:
        text = Path(log_file).read_text(encoding="utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])
    except OSError:
        return ""


# Backward-compat alias (code that imported CiStatusTool still works)
CiStatusTool = AsyncJobTool
