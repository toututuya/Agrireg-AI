from __future__ import annotations

import json
from pathlib import Path

from agrireg_agent.planner import fallback_plan


def main() -> int:
    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    failures = []
    for case in cases:
        plan = fallback_plan(case["question"], case.get("forceApproval", False))
        actual = {
            "taskType": plan.task_type,
            "approval": plan.requires_approval,
            "missing": bool(plan.missing_information),
            "tools": [step.tool for step in plan.steps],
        }
        expected = {key: case[key] for key in ("taskType", "approval", "missing", "tools")}
        if actual != expected:
            failures.append({"id": case["id"], "expected": expected, "actual": actual})

    summary = {
        "cases": len(cases),
        "passed": len(cases) - len(failures),
        "failed": len(failures),
        "failures": failures,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

