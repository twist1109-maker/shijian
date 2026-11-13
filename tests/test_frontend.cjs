// 无需npm依赖。执行真实前端事件处理器，DOM和HTTP使用明确的测试替身。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8').replace(/boot\(\);\s*$/, '');
function element(text = '') { return { textContent: text, value: '', disabled: false, isConnected: true, style: {}, dataset: {}, querySelector: () => null }; }
function setup(ids = [], groups = {}) {
  const els = Object.fromEntries(['app', 'toast', ...ids].map(id => [id, element(id)]));
  const calls = [], downloads = [];
  const context = vm.createContext({
    console, Map, JSON, Error, Number, String, Object, Blob,
    setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
    document: { querySelector: s => els[s.slice(1)] || null, getElementById: id => els[id] || null, querySelectorAll: s => groups[s] || [] },
    FormData: class { constructor(form) { this.values = form.values; } *[Symbol.iterator]() { yield* Object.entries(this.values); } },
    fetch() { throw Error('unexpected fetch'); }, URL: { createObjectURL: () => '', revokeObjectURL() {} },
    __calls: calls, __downloads: downloads
  });
  vm.runInContext(source, context);
  vm.runInContext(`state={key_configured:true,user:{role:'editor'},model_config:{configured:false,provider:'deepseek',model:'deepseek-chat'}};selected=1;detail={task:{id:1},versions:[{id:8,content:'已有正文'}],runs:[],reviews:[],logs:[]};render=()=>{};refresh=async()=>{};download=(c,n)=>__downloads.push([c,n]);api=async(p,d)=>{__calls.push([p,d]); if(p==='/tasks/1')return {task:{id:1},versions:[{id:9,content:'修改正文'}],runs:[],reviews:[],logs:[]};if(p.endsWith('/export'))return {content:'<html>正文</html>',filename:'marketing-1.html'};if(p.endsWith('/test'))return {message:'连接成功'};return {ok:true};};`, context);
  return { els, calls, downloads, run: code => vm.runInContext(code, context), context };
}
(async () => {
  let passed = 0;
  // 原bug：成功后按钮永久disabled；覆盖导出后再次点击。
  {
    const t = setup(['export']); t.run('bind()');
    await t.els.export.onclick(); await t.els.export.onclick();
    assert.equal(t.downloads.length, 2); assert.equal(t.els.export.disabled, false);
    assert.equal(t.calls[0][0], '/tasks/1/export'); passed++;
  }
  // 原bug：保存按钮成功后若未重新渲染会锁死；统一finally恢复状态。
  {
    const t = setup(['button']);
    await t.run('perform(document.querySelector("#button"),async()=>{})');
    assert.equal(t.els.button.disabled, false); assert.equal(t.els.button.textContent, 'button'); passed++;
  }
  // 异常反馈后也恢复按钮，允许重试。
  {
    const t = setup(['button']);
    await t.run('perform(document.querySelector("#button"),async()=>{throw Error("测试错误")})');
    assert.equal(t.els.button.disabled, false); assert.equal(t.els.toast.textContent, '测试错误'); passed++;
  }
  // 前端实际保存、提交处理器：先保存脏正文，后调用submit。
  {
    const t = setup(['content', 'submit']); t.els.content.value = '修改正文'; t.run('bind()');
    t.els.content.oninput(); await t.els.submit.onclick();
    assert.deepEqual(t.calls.map(c => c[0]), ['/tasks/1/save', '/tasks/1', '/tasks/1/submit']);
    assert.equal(t.calls[0][1].base_version, 8); passed++;
  }
  // 切页签时草稿仍存内存，并带原版本基线。
  {
    const button = element(); button.dataset.tab = 'logs';
    const t = setup(['content'], { '[data-tab]': [button] }); t.els.content.value = '未保存草稿'; t.run('bind()');
    t.els.content.oninput(); button.onclick();
    assert.equal(t.run('drafts.get(1).content'), '未保存草稿'); assert.equal(t.run('drafts.get(1).base_version'), 8); passed++;
  }
  // 未配置key直接进入配置页，不会无提示地发送失败任务。
  {
    const t = setup(['mode', 'run']); t.els.mode.value = 'real'; t.run('state.key_configured=false;bind()');
    await t.els.run.onclick(); assert.equal(t.run('page'), 'settings'); assert.equal(t.calls.length, 0);
    assert.match(t.els.toast.textContent, /配置/); passed++;
  }
  // 需求未保存时，生成先同步需求再调用运行接口。
  {
    const t = setup(['mode', 'run']); t.els.mode.value = 'simulation';
    t.run('formDrafts.set("update-1",{audience:"亲子家庭"});bind()'); await t.els.run.onclick();
    assert.deepEqual(t.calls.map(c => c[0]), ['/tasks/1/update', '/tasks/1/run']); passed++;
  }
  // 模型配置表单真调用保存与测试两个业务接口，并清空输入框。
  {
    const t = setup(['model-settings', 'provider', 'model-name', 'test-model', 'connection-result']);
    const form = t.els['model-settings']; form.values = { provider: 'deepseek', model: 'deepseek-chat', api_key: 'test-only-token' };
    form.elements = { api_key: { value: 'test-only-token' } }; form.querySelector = () => element();
    t.run('bind()'); await t.els['test-model'].onclick();
    assert.deepEqual(t.calls.map(c => c[0]), ['/settings/model', '/settings/model/test']);
    assert.equal(form.elements.api_key.value, ''); assert.equal(t.els['connection-result'].textContent, '连接成功'); passed++;
  }
  // 审核按钮分别走实际approve/return接口，意见随请求发送。
  for (const action of ['approve', 'return']) {
    const t = setup([action, 'comment']); t.els.comment.value = '测试审核意见'; t.run('bind()');
    await t.els[action].onclick(); assert.equal(t.calls[0][0], '/tasks/1/' + action);
    assert.equal(t.calls[0][1].comment, '测试审核意见'); passed++;
  }
  // 保存需求、创建任务、资料保存通过真正的submit事件处理器。
  for (const [id, expected] of [['create', '/tasks'], ['update', '/tasks/1/update'], ['material', '/materials']]) {
    const t = setup([id]); const f = t.els[id];
    f.values = { title: '测试', audience: '读者', channel: '公众号', tone: '自然', length: '500', material_id: '1' };
    f.querySelector = () => element(); t.run('bind()');
    await f.onsubmit({ preventDefault() {} }); assert.equal(t.calls[0][0], expected);
    assert.equal(t.calls[0][1].length, 500); passed++;
  }
  // 新增证据导出按钮可连续工作，走后端接口。
  {
    const t = setup(['evidence']); t.run('bind()');
    await t.els.evidence.onclick(); await t.els.evidence.onclick();
    assert.equal(t.calls[0][0], '/tasks/1/evidence'); assert.equal(t.els.evidence.disabled, false); passed++;
  }
  // 版本比较使用任务内的两个版本ID，而非前端虚构比较结果。
  {
    const t = setup(['compare', 'compare-from', 'compare-to', 'compare-result']);
    t.els['compare-from'].value = '8'; t.els['compare-to'].value = '9';
    t.run('bind()'); await t.els.compare.onclick();
    assert.equal(t.calls[0][0], '/tasks/1/compare?from=8&to=9'); passed++;
  }
  // 质量页显示规则级别与真实来源字段，正文按后端受控渲染。
  {
    const t = setup();
    t.run('detail.quality={errors:1,warnings:0,characters:30,channel:"公众号",checks:[{level:"error",message:"价格未核对"}],source_hash:"abc",rule_id:"rules",channel_guidance:{structure:"标题",suggestion:"短句"},limits:"仅初筛"};detail.material={id:1,version:1,title:"原书",source:"教学",content:"价格49元"};');
    const html = t.run('qualityPanel()'); assert.match(html, /价格未核对/); assert.match(html, /原书/); passed++;
  }
  // 搜索和状态筛选保持任务原始数据，不混入其他状态。
  {
    const t = setup();
    t.run('state.tasks=[{id:1,title:"阅读",audience:"大学生",status:"draft"},{id:2,title:"亲子",audience:"家庭",status:"completed"}];taskSearch="阅读";taskFilter="draft";');
    assert.equal(t.run('visibleTasks().length'), 1); t.run('taskFilter="completed"'); assert.equal(t.run('visibleTasks().length'), 0); passed++;
  }
  console.log(`${passed} frontend event-handler tests passed (DOM/HTTP stubs; not full browser QA).`);
})().catch(e => { console.error(e); process.exitCode = 1; });
