"""Single LLM planner + tool execution + auditable evidence synthesis.

The offline mode is explicitly a rule-driven demonstration, not an LLM run.
"""
import json
import time
from .model import chat
from .tools import query_link, evaluate_link, check_service

TOOL_NAMES = ["query_link", "evaluate_link", "check_service"]
PLAN_SCHEMA = {"type": "object", "properties": {
    "intent": {"type": "string", "enum": ["diagnose", "calculate", "service", "clarify"]},
    "tools": {"type": "array", "items": {"type": "string", "enum": TOOL_NAMES}, "maxItems": 3},
    "reason": {"type": "string"}}, "required": ["intent", "tools", "reason"], "additionalProperties": False}
VERDICTS = ["healthy", "excess_delay", "propagation_limited", "insufficient_data", "inconsistent_data", "invalid_input"]
ANSWER_SCHEMA = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": VERDICTS},
    "one_way_propagation_ms": {"type": ["number", "null"]},
    "reason": {"type": "string"}}, "required": ["verdict", "one_way_propagation_ms", "reason"], "additionalProperties": False}
POLICY = """你是光纤网络时延助手。使用单程实际光路长度、群折射率1.468、光速299792458 m/s。
传播单程t=L*n/c；对称RTT下限2t。传播不等于总时延，额外RTT不能直接等同排队。
只有测得的同一指标<=用户阈值时才判业务达标。one_way阈值不能直接比较RTT。
裁决优先级：非法值invalid_input；测量RTT低于物理下限0.1ms以上inconsistent_data；
传播下限超过用户业务预算propagation_limited；数据不足insufficient_data；
RTT超预算且有明显额外时延excess_delay；否则healthy。
对于计算问题，有长度即可完成；只有业务测量与预算的问题不需要长度。
诊断问题缺长度或RTT应说明信息不足。只能提出可能原因，禁止确定根因。"""
PLANNER = """你是工具调度员。只输出JSON计划，不计算答案，也不诊断原因。
必须阅读JSON字段：有link_id就必须先query_link，否则没有测量数据！
query_link: 输入link_id查询模拟测量；问题有link_id需要它，没有link_id不要选。
evaluate_link: 根据length_km/refractive_index/rtt_ms计算传播和额外RTT；诊断和计算需要它。
check_service: 检查用户budget_ms/metric对应的业务阈值；有预算需要它。
按依赖顺序排列工具：先查数据，再计算，再阈值检查。不要重复工具。
计算问题intent=calculate；测量达标问题intent=service；链路异常分析intent=diagnose。
即使信息缺失也允许选择工具，工具返回错误后诚实说明。
例1: {"question":"分析链路","link_id":"ABC","budget_ms":20} ->
{"intent":"diagnose","tools":["query_link","evaluate_link","check_service"],"reason":"先查询编号对应测量，再计算并检查预算"}
例2: {"question":"只计算500km的传播时延","facts":{"length_km":500}} ->
{"intent":"calculate","tools":["evaluate_link"],"reason":"只需传播计算"}
例3: {"question":"单程10ms，预算20ms是否达标","facts":{"one_way_measured_ms":10},"budget_ms":20,"metric":"one_way"} ->
{"intent":"service","tools":["check_service"],"reason":"只需业务阈值比较"}
reason用简短中文。"""


def offline_plan(request):
    intent = request.get("intent", "diagnose")
    tools = (["query_link"] if request.get("link_id") else [])
    if intent != "service":
        tools.append("evaluate_link")
    if "budget_ms" in request:
        tools.append("check_service")
    return {"intent": intent, "tools": tools, "reason": "离线规则演示：按显式意图选择工具；本模式不使用 LLM。"}


def synthesize(request, plan, traces, metrics, service):
    errors = [t["error"] for t in traces if "error" in t]
    observations, analysis, advice = [], [], []
    verdict = "insufficient_data"
    hypotheses = ["H1：光路传播距离限制业务时延", "H2：负载、路由或处理增加额外时延"]
    if metrics:
        observations.append(f"单程传播 {metrics['one_way_propagation_ms']:.6f} ms；对称 RTT 传播下限 {metrics['symmetric_rtt_floor_ms']:.6f} ms。")
        if metrics["measured_rtt_ms"] is not None:
            observations.append(f"实测 RTT {metrics['measured_rtt_ms']:g} ms，额外 RTT {metrics['excess_rtt_ms']:.6f} ms。")
    if errors:
        observations.extend(errors)
        if any(t.get("error_kind") == "invalid_input" for t in traces):
            verdict = "invalid_input"
        advice.append("核对参数单位、合法范围和缺失字段后重试。")
    elif metrics and metrics["below_physical_floor"]:
        verdict = "inconsistent_data"
        analysis.append("实测 RTT 低于按给定光路计算的传播下限，现有输入相互矛盾，不能据此宣布网络正常。")
        advice.append("核对实际光路长度、RTT/单程单位、反向路径与测量时间。")
    elif service and service["propagation_alone_exceeds_budget"]:
        verdict = "propagation_limited"
        analysis.append("即使没有排队，给定路径的传播下限已超过当前业务预算，支持 H1。")
        advice.append("考虑缩短实际路径、边缘部署或调整业务预算；仅增加带宽不能消除传播时延。")
    elif plan["intent"] == "calculate" and metrics:
        verdict = "healthy"
        analysis.append("已完成传播计算；这是物理下限，不能当作实际业务总时延。")
    elif plan["intent"] == "service" and service and service["measurement_pass"] is not None:
        verdict = "healthy" if service["measurement_pass"] else "excess_delay"
        analysis.append("按用户给定的同种时延指标和项目阈值比较；本次没有证据定位故障原因。")
    elif not metrics or metrics["measured_rtt_ms"] is None or not service or service["metric"] != "rtt":
        verdict = "insufficient_data"
        analysis.append("信息不足：诊断需要长度、同一时段 RTT 及明确的 RTT 预算；不能用 RTT/2 代替实测单程时延。")
        advice.append("补充缺失数据或单程同步测量，再复测高峰/低峰差异。")
    elif service["measurement_pass"]:
        verdict = "healthy"
        analysis.append("当前 RTT 未超过用户设定预算，本次快照未支持时延超标。仍不能据此排除间歇性故障。")
    else:
        verdict = "excess_delay"
        analysis.append("RTT 超过预算，且存在传播以外的额外时延，H1 不能单独解释现象。")
        if metrics["utilization_pct"] is not None and metrics["utilization_pct"] >= 85:
            analysis.append("利用率达到 85% 经验告警线，支持负载竞争的可能性，但不证明排队是唯一根因。")
        if metrics["loss_pct"] is not None and metrics["loss_pct"] > 1:
            analysis.append("丢包超过项目 1% 经验告警线；还应检查错误计数、拥塞和测量偏差。")
        advice.append("收集高低峰 RTT/利用率时间序列，检查接口错误、路径变化和设备处理时延。")
    if not advice:
        advice.append("保留工具结果并结合更多时段测量复核；不要从单个快照断言根因。")
    return {"verdict": verdict,
            "one_way_propagation_ms": metrics.get("one_way_propagation_ms") if metrics else None,
            "Incident": request["question"], "Observations": observations,
            "Possible Causes": hypotheses, "Tool Results": traces,
            "Analysis": analysis, "Conclusion": verdict, "Recommendation": advice}


def run_agent(request, mode="llm"):
    start = time.perf_counter()
    if not isinstance(request, dict) or not isinstance(request.get("question"), str) or not request["question"].strip():
        raise ValueError("question 必须是非空字符串")
    usage = {}
    if mode == "offline":
        plan = offline_plan(request)
    elif mode == "llm":
        response = chat([{"role": "system", "content": PLANNER},
                         {"role": "user", "content": json.dumps(request, ensure_ascii=False)}], PLAN_SCHEMA, 500)
        plan = json.loads(response["content"])
        usage = response["usage"]
    else:
        raise ValueError("mode 必须为 llm 或 offline")
    if plan.get("intent") not in ("diagnose", "calculate", "service", "clarify"):
        raise ValueError("模型计划 intent 非法")
    selected = plan.get("tools", [])
    if not isinstance(selected, list) or len(selected) > 3 or any(t not in TOOL_NAMES for t in selected) or len(set(selected)) != len(selected):
        raise ValueError("模型工具计划非法")
    facts = dict(request.get("facts", {}))
    traces, metrics, service = [], None, None
    for name in selected:
        args = {}
        try:
            if name == "query_link":
                args = {"link_id": request.get("link_id")}
                result = query_link(**args)
                # Explicit user measurements override snapshot fields; log both.
                facts = {**result, **facts}
            elif name == "evaluate_link":
                args = {key: facts[key] for key in ("length_km", "refractive_index", "rtt_ms", "utilization_pct", "loss_pct") if key in facts}
                if facts.get("length_km") is None:
                    raise KeyError("缺少 length_km，无法计算传播时延")
                result = evaluate_link(**args)
                metrics = result
            else:
                metric = request.get("metric", "rtt")
                floor = None if metrics is None else metrics["symmetric_rtt_floor_ms" if metric == "rtt" else "one_way_propagation_ms"]
                args = {"budget_ms": request.get("budget_ms"), "metric": metric,
                        "measured_ms": facts.get("rtt_ms" if metric == "rtt" else "one_way_measured_ms"),
                        "propagation_floor_ms": floor}
                result = check_service(**args)
                service = result
            traces.append({"tool": name, "arguments": args, "result": result})
        except (ValueError, KeyError, TypeError) as exc:
            traces.append({"tool": name, "arguments": args, "error": str(exc),
                           "error_kind": "missing_data" if isinstance(exc, KeyError) else "invalid_input"})
    answer = synthesize(request, plan, traces, metrics, service)
    answer.update({"mode": mode, "plan": plan, "usage": usage,
                   "elapsed_seconds": round(time.perf_counter() - start, 4),
                   "disclosure": "LLM 负责任务理解及工具选择；结论由可审计规则归纳，避免小模型改写数值。"})
    return answer


def run_direct(request):
    # Same factual measurements as B; no calculated tool outputs supplied to A.
    facts = dict(request.get("facts", {}))
    if request.get("link_id"):
        facts = {**query_link(request["link_id"]), **facts}
    response = chat([{"role": "system", "content": POLICY + "直接推理并输出JSON，不使用外部工具。reason用简洁中文。"},
                     {"role": "user", "content": json.dumps({**request, "facts": facts}, ensure_ascii=False)}], ANSWER_SCHEMA, 700)
    return {**json.loads(response["content"]), "usage": response["usage"], "model": response["model"]}
