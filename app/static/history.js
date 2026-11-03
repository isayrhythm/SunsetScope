/* Daily model comparisons use population Z-scores within the selected city/event/year. */
function buildHistoryScores(observations, city, event, year, model) {
  if (model === 'GLOW_QUALITY' || model === 'GLOW_PROBABILITY') {
    const field = model === 'GLOW_QUALITY' ? 'quality' : 'probability';
    const daily = new Map();
    observations.forEach(item => {
      if (item.model !== 'GLOW_SUNSET' || item.city !== city || item.event !== event ||
          !String(item.event_date).startsWith(`${year}-`)) return;
      if (!daily.has(item.event_date) || (item.collected_at || '') >= (daily.get(item.event_date).collected_at || '')) {
        daily.set(item.event_date, item);
      }
    });
    const scores = [...daily].sort(([a], [b]) => a.localeCompare(b)).map(([date, item]) => {
      const valid = ['evaluated', 'no_opportunity'].includes(item.status) &&
        typeof item[field] === 'number' && Number.isFinite(item[field]) && item[field] >= 0 && item[field] <= 100;
      return {date, results: {GLOW_SUNSET: item}, zscores: {}, complete: valid, value: valid ? item[field] : null};
    });
    return {scores, stats: {}};
  }
  const models = event === 'set' ? ['GFS', 'EC', 'SUNSETHUE', 'GLOW_SUNSET'] : ['GFS', 'EC', 'SUNSETHUE'];
  const days = new Map();
  observations.forEach((item) => {
    if (item.city !== city || item.event !== event || !String(item.event_date).startsWith(`${year}-`) ||
        !['GFS', 'EC', 'SUNSETHUE'].includes(item.model) || typeof item.quality !== 'number' || !Number.isFinite(item.quality)) return;
    if (!days.has(item.event_date)) days.set(item.event_date, {});
    days.get(item.event_date)[item.model] = item;
  });
  if (event === 'set') {
    // Reuse the validated, latest-per-day potential only; probability is not another vote.
    buildHistoryScores(observations, city, event, year, 'GLOW_QUALITY').scores.forEach(day => {
      if (!days.has(day.date)) days.set(day.date, {});
      if (day.value !== null) days.get(day.date).GLOW_SUNSET = day.results.GLOW_SUNSET;
    });
  }
  const stats = {};
  models.forEach((name) => {
    const values = [...days.values()].filter(d => d[name]).map(d => d[name].quality);
    const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
    const sd = values.length ? Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length) : 0;
    stats[name] = {n: values.length, mean, sd};
  });
  const scores = [...days].sort(([a], [b]) => a.localeCompare(b)).map(([date, results]) => {
    const zscores = {};
    models.forEach(name => {
      if (results[name]) zscores[name] = stats[name].sd > 0 ? (results[name].quality - stats[name].mean) / stats[name].sd : 0;
    });
    const complete = models.every(name => results[name]);
    const value = model === 'combined' ? (Object.keys(zscores).length ? Object.values(zscores).reduce((sum, z) => sum + z, 0) : null) : (results[model]?.quality ?? null);
    return {date, results, zscores, complete, value, expectedModels: models};
  });
  return {scores, stats};
}

(function () {
  const root = document.getElementById('history-data');
  if (!root) return;
  const observations = JSON.parse(root.textContent);
  const city = document.getElementById('history-city');
  const event = document.getElementById('history-event');
  const year = document.getElementById('history-year');
  const model = document.getElementById('history-model');
  const summary = document.getElementById('history-summary');
  const detail = document.getElementById('history-detail');
  const names = {GFS: 'GFS', EC: 'EC', SUNSETHUE: 'Sunsethue', GLOW_SUNSET: 'Glow Sunset', GLOW_QUALITY: 'Glow Sunset 观赏潜力', GLOW_PROBABILITY: 'Glow Sunset 出现概率'};
  const cities = [...new Set(observations.map(d => d.city).filter(Boolean))].sort();
  const years = [...new Set(observations.map(d => String(d.event_date).slice(0, 4)).filter(v => /^\d{4}$/.test(v)))].sort().reverse();
  cities.forEach(name => city.add(new Option(name, name)));
  years.forEach(value => year.add(new Option(value, value)));
  if (!cities.length || !years.length) { summary.textContent = '还没有历史预报记录。'; return; }
  if (typeof echarts === 'undefined') { summary.textContent = '图表加载失败，请刷新页面。'; return; }
  const chart = echarts.init(document.getElementById('history-chart'));
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const colors = ['#f0ede8', '#e5cba2', '#d9a45b', '#cc762d', '#b74b28', '#853347'];
  function grade(item) {
    if (item.model === 'SUNSETHUE') return item.quality < .2 ? 0 : item.quality < .4 ? 1 : item.quality < .6 ? 3 : item.quality < .8 ? 4 : 5;
    const text = item.quality_text || '';
    for (const [label, value] of [['超烧',5], ['大烧',4], ['中烧',3], ['小烧',2], ['微烧',1], ['不烧',0]]) {
      if (text.includes(label)) return value;
    }
    return null;
  }
  let current = new Map();
  function describe(date) {
    const day = current.get(date);
    let content = `<strong>${escape(date)} · ${escape(city.value)} · ${event.value === 'set' ? '晚霞' : '朝霞'}</strong>`;
    if (!day) return content + '无历史记录';
    if (model.value === 'GLOW_QUALITY' || model.value === 'GLOW_PROBABILITY') {
      const result = day.results.GLOW_SUNSET;
      const metric = (value, unit) => typeof value === 'number' && Number.isFinite(value) ? `${value}${unit}` : '暂无有效预测';
      content += `<div>Glow Sunset · ${escape(result.spot_name)}</div>`;
      content += `<div>观赏潜力：${escape(metric(result.quality, '/100'))} · 出现概率：${escape(metric(result.probability, '%'))}</div>`;
      content += `<div>采集时状态：${escape(result.status_label || result.status)} · ${escape(result.reason || '')}</div>`;
      content += `<div>预测更新：${escape(result.generated_at || '—')} · 有效至：${escape(result.valid_until || '—')}</div>`;
      content += `<div>最近采集：${escape(result.collected_at || '—')}（北京时间）</div>`;
      return content + '<div>历史预测快照，不代表实况；仅观赏潜力参与晚霞四模型合成，概率不参与。</div>';
    }
    for (const name of day.expectedModels) {
      const result = day.results[name];
      const text = result ? (name === 'GLOW_SUNSET' ? `${result.quality} 分` : result.quality_text || (name === 'SUNSETHUE' ? `${(result.quality * 100).toFixed(0)} 分` : result.quality.toFixed(3))) : '无记录';
      content += `<div class="history-model-row">${names[name]}：${escape(text)}${result ? ` · Z=${day.zscores[name].toFixed(2)}` : ''}</div>`;
    }
    if (model.value === 'combined') content += `<div>融合评分：${day.value === null ? '暂无数据' : day.value.toFixed(2)} · ${Object.keys(day.zscores).length}/${day.expectedModels.length} 个模型</div>`;
    return content;
  }
  function draw() {
    const glow = model.value === 'GLOW_QUALITY' || model.value === 'GLOW_PROBABILITY';
    event.querySelector('option[value="rise"]').disabled = glow;
    if (glow) event.value = 'set';
    const {scores, stats} = buildHistoryScores(observations, city.value, event.value, year.value, model.value);
    current = new Map(scores.map(d => [d.date, d]));
    const combined = model.value === 'combined';
    const modelCount = event.value === 'set' ? 4 : 3;
    model.querySelector('option[value="combined"]').textContent = `${modelCount === 4 ? '四' : '三'}模型融合`;
    const valued = scores.filter(d => d.value !== null);
    const glowStats = stats.GLOW_SUNSET;
    const sampleNote = combined && glowStats?.n > 0 && glowStats.sd === 0 ? ` · Glow ${glowStats.n === 1 ? '仅有一天记录' : '历史评分无波动'}，Z 暂为 0` : '';
    summary.textContent = `${city.value} · ${year.value} 年 · ${scores.length} 天有记录 · ${combined ? scores.filter(d => d.complete).length + ` 天${modelCount === 4 ? '四' : '三'}模型齐全` : valued.length + ' 天有 ' + names[model.value] + ' 评分'}${glow ? ' · 仅晚霞，每日最后一次采集；潜力参与四模型合成，概率不参与' : ''}${sampleNote}`;
    document.getElementById('history-scale').textContent = combined ? '综合颜色：相对低 → 相对高' : glow ? (model.value === 'GLOW_QUALITY' ? '观赏潜力：0 → 100 分' : '出现概率：0 → 100%') : model.value === 'SUNSETHUE' ? '等级颜色：差 → 极佳' : '等级颜色：不烧 → 超烧';
    document.getElementById('history-partial-label').textContent = glow ? '暂无有效预测' : '模型不齐';
    detail.textContent = '';
    detail.hidden = true;
    const values = valued.map(d => d.value);
    const min = combined ? Math.min(0, ...values) : 0;
    const max = combined ? Math.max(0, ...values) : glow ? 100 : model.value === 'SUNSETHUE' ? 1 : Math.max(1, ...values);
    const data = valued.map(d => ({value:[d.date,d.value], ...(combined ? (d.complete ? {} : {itemStyle:{borderColor:'#8d8178',borderWidth:1,borderType:'dashed'}}) : {itemStyle:{color: colors[glow ? Math.min(5, Math.floor(d.value / 20)) : grade(d.results[model.value])] || '#c5bbb1'}})}));
    const partial = scores.filter(d => d.value === null).map(d => ({value:[d.date,0],itemStyle:{color:'#c5bbb1',borderColor:'#8d8178',borderWidth:1,borderType:'dashed'}}));
    chart.setOption({
      animation:false,
      tooltip:{confine:true, backgroundColor:'#fffdfa', borderColor:'#e0d5c9', textStyle:{color:'#302a27',fontSize:12}, formatter: p => describe(p.value[0])},
      visualMap: combined ? {show:true, min:min===max ? min-1 : min, max:min===max ? max+1 : max, dimension:1, seriesIndex:0, calculable:false, orient:'horizontal', left:'center',bottom:3,itemWidth:12,itemHeight:170,precision:2,text:['高','低'],inRange:{color:['#d4dce3','#ece7dd','#e4ac61','#bd5a32','#853347']}} : {show:false},
      calendar:{range:year.value,top:43,left:43,right:18,bottom:52,cellSize:['auto',19],orient:'horizontal',splitLine:{lineStyle:{color:'#ddd6ce',width:1}},itemStyle:{color:'#f0ede8',borderColor:'#fffdfa',borderWidth:3},yearLabel:{show:false},dayLabel:{firstDay:1,nameMap:['日','一','二','三','四','五','六'],color:'#81756b'},monthLabel:{nameMap:'cn',color:'#756b65'}},
      series:[{type:'heatmap',coordinateSystem:'calendar',data,emphasis:{itemStyle:{borderColor:'#302a27',borderWidth:2}}},{type:'heatmap',coordinateSystem:'calendar',data:partial,emphasis:{itemStyle:{borderColor:'#302a27',borderWidth:2}}}],
    },true);
    chart.off('click');chart.on('click',p => { if(p.value) { detail.innerHTML=describe(p.value[0]); detail.hidden=false; } });
  }
  [city,event,year,model].forEach(input => input.addEventListener('change',draw));
  new ResizeObserver(() => chart.resize()).observe(document.getElementById('history-chart'));
  draw();
})();
