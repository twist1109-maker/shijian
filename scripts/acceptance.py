"""对已启动的本机服务执行验收流程；默认模拟，--real才使用服务商。"""
import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--real', action='store_true', help='对正常与资料不足场景发起真实服务商调用，会产生API费用')
parser.add_argument('--url', default='http://127.0.0.1:8765')
args = parser.parse_args()
url = urllib.parse.urlparse(args.url)
if url.scheme != 'http' or url.hostname not in ['127.0.0.1', 'localhost', '::1']:
    parser.error('验收只允许连接本机HTTP服务')
base = args.url.rstrip('/') + '/api'
output = Path(__file__).resolve().parents[1] / 'evidence' / datetime.now().strftime('%Y%m%d-%H%M%S')
output.mkdir(parents=True, exist_ok=True)

def client(name, password):
    c = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request(c, '/login', {'name': name, 'password': password})
    return c

def request(c, path, data=None):
    req = urllib.request.Request(base+path, data=None if data is None else json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    try:
        with c.open(req, timeout=25) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        info = json.load(e)
        raise RuntimeError(info.get('error', str(e.code))) from None
    except urllib.error.URLError:
        raise RuntimeError('无法连接本机服务，请先运行 py -3 app.py') from None

def wait(c, tid):
    end = time.monotonic()+180
    while time.monotonic() < end:
        d = request(c, '/tasks/'+str(tid))
        if d['task']['ai_status'] != 'running': return d
        time.sleep(1)
    raise RuntimeError('验收等待超时；请在页面查看任务，不会清除已有数据')

def task(c, material_id, label, mode):
    t = request(c, '/tasks', {'title': '验收 / '+label, 'material_id': material_id, 'audience': '大学生' if label=='正常流程' else '亲子家庭', 'channel': '微信公众号', 'tone': '真诚清晰；价格和销量缺失必须明确待确认', 'length': 500})
    tid = t['id']; request(c, f'/tasks/{tid}/run', {'mode': mode})
    return tid, wait(c, tid)

def save_evidence(c, tid, label):
    e = request(c, f'/tasks/{tid}/evidence')
    (output/(label+'.json')).write_text(e['content'], encoding='utf-8')

try:
    editor = client('editor', 'Editor123!'); reviewer = client('reviewer', 'Review123!')
    state = request(editor, '/state')
    if args.real and not state['key_configured']:
        raise RuntimeError('真实模式需要先在模型配置页保存密钥并测试连接')
    materials = {m['title']: m['id'] for m in state['materials']}
    if not all(title in materials for title in ['把时间留给阅读', '城市里的自然课']):
        raise RuntimeError('缺少初始化样例资料，请在页面导入对应samples文本后重试')
    mode = 'real' if args.real else 'simulation'; summary = {'mode': mode, 'steps': [], 'limits': '故障场景为明确标注的模拟超时，不作为真实服务商失败证据。请另外录屏和人工核对模型输出。'}
    for label, title in [('正常流程', '把时间留给阅读'), ('资料不足', '城市里的自然课')]:
        tid, d = task(editor, materials[title], label, mode)
        save_evidence(editor, tid, label)
        if d['task']['ai_status'] != 'completed':
            raise RuntimeError(f'任务#{tid}失败，原因见页面执行依据与已导出的{label}.json')
        if label == '正常流程':
            latest = d['versions'][0]
            request(editor, f'/tasks/{tid}/save', {'content': latest['content']+'\n\n人工核对记录：本次使用教学模拟资料，未向真实渠道发布。', 'base_version': latest['id']})
            request(editor, f'/tasks/{tid}/submit', {})
            request(reviewer, f'/tasks/{tid}/return', {'comment': '请确认来源说明与缺失信息提示。'})
            request(editor, f'/tasks/{tid}/submit', {})
            # 规则错误不强行通过；提示操作者检查文案。
            request(reviewer, f'/tasks/{tid}/approve', {'comment': '演示确认：来源说明已保留，最终事实仍需人工复核。'})
            e = request(editor, f'/tasks/{tid}/export'); (output/'营销图文.html').write_text(e['content'], encoding='utf-8')
            save_evidence(editor, tid, label)
        summary['steps'].append({'scenario': label, 'task_id': tid, 'ai_status': d['task']['ai_status']})
        print(label+' 已完成，任务 #'+str(tid))
    tid, d = task(editor, materials['把时间留给阅读'], '模拟调用失败', 'failure')
    save_evidence(editor, tid, '模拟调用失败')
    summary['steps'].append({'scenario': '模拟调用失败', 'task_id': tid, 'ai_status': d['task']['ai_status']})
    (output/'验收执行摘要.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('证据目录：'+str(output)); print('请人工检查图文与来源，并录制浏览器演示。')
except Exception as e:
    print('验收未完成：'+str(e), file=sys.stderr)
    print('已有证据保存在：'+str(output), file=sys.stderr)
    sys.exit(1)
