"""Pure network tools. No tool returns a pre-written root cause."""
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "links.json"
C = 299_792_458.0


def number(value, name, low, high, *, low_open=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须是数值")
    if not math.isfinite(value) or value > high or value < low or (low_open and value == low):
        raise ValueError(f"{name} 超出允许范围")
    return float(value)


def query_link(link_id: str) -> dict:
    """Query local simulated measurements, preserving missing values and provenance."""
    records = json.loads(DATA.read_text(encoding="utf-8"))
    if not isinstance(link_id, str) or link_id not in records:
        raise ValueError("未知链路编号，请选择 " + ", ".join(records))
    return {"link_id": link_id, **records[link_id]}


def evaluate_link(length_km, refractive_index=1.468, rtt_ms=None,
                  utilization_pct=None, loss_pct=None, **unused) -> dict:
    """L*n/c one-way propagation; 2*L*n/c symmetric RTT lower bound.

    Excess RTT is not automatically queueing delay. The symmetric-route
    assumption and measurement timing must be checked before causal claims.
    """
    length = number(length_km, "length_km", 0, 50_000)
    n = number(refractive_index, "refractive_index", 1, 2)
    rtt = None if rtt_ms is None else number(rtt_ms, "rtt_ms", 0, 1_000_000)
    util = None if utilization_pct is None else number(utilization_pct, "utilization_pct", 0, 100)
    loss = None if loss_pct is None else number(loss_pct, "loss_pct", 0, 100)
    one_way = length * 1000 * n / C * 1000
    floor = 2 * one_way
    return {
        "one_way_propagation_ms": round(one_way, 6),
        "symmetric_rtt_floor_ms": round(floor, 6),
        "measured_rtt_ms": rtt,
        "excess_rtt_ms": None if rtt is None else round(rtt - floor, 6),
        "below_physical_floor": None if rtt is None else rtt + 0.1 < floor,
        "utilization_pct": util, "loss_pct": loss,
        "assumption": "长度为单程实际光路；正反向路径等长；折射率代表群折射率",
        "source": "calculation", "formula": "t_oneway_ms = length_km * n / 299.792458",
    }


def check_service(budget_ms, metric, measured_ms=None, propagation_floor_ms=None) -> dict:
    """Apply an explicitly supplied project policy to matching metrics only."""
    budget = number(budget_ms, "budget_ms", 0, 1_000_000, low_open=True)
    if metric not in ("rtt", "one_way"):
        raise ValueError("metric 必须是 rtt 或 one_way")
    measured = None if measured_ms is None else number(measured_ms, "measured_ms", 0, 1_000_000)
    floor = None if propagation_floor_ms is None else number(propagation_floor_ms, "propagation_floor_ms", 0, 1_000_000)
    return {"budget_ms": budget, "metric": metric, "measured_ms": measured,
            "propagation_floor_ms": floor,
            "measurement_pass": None if measured is None else measured <= budget,
            "propagation_alone_exceeds_budget": None if floor is None else floor > budget,
            "policy_source": "用户指定的项目演示阈值，不是行业通用语音标准"}
