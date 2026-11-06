"""Run paired experiments. Every result includes actual model output and trace."""
import argparse
import csv
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agent import run_agent, run_direct
from src.model import DEFAULT_MODEL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["llm", "offline"], default="llm")
    parser.add_argument("--label", default="", help="Result stem, preserving earlier runs")
    args = parser.parse_args()
    cases = json.loads((ROOT / "tests/cases.json").read_text(encoding="utf-8"))
    records, rows = [], []
    for case in cases:
        request = {k:v for k,v in case.items() if k not in ("expected", "id", "title")}
        for group in (["direct_llm", "agent_tools"] if args.mode == "llm" else ["offline_rules"]):
            started = time.perf_counter()
            try:
                answer = run_direct(request) if group == "direct_llm" else run_agent(request, args.mode)
                expected = case["expected"]
                correct = answer["verdict"] == expected["verdict"]
                target = expected["one_way_propagation_ms"]
                val = answer.get("one_way_propagation_ms")
                numeric = None if target is None else isinstance(val,(float,int)) and abs(val-target) <= 0.01
                tools = None if group == "direct_llm" else [t["tool"] for t in answer["Tool Results"]] == expected["tools"]
                success = correct and (numeric is not False) and (tools is not False)
                error = None
            except Exception as exc:
                answer = {}; correct = False; numeric = False if case["expected"]["one_way_propagation_ms"] is not None else None
                tools = None if group == "direct_llm" else False
                success = False; error = f"{type(exc).__name__}: {exc}"
            elapsed = round(time.perf_counter()-started,4)
            record = {"case":case["id"],"group":group,"request":request,"expected":case["expected"],"answer":answer,"error":error,"elapsed_seconds":elapsed}
            records.append(record)
            rows.append({"case":case["id"],"title":case["title"],"group":group,"verdict":answer.get("verdict","error"),
                         "verdict_correct":int(correct),"numeric_correct":"" if numeric is None else int(numeric),
                         "tools_correct":"" if tools is None else int(tools),"task_success":int(success),"elapsed_seconds":elapsed})
            print(f"{case['id']} {group}: {answer.get('verdict',error)} success={success} time={elapsed:.2f}s", flush=True)
            output = ROOT / "results" / (args.label or ("evaluation" if args.mode == "llm" else "offline"))
            output.with_suffix(".json").write_text(json.dumps({"metadata":{"timestamp_utc":datetime.now(timezone.utc).isoformat(),"mode":args.mode,"model":DEFAULT_MODEL,"temperature":0,"seed":42,"python":platform.python_version(),"numeric_tolerance_ms":0.01,"repeats":1},"runs":records},ensure_ascii=False,indent=2),encoding="utf-8")
            with output.with_suffix(".csv").open("w",encoding="utf-8-sig",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    if any(r["error"] for r in records):
        print("Some runs failed; retained as failed runs. See JSON.")


if __name__ == "__main__":
    main()
