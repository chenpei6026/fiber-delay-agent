import argparse
import json
from pathlib import Path
from .agent import run_agent


def main():
    parser = argparse.ArgumentParser(description="FiberScope 光纤链路时延诊断助手")
    parser.add_argument("--mode", choices=["llm", "offline"], default="llm")
    parser.add_argument("--case", default="C2")
    parser.add_argument("--request", help="自定义 UTF-8 JSON 请求文件")
    parser.add_argument("--output", help="保存完整 JSON 工具日志")
    args = parser.parse_args()
    if args.request:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    else:
        cases = json.loads((Path(__file__).resolve().parents[1] / "tests/cases.json").read_text(encoding="utf-8"))
        request = next((c for c in cases if c["id"] == args.case), None)
        if request is None:
            parser.error("未知 Case")
        request = {k: v for k, v in request.items() if k not in ("expected", "id", "title")}
    try:
        answer = run_agent(request, args.mode)
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
    text = json.dumps(answer, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
