const state = {
  data: null,
  selectedDate: null,
  query: ""
};

const els = {
  generatedAt: document.getElementById('generatedAt'),
  argumentCount: document.getElementById('argumentCount'),
  themeCount: document.getElementById('themeCount'),
  reportDate: document.getElementById('reportDate'),
  searchBox: document.getElementById('searchBox'),
  reportMeta: document.getElementById('reportMeta'),
  dailySummary: document.getElementById('dailySummary'),
  reportList: document.getElementById('reportList')
};

async function loadData() {
  const resp = await fetch('./data/index.json', { cache: 'no-store' });
  state.data = await resp.json();
  renderDateOptions();
  render();
}

function renderDateOptions() {
  const option = document.createElement('option');
  option.value = 'today';
  option.textContent = '最新報告';
  els.reportDate.appendChild(option);
  els.reportDate.value = 'today';
  state.selectedDate = 'today';
}

function filterReports() {
  const q = state.query.trim().toLowerCase();
  const reports = state.data?.reports || [];
  if (!q) return reports;
  return reports.filter(r =>
    [r.argument_id, r.theme, r.core, ...(r.supporting_points || []), ...(r.sources || []).map(s => s.title || '')]
      .join(' ')
      .toLowerCase()
      .includes(q)
  );
}

function render() {
  if (!state.data) return;
  els.generatedAt.textContent = state.data.generated_at || '-';
  els.argumentCount.textContent = state.data.mention_count ?? '-';
  els.themeCount.textContent = state.data.theme_count ?? '-';
  els.reportMeta.textContent = `共 ${state.data.reports?.length || 0} 筆論點`;

  els.dailySummary.innerHTML = `
    <p class="muted">這是每日規則式整理結果。可用搜尋直接找主題、論點或來源標題。</p>
    <p>當前資料庫中共有 <strong>${state.data.mention_count || 0}</strong> 則整理內容，涵蓋 <strong>${state.data.theme_count || 0}</strong> 個主題。</p>
    <p class="muted">更新時間以 pipeline 完成時間為準，會隨每日排程自動改寫。</p>
  `;

  const reports = filterReports();
  els.reportList.innerHTML = reports.map(report => `
    <article class="card">
      <div class="tag">${report.theme} · ${report.argument_id}</div>
      <h3>${report.core}</h3>
      <p class="muted">出現次數 ${report.count} 次</p>
      <p>${(report.supporting_points || []).map(x => `• ${x}`).join('<br>') || '<span class="muted">尚無補充句</span>'}</p>
      <div class="sources">
        ${(report.sources || []).map(src => `<a href="${src.url}" target="_blank" rel="noreferrer">${src.title || src.url}</a>`).join('')}
      </div>
    </article>
  `).join('') || '<div class="card"><p class="muted">沒有符合條件的報告。</p></div>';
}

els.searchBox.addEventListener('input', e => {
  state.query = e.target.value;
  render();
});

loadData();
