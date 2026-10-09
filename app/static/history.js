/* Daily model comparisons use population Z-scores within the selected city/event/year. */
function buildHistoryScores(observations, city, event, year, model) {
  const models = ['GFS', 'EC', 'SUNSETHUE'];
  const days = new Map();
  observations.forEach((item) => {
    if (item.city !== city || item.event !== event || !String(item.event_date).startsWith(`${year}-`) ||
        !models.includes(item.model) || typeof item.quality !== 'number' || !Number.isFinite(item.quality)) return;
    if (!days.has(item.event_date)) days.set(item.event_date, {});
    days.get(item.event_date)[item.model] = item;
  });
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
    const value = model === 'combined' ? Object.values(zscores).reduce((sum, z) => sum + z, 0) : (results[model]?.quality ?? null);
    return {date, results, zscores, complete, value};
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
  const names = {GFS: 'GFS', EC: 'EC', SUNSETHUE: 'Sunsethue'};
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
    for (const name of ['GFS', 'EC', 'SUNSETHUE']) {
      const result = day.results[name];
      const text = result ? (result.quality_text || (name === 'SUNSETHUE' ? `${(result.quality * 100).toFixed(0)} 分` : result.quality.toFixed(3))) : '无记录';
      content += `<div class="history-model-row">${names[name]}：${escape(text)}${result ? ` · Z=${day.zscores[name].toFixed(2)}` : ''}</div>`;
    }
    if (model.value === 'combined') content += `<div>Z-score 加和：${day.value.toFixed(2)} · ${Object.keys(day.zscores).length}/3 个模型${day.complete ? '' : '（模型不齐）'}</div>`;
    return content;
  }
  function draw() {
    const {scores, stats} = buildHistoryScores(observations, city.value, event.value, year.value, model.value);
    current = new Map(scores.map(d => [d.date, d]));
    const combined = model.value === 'combined';
    const valued = scores.filter(d => d.value !== null);
    summary.textContent = `${city.value} · ${year.value} 年 · ${scores.length} 天有记录 · ${combined ? scores.filter(d => d.complete).length + ' 天三模型齐全' : valued.length + ' 天有 ' + names[model.value] + ' 评分'}`;
    document.getElementById('history-method').textContent = combined
      ? `各模型用所选地点、类型、年份的有效历史计算 Z=(评分−均值)/标准差，再将当天有记录模型的 Z 相加。GFS ${stats.GFS.n} 条、EC ${stats.EC.n} 条、Sunsethue ${stats.SUNSETHUE.n} 条。模型不齐用虚线边框标记，参与模型数不同的日期不宜直接比较；标准差为零时 Z=0。综合值表示相对强弱，没有固定的“小烧 / 大烧”等级。`
      : model.value === 'SUNSETHUE' ? 'Sunsethue 采用自己的质量等级：0–20 差、20–40 一般、40–60 好、60–80 很好、80–100 极佳。' : '颜色按数据源返回的预报等级：不烧 → 微烧 → 小烧 → 中烧 → 大烧 → 超烧；混合等级按其中较高等级显示，详细文字保留在日期详情。';
    document.getElementById('history-scale').textContent = combined ? '综合颜色：相对低 → 相对高' : model.value === 'SUNSETHUE' ? '等级颜色：差 → 极佳' : '等级颜色：不烧 → 超烧';
    detail.textContent = '点击日期查看各模型评分和等级。';
    const values = valued.map(d => d.value);
    const min = combined ? Math.min(0, ...values) : 0;
    const max = combined ? Math.max(0, ...values) : model.value === 'SUNSETHUE' ? 1 : Math.max(1, ...values);
    const data = valued.map(d => ({value:[d.date,d.value], ...(combined ? (d.complete ? {} : {itemStyle:{borderColor:'#8d8178',borderWidth:1,borderType:'dashed'}}) : {itemStyle:{color: colors[grade(d.results[model.value])] || '#c5bbb1'}})}));
    const partial = scores.filter(d => d.value === null).map(d => ({value:[d.date,0],itemStyle:{color:'#c5bbb1',borderColor:'#8d8178',borderWidth:1,borderType:'dashed'}}));
    chart.setOption({
      animation:false,
      tooltip:{confine:true, backgroundColor:'#fffdfa', borderColor:'#e0d5c9', textStyle:{color:'#302a27',fontSize:12}, formatter: p => describe(p.value[0])},
      visualMap: combined ? {show:true, min:min===max ? min-1 : min, max:min===max ? max+1 : max, dimension:1, seriesIndex:0, calculable:false, orient:'horizontal', left:'center',bottom:3,itemWidth:12,itemHeight:170,precision:2,text:['高','低'],inRange:{color:['#d4dce3','#ece7dd','#e4ac61','#bd5a32','#853347']}} : {show:false},
      calendar:{range:year.value,top:43,left:43,right:18,bottom:52,cellSize:['auto',19],orient:'horizontal',splitLine:{lineStyle:{color:'#ddd6ce',width:1}},itemStyle:{color:'#f0ede8',borderColor:'#fffdfa',borderWidth:3},yearLabel:{show:false},dayLabel:{firstDay:1,nameMap:['日','一','二','三','四','五','六'],color:'#81756b'},monthLabel:{nameMap:'cn',color:'#756b65'}},
      series:[{type:'heatmap',coordinateSystem:'calendar',data,emphasis:{itemStyle:{borderColor:'#302a27',borderWidth:2}}},{type:'heatmap',coordinateSystem:'calendar',data:partial,emphasis:{itemStyle:{borderColor:'#302a27',borderWidth:2}}}],
    },true);
    chart.off('click');chart.on('click',p => { if(p.value) detail.innerHTML=describe(p.value[0]); });
  }
  [city,event,year,model].forEach(input => input.addEventListener('change',draw));
  new ResizeObserver(() => chart.resize()).observe(document.getElementById('history-chart'));
  draw();
})();
