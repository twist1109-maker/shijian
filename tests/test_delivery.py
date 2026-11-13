import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import marketing
import app
import test_regressions as regression

class MarketingTests(unittest.TestCase):
    def setUp(self):
        self.material = {'id': 1, 'title': '阅读课', 'version': 1, 'source': '教学资料', 'content': '书名：阅读课\n作者：小林\n定价：49.00元\n销量：未提供'}
        self.task = {'id': 1, 'title': '营销', 'length': 500, 'channel': '微信公众号', 'audience': '学生', 'status': 'draft'}

    def test_wrong_price_is_error(self):
        q = marketing.validate('定价39元', self.material, self.task)
        self.assertGreater(q['errors'], 0); self.assertIn('unverified_price', [c['code'] for c in q['checks']])

    def test_same_price_numeric_format_is_accepted(self):
        self.assertEqual(marketing.validate('定价49元', self.material, self.task)['errors'], 0)

    def test_page_count_does_not_justify_price(self):
        self.material['content'] = '书名：阅读课\n页数：49\n定价：未提供'
        self.assertGreater(marketing.validate('定价49元', self.material, self.task)['errors'], 0)

    def test_unverified_sales_is_error(self):
        self.assertGreater(marketing.validate('销量突破10万册', self.material, self.task)['errors'], 0)

    def test_missing_data_is_explicit(self):
        self.material['content'] = '定价：未提供'
        self.assertIn('定价', marketing.validate('价格待确认', self.material, self.task)['missing_fields'])

    def test_negative_award_statement_not_flagged(self):
        q = marketing.validate('获奖信息未提供，不作声明', self.material, self.task)
        self.assertNotIn('award_review', [x['code'] for x in q['checks']])

    def test_channel_guidance_changes_with_channel(self):
        first = marketing.validate('正文', self.material, self.task)['channel_guidance']
        self.task['channel'] = '小红书'
        self.assertNotEqual(first, marketing.validate('正文', self.material, self.task)['channel_guidance'])

    def test_markdown_escapes_html_and_formats_headings(self):
        result = marketing.markdown('# 标题\n- **卖点**\n<script>alert(1)</script>')
        self.assertIn('<h2>标题</h2>', result); self.assertIn('<strong>卖点</strong>', result)
        self.assertNotIn('<script>', result)

    def test_cover_rejects_svg_and_mismatched_image(self):
        for invalid in ['data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,YmFk', 'https://example.com/image.png']:
            with self.assertRaises(ValueError): marketing.validate_cover(invalid)

    def test_original_png_can_be_embedded(self):
        data = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'0'*16).decode()
        self.assertEqual(marketing.validate_cover(data), data)

    def test_source_digest_changes_when_content_changes(self):
        first = marketing.digest(self.material); self.material['content'] += '新增事实'
        self.assertNotEqual(first, marketing.digest(self.material))

    def test_diff_and_redaction(self):
        self.assertTrue(marketing.compare({'id': 1, 'content': '旧正文'}, {'id': 2, 'content': '新正文'})['changed'])
        data = marketing.redact({'api_key': 'a', 'text': 'test-real-secret sk-12345678901234567890'}, ['test-real-secret'])
        self.assertEqual(data['api_key'], '[REDACTED]'); self.assertNotIn('sk-', data['text'])

class DeliveryAPITests(regression.APITests):
    # 继承复用独立HTTP测试环境；不重复执行父类用例。
    pass
for _name in [n for n in dir(regression.APITests) if n.startswith('test_')]:
    setattr(DeliveryAPITests, _name, None)

def test_audit_export_and_snapshot(self):
    self.configure(); p = self.new(); self.simulate(p)
    d = self.req(self.editor, p)[1]
    self.assertEqual(len(json.loads(d['runs'][0]['snapshot'])['source_hash']), 64)
    self.assertIn('quality', d); self.assertIn('preview_html', d)
    exported = json.loads(self.req(self.editor, p + '/evidence')[1]['content'])
    self.assertEqual(exported['task']['id'], d['task']['id'])
    self.assertEqual(exported['runs'][0]['mode'], 'simulation')
    self.assertNotIn('test-only-token', json.dumps(exported))
DeliveryAPITests.test_audit_export_and_snapshot = test_audit_export_and_snapshot

def test_compare_scoped_to_task(self):
    p = self.new(); self.simulate(p)
    v = self.req(self.editor, p)[1]['versions'][0]
    self.req(self.editor, p + '/save', {'content': '人工修改', 'base_version': v['id']})
    self.assertTrue(self.req(self.editor, p + '/compare')[1]['changed'])
    self.assertEqual(self.req(self.editor, p + '/compare?from=99999')[0], 400)
DeliveryAPITests.test_compare_scoped_to_task = test_compare_scoped_to_task

def test_approval_blocks_wrong_price(self):
    p = self.new(); self.simulate(p)
    v = self.req(self.editor, p)[1]['versions'][0]
    self.req(self.editor, p + '/save', {'content': '定价999元，保证有效', 'base_version': v['id']})
    self.req(self.editor, p + '/submit', {})
    status, result = self.req(self.reviewer, p + '/approve', {'comment': '通过'})
    self.assertEqual(status, 400); self.assertIn('校验错误', result['error'])
DeliveryAPITests.test_approval_blocks_wrong_price = test_approval_blocks_wrong_price

def test_material_image_type_validation(self):
    body = {'title': '新资料', 'content': '定价：49元', 'source': '原创教学模拟', 'cover_data': 'data:image/svg+xml;base64,PHN2Zz4='}
    self.assertEqual(self.req(self.editor, '/materials', body)[0], 400)
    body['cover_data'] = ''
    self.assertEqual(self.req(self.editor, '/materials', body)[0], 200)
DeliveryAPITests.test_material_image_type_validation = test_material_image_type_validation
