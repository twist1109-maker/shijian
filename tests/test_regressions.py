"""无需依赖：python -m unittest discover -s tests -v。模型响应为显式测试替身，不连接服务商。"""
import contextlib
import http.cookiejar
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
import app
import model_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop(); self.temp.cleanup()

    def write(self, filename, text):
        (self.root / filename).write_text(text, encoding='utf-8-sig')

    def test_local_config_trims_key_and_provider(self):
        self.write('config.local.json', json.dumps({'provider': ' DeepSeek ', 'api_key': ' test-only-token ', 'model': ' deepseek-chat '}))
        info, key = model_config.resolve(self.root)
        self.assertTrue(info['configured']); self.assertEqual(key, 'test-only-token')
        self.assertEqual(info['key_source'], 'config.local.json')

    def test_example_file_is_diagnosed(self):
        self.write('config.example.json', '{"api_key":"test-only-token"}')
        info, _ = model_config.resolve(self.root)
        self.assertFalse(info['configured']); self.assertIn('示例', info['error'])

    def test_dotenv_openai_alias_infers_provider(self):
        self.write('.env', 'OPENAI_API_KEY="test-openai-token"\nMODEL_NAME=gpt-4o-mini\n')
        info, key = model_config.resolve(self.root)
        self.assertEqual(info['provider'], 'openai'); self.assertEqual(key, 'test-openai-token')
        self.assertEqual(info['key_source'], '.env')

    def test_empty_environment_does_not_override_file(self):
        self.write('config.local.json', '{"api_key":"test-only-token"}')
        with patch.dict(os.environ, {'MODEL_API_KEY': '   '}):
            self.assertTrue(model_config.resolve(self.root)[0]['configured'])

    def test_environment_priority_is_visible(self):
        self.write('.env', 'MODEL_API_KEY=file-test-token')
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'environment-test-token'}):
            info, key = model_config.resolve(self.root)
            self.assertEqual(key, 'environment-test-token'); self.assertEqual(info['key_source'], '环境变量')

    def test_invalid_json_does_not_break_diagnostics(self):
        self.write('config.local.json', '{invalid}')
        info, _ = model_config.resolve(self.root)
        self.assertFalse(info['configured']); self.assertIn('格式错误', info['error'])
        saved = model_config.save(self.root, {'provider': 'deepseek', 'api_key': 'test-only-token'})
        self.assertTrue(saved['configured'])

    def test_windows_hidden_extension_diagnostic(self):
        self.write('config.local.json.txt', '{}')
        self.assertIn('隐藏扩展名', model_config.resolve(self.root)[0]['error'])

    def test_save_does_not_return_key_and_keeps_blank(self):
        first = model_config.save(self.root, {'provider': 'deepseek', 'api_key': 'test-only-token'})
        second = model_config.save(self.root, {'provider': 'deepseek', 'api_key': '', 'model': 'deepseek-chat'})
        self.assertNotIn('test-only-token', json.dumps(first)); self.assertTrue(second['configured'])
        with self.assertRaisesRegex(ValueError, '切换服务商'):
            model_config.save(self.root, {'provider': 'openai', 'api_key': ''})

    def test_placeholder_rejected(self):
        with self.assertRaises(ValueError):
            model_config.save(self.root, {'provider': 'deepseek', 'api_key': '在本机填写，不要提交或分享'})


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_root, cls.old_db = app.ROOT, app.DB
        app.ROOT = Path(cls.temp.name); app.DB = app.ROOT / 'data.db'
        (app.ROOT / 'static').mkdir()
        (app.ROOT / 'static' / 'cover.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        cls.env = patch.dict(os.environ, {}, clear=True); cls.env.start()
        app.init()
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.base = f'http://127.0.0.1:{cls.server.server_port}/api'
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.env.stop()
        app.ROOT, app.DB = cls.old_root, cls.old_db; cls.temp.cleanup()

    def setUp(self):
        self.editor = self.client('editor', 'Editor123!')
        self.reviewer = self.client('reviewer', 'Review123!')
        (app.ROOT / 'config.local.json').unlink(missing_ok=True)

    def client(self, name, password):
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.assertEqual(self.req(opener, '/login', {'name': name, 'password': password})[0], 200)
        return opener

    def req(self, client, path, data=None):
        req = urllib.request.Request(self.base + path, data=None if data is None else json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
        try:
            with client.open(req, timeout=8) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def new(self, **kwargs):
        body = {'title': '回归测试', 'material_id': 1, 'audience': '大学生', 'channel': '微信公众号', 'tone': '自然', 'length': 500}
        body.update(kwargs)
        status, data = self.req(self.editor, '/tasks', body)
        self.assertEqual(status, 200)
        return '/tasks/' + str(data['id'])

    def wait(self, path):
        for _ in range(100):
            data = self.req(self.editor, path)[1]
            if data['task']['ai_status'] != 'running': return data
            time.sleep(.02)
        self.fail('任务没有退出运行态')

    def simulate(self, path):
        self.assertEqual(self.req(self.editor, path + '/run', {'mode': 'simulation'})[0], 200)
        self.assertEqual(self.wait(path)['task']['ai_status'], 'completed')

    def configure(self):
        status, info = self.req(self.editor, '/settings/model', {'provider': 'deepseek', 'api_key': 'test-only-token'})
        self.assertEqual(status, 200); self.assertTrue(info['configured'])
        return info

    def test_settings_save_and_state_use_same_config(self):
        info = self.configure()
        data = self.req(self.editor, '/state')[1]
        self.assertTrue(data['key_configured']); self.assertEqual(data['model_config'], info)
        self.assertNotIn('test-only-token', json.dumps(data))

    def test_reviewer_cannot_change_or_probe_model(self):
        self.assertEqual(self.req(self.reviewer, '/settings/model', {'provider': 'deepseek', 'api_key': 'test-only-token'})[0], 403)
        self.assertEqual(self.req(self.reviewer, '/settings/model/test', {})[0], 403)

    def test_malformed_config_does_not_break_state_or_failure_record(self):
        (app.ROOT / 'config.local.json').write_text('{invalid}')
        self.assertEqual(self.req(self.editor, '/state')[0], 200)
        p = self.new(); self.req(self.editor, p + '/run', {'mode': 'real'})
        d = self.wait(p); self.assertEqual(d['task']['ai_status'], 'failed')
        self.assertIn('格式错误', d['runs'][0]['error'])

    def test_model_connection_success_uses_saved_key(self):
        self.configure()
        def response(req, timeout):
            self.assertEqual(req.headers['Authorization'], 'Bearer test-only-token')
            return io.BytesIO(b'{"choices":[{"message":{"content":"OK"}}]}')
        with patch.object(model_config.urllib.request, 'urlopen', side_effect=response):
            status, data = self.req(self.editor, '/settings/model/test', {})
        self.assertEqual(status, 200); self.assertTrue(data['ok'])
        self.assertNotIn('test-only-token', json.dumps(data))

    def test_http_401_is_visible_and_does_not_leak_key(self):
        self.configure()
        error = urllib.error.HTTPError('https://example.invalid', 401, 'unauthorized', {}, None)
        with patch.object(model_config.urllib.request, 'urlopen', side_effect=error):
            status, data = self.req(self.editor, '/settings/model/test', {})
        self.assertEqual(status, 400); self.assertIn('401', data['error'])
        self.assertNotIn('test-only-token', data['error'])

    def test_network_timeout_is_visible(self):
        self.configure()
        with patch.object(model_config.urllib.request, 'urlopen', side_effect=TimeoutError()):
            self.assertIn('超时', self.req(self.editor, '/settings/model/test', {})[1]['error'])

    def test_agent_real_path_with_explicit_provider_stub(self):
        self.configure(); p = self.new()
        def response(req, timeout):
            payload = json.loads(req.data); messages = payload['messages']
            tool_messages = [m for m in messages if m['role'] == 'tool']
            if not tool_messages:
                msg = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'r1', 'type': 'function', 'function': {'name': 'read_sources', 'arguments': '{"material_id":1}'}}]}
            elif len(tool_messages) == 1:
                msg = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'v1', 'type': 'function', 'function': {'name': 'validate_copy', 'arguments': json.dumps({'text': '面向大学生的阅读邀请，资料来源：图书资料。'})}}]}
            else:
                msg = {'role': 'assistant', 'content': '面向大学生的阅读邀请。来源：资料1 v1；未提供销量，不做推断。'}
            return io.BytesIO(json.dumps({'choices': [{'message': msg}]}).encode())
        with patch.object(model_config.urllib.request, 'urlopen', side_effect=response):
            self.req(self.editor, p + '/run', {'mode': 'real'}); d = self.wait(p)
        self.assertEqual(d['task']['ai_status'], 'completed')
        self.assertEqual({x['tool'] for x in d['logs']}, {'read_sources', 'validate_copy'})
        self.assertEqual(d['runs'][0]['mode'], 'real')
        self.assertEqual(len(d['logs']), 3)

    def test_workflow_versions_review_and_export(self):
        p = self.new(); self.simulate(p)
        v = self.req(self.editor, p)[1]['versions'][0]
        self.assertEqual(self.req(self.editor, p + '/save', {'content': v['content'] + '\n人工确认', 'base_version': v['id']})[0], 200)
        self.assertEqual(self.req(self.editor, p + '/submit', {})[0], 200)
        self.assertEqual(self.req(self.editor, p + '/submit', {})[0], 400)
        self.assertEqual(self.req(self.editor, p + '/approve', {'comment': '越权'})[0], 403)
        self.assertEqual(self.req(self.reviewer, p + '/return', {'comment': '补充来源'})[0], 200)
        self.assertEqual(self.req(self.editor, p + '/submit', {})[0], 200)
        self.assertEqual(self.req(self.reviewer, p + '/approve', {'comment': '核对通过'})[0], 200)
        status, exported = self.req(self.reviewer, p + '/export')
        self.assertEqual(status, 200); self.assertIn('人工确认', exported['content'])
        self.assertEqual(len(self.req(self.editor, p)[1]['versions']), 2)

    def test_export_escapes_text_and_rejects_empty_task(self):
        p = self.new(title='<script>alert(1)</script>')
        self.assertEqual(self.req(self.editor, p + '/export')[0], 400)
        self.req(self.editor, p + '/save', {'content': '<img src=x onerror=alert(1)>', 'base_version': None})
        data = self.req(self.editor, p + '/export')[1]
        self.assertNotIn('<script>', data['content']); self.assertIn('&lt;img', data['content'])

    def test_restart_unlocks_only_running_tasks_and_preserves_versions(self):
        p = self.new(); self.simulate(p); tid = int(p.split('/')[-1])
        with app.connect() as c:
            c.execute("UPDATE tasks SET ai_status='running' WHERE id=?", (tid,))
            c.execute("INSERT INTO runs(task_id,mode,status,error,created) VALUES(?,'real','running','',?)", (tid, app.now()))
        app.init()
        d = self.req(self.editor, p)[1]
        self.assertEqual(d['task']['ai_status'], 'failed'); self.assertEqual(len(d['versions']), 1)
        self.assertIn('重启', d['runs'][0]['error'])

    def test_failure_keeps_manual_version_and_retry_works(self):
        p = self.new(); self.req(self.editor, p + '/save', {'content': '人工正文', 'base_version': None})
        self.req(self.editor, p + '/run', {'mode': 'failure'})
        d = self.wait(p)
        self.assertEqual(d['task']['ai_status'], 'failed'); self.assertEqual(d['versions'][0]['content'], '人工正文')
        self.simulate(p)

    def test_empty_fields_and_invalid_material_are_rejected(self):
        self.assertEqual(self.req(self.editor, '/tasks', {})[0], 400)
        self.assertEqual(self.req(self.reviewer, '/materials', {'title': 'x', 'content': 'x', 'source': 'x'})[0], 403)


if __name__ == '__main__':
    unittest.main()
