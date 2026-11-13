"""本地模型配置与连接测试；只返回诊断信息，不返回或记录原始密钥。"""
import json
import os
import re
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

PROVIDERS = {
    'deepseek': ('https://api.deepseek.com', 'deepseek-chat'),
    'openai': ('https://api.openai.com/v1', 'gpt-4o-mini'),
}
PLACEHOLDERS = {'', 'your_api_key', 'your-api-key', 'sk-xxx', 'sk-...', '在本机填写，不要提交或分享', '你的密钥', 'your_deepseek_api_key', 'your_openai_api_key'}


def clean(value):
    return value.strip() if isinstance(value, str) else ''


def usable(key):
    value = clean(key)
    return value.lower() not in PLACEHOLDERS and not any(w in value for w in ['请填写', '替换为', 'YOUR_KEY'])


def dotenv(path):
    result = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        name, sep, value = line.partition('=')
        if not sep:
            continue
        value = value.strip()
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end >= 1 else value[1:]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
        result[name.strip()] = value
    return result


def resolve(root):
    """配置字段逐项解析：非空环境变量 > .env > config.local.json。"""
    root = Path(root).resolve()
    cfg = {}
    problem = ''
    path = root / 'config.local.json'
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(cfg, dict):
                raise ValueError('配置顶层必须是JSON对象')
        except (ValueError, OSError) as exc:
            line = getattr(exc, 'lineno', None)
            problem = 'config.local.json 格式错误' + (f'（第{line}行）' if line else '') + '。可在模型配置页重新保存。'
            cfg = {}
    try:
        envfile = dotenv(root / '.env')
    except (ValueError, OSError, UnicodeError):
        envfile = {}
        problem = '.env 无法读取，请使用UTF-8编码。'

    def pick(names, json_names=()):
        for source, values in [('环境变量', os.environ), ('.env', envfile), ('config.local.json', cfg)]:
            for name in (json_names if source == 'config.local.json' else names):
                value = clean(values.get(name))
                if value:
                    return value, source
        return '', ''

    provider, provider_source = pick(['MODEL_PROVIDER'], ['provider', 'MODEL_PROVIDER'])
    if not provider:
        ds, _ = pick(['DEEPSEEK_API_KEY'], ['deepseek_api_key', 'DEEPSEEK_API_KEY'])
        oa, _ = pick(['OPENAI_API_KEY'], ['openai_api_key', 'OPENAI_API_KEY'])
        provider = 'openai' if oa and not ds else 'deepseek'
    provider = provider.lower()
    error = ''
    if provider not in PROVIDERS:
        error = '服务商只支持 deepseek 或 openai，请在模型配置页修正。'
    base, default_model = PROVIDERS.get(provider, PROVIDERS['deepseek'])
    alias = 'OPENAI_API_KEY' if provider == 'openai' else 'DEEPSEEK_API_KEY'
    key, source = pick(['MODEL_API_KEY', alias], ['api_key', 'key', 'MODEL_API_KEY', alias, alias.lower()])
    model, model_source = pick(['MODEL_NAME'], ['model', 'MODEL_NAME'])
    model = model or default_model
    configured = usable(key)
    if not configured:
        error = error or problem or '没有找到有效密钥。请在模型配置页填写并保存，或使用 .env / 环境变量。'
        if not path.exists() and (root / 'config.local.json.txt').exists():
            error = '发现 config.local.json.txt。Windows隐藏扩展名导致文件名不正确，请改成 config.local.json，或在页面保存。'
        if not path.exists() and (root / 'config.example.json').exists():
            try:
                example = json.loads((root / 'config.example.json').read_text(encoding='utf-8-sig'))
                if usable(example.get('api_key', '')):
                    error = '密钥填在 config.example.json 中，该文件是示例。请复制为 config.local.json；不要提交含密钥的示例文件。'
            except (ValueError, OSError):
                pass
    info = {
        'provider': provider, 'model': model, 'configured': configured and not error,
        'key_source': source or '未找到', 'model_source': model_source or '服务商默认',
        'provider_source': provider_source or '默认或自动识别',
        'config_path': str(path), 'error': error,
        'warning': problem if configured else '',
        'endpoint': base + '/chat/completions',
        'priority': '非空环境变量 > 项目根目录 .env > config.local.json',
    }
    return info, key


def save(root, data):
    if not isinstance(data, dict):
        raise ValueError('配置须为JSON对象')
    provider = clean(data.get('provider')).lower()
    if provider not in PROVIDERS:
        raise ValueError('请选择 DeepSeek 或 OpenAI')
    model = clean(data.get('model')) or PROVIDERS[provider][1]
    if len(model) > 200 or '\n' in model:
        raise ValueError('模型名称格式不正确')
    path = Path(root).resolve() / 'config.local.json'
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(existing, dict):
                existing = {}
        except (ValueError, OSError):
            pass
    key = clean(data.get('api_key'))
    if not key:
        if clean(existing.get('provider', 'deepseek')).lower() != provider:
            raise ValueError('切换服务商时，请填写该服务商对应的密钥')
        key = clean(existing.get('api_key'))
    if not usable(key):
        raise ValueError('请填写有效密钥；留空仅能保留已有本地密钥')
    if any(c.isspace() for c in key):
        raise ValueError('密钥不能包含空格或换行')
    config = {'provider': provider, 'model': model, 'api_key': key}
    fd, temp = tempfile.mkstemp(prefix='.model-config-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(config, out, ensure_ascii=False, indent=2)
        os.replace(temp, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    info, _ = resolve(root)
    if info['key_source'] != 'config.local.json':
        info['warning'] = '已保存本地文件，但当前有更高优先级的环境变量或 .env 配置；实际生效来源见上方。'
    return info


def completion(settings, key, payload, timeout=30):
    if settings.get('error'):
        raise ValueError(settings['error'])
    req = urllib.request.Request(settings['endpoint'], data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        hints = {400: '请求或模型参数不兼容', 401: '密钥无效或不属于所选服务商', 402: '余额不足', 403: '账号无访问权限', 404: '模型不存在或当前账号不可用', 429: '调用过于频繁、配额或余额不足'}
        raise ValueError(f"模型接口 HTTP {exc.code}：{hints.get(exc.code, '服务商暂时不可用')}。请核对服务商、模型名和账户状态。") from None
    except (TimeoutError, urllib.error.URLError, OSError):
        raise ValueError('连接超时或网络不可达，请检查本机网络与代理设置后重试。') from None
    except ValueError:
        raise ValueError('模型接口返回的内容不是有效JSON。') from None
    if not isinstance(result, dict) or not result.get('choices'):
        raise ValueError('模型接口没有返回有效choices，请核对所选模型。')
    return result


def test_connection(root):
    info, key = resolve(root)
    result = completion(info, key, {'model': info['model'], 'messages': [{'role': 'user', 'content': 'Reply with OK.'}], 'max_tokens': 16}, timeout=20)
    return {'ok': True, 'message': '连接成功，已收到真实模型响应；完整工具调用请再运行一项营销任务验证。', 'provider': info['provider'], 'model': info['model']}
