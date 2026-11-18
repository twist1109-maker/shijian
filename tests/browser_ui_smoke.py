import os,sys,subprocess,tempfile,shutil,time,json
from pathlib import Path
import urllib.request
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'evidence'/'ui-smoke';OUT.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    tmp=Path(temp)
    for f in ['app.py','model_config.py','marketing.py']:shutil.copy(ROOT/f,tmp/f)
    shutil.copytree(ROOT/'static',tmp/'static')
    server=subprocess.Popen([sys.executable,str(tmp/'app.py')],env={**os.environ,'PORT':'18770'},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen('http://127.0.0.1:18770',timeout=1).close();break
            except Exception:time.sleep(.1)
        with sync_playwright() as pw:
            browser_path=shutil.which('chromium') or shutil.which('google-chrome')
            browser=pw.chromium.launch(headless=True,**({'executable_path':browser_path} if browser_path else {}))
            context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
            page=context.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:18770');expect(page.locator('#login')).to_be_visible()
            page.screenshot(path=str(OUT/'login.png'),full_page=True)
            def login(name,password):
                page.locator('#login [name=name]').fill(name);page.locator('#login [name=password]').fill(password)
                page.locator('#login button').click();expect(page.locator('.sidebar')).to_be_visible()
            def open_task(tid):
                page.locator(f'[data-task="{tid}"]').click();expect(page.locator('.detail-card')).to_be_visible()
            login('editor','Editor123!')
            expect(page.locator('#create')).to_be_visible();page.screenshot(path=str(OUT/'workspace-create.png'),full_page=True)
            page.locator('#create [name=material_id]').select_option('1')
            page.locator('#create [name=title]').fill('阅读新提案 · 让好书走近日常')
            page.locator('#create button[type=submit]').click();expect(page.locator('.detail-card')).to_be_visible()
            tid=page.locator('.task.selected').get_attribute('data-task')
            page.locator('#mode').select_option('simulation');page.locator('#run').click()
            expect(page.locator('.status-stack')).to_contain_text('AI 已完成',timeout=15000)
            page.locator('.tabs [data-tab=copy]').click()
            content='# 把时间留给阅读\n\n给大学生的一份阅读邀请。\n\n## 从十分钟开始\n\n**林知（虚构）**带你从阅读计划、笔记方法与注意力练习开始，建立自己的阅读节奏。\n\n- 包含阅读计划表与笔记示例\n- 先浏览目录，再选择适合自己的书\n\n定价49元。销量与获奖信息未提供。\n\n资料为原创教学模拟，仅用于实训演示。'
            page.locator('#content').fill(content);page.locator('#save').click();expect(page.locator('.rich-copy')).to_contain_text('从十分钟开始')
            page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(OUT/'workspace-content.png'),full_page=True)
            page.locator('.tabs [data-tab=quality]').click();expect(page.locator('.quality-summary')).to_contain_text('0 项明确错误')
            page.locator('.tabs [data-tab=versions]').click();page.locator('#compare').click();expect(page.locator('#compare-result')).not_to_be_empty()
            page.locator('.tabs [data-tab=copy]').click()
            for _ in range(2):
                with page.expect_download() as dl:page.locator('#export').click()
                assert dl.value.suggested_filename.endswith('.html')
                expect(page.locator('#export')).to_be_enabled()
            page.locator('#submit').click();expect(page.locator('.status-pending_review').first).to_be_visible()
            expect(page.locator('.next-step')).to_contain_text('reviewer')
            page.locator('#logout').click();login('reviewer','Review123!');open_task(tid)
            page.locator('.tabs [data-tab=review]').click();page.locator('#comment').fill('请进一步明确资料用途。');page.locator('#return').click()
            expect(page.locator('.status-returned').first).to_be_visible()
            page.locator('#logout').click();login('editor','Editor123!');open_task(tid)
            page.locator('#content').fill(content+'\n\n本页不用于真实营销发布。');page.locator('#submit').click()
            page.locator('#logout').click();login('reviewer','Review123!');open_task(tid);page.locator('.tabs [data-tab=review]').click()
            page.locator('#comment').fill('已核对资料与教学用途，同意通过。');page.locator('#approve').click()
            expect(page.locator('.status-completed').first).to_be_visible();expect(page.locator('.next-step')).to_contain_text('审核已完成')
            page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(OUT/'review-completed.png'),full_page=True)
            page.locator('#logout').click();login('editor','Editor123!')
            page.locator('[data-page=materials]').first.click();expect(page.locator('#material')).to_be_visible()
            page.screenshot(path=str(OUT/'materials.png'),full_page=True)
            page.locator('[data-page=settings]').first.click();expect(page.locator('#model-settings')).to_be_visible()
            page.screenshot(path=str(OUT/'settings.png'),full_page=True)
            page.locator('[data-page=tasks]').first.click();open_task(tid);page.locator('.tabs [data-tab=copy]').click()
            overflow=[]
            for w,h in [(1440,1000),(1366,768),(1024,800),(768,1024),(390,844)]:
                page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(100)
                diff=page.evaluate('document.documentElement.scrollWidth - window.innerWidth')
                overflow.append({'width':w,'overflow':diff});assert diff<=1,(w,diff)
                if w==390:page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
            assert not errors,errors
            browser.close()
            print(json.dumps({'status':'PASS','flow':'browser: create/simulate/edit/save/quality/compare/export twice/submit/return/edit/resubmit/approve/materials/settings','viewports':overflow,'js_errors':errors,'limits':'真实后端与浏览器；模型仅使用明确模拟模式，不验证服务商'},ensure_ascii=False,indent=2))
    finally:
        server.terminate();server.wait(timeout=5)
