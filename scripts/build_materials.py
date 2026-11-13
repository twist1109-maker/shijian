"""可选：重建汇报材料。仅重建时需 pip install python-docx python-pptx pillow。"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches, Pt
from pptx import Presentation
from pptx.util import Inches as PI, Pt as PP
from pptx.dml.color import RGBColor
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs'; FIG = DOCS/'架构图'; FIG.mkdir(exist_ok=True)
font_paths = ['C:/Windows/Fonts/msyh.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
FONT = next((p for p in font_paths if Path(p).exists()), None)
def font(n): return ImageFont.truetype(FONT, n) if FONT else ImageFont.load_default()
def diagram(name,title,labels,edges):
    im = Image.new('RGB',(1440,730),'#f3f5ef');d=ImageDraw.Draw(im)
    d.text((50,35),title,font=font(38),fill='#203f32')
    boxes=[(55,145,435,315),(530,145,910,315),(1005,145,1385,315),(55,480,435,650),(530,480,910,650),(1005,480,1385,650)]
    for a,b in edges:
        aa,bb=boxes[a],boxes[b]
        if b==a+1:
            start=(aa[2],(aa[1]+aa[3])//2);end=(bb[0],(bb[1]+bb[3])//2)
        elif b==a+3:
            start=((aa[0]+aa[2])//2,aa[3]);end=((bb[0]+bb[2])//2,bb[1])
        elif b==a-1:
            start=(aa[0],(aa[1]+aa[3])//2);end=(bb[2],(bb[1]+bb[3])//2)
        else:
            start=((aa[0]+aa[2])//2,aa[1]);end=((bb[0]+bb[2])//2,bb[3])
        d.line([start,end],fill='#839a70',width=5)
        x,y=end;dx=end[0]-start[0];dy=end[1]-start[1]
        if abs(dx)>abs(dy):delta=12 if dx>0 else -12; pts=[(x,y),(x-delta,y-9),(x-delta,y+9)]
        else:delta=12 if dy>0 else -12;pts=[(x,y),(x-9,y-delta),(x+9,y-delta)]
        d.polygon(pts,fill='#839a70')
    for box,label in zip(boxes,labels):
        d.rounded_rectangle(box,radius=18,fill='#ffffff',outline='#c7d4be',width=3)
        for i,line in enumerate(label.split('\n')):
            f=font(28 if i==0 else 22);bb=d.textbbox((0,0),line,font=f)
            d.text(((box[0]+box[2]-(bb[2]-bb[0]))/2,box[1]+42+i*44),line,font=f,fill='#244f3c' if i==0 else '#6b7b60')
    im.save(FIG/name)
diagram('01_系统功能图.png','书语 v1.2 / 系统功能图',['营销编辑\n资料、任务、人工修改','AI营销草稿\n读取、生成、质量检查','审核确认\n提交、退回、通过','资料与来源\nID、版本、封面、指纹','历史与执行依据\n工具日志、版本差异','成果导出\n图文HTML、证据JSON'],[(0,1),(1,2),(0,3),(1,4),(2,5)])
diagram('02_技术调用图.png','书语 v1.2 / 技术调用图',['Windows浏览器\nHTML / CSS / JavaScript','Python本机服务\n会话、权限、状态校验','SQLite\n任务、版本、日志、审核','DeepSeek / OpenAI\n官方Chat Completions','受控工具执行\n读取资料、文案校验','本机配置与导出\n密钥不入库、不上传'],[(0,1),(1,2),(1,4),(4,3),(2,5)])
diagram('03_数据与工具图.png','书语 v1.2 / 数据处理与工具执行图',['任务需求与资料\n读者、渠道、素材ID','模型自主选择工具\n名称、参数、后续决策','read_sources\n资料、规则、渠道建议','人工版本与审核\n保存、退回、通过','最终正文与复核\n来源、检查项、证据','validate_copy\n价格、销量、篇幅初筛'],[(0,1),(1,2),(2,5),(5,4),(4,3)])

pages=[('业务需求与范围',[
'项目名称：书语图书营销生成与审核系统。业务角色为营销编辑与审核人员，采用两个本地账号演示；开发者一人，单人成组资格仍以教师确认为准。',
'输入：图书资料TXT/Markdown或表单，可选PNG/JPEG/WebP封面；需求包含目标读者、渠道、语气、篇幅。输出为营销图文、质量检查、历史版本与运行证据。',
'流程：创建任务→模型选择工具→查看草稿与依据→人工保存→提交→退回或通过→导出。业务状态和AI状态分别保存，不混用。范围不包含真实渠道发布、OCR或模型训练。'], '01_系统功能图.png'),
('技术设计与部署',[
'Windows浏览器访问本机Python HTTP服务，SQLite保存业务数据。运行仅需Python3.10+；无前端构建或第三方运行依赖。接口采用同源JSON，会话Cookie为HttpOnly与SameSite=Strict。',
'后端检查角色、归属、业务状态和版本基线。只绑定127.0.0.1。模型配置可页面保存，也支持.env与环境变量，密钥不通过状态接口回显，不写入源码仓库。',
'模型按真实tool_calls选择工具与参数。后端执行、返回结果后继续循环，至多7轮、10次工具调用、总预算150秒。连接测试不替代完整Agent验收。'], '02_技术调用图.png'),
('数据处理与结果依据',[
'read_sources只读取任务关联资料，返回ID、版本、内容、来源、指纹、营销规则与渠道建议。validate_copy检查明确价格、部分销量、绝对化表达、篇幅和缺失项。检查分错误、提示和信息。',
'模型读取工具结果继续处理，结合上次保存版本和最近退回意见修改。最终正文另做确定性复核，该条日志不冒充模型选择的调用。明确校验错误阻止审核通过。',
'资料新增后不覆盖；任务绑定资料ID，执行快照保存当次需求、规则ID和来源SHA256。封面不发给文本模型，仅用于图文排版。规则初筛不等于完整语义或法律审查。'], '03_数据与工具图.png'),
('数据结构、接口与异常',[
'核心表：users(角色、盐和密码哈希)；materials(内容、来源、版本、封面)；tasks(需求、归属、业务/AI状态)；versions(正文、操作者、时间)；reviews(动作与意见)；runs(模式、模型、快照、状态与错误)；logs(工具参数、返回与状态)。',
'接口：/api/login、/state、/materials、/settings/model及/test；/tasks创建任务；/tasks/{id}/update、run、save、submit、return、approve；GET任务详情、compare、export、evidence。',
'修改追加版本，过期base_version被拒绝；至少两个正文版本才能通过。审核完成仍可导出。模型失败不删除人工版本；服务重启时把中断任务标为失败，允许重试。旧库启动时添加新字段，保留原数据。',
'封面限制500KB，仅支持受控图片格式，禁止任意SVG上传。正文受控Markdown先转义再排版。证据导出屏蔽密钥，但业务资料仍需分享前人工核对。'], None),
('测试、交付与验证边界',[
'本轮37项后端/配置/业务回归、17项前端事件测试通过；HTTP验收脚本已完成模拟正常、资料不足和失败流程。测试使用明确的模型替身，不宣称已连接真实服务商。',
'交付：源码、启动脚本、配置示例、五页设计说明、三张架构图、更新PPT、测试用例、修复记录、模拟运行证据、验收脚本、GitHub参考说明及分工模板。',
'用户需在Windows上配置真实密钥，核对模型结果并保存真实正常/资料不足记录；失败演练的simulation或failure标记不能当作真实网络失败。还需录制备用视频，确认教师最新提交时间。日记与报告基于真实经历另写。',
'参考：uyanga-gb/marketing-content-generator的校验与反馈修订思路；openai/openai-agents-python的工具schema和日志脱敏思路。未复制参考项目代码，详见GitHub参考与改进说明。'], None)]
d=Document();sec=d.sections[0];sec.top_margin=Inches(.6);sec.bottom_margin=Inches(.6)
style=d.styles['Normal'];style.font.name='Microsoft YaHei';style.font.size=Pt(10)
for i,(title,paragraphs,fig) in enumerate(pages):
    if i:d.add_page_break()
    d.add_heading('书语 v1.2 · 需求与设计说明',0);d.add_heading(str(i+1)+' / '+title,1)
    for para in paragraphs:d.add_paragraph(para)
    if fig:d.add_picture(str(FIG/fig),width=Inches(6.1))
d.save(DOCS/'需求与设计说明.docx')

slides=[
('书语 · 让好书被看见','出版业务AI实训 / 营销内容制作',['图书资料 → 营销图文 → 人工修改 → 审核确认','v1.2.0 / 单人开发 / Windows本机运行','验证边界：真实服务商与目标机演示需本人完成'],None),
('业务问题与最小范围','01 / 业务价值',['重复整理资料、撰写不同渠道文案，容易缺少来源','单本图书、固定图文模板、两个业务角色','不训练模型，不对接真实发布渠道；优先完成验收闭环'],None),
('角色与功能闭环','02 / 功能设计',[], '01_系统功能图.png'),
('轻量技术架构','03 / 技术设计',[], '02_技术调用图.png'),
('模型选择工具，后端实际执行','04 / Agent流程',[], '03_数据与工具图.png'),
('图文生成与渠道表达','05 / 核心成果',['TXT/Markdown资料 + 可选本地图书封面','公众号、小红书、电商详情页的教学渠道建议','标题、正文、列表排版；导出图文HTML，可浏览器打印PDF'],None),
('质量检查与来源核对','06 / 结果可信',['价格字段核对、部分销量表述与绝对化表达初筛','错误/待核对/提示分级；明确错误阻止审核通过','原始资料、版本、来源SHA256与规则随任务可查'],None),
('人工修改与审核反馈','07 / 人工闭环',['保存追加版本，过期版本覆盖被后端拒绝','提交→退回→结合意见修改/重新生成→重提→通过','版本差异、操作者、时间和意见可查'],None),
('异常与运行证据','08 / 可追溯',['记录工具名称、参数、返回、状态、错误与任务ID','每次运行保存需求快照、来源指纹与模型名称','失败保留人工版本；重启解锁；JSON证据屏蔽密钥'],None),
('测试结果与验证范围','09 / 验证',['37项后端/配置/业务检查；17项前端事件测试通过','HTTP验收脚本完成模拟正常、资料不足和失败流程','模型响应替身不代表真实服务商；目标机浏览器与录屏待本人完成'],None),
('GitHub调研如何落地','10 / 学习与取舍',['Marketing Content Generator：渠道校验、错误分级、反馈修改','OpenAI Agents Python：工具schema、执行日志与脱敏边界','参考设计思路、自行实现；没有引入多Agent与云部署负担'],None),
('现场演示与交付','11 / 验收路线',['配置并测试→导入封面与资料→创建真实任务→展示工具依据','核对质量→人工修改→退回重提→审核通过→版本比较与导出','源码、设计、图、PPT、样例、测试、证据、讲稿与单人记录模板'],None)]
prs=Presentation();prs.slide_width=PI(13.333);prs.slide_height=PI(7.5)
for i,(title,kicker,bullets,fig) in enumerate(slides):
    slide=prs.slides.add_slide(prs.slide_layouts[6]);slide.background.fill.solid();slide.background.fill.fore_color.rgb=RGBColor.from_string('F3F5EF')
    def text(x,y,w,h,value,size=20,color='244F3C'):
        shape=slide.shapes.add_textbox(PI(x),PI(y),PI(w),PI(h));tf=shape.text_frame;tf.word_wrap=True;p=tf.paragraphs[0];p.text=value;p.font.name='Microsoft YaHei';p.font.size=PP(size);p.font.color.rgb=RGBColor.from_string(color)
    text(.65,.4,12,.4,kicker,13,'71836A');text(.65,1,12,1,title,30)
    if fig:slide.shapes.add_picture(str(FIG/fig),PI(2),PI(2),width=PI(9.3))
    else:
        for j,b in enumerate(bullets):text(.85,2.55+j*.95,11.7,.85,'• '+b,21)
    text(.65,7.05,11,.25,'SHUYU / 教学模拟项目 · v1.2.0',10,'71836A');text(12,7.05,.6,.25,str(i+1),10,'71836A')
prs.save(DOCS/'书语营销系统_汇报PPT.pptx')
print('已重建五页设计说明、12页PPT、三张PNG架构图')
