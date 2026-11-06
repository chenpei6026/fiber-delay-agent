人工智能的网络应用 · 课程综合项目

FiberScope
光纤链路时延诊断助手

陈佩 23231203　　赵浩然 23211256
成员职责各 50%　|　2026 年 11 月 6 日

摘要

面向“光纤链路为什么卡顿”这一具体问题，本项目将课堂时延计算扩展为可运行的诊断应用。单 Agent 调用本地 Qwen3 小模型选择工具，查询模拟快照、计算传播下限并比较业务预算，输出带依据和不确定性说明的结论。八个案例的正式单次实验中，直接模型结论正确率为37.5%，Agent系统为100%；同时保留初版规划失败记录。结果说明工具和输入约束的工程价值，但不能外推为真实网络性能。

一、项目背景与真实问题

本项目来源于本组课堂表格中“通信系统的链路质量分析与决策”及光纤链路时延评估方向。原课堂记录提出通过工具避免模型心算，并观察到小模型可能歪曲工具结论。综合项目据此缩小到光纤时延，增加测量查询、异常识别、业务预算和可复现实验；原表格没有提供旧代码，本次完成可独立运行的新实现。

目标用户是校园网络维护者或通信课程学习者。典型场景为跨校区链路高峰RTT达到80ms，用户看到信号正常便怀疑光纤距离太远。通常只能反复测速、重启设备或凭经验判断，难以区分距离传播、负载竞争和测量错误。助手先用实际光路长度计算物理基线，再对照RTT、利用率与丢包，帮助决定下一步应该查路径、查接口还是补充数据。

系统完成单次调查闭环，不修改设备、不扫描网络、不训练模型，也不把额外RTT直接宣布为排队时延。数据是有来源标签的模拟场景，目的是验证查询、计算与分析流程，而非声称采集了校园网实测。用户仍需用更多时段测量确认根因。

二、系统架构与设计

图1　用户、LLM、Agent、三个工具、模拟数据源与结果输出。

系统使用Qwen3-0.6B的Q8_0量化模型，文件约640MB，通过llama.cpp的本地OpenAI兼容/v1接口服务。用户此前已移除Ollama，因此采用独立推理程序降低安装负担。配置为temperature=0、seed=42、关闭思考、4096上下文、CPU四线程；模型小，便于复现，但工具规划能力有限。

Agent使用Python标准库实现受约束计划执行结构，没有调用PydanticAI或CrewAI运行时。模型读取问题、链路编号和显式参数，输出intent、tools与reason三个字段；JSON Schema限制合法工具名，执行器进一步检查重复调用及数量上限。程序按模型给出的顺序执行，而不是每题固定运行全部工具。

查询工具读取JSON快照；计算工具接收长度、折射率和测量；阈值工具比较同种时延指标。参数从结构化字段和查询结果绑定，显式输入覆盖快照。工具返回值、输入、错误及耗时均进入日志。证据归纳层按公开规则整理观测、两种候选原因、结论与建议，避免小模型再次改写数字。

用户可用CLI或本机网页操作。典型流程是：输入问题与编号→模型选择查询/计算/检查→执行并记录→比较候选解释→输出结论。C7只调用传播计算，C8只检查单程业务阈值，体现不同问题触发不同流程。

三、Agent 与 Tool 的具体实现

src/agent.py负责请求校验、模型规划、工具分派和证据归纳；model.py封装HTTP接口；tools.py集中执行网络计算；web.py与main.py提供交互。系统提示词要求有编号先查询，诊断和计算需要传播工具，有预算再检查业务，并提供三个不同意图的示例。模型决定选择，执行器只绑定参数和检查合法性。

光纤群速度v=c/n，故单程传播时间t=Ln/c。代码将km换为m，再把秒换为ms；1000km、n=1.468得到4.896721ms。对称等长路径的RTT传播下限为2t，额外RTT为实测RTT减去此下限。它还可能包含序列化、路由绕行、排队、设备处理和测量偏差，不能等同于单一故障原因。

业务阈值由请求明确提供。RTT仅与RTT预算比较，单程业务必须提供同类单程测量，不能直接用RTT/2替代。85%利用率及1%丢包只是项目经验告警线，支持调查优先级，不构成行业通用标准或因果证明。若传播下限已超过预算，单纯增加带宽不能消除传播限制。

关键计算与调用逻辑

one_way = length_km * 1000 * n / 299792458 * 1000
floor = 2 * one_way
excess = rtt_ms - floor
result = evaluate_link(**arguments)

数值校验拒绝负长度、NaN、无穷值、布尔值及错误单位类型；未知编号、缺字段和服务不可达给出明确错误。实测RTT比传播下限低0.1ms以上时，优先判断数据矛盾。缺长度时保留工具错误和证据不足结论，不通过猜测补齐。最终输出保留Incident、Observations、Possible Causes、Tool Results、Analysis、Conclusion与Recommendation。

三、工具函数定义与实际分派（续）

以下代码直接摘录src/tools.py和src/agent.py，# ...仅表示省略的实现。三个工具返回结构化字典，参数及调用均可与源代码和运行日志核对。

1. 查询工具：编号 → 原始测量

def query_link(link_id: str) -> dict:
    # ...
    records = json.loads(DATA.read_text(encoding="utf-8"))
    if not isinstance(link_id, str) or link_id not in records:
        raise ValueError("未知链路编号，请选择 " + ", ".join(records))
    return {"link_id": link_id, **records[link_id]}

link_id为字符串编号；查询结果保留模拟数据来源，未知编号抛出ValueError，不返回预写根因。

2. 计算与业务检查工具：参数签名和关键返回

def evaluate_link(length_km, refractive_index=1.468, rtt_ms=None,
                  utilization_pct=None, loss_pct=None, **unused) -> dict:
    # ...
    length = number(length_km, "length_km", 0, 50_000)
    n = number(refractive_index, "refractive_index", 1, 2)
    # ...
    one_way = length * 1000 * n / C * 1000
    floor = 2 * one_way
    return {
        "one_way_propagation_ms": round(one_way, 6),
        "symmetric_rtt_floor_ms": round(floor, 6),

def check_service(budget_ms, metric, measured_ms=None, propagation_floor_ms=None) -> dict:
    # ...
    if metric not in ("rtt", "one_way"):
        raise ValueError("metric 必须是 rtt 或 one_way")
    # ...
    return {"budget_ms": budget, "metric": metric, "measured_ms": measured,
            "propagation_floor_ms": floor,
            "measurement_pass": None if measured is None else measured <= budget,

length_km单位km，refractive_index无量纲且默认1.468；rtt_ms为往返毫秒，缺失用None。utilization_pct与loss_pct均为0至100的百分数。budget_ms、measured_ms及propagation_floor_ms均为ms，metric仅允许rtt或one_way；缺测量返回None，不冒充达标。

3. Agent 执行模型所选工具并记录证据

    for name in selected:
        args = {}
        try:
            if name == "query_link":
                args = {"link_id": request.get("link_id")}
                result = query_link(**args)
    # ...
            traces.append({"tool": name, "arguments": args, "result": result})

selected来自LLM计划。上例展示查询分支：绑定请求编号、实际调用函数，再将输入和返回值写入traces；计算分支绑定facts后执行evaluate_link(**args)，阈值分支执行check_service(**args)。工具失败写入error日志，完整分支见src/agent.py。

四、典型工作案例与实际运行

代表案例C2：用户输入“F1000光纤链路高峰RTT 80ms，信号正常却卡顿，分析原因”，项目RTT预算30ms。模型输出diagnose计划，依次选择query_link、evaluate_link和check_service。候选解释为H1：光路距离限制；H2：负载、路径或处理产生额外时延。

传播下限9.793442ms显著低于80ms，说明距离不能单独解释现象。94%利用率支持竞争资源的可能，1.8%丢包提示进一步检查错误计数与拥塞，但二者不是根因证明。结论为excess_delay，建议采集高低峰的同时间序列、核对路径变化和设备处理情况。正式结果及原始参数完整保存在evaluation.json，截图展示同一场景的实际网页运行。

图2　真实网页运行：用户输入、LLM模式、计划与查询工具返回。

四、运行结果与证据边界（续）

图3　实际工具数值与最终分析，来自真实网页运行截图。

五、测试案例与效果评测

5.1 案例设计与判断标准

八个Case覆盖计算、查询、调查、业务检查和异常处理。标准由解析公式与公开裁决规则预先给出；不是看答案文字像不像预设句子。对于诊断，先拒绝非法输入，再检查物理矛盾、传播预算、缺失信息，最后比较同类业务测量。测试输入和预期均随代码提供。

5.2 同模型对照设计

A组直接使用Qwen3-0.6B，不允许调用外部工具。B组使用同一模型输出工具计划，随后调用Python工具及证据归纳。两组采用相同问题、原始快照和统一裁决规则；A预先获得B可查询的相同事实，但不获得工具算出的传播答案。两组均关闭思考，温度0、seed=42，使用结构化输出。

正式实验每题每组一次，结果包含全部16条运行；初版提示词另存pilot-v1，不混入正式统计。调整提示词使用了相同开发题集，因此本次属于开发集验证，不是独立盲测。单元测试另核对公式、边界、非法值、缺失字段、指标混用以及8个离线场景，均通过；离线规则结果不冒充LLM实验。

五、评测结果与解释（续）

图4　来自evaluation.csv的正式单次实验结果。

结论正确率为正确标签数/8：A为3/8=37.5%，B为8/8=100%。数值正确率仅统计5个具有有效传播答案的案例，绝对误差≤0.01ms为正确：A为0/5，B为5/5。工具正确率要求按依赖顺序选择的工具列表与预期一致：B为8/8。任务成功同时要求结论、适用数值与B组工具均正确，A为2/8=25%，B为8/8=100%。

平均端到端耗时A为2.880秒、B为1.874秒，包含本机HTTP与执行开销。B只输出短计划，A要生成推理文字；本机缓存和首请求差异也影响时间，所以不能宣称工具系统必然更快。C1直接模型标签正确却把2ms RTT当成传播值，故任务失败。收益来自计算工具、参数约束和规则归纳的整体设计，并非小模型推理能力本身提升。

五、失败案例与局限（续）

初版规划提示词把网络裁决规则和工具说明堆在一起。实际运行中，C2模型只选evaluate_link和check_service，漏掉query_link，导致没有长度和测量，输出证据不足；C8还出现非法工具计划。初版B组八题任务成功为0/8，原始输出完整保存在pilot-v1.json，不能因正式版本成功而删除。

改进后将规划提示词收窄为工具选择，强调编号必须先查询，并分别给出调查、纯计算、纯阈值三个示例。执行器未补写缺失工具，也未替模型选择；正式日志显示C7和C8选用不同工具。八题通过表明修改对当前题集有效，但尚不能证明对任意自然语言稳定。后续应加入独立题集、参数抽取、不同温度和多次重复实验。

FMISSING是保留的不理想业务案例：即使高利用率，缺实际光路长度仍不能定位距离或排队贡献。本项目也未接入真实测量系统，未覆盖非对称路径、时序变化和复杂故障共存。因此只适合作为可解释MVP与学习工具，不直接代替现场排障。

六、总结与学习反思

项目把课堂光纤时延工具扩展为查询、计算、预算检查、证据解释和实验记录的完整闭环。Agent的作用是理解任务并选择需要的信息，Tool的作用是提供可检验数据和数值。对公式、单位和物理下限，应优先信任可复核程序；对故障原因，应把模型输出当候选解释，再用测量验证。

本次使用Codex协助需求分析、编程、测试、报告与图表，自动检查和模型实验在本机实际执行；没有补造Trae历史或学生独立操作经历。成员应亲自复现并理解关键代码。最大的不足是小模型规划仍依赖清楚的输入字段，样本也偏小；下一步最值得做的是接入经授权的时序测量并建立独立评测集。

参考资料：[1] 课程综合项目1班要求（本地原始PDF/Markdown）；[2] 本组腾讯课堂表格，docs.qq.com/sheet/DT1BoanFVTUNWY0xV；[3] Qwen/Qwen3-0.6B-GGUF 官方模型卡；[4] ggml-org/llama.cpp 官方文档。课堂表格摘录见coursework-evidence.md。访问日期：2026-11-06。