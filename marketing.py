"""图书营销业务规则、受控图文排版和证据脱敏。仅依赖Python标准库。"""
import base64
import difflib
import hashlib
import html
import json
import re

CHANNELS = {
    '微信公众号': {'structure': '标题、导语、读者痛点、三个有依据卖点、阅读建议、行动引导', 'suggestion': '段落清晰，适合连续阅读，避免虚构推荐语。'},
    '小红书': {'structure': '短标题、场景化开头、分点卖点、适读人群、互动提问', 'suggestion': '使用简洁短句，可用少量表情，避免伪造亲历或读者评价。'},
    '电商详情页': {'structure': '图书信息、适读对象、内容亮点、目录节选、购买前须知', 'suggestion': '强调资料支持的内容和规格，不虚构折扣、销量及功效承诺。'},
}
BANNED = ['全网第一', '最有效', '100%', '保证有效', '绝对有效', '零风险']


def digest(material):
    return hashlib.sha256(material['content'].encode()).hexdigest()


def facts(material):
    fields = {}
    for line in material['content'].splitlines():
        name, sep, value = line.partition('：')
        if not sep:
            name, sep, value = line.partition(':')
        if sep and name.strip():
            fields[name.strip()] = value.strip()
    return fields


def validate(text, material, task):
    if not isinstance(text, str) or not text.strip() or len(text) > 30000:
        raise ValueError('待校验文本须为1—30000字符')
    source = material['content']; field_map = facts(material)
    checks = []
    for word in BANNED:
        if word in text:
            checks.append({'level': 'error', 'code': 'absolute_claim', 'message': '需修改绝对化表达：' + word})
    # 价格按明确货币单位匹配，不能把资料里的页码或年份当成价格依据。
    prices = re.findall(r'(?:[¥￥]\s*)?(\d+(?:\.\d{1,2})?)\s*元', text)
    price_source = ' '.join(v for k, v in field_map.items() if any(w in k for w in ['价', '金额']))
    source_prices = {float(x) for x in re.findall(r'\d+(?:\.\d+)?', price_source)}
    for price in prices:
        if float(price) not in source_prices:
            checks.append({'level': 'error', 'code': 'unverified_price', 'message': f'价格 {price}元 无资料价格字段支持，请核对'})
    # 只针对明确事实语境标记，不对章节编号和素材ID发出无意义警告。
    for match in re.finditer(r'(?:销量|售出|销售突破|累计销售)[^\n。；]{0,8}?\d+(?:\.\d+)?\s*[万亿]?\s*[册本份]', text):
        claim = match.group()
        if not any(claim in v for k, v in field_map.items() if '销' in k):
            checks.append({'level': 'error', 'code': 'unverified_sales', 'message': '销量表述缺少来源：' + claim})
    if any(w in text for w in ['获奖', '荣获', '畅销榜冠军']):
        # 对“未提供获奖信息”等否定提示不误报，只检查肯定声称。
        for line in text.splitlines():
            if any(w in line for w in ['荣获', '获得大奖', '畅销榜冠军']) and line.strip() not in source:
                checks.append({'level': 'warning', 'code': 'award_review', 'message': '获奖或榜单表述需人工核对：' + line[:120]})
    price_missing = not price_source or any(w in price_source for w in ['未提供', '待确认', '未知'])
    missing = ['定价'] if price_missing else []
    if missing:
        checks.append({'level': 'warning', 'code': 'missing_data', 'message': '资料缺少定价；如涉及价格，请明确标注待确认，不得编造'})
    for k in ['作者', '书名']:
        expected = field_map.get(k)
        if expected and expected not in text:
            checks.append({'level': 'info', 'code': 'fact_review', 'message': f'{k}字段未完整出现，请人工确认是否需要补充：{expected}'})
    if len(text) > int(task['length']) * 1.5:
        checks.append({'level': 'warning', 'code': 'length', 'message': '篇幅明显超过目标字数'})
    return {'issues': [c['message'] for c in checks], 'checks': checks,
            'errors': sum(c['level'] == 'error' for c in checks), 'warnings': sum(c['level'] == 'warning' for c in checks),
            'characters': len(text), 'missing_fields': missing, 'material_id': material['id'],
            'material_version': material['version'], 'source_hash': digest(material),
            'rule_id': 'marketing-rules-v2', 'channel': task['channel'],
            'channel_guidance': CHANNELS.get(task['channel'], CHANNELS['微信公众号']),
            'limits': '仅检查明确价格、部分销量和文案规则；不代表完整语义、事实或法律审查。审核人员需核对原始资料。'}


def validate_cover(value):
    if not value:
        return ''
    if not isinstance(value, str) or len(value) > 750000:
        raise ValueError('封面图片请控制在500KB以内')
    m = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)', value)
    if not m:
        raise ValueError('封面仅支持PNG、JPEG、WebP图片')
    try:
        raw = base64.b64decode(m[2], validate=True)
    except ValueError:
        raise ValueError('封面编码无效') from None
    if len(raw) > 512000:
        raise ValueError('封面图片请控制在500KB以内')
    valid = (m[1] == 'png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (m[1] == 'jpeg' and raw.startswith(b'\xff\xd8\xff')) or (m[1] == 'webp' and raw.startswith(b'RIFF') and raw[8:12] == b'WEBP')
    if not valid:
        raise ValueError('封面格式与文件内容不一致')
    return value


def cover_svg(title):
    lines = [title[i:i+7] for i in range(0, min(len(title), 28), 7)]
    words = ''.join(f'<text x="38" y="{155+i*45}" font-family="serif" font-size="29" fill="#244f3c">{html.escape(s)}</text>' for i, s in enumerate(lines))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="480"><rect width="360" height="480" fill="#e4e8d5"/><rect x="20" y="20" width="320" height="440" fill="none" stroke="#91a37b"/><text x="38" y="70" font-size="15" fill="#657955">SHUYU / BOOK NOTES</text>'+words+'<path d="M40 350Q120 320 180 360Q245 315 320 345V405Q240 380 180 425Q110 382 40 405Z" fill="#476b4f"/><text x="38" y="450" font-size="12" fill="#657955">教学排版示意 · 非真实图书封面</text></svg>'


def cover_markup(material):
    if material.get('cover_data'):
        return '<img class="book-cover" alt="用户提供的图书封面" src="'+html.escape(validate_cover(material['cover_data']), quote=True)+'">'
    return cover_svg(material['title'])


def markdown(text):
    """受控Markdown子集：先转义再排版；不支持任意HTML、远程图片或脚本链接。"""
    result = []; in_list = False
    def inline(value):
        value = html.escape(value)
        value = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong>\1</strong>', value)
        return value
    for line in text.splitlines():
        match = re.match(r'^\s*(?:[-*]|\d+[.)、])\s+(.+)$', line)
        if match:
            if not in_list: result.append('<ul>'); in_list = True
            result.append('<li>'+inline(match[1])+'</li>'); continue
        if in_list: result.append('</ul>'); in_list = False
        heading = re.match(r'^(#{1,3})\s+(.+)$', line)
        if heading:
            n = len(heading[1]) + 1; result.append(f'<h{n}>'+inline(heading[2])+f'</h{n}>')
        elif line.strip(): result.append('<p>'+inline(line)+'</p>')
    if in_list: result.append('</ul>')
    return '\n'.join(result)


def report(task, version, material):
    content = version['content']; review = validate(content, material, task)
    status = {'draft': '待处理', 'returned': '已退回', 'pending_review': '待审核', 'completed': '审核完成'}.get(task['status'], task['status'])
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(task['title'])+'</title><style>body{max-width:900px;margin:45px auto;padding:24px;color:#24392f;font-family:system-ui,"Microsoft YaHei";line-height:1.9;background:#fafbf7}.book-cover,svg{width:160px;float:left;margin:0 28px 18px 0}article{min-height:240px}footer{clear:both;border-top:1px solid #ccd7c4;padding-top:20px;font-size:12px;color:#63705b}h1,h2,h3{line-height:1.5}@media print{body{margin:0;background:white}}</style><h1>'+html.escape(task['title'])+'</h1><p>'+html.escape(task['channel'])+' · '+html.escape(task['audience'])+' · '+status+'</p><article>'+cover_markup(material)+markdown(content)+'</article><footer>教学图文报告 · 任务 #'+str(task['id'])+' · 正文版本 #'+str(version['id'])+'<br>资料 #'+str(material['id'])+' v'+str(material['version'])+' · 来源：'+html.escape(material['source'])+'<br>校验：'+str(review['errors'])+'项错误 / '+str(review['warnings'])+'项提示。'+html.escape(review['limits'])+'</footer></html>'


def compare(older, newer):
    return {'from_id': older['id'], 'to_id': newer['id'], 'changed': older['content'] != newer['content'],
            'diff': '\n'.join(difflib.unified_diff(older['content'].splitlines(), newer['content'].splitlines(), fromfile='版本#'+str(older['id']), tofile='版本#'+str(newer['id']), lineterm=''))}


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if k.lower() in ['api_key', 'authorization', 'password', 'key'] else redact(v, secrets)) for k, v in value.items()}
    if isinstance(value, list): return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret: value = value.replace(secret, '[REDACTED]')
        return re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[REDACTED]', value)
    return value
