let state = null, detail = null, selected = null, page = 'tasks', tab = 'copy', timer = null;
let requestBusy = false;
const app = document.querySelector('#app');
const drafts = new Map();
const formDrafts = new Map();
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const labels = { draft: '待处理', pending_review: '待审核', returned: '已退回', completed: '已完成', pending: '待执行', running: '运行中', failed: '失败', submit: '提交', approve: '通过', return: '退回', real: '真实模型', simulation: '模拟演练', failure: '故障演示' };

async function api(path, data) {
  let r;
  try {
    r = await fetch('/api' + path, { method: data === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : JSON.stringify(data) });
  } catch { throw Error('无法连接后端，请确认 app.py 正在运行，然后重试。'); }
  const text = await r.text();
  let j;
  try { j = JSON.parse(text); } catch { throw Error('后端返回了非JSON内容，请通过 http://127.0.0.1:8765 打开项目，不要使用 Live Server。'); }
  if (!r.ok) {
    if (r.status === 401) login();
    throw Error(j.error || '请求失败');
  }
  return j;
}
function toast(s) {
  const x = document.querySelector('#toast');
  x.textContent = s; x.style.display = 'block';
  clearTimeout(toast.timeout); toast.timeout = setTimeout(() => x.style.display = 'none', 6500);
}
function resetSession() {
  clearInterval(timer); selected = null; detail = null; page = 'tasks'; tab = 'copy';
  drafts.clear(); formDrafts.clear();
}
function login() {
  resetSession(); state = null;
  app.innerHTML = `<div class="login"><div class="eyebrow">PUBLISHING × AI</div><div class="brand">书语 / 营销工作台</div><p class="muted">从图书资料，到有依据的营销表达。</p><div class="card"><h2>登录工作台</h2><form id="login"><label>账号</label><input name="name" value="editor" required autocomplete="username"><label>密码</label><input name="password" type="password" value="Editor123!" required autocomplete="current-password"><button class="primary" type="submit">进入工作台 →</button></form><p class="muted" style="margin-top:22px">营销：editor / Editor123!<br>审核：reviewer / Review123!</p><div class="warn">教学演示系统。样例图书、封面与规则均为模拟资料。</div><small>版本 1.1.0</small></div></div>`;
  document.querySelector('#login').onsubmit = e => {
    e.preventDefault();
    return perform(e.target.querySelector('button'), async () => {
      await api('/login', Object.fromEntries(new FormData(e.target)));
      resetSession(); await refresh();
    });
  };
}
async function perform(button, action) {
  if (requestBusy) return;
  requestBusy = true;
  const label = button?.textContent;
  if (button) { button.disabled = true; button.textContent = '处理中…'; }
  try { await action(); }
  catch (e) { toast(e.message); }
  finally {
    requestBusy = false;
    if (button?.isConnected) { button.disabled = false; button.textContent = label; }
  }
}
async function refresh() {
  clearInterval(timer);
  state = await api('/state');
  if (selected) detail = await api('/tasks/' + selected);
  render();
  if (detail?.task.ai_status === 'running' && page === 'tasks') {
    timer = setInterval(async () => {
      try {
        const id = selected;
        if (!id || page !== 'tasks') { clearInterval(timer); return; }
        const updated = await api('/tasks/' + id);
        if (selected !== id || page !== 'tasks') return;
        detail = updated;
        if (detail.task.ai_status !== 'running') {
          clearInterval(timer); await refresh();
          toast(detail.task.ai_status === 'completed' ? '生成完成，请打开图文草稿查看' : '生成失败，请在执行依据中查看原因');
        } else if (tab === 'logs') render();
      } catch (e) { clearInterval(timer); toast(e.message); }
    }, 1800);
  }
}
const fields = (t = {}) => `<label>任务名称</label><input name="title" required value="${esc(t.title || '新书营销图文策划')}"><label>目标读者</label><input name="audience" required value="${esc(t.audience || '大学生')}"><label>发布渠道</label><select name="channel">${['微信公众号', '小红书', '电商详情页'].map(x => `<option ${t.channel === x ? 'selected' : ''}>${x}</option>`).join('')}</select><label>表达风格</label><input name="tone" required value="${esc(t.tone || '自然、真诚、有亲和力')}"><label>目标字数</label><input name="length" type="number" min="100" max="2000" value="${esc(t.length || 500)}" required>`;
function render() {
  if (!state) return;
  const editor = state.user.role === 'editor';
  const titles = { tasks: '让好书，被更多人看见。', materials: '每一句表达，都有据可查。', settings: '连接模型，开始真实创作。' };
  app.innerHTML = `<div class="shell"><aside class="sidebar"><div class="brand">书语<span style="font-size:13px"> SHUYU</span></div><small>图书营销工作台</small><nav><button type="button" data-page="tasks" class="${page === 'tasks' ? 'active' : ''}">◫　营销任务</button><button type="button" data-page="materials" class="${page === 'materials' ? 'active' : ''}">▤　资料与规则</button>${editor ? `<button type="button" data-page="settings" class="${page === 'settings' ? 'active' : ''}">⚙　模型配置</button>` : ''}</nav><footer>${editor ? '营销编辑' : '内容审核'} · ${esc(state.user.name)}<br><button type="button" id="logout">退出账号</button><br>教学项目 / v${esc(state.app_version || '1.1.0')}</footer></aside><main class="main"><header class="top"><div><div class="eyebrow">BOOK MARKETING STUDIO</div><h1>${titles[page]}</h1><span class="muted">资料驱动生成 · 工具执行可追溯 · 人工审核闭环</span></div><div class="row"><button type="button" id="refresh">刷新状态</button>${editor ? `<button type="button" data-page="settings">${state.key_configured ? '模型密钥已配置' : '配置真实模型 →'}</button>` : `<span class="badge">${state.key_configured ? '模型密钥已配置' : '模型未配置，请联系营销人员'}</span>`}</div></header>${page === 'tasks' ? taskPage(editor) : page === 'settings' ? settingsPage() : materialPage(editor)}</main></div>`;
  bind();
}
function taskPage(editor) {
  const create = formDrafts.get('create') || {};
  return `<section class="hero"><div><h2>从一本书，开始一次好好表达</h2><p>选择资料，明确读者，让 AI 协助完成营销草稿。<br><span class="muted">生成内容经规则初筛后，仍需人工核对与审核。</span></p></div><img src="/cover.svg" alt="原创教学封面"></section><div class="stats"><div><strong>${state.tasks.length}</strong><span>营销任务</span></div><div><strong>${state.tasks.filter(t => t.status === 'pending_review').length}</strong><span>等待审核</span></div><div><strong>${state.materials.length}</strong><span>图书资料</span></div></div><div class="grid"><section><div class="card"><div class="row between"><h2>任务列表</h2>${editor ? '<button type="button" id="new">＋ 新建</button>' : ''}</div>${state.tasks.map(t => `<button type="button" class="task ${t.id === selected ? 'selected' : ''}" data-task="${t.id}"><div class="row between"><strong>${esc(t.title)}</strong><span class="badge">${labels[t.status]}</span></div><p class="muted" style="margin:8px 0 0">#${t.id} · ${esc(t.channel)} · ${labels[t.ai_status]}</p></button>`).join('') || '<p class="muted">暂无任务，创建第一份营销内容。</p>'}</div>${editor && !selected ? `<div class="card"><h2>创建营销任务</h2><form id="create"><label>图书资料</label><select name="material_id">${state.materials.map(m => `<option value="${m.id}" ${String(create.material_id) === String(m.id) ? 'selected' : ''}>${esc(m.title)} · v${m.version}</option>`).join('')}</select>${fields(create)}<button type="submit" class="primary" style="margin-top:18px">保存任务</button></form></div>` : ''}</section><section>${detail && selected ? detailPage(editor) : '<div class="card empty">选择任务，查看图文草稿与执行记录。</div>'}</section></div>`;
}
function detailPage(editor) {
  const t = detail.task, v = detail.versions[0];
  const editable = editor && ['draft', 'returned'].includes(t.status) && t.ai_status !== 'running';
  const draft = drafts.get(t.id);
  let body = '';
  if (tab === 'copy') body = `<div class="preview"><img src="/cover.svg" alt="教学示意封面"><div class="copy">${esc(v?.content || '暂未生成文案。请选择运行模式并开始生成。')}</div></div>${editable ? `<label>人工修改正文（切换页签保留草稿；保存后形成新版本）${draft ? ' · 有未保存修改' : ''}</label><textarea id="content" rows="12">${esc(draft?.content ?? v?.content ?? '')}</textarea><div class="row" style="margin-top:12px"><button type="button" id="save">保存新版本</button><button type="button" id="submit" class="primary">保存并提交审核</button></div>` : ''}${v ? '<button type="button" id="export" style="margin-top:15px">导出已保存图文 HTML</button>' : ''}`;
  if (tab === 'logs') body = detail.runs.map(r => `<div class="log ${r.status === 'failed' ? 'failed' : ''}"><strong>运行 #${r.id} · ${labels[r.mode]} · ${labels[r.status]}</strong><p class="muted">${esc(r.created)}</p>${r.mode !== 'real' ? '<div class="warn">演练记录，不作为真实模型调用证据。</div>' : ''}${r.error ? `<p role="alert">${esc(r.error)}</p>` : ''}${detail.logs.filter(l => l.run_id === r.id).map(l => `<details><summary>${esc(l.tool)} · ${labels[l.status]} · #${l.id}</summary><pre>参数：${esc(l.args)}\n返回：${esc(l.result)}\n时间：${esc(l.created)}</pre></details>`).join('')}</div>`).join('') || '<p class="muted">暂无运行记录</p>';
  if (tab === 'versions') body = detail.versions.map(v => `<details class="log"><summary>版本 #${v.id} · ${esc(v.actor)} · ${esc(v.created)}</summary><pre>${esc(v.content)}</pre></details>`).join('') || '<p>暂无版本</p>';
  if (tab === 'review') body = `${!editor && t.status === 'pending_review' ? `<label>审核意见</label><textarea id="comment" rows="4" placeholder="说明通过依据或需要修改的内容">${esc(formDrafts.get('review-' + t.id) || '')}</textarea><div class="row" style="margin:12px 0"><button type="button" id="return">退回修改</button><button type="button" id="approve" class="primary">审核通过</button></div>` : editor && t.status === 'pending_review' ? '<div class="warn">已提交，请退出并使用 reviewer 账号审核。</div>' : ''}${detail.reviews.map(r => `<div class="log"><strong>${labels[r.action]} · ${esc(r.actor)}</strong><p>${esc(r.comment)}</p><small>${esc(r.created)}</small></div>`).join('') || '<p class="muted">暂无审核记录</p>'}`;
  const latestRun = detail.runs[0];
  return `<div class="card"><div class="row between"><h2>${esc(t.title)}</h2><span class="badge">${labels[t.status]} / AI ${labels[t.ai_status]}</span></div><p class="muted">${esc(t.audience)} · ${esc(t.channel)} · ${esc(t.tone)} · 目标 ${t.length} 字</p>${editable ? `<details><summary>修改任务需求</summary><form id="update">${fields(formDrafts.get('update-' + t.id) || t)}<button type="submit" style="margin-top:12px">保存需求</button></form></details><div class="row" style="margin-top:18px"><select id="mode" style="width:auto"><option value="real" ${state.key_configured ? 'selected' : ''}>真实模型调用</option><option value="simulation" ${!state.key_configured ? 'selected' : ''}>模拟流程演练</option><option value="failure">模拟超时故障</option></select><button type="button" class="primary" id="run">生成营销草稿 →</button></div>` : ''}${t.ai_status === 'running' ? '<div class="warn" style="margin-top:16px">模型运行中，最多约 150 秒。已有文案保留，请等待执行结果。</div>' : t.ai_status === 'failed' && latestRun?.error ? `<div class="warn" role="alert" style="margin-top:16px">生成失败：${esc(latestRun.error)}。已有版本保留，可修正配置后重试。</div>` : ''}<div class="tabs">${[['copy', '图文草稿'], ['logs', '执行依据'], ['versions', '历史版本 (' + detail.versions.length + ')'], ['review', '审核记录']].map(([k, n]) => `<button type="button" data-tab="${k}" class="${tab === k ? 'on' : ''}">${n}</button>`).join('')}</div>${body}</div>`;
}
function settingsPage() {
  const c = state.model_config || {};
  return `<div class="grid"><section><div class="card"><h2>模型配置</h2><p class="muted">密钥只写入本机 config.local.json，不回显到页面。保存立即生效，无需重启。</p><form id="model-settings"><label>服务商</label><select name="provider" id="provider"><option value="deepseek" ${c.provider === 'deepseek' ? 'selected' : ''}>DeepSeek</option><option value="openai" ${c.provider === 'openai' ? 'selected' : ''}>OpenAI</option></select><label>模型名称</label><input name="model" id="model-name" value="${esc(c.model || 'deepseek-chat')}" required><label>API Key（留空保留已保存的本地密钥）</label><input name="api_key" type="password" autocomplete="off" placeholder="在此输入对应服务商的密钥"><div class="row" style="margin-top:18px"><button type="submit" class="primary">保存配置</button><button type="button" id="test-model">保存并测试连接</button></div><p class="muted">测试会发送一条简短的真实请求，可能产生少量 API 费用。</p></form><div id="connection-result" role="status"></div></div></section><section><div class="card"><h2>后端实际读取状态</h2><p><span class="badge">${c.configured ? '已找到密钥' : '尚未配置有效密钥'}</span></p><p>当前服务商：${esc(c.provider)}<br>当前模型：${esc(c.model)}<br>密钥来源：${esc(c.key_source)}</p>${c.error ? `<div class="warn" role="alert">${esc(c.error)}</div>` : ''}${c.warning ? `<div class="warn">${esc(c.warning)}</div>` : ''}<label>配置文件绝对路径</label><pre>${esc(c.config_path)}</pre><label>配置优先级</label><p class="muted">${esc(c.priority)}</p><p class="muted">修改 config.example.json 不会启用密钥。如果误填在那里，请复制为 config.local.json，并把示例文件恢复为空占位符；不要将密钥上传 GitHub。</p></div></section></div>`;
}
function materialPage(editor) {
  const d = formDrafts.get('material') || {};
  return `<div class="warn">所有样例均为教学模拟数据。资料新增后保持不可变，以资料 ID 和版本追溯；更新内容请新增一份资料。支持 UTF-8 TXT / Markdown 文本导入。</div><div class="grid"><section>${editor ? `<div class="card"><h2>新增图书资料</h2><form id="material"><label>资料标题</label><input name="title" value="${esc(d.title)}" required><label>导入 TXT / Markdown（可选）</label><input id="file" type="file" accept=".txt,.md"><label>正文</label><textarea name="content" id="material-content" rows="12" required placeholder="书名、作者、定价、简介、目录、已确认卖点">${esc(d.content)}</textarea><label>资料来源与用途</label><input name="source" required value="${esc(d.source || '原创教学模拟资料，不用于真实营销')}"><button type="submit" class="primary" style="margin-top:16px">保存资料</button></form></div>` : ''}<div class="card"><h2>营销规则 · ${esc(state.rules.id)}</h2>${state.rules.rules.map(x => `<p>· ${esc(x)}</p>`).join('')}<p class="muted">${esc(state.rules.source)}</p></div></section><section>${state.materials.map(m => `<div class="card"><h2>${esc(m.title)}</h2><span class="badge">资料 #${m.id} · v${m.version}</span><pre>${esc(m.content)}</pre><p class="muted">来源：${esc(m.source)}<br>${esc(m.created)}</p></div>`).join('')}</section></div>`;
}
function formData(form) {
  const d = Object.fromEntries(new FormData(form));
  if (d.material_id) d.material_id = Number(d.material_id);
  if (d.length) d.length = Number(d.length);
  return d;
}
async function saveContent(force = false) {
  const input = document.querySelector('#content');
  const draft = drafts.get(selected);
  const content = input?.value ?? draft?.content;
  if (content === undefined) return;
  if (!force && !draft && content === (detail.versions[0]?.content || '')) return;
  await api('/tasks/' + selected + '/save', { content, base_version: draft?.base_version ?? detail.versions[0]?.id ?? null });
  drafts.delete(selected);
  detail = await api('/tasks/' + selected);
}
function download(content, filename) {
  const a = document.createElement('a');
  const url = URL.createObjectURL(new Blob([content], { type: 'text/html;charset=utf-8' }));
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
function bind() {
  const on = (id, fn) => {
    const x = document.getElementById(id);
    if (x) x.onclick = () => perform(x, fn);
  };
  document.querySelectorAll('[data-page]').forEach(b => b.onclick = () => perform(b, async () => {
    clearInterval(timer); page = b.dataset.page; await refresh();
  }));
  document.querySelectorAll('[data-task]').forEach(b => b.onclick = () => perform(b, async () => {
    selected = Number(b.dataset.task); tab = 'copy'; await refresh();
  }));
  document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => { tab = b.dataset.tab; render(); });
  on('logout', async () => { await api('/logout', {}); login(); });
  on('refresh', refresh);
  on('new', async () => { clearInterval(timer); selected = null; detail = null; render(); });
  for (const [id, path] of [['create', '/tasks'], ['update', '/tasks/' + selected + '/update'], ['material', '/materials']]) {
    const f = document.getElementById(id);
    if (!f) continue;
    const key = id === 'update' ? 'update-' + selected : id;
    f.oninput = f.onchange = () => formDrafts.set(key, formData(f));
    f.onsubmit = e => {
      e.preventDefault();
      return perform(f.querySelector('button'), async () => {
        const j = await api(path, formData(f));
        formDrafts.delete(key);
        if (id === 'create') { selected = j.id; tab = 'copy'; }
        await refresh(); toast('已保存');
      });
    };
  }
  const content = document.querySelector('#content');
  if (content) content.oninput = () => drafts.set(selected, { content: content.value, base_version: drafts.get(selected)?.base_version ?? detail.versions[0]?.id ?? null });
  const comment = document.querySelector('#comment');
  if (comment) comment.oninput = () => formDrafts.set('review-' + selected, comment.value);
  on('run', async () => {
    const mode = document.querySelector('#mode').value;
    if (mode === 'real' && !state.key_configured) {
      page = 'settings'; await refresh(); throw Error('请先保存模型配置并测试连接。');
    }
    if (drafts.has(selected)) await saveContent();
    const changes = formDrafts.get('update-' + selected);
    if (changes) { await api('/tasks/' + selected + '/update', changes); formDrafts.delete('update-' + selected); }
    await api('/tasks/' + selected + '/run', { mode }); tab = 'logs'; await refresh();
  });
  on('save', async () => { await saveContent(true); await refresh(); toast('已保存新版本'); });
  on('submit', async () => {
    await saveContent();
    await api('/tasks/' + selected + '/submit', {});
    tab = 'review'; await refresh(); toast('已提交，请使用 reviewer 账号审核');
  });
  for (const action of ['approve', 'return']) on(action, async () => {
    await api('/tasks/' + selected + '/' + action, { comment: document.querySelector('#comment').value });
    formDrafts.delete('review-' + selected); await refresh(); toast(action === 'approve' ? '审核通过' : '已退回修改');
  });
  const file = document.querySelector('#file');
  if (file) file.onchange = async () => {
    try {
      const f = file.files[0]; if (!f) return;
      if (f.size > 80000) throw Error('文件请控制在80KB以内');
      if (!/\.(txt|md)$/i.test(f.name)) throw Error('仅支持 TXT 或 Markdown 文件');
      document.querySelector('#material-content').value = await f.text();
      const form = document.querySelector('#material');
      if (!form.elements.title.value) form.elements.title.value = f.name.replace(/\.(txt|md)$/i, '');
      formDrafts.set('material', formData(form)); toast('文件已读入，请点击保存资料');
    } catch (e) { toast(e.message); }
  };
  on('export', async () => {
    if (drafts.has(selected)) await saveContent();
    const result = await api('/tasks/' + selected + '/export');
    download(result.content, result.filename); toast('图文已导出');
  });
  const settings = document.querySelector('#model-settings');
  if (settings) {
    document.querySelector('#provider').onchange = e => {
      document.querySelector('#model-name').value = e.target.value === 'openai' ? 'gpt-4o-mini' : 'deepseek-chat';
    };
    const saveModel = async (test) => {
      const data = formData(settings), old = state.model_config;
      const useExisting = test && !data.api_key.trim() && old.configured && data.provider === old.provider && data.model === old.model;
      if (!useExisting) await api('/settings/model', data);
      // 立即清空密码框，之后的网络诊断与刷新均不携带明文密钥。
      settings.elements.api_key.value = '';
      if (test) {
        document.querySelector('#connection-result').textContent = '已保存，正在请求模型验证连接（最多20秒）…';
        try {
          const result = await api('/settings/model/test', {});
          await refresh(); document.querySelector('#connection-result').textContent = result.message; toast('真实连接测试成功');
        } catch (e) {
          await refresh(); document.querySelector('#connection-result').textContent = '配置已保存；连接测试失败：' + e.message; throw e;
        }
      } else { await refresh(); toast('配置已保存，实际生效来源见右侧'); }
    };
    settings.onsubmit = e => { e.preventDefault(); return perform(settings.querySelector('button[type="submit"]'), () => saveModel(false)); };
    on('test-model', () => saveModel(true));
  }
}
async function boot() {
  try { await refresh(); }
  catch (e) {
    if (!state && !document.querySelector('#login')) {
      app.innerHTML = `<div class="login card"><h2>工作台暂时无法加载</h2><p>${esc(e.message)}</p><button id="retry">重新连接</button></div>`;
      document.querySelector('#retry').onclick = boot;
    } else if (state) toast(e.message);
  }
}
boot();
