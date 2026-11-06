"""Rebuild the final PDF from actual evaluation logs and captured UI images."""
import csv
import json
import re
import statistics
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, Preformatted
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
ROWS = list(csv.DictReader((ROOT/'results/evaluation.csv').open(encoding='utf-8-sig')))
RUNS = json.loads((ROOT/'results/evaluation.json').read_text(encoding='utf-8'))['runs']
pdfmetrics.registerFont(TTFont('CN', 'C:/Windows/Fonts/simsun.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('CNB', 'C:/Windows/Fonts/simhei.ttf'))
FONT='C:/Windows/Fonts/msyh.ttc'
NAVY='#15394C'; TEAL='#187985'; MUTED='#57717E'


def figure_assets():
    im=PILImage.new('RGB',(1440,850),'#f3f7f9'); d=ImageDraw.Draw(im)
    def font(n): return ImageFont.truetype(FONT,n)
    def box(x,y,w,h,title,sub=''):
        d.rounded_rectangle((x,y,x+w,y+h),18,fill='white',outline='#b8d2d8',width=3)
        d.text((x+w/2,y+23),title,font=font(29),fill=NAVY,anchor='mt')
        if sub:d.text((x+w/2,y+68),sub,font=font(21),fill=MUTED,anchor='mt')
    def arrow(x1,y1,x2,y2):
        import math
        d.line((x1,y1,x2,y2),fill=TEAL,width=5)
        a=math.atan2(y2-y1,x2-x1)
        d.polygon([(x2,y2),(x2-17*math.cos(a-.4),y2-17*math.sin(a-.4)),(x2-17*math.cos(a+.4),y2-17*math.sin(a+.4))],fill=TEAL)
    box(480,30,480,110,'用户 / CLI 与网页','问题 + 编号或事实 + 时延预算')
    arrow(720,140,720,185)
    box(480,185,480,110,'Agent 计划与执行器','解析、参数绑定、校验、日志')
    box(1030,185,350,110,'本地 LLM','Qwen3-0.6B / llama.cpp')
    arrow(960,220,1030,220);arrow(1030,267,960,267)
    for x,title,sub in [(70,'query_link','读取模拟快照'),(530,'evaluate_link','传播下限与额外 RTT'),(990,'check_service','同指标的预算比较')]:
        box(x,390,380,110,title,sub)
        arrow(720,295,x+190,390)
    box(70,580,380,110,'本地数据源','data/links.json，明确模拟')
    arrow(260,500,260,580)
    box(530,625,840,145,'证据归纳 → 分析结果','观测 / 候选原因 / 工具证据 / 结论 / 建议')
    arrow(720,500,720,625);arrow(1180,500,1180,625);arrow(450,635,530,680)
    d.text((720,812),'LLM 决定用哪些工具；程序执行计算并保留证据边界',font=font(24),fill=MUTED,anchor='mm')
    im.save(DOCS/'architecture.png')
    chart=PILImage.new('RGB',(1440,740),'white');d=ImageDraw.Draw(chart)
    d.text((70,35),'同模型实测：直接 LLM 与 Agent + Tools',font=font(34),fill=NAVY)
    names=[('结论正确率','verdict_correct'),('任务成功率','task_success')]
    for x,(label,key) in zip([170,800],names):
        for offset,g,color in [(0,'direct_llm','#8aa3b2'),(200,'agent_tools',TEAL)]:
            subset=[r for r in ROWS if r['group']==g];value=sum(int(r[key]) for r in subset)/len(subset)
            xx=x+offset; y=560-int(value*370)
            d.rectangle((xx,y,xx+135,560),fill=color)
            d.text((xx+67,y-40),f'{value:.1%}',font=font(28),fill=NAVY,anchor='mm')
            d.text((xx+67,590),'直接 LLM' if g=='direct_llm' else 'Agent',font=font(24),fill=NAVY,anchor='mm')
        d.text((x+165,650),label,font=font(28),fill=NAVY,anchor='mm')
    d.text((70,705),'n=8，单次运行；固定模拟题集；结果不代表真实网络泛化能力。',font=font(20),fill=MUTED)
    chart.save(DOCS/'evaluation-chart.png')
    full=PILImage.open(DOCS/'screenshots/full-run.png')
    # Crop only existing screenshot pixels; no rendered or invented UI content.
    full.crop((375,1740,827,2710)).save(DOCS/'screenshots/conclusion-detail.png')


styles={
 'body':ParagraphStyle('body',fontName='CN',fontSize=12,leading=18,spaceAfter=9,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='CN',fontSize=9,leading=14,spaceAfter=6,wordWrap='CJK',textColor=HexColor(MUTED)),
 'h1':ParagraphStyle('h1',fontName='CNB',fontSize=19,leading=27,spaceAfter=17,textColor=HexColor(NAVY),wordWrap='CJK'),
 'h2':ParagraphStyle('h2',fontName='CNB',fontSize=13,leading=19,spaceBefore=9,spaceAfter=9,textColor=HexColor(TEAL)),
 'title':ParagraphStyle('title',fontName='CNB',fontSize=27,leading=38,spaceAfter=16,textColor=HexColor(NAVY)),
 'caption':ParagraphStyle('caption',fontName='CN',fontSize=9,leading=14,spaceAfter=12,alignment=TA_CENTER,textColor=HexColor(MUTED)),
 'cell':ParagraphStyle('cell',fontName='CN',fontSize=9,leading=14,wordWrap='CJK'),
}
story=[]; source=[]
def p(text,kind='body'):
    story.append(Paragraph(escape(text).replace('\n','<br/>'),styles[kind]));source.append(text)
def h(text):p(text,'h1')
def sub(text):p(text,'h2')
def pic(path,w,maxh=None):
    im=PILImage.open(path);hh=w*im.height/im.width
    if maxh and hh>maxh:w*=maxh/hh;hh=maxh
    story.append(Image(str(path),width=w,height=hh))
def table(rows,widths):
    t=Table([[Paragraph(escape(str(c)),styles['cell']) for c in r] for r in rows],colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#e1eef1')),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#f5f8fa')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,HexColor('#bad0d7'))]));story.append(t);story.append(Spacer(1,10))
def page():story.append(PageBreak())

def code_excerpt(relative_path, ranges):
    """Quote actual source lines; gaps are explicitly marked, never invented code."""
    lines=(ROOT/relative_path).read_text(encoding='utf-8').splitlines()
    pieces=[]
    for start,end in ranges:
        if pieces: pieces.append('    # ...')
        pieces.extend(lines[start-1:end])
    text='\n'.join(pieces)
    code_style=ParagraphStyle('code',fontName='CN',fontSize=8.2,leading=11,
        backColor=HexColor('#f2f6f8'),borderPadding=7,spaceAfter=10)
    story.append(Preformatted(text,code_style));source.append(text)


def build():
    figure_assets()
    p('人工智能的网络应用 · 课程综合项目','small')
    p('FiberScope\n光纤链路时延诊断助手','title')
    p('陈佩 23231203　　赵浩然 23211256\n成员职责各 50%　|　2026 年 11 月 6 日','small')
    sub('摘要')
    p('面向“光纤链路为什么卡顿”这一具体问题，本项目将课堂时延计算扩展为可运行的诊断应用。单 Agent 调用本地 Qwen3 小模型选择工具，查询模拟快照、计算传播下限并比较业务预算，输出带依据和不确定性说明的结论。八个案例的正式单次实验中，直接模型结论正确率为37.5%，Agent系统为100%；同时保留初版规划失败记录。结果说明工具和输入约束的工程价值，但不能外推为真实网络性能。')
    h('一、项目背景与真实问题')
    p('本项目来源于本组课堂表格中“通信系统的链路质量分析与决策”及光纤链路时延评估方向。原课堂记录提出通过工具避免模型心算，并观察到小模型可能歪曲工具结论。综合项目据此缩小到光纤时延，增加测量查询、异常识别、业务预算和可复现实验；原表格没有提供旧代码，本次完成可独立运行的新实现。')
    p('目标用户是校园网络维护者或通信课程学习者。典型场景为跨校区链路高峰RTT达到80ms，用户看到信号正常便怀疑光纤距离太远。通常只能反复测速、重启设备或凭经验判断，难以区分距离传播、负载竞争和测量错误。助手先用实际光路长度计算物理基线，再对照RTT、利用率与丢包，帮助决定下一步应该查路径、查接口还是补充数据。')
    p('系统完成单次调查闭环，不修改设备、不扫描网络、不训练模型，也不把额外RTT直接宣布为排队时延。数据是有来源标签的模拟场景，目的是验证查询、计算与分析流程，而非声称采集了校园网实测。用户仍需用更多时段测量确认根因。')
    page()
    h('二、系统架构与设计')
    pic(DOCS/'architecture.png',475)
    p('图1　用户、LLM、Agent、三个工具、模拟数据源与结果输出。','caption')
    p('系统使用Qwen3-0.6B的Q8_0量化模型，文件约640MB，通过llama.cpp的本地OpenAI兼容/v1接口服务。用户此前已移除Ollama，因此采用独立推理程序降低安装负担。配置为temperature=0、seed=42、关闭思考、4096上下文、CPU四线程；模型小，便于复现，但工具规划能力有限。')
    p('Agent使用Python标准库实现受约束计划执行结构，没有调用PydanticAI或CrewAI运行时。模型读取问题、链路编号和显式参数，输出intent、tools与reason三个字段；JSON Schema限制合法工具名，执行器进一步检查重复调用及数量上限。程序按模型给出的顺序执行，而不是每题固定运行全部工具。')
    p('查询工具读取JSON快照；计算工具接收长度、折射率和测量；阈值工具比较同种时延指标。参数从结构化字段和查询结果绑定，显式输入覆盖快照。工具返回值、输入、错误及耗时均进入日志。证据归纳层按公开规则整理观测、两种候选原因、结论与建议，避免小模型再次改写数字。')
    p('用户可用CLI或本机网页操作。典型流程是：输入问题与编号→模型选择查询/计算/检查→执行并记录→比较候选解释→输出结论。C7只调用传播计算，C8只检查单程业务阈值，体现不同问题触发不同流程。')
    page()
    h('三、Agent 与 Tool 的具体实现')
    p('src/agent.py负责请求校验、模型规划、工具分派和证据归纳；model.py封装HTTP接口；tools.py集中执行网络计算；web.py与main.py提供交互。系统提示词要求有编号先查询，诊断和计算需要传播工具，有预算再检查业务，并提供三个不同意图的示例。模型决定选择，执行器只绑定参数和检查合法性。')
    table([['工具','关键输入','实际返回'],['query_link','link_id','长度、RTT、利用率、丢包、来源'],['evaluate_link','length_km / n / RTT','单程传播、对称RTT下限、额外RTT、矛盾标记'],['check_service','预算 / metric / 实测值','同指标是否达标、传播下限是否超预算']],[105,165,205])
    p('光纤群速度v=c/n，故单程传播时间t=Ln/c。代码将km换为m，再把秒换为ms；1000km、n=1.468得到4.896721ms。对称等长路径的RTT传播下限为2t，额外RTT为实测RTT减去此下限。它还可能包含序列化、路由绕行、排队、设备处理和测量偏差，不能等同于单一故障原因。')
    p('业务阈值由请求明确提供。RTT仅与RTT预算比较，单程业务必须提供同类单程测量，不能直接用RTT/2替代。85%利用率及1%丢包只是项目经验告警线，支持调查优先级，不构成行业通用标准或因果证明。若传播下限已超过预算，单纯增加带宽不能消除传播限制。')
    sub('关键计算与调用逻辑')
    p('one_way = length_km * 1000 * n / 299792458 * 1000\nfloor = 2 * one_way\nexcess = rtt_ms - floor\nresult = evaluate_link(**arguments)','small')
    p('数值校验拒绝负长度、NaN、无穷值、布尔值及错误单位类型；未知编号、缺字段和服务不可达给出明确错误。实测RTT比传播下限低0.1ms以上时，优先判断数据矛盾。缺长度时保留工具错误和证据不足结论，不通过猜测补齐。最终输出保留Incident、Observations、Possible Causes、Tool Results、Analysis、Conclusion与Recommendation。')
    page()
    h('三、工具函数定义与实际分派（续）')
    p('以下代码直接摘录src/tools.py和src/agent.py，# ...仅表示省略的实现。三个工具返回结构化字典，参数及调用均可与源代码和运行日志核对。','small')
    sub('1. 查询工具：编号 → 原始测量')
    code_excerpt('src/tools.py',[(18,18),(20,23)])
    p('link_id为字符串编号；查询结果保留模拟数据来源，未知编号抛出ValueError，不返回预写根因。','small')
    sub('2. 计算与业务检查工具：参数签名和关键返回')
    code_excerpt('src/tools.py',[(26,27),(33,34),(38,42)])
    code_excerpt('src/tools.py',[(52,52),(55,56),(59,61)])
    p('length_km单位km，refractive_index无量纲且默认1.468；rtt_ms为往返毫秒，缺失用None。utilization_pct与loss_pct均为0至100的百分数。budget_ms、measured_ms及propagation_floor_ms均为ms，metric仅允许rtt或one_way；缺测量返回None，不冒充达标。','small')
    sub('3. Agent 执行模型所选工具并记录证据')
    code_excerpt('src/agent.py',[(128,133),(150,150)])
    p('selected来自LLM计划。上例展示查询分支：绑定请求编号、实际调用函数，再将输入和返回值写入traces；计算分支绑定facts后执行evaluate_link(**args)，阈值分支执行check_service(**args)。工具失败写入error日志，完整分支见src/agent.py。','small')
    page()
    h('四、典型工作案例与实际运行')
    p('代表案例C2：用户输入“F1000光纤链路高峰RTT 80ms，信号正常却卡顿，分析原因”，项目RTT预算30ms。模型输出diagnose计划，依次选择query_link、evaluate_link和check_service。候选解释为H1：光路距离限制；H2：负载、路径或处理产生额外时延。')
    table([['实际调用','输入和真实返回'],['query_link','link_id=F1000 → 长度1000km，n=1.468，RTT=80ms，利用率94%，丢包1.8%'],['evaluate_link','长度1000km等 → 单程4.896721ms；RTT下限9.793442ms；额外70.206558ms'],['check_service','预算30ms，metric=rtt，测量80ms → measurement_pass=false；传播单独未超预算']],[108,367])
    p('传播下限9.793442ms显著低于80ms，说明距离不能单独解释现象。94%利用率支持竞争资源的可能，1.8%丢包提示进一步检查错误计数与拥塞，但二者不是根因证明。结论为excess_delay，建议采集高低峰的同时间序列、核对路径变化和设备处理情况。正式结果及原始参数完整保存在evaluation.json，截图展示同一场景的实际网页运行。')
    pic(DOCS/'screenshots/01-agent-process.png',430,280)
    p('图2　真实网页运行：用户输入、LLM模式、计划与查询工具返回。','caption')
    page()
    h('四、运行结果与证据边界（续）')
    # Result crop is tall; place it beside a narrow explanatory column.
    img=PILImage.open(DOCS/'screenshots/conclusion-detail.png')
    shot=Image(str(DOCS/'screenshots/conclusion-detail.png'),width=250,height=250*img.height/img.width)
    notes=[Paragraph(escape(t),styles['body']) for t in [
        '图3为实际全页截图的结果区域裁切，保留传播数值、两个候选解释、分析和后续建议。截图源文件另存于docs/screenshots，未重画界面或替换数字。',
        '本次输出只能说明“存在需要调查的额外时延”。信号正常不等于链路所有环节正常，高利用率也不能排除路径变化、接口错误或测量时段不一致。',
        '作为对照，C3的5000km链路单程传播约24.484ms，对称RTT下限约48.967ms，已经超过30ms预算。它应优先考虑路径与业务部署，而非只增带宽。',
        'C4缺少实际光路长度，不能区分距离贡献；C5的5000km与5ms RTT相互矛盾，需核对数据。承认不能确定，是本项目的一种合理输出。']]
    t=Table([[shot,notes]],colWidths=[265,210]);t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),10)]));story.append(t)
    p('图3　实际工具数值与最终分析，来自真实网页运行截图。','caption')
    page()
    h('五、测试案例与效果评测')
    sub('5.1 案例设计与判断标准')
    p('八个Case覆盖计算、查询、调查、业务检查和异常处理。标准由解析公式与公开裁决规则预先给出；不是看答案文字像不像预设句子。对于诊断，先拒绝非法输入，再检查物理矛盾、传播预算、缺失信息，最后比较同类业务测量。测试输入和预期均随代码提供。')
    caseRows=[['Case','输入要点','预期 / 检查能力'],['C1','100km，RTT2ms，预算10ms','正常；完整诊断流程'],['C2','1000km，RTT80ms，利用率94%','额外时延；不能只怪距离'],['C3','5000km，RTT60ms，预算30ms','传播受限；带宽建议正确'],['C4','缺长度，RTT80ms','证据不足；不编造参数'],['C5','5000km，RTT5ms','数据矛盾；物理下限校验'],['C6','长度-10km','非法输入；参数校验'],['C7','1000km，仅计算','单程4.896721ms；只选计算'],['C8','单程30ms，预算50ms','达标；只选阈值检查']]
    table(caseRows,[45,190,240])
    sub('5.2 同模型对照设计')
    p('A组直接使用Qwen3-0.6B，不允许调用外部工具。B组使用同一模型输出工具计划，随后调用Python工具及证据归纳。两组采用相同问题、原始快照和统一裁决规则；A预先获得B可查询的相同事实，但不获得工具算出的传播答案。两组均关闭思考，温度0、seed=42，使用结构化输出。')
    p('正式实验每题每组一次，结果包含全部16条运行；初版提示词另存pilot-v1，不混入正式统计。调整提示词使用了相同开发题集，因此本次属于开发集验证，不是独立盲测。单元测试另核对公式、边界、非法值、缺失字段、指标混用以及8个离线场景，均通过；离线规则结果不冒充LLM实验。')
    page()
    h('五、评测结果与解释（续）')
    labels={'healthy':'通过','excess_delay':'额外时延','propagation_limited':'传播受限','insufficient_data':'证据不足','inconsistent_data':'数据矛盾','invalid_input':'输入非法'}
    rr=[['Case','标准','直接 LLM 实际','Agent 实际']]
    for cid in [f'C{i}' for i in range(1,9)]:
        pair=[r for r in RUNS if r['case']==cid]
        rr.append([cid,labels[pair[0]['expected']['verdict']],labels.get(pair[0]['answer'].get('verdict'),'错误'),labels.get(pair[1]['answer'].get('verdict'),'错误')])
    table(rr,[45,135,155,140])
    pic(DOCS/'evaluation-chart.png',440,230)
    p('图4　来自evaluation.csv的正式单次实验结果。','caption')
    p('结论正确率为正确标签数/8：A为3/8=37.5%，B为8/8=100%。数值正确率仅统计5个具有有效传播答案的案例，绝对误差≤0.01ms为正确：A为0/5，B为5/5。工具正确率要求按依赖顺序选择的工具列表与预期一致：B为8/8。任务成功同时要求结论、适用数值与B组工具均正确，A为2/8=25%，B为8/8=100%。')
    p('平均端到端耗时A为2.880秒、B为1.874秒，包含本机HTTP与执行开销。B只输出短计划，A要生成推理文字；本机缓存和首请求差异也影响时间，所以不能宣称工具系统必然更快。C1直接模型标签正确却把2ms RTT当成传播值，故任务失败。收益来自计算工具、参数约束和规则归纳的整体设计，并非小模型推理能力本身提升。')
    page()
    h('五、失败案例与局限（续）')
    p('初版规划提示词把网络裁决规则和工具说明堆在一起。实际运行中，C2模型只选evaluate_link和check_service，漏掉query_link，导致没有长度和测量，输出证据不足；C8还出现非法工具计划。初版B组八题任务成功为0/8，原始输出完整保存在pilot-v1.json，不能因正式版本成功而删除。')
    p('改进后将规划提示词收窄为工具选择，强调编号必须先查询，并分别给出调查、纯计算、纯阈值三个示例。执行器未补写缺失工具，也未替模型选择；正式日志显示C7和C8选用不同工具。八题通过表明修改对当前题集有效，但尚不能证明对任意自然语言稳定。后续应加入独立题集、参数抽取、不同温度和多次重复实验。')
    p('FMISSING是保留的不理想业务案例：即使高利用率，缺实际光路长度仍不能定位距离或排队贡献。本项目也未接入真实测量系统，未覆盖非对称路径、时序变化和复杂故障共存。因此只适合作为可解释MVP与学习工具，不直接代替现场排障。')
    h('六、总结与学习反思')
    p('项目把课堂光纤时延工具扩展为查询、计算、预算检查、证据解释和实验记录的完整闭环。Agent的作用是理解任务并选择需要的信息，Tool的作用是提供可检验数据和数值。对公式、单位和物理下限，应优先信任可复核程序；对故障原因，应把模型输出当候选解释，再用测量验证。')
    p('本次使用Codex协助需求分析、编程、测试、报告与图表，自动检查和模型实验在本机实际执行；没有补造Trae历史或学生独立操作经历。成员应亲自复现并理解关键代码。最大的不足是小模型规划仍依赖清楚的输入字段，样本也偏小；下一步最值得做的是接入经授权的时序测量并建立独立评测集。')
    table([['成员','职责划分','比例'],['陈佩 23231203','需求/架构、Agent与日志、模型配置、报告一至三部分','50%'],['赵浩然 23211256','网络工具/数据、测试评测、界面、报告四至六部分','50%']],[105,320,50])
    p('参考资料：[1] 课程综合项目1班要求（本地原始PDF/Markdown）；[2] 本组腾讯课堂表格，docs.qq.com/sheet/DT1BoanFVTUNWY0xV；[3] Qwen/Qwen3-0.6B-GGUF 官方模型卡；[4] ggml-org/llama.cpp 官方文档。课堂表格摘录见coursework-evidence.md。访问日期：2026-11-06。','small')
    def footer(canvas,doc):
        canvas.setFont('CN',8);canvas.setFillColor(HexColor(MUTED));canvas.drawString(58,28,'FiberScope  |  陈佩 · 赵浩然');canvas.drawRightString(A4[0]-58,28,str(doc.page))
    SimpleDocTemplate(str(ROOT/'report.pdf'),pagesize=A4,rightMargin=60,leftMargin=60,topMargin=48,bottomMargin=48,title='FiberScope 光纤链路时延诊断助手',author='陈佩 23231203；赵浩然 23211256').build(story,onFirstPage=footer,onLaterPages=footer)
    (DOCS/'report-text.md').write_text('\n\n'.join(source),encoding='utf-8')
    print('Chinese characters incl captions:',len(re.findall(r'[\u4e00-\u9fff]',''.join(source))))


if __name__=='__main__':build()
