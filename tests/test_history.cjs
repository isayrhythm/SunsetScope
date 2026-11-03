const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../app/static/history.js'), 'utf8');
const context = vm.createContext({document: {getElementById: () => null}});
vm.runInContext(source, context);
const build = context.buildHistoryScores;
const city = '海南省-三亚';
const glow = {city, event: 'set', event_date: '2026-11-03', model: 'GLOW_SUNSET',
  quality: 67, probability: 0, status: 'no_opportunity', collected_at: '2026-11-03 16:50'};

test('original population Z-scores, partial models, zero and filters are unchanged', () => {
  const item = (date, model, quality) => ({city: '三亚', event: 'set', event_date: date, model, quality});
  const observations = [
    ...['GFS', 'EC', 'SUNSETHUE'].map(model => item('2026-09-01', model, 0)),
    ...['GFS', 'EC', 'SUNSETHUE'].map(model => item('2026-09-02', model, 1)),
    item('2026-09-03', 'GFS', 0.5), item('2025-09-01', 'GFS', 99),
    {...item('2026-09-04', 'EC', 99), city: '武汉'},
  ];
  const result = build(observations, '三亚', 'set', '2026', 'combined');
  assert.equal(result.scores.length, 3);
  assert.equal(result.stats.GFS.n, 3);
  assert.ok(Math.abs(result.scores[0].value - (-Math.sqrt(1.5) - 2)) < 1e-10);
  assert.ok(Math.abs(result.scores[1].value - (Math.sqrt(1.5) + 2)) < 1e-10);
  assert.equal(result.scores[2].value, 0);
  assert.equal(result.scores[2].complete, false);
  const constant = build([item('2026-09-01', 'GFS', 0)], '三亚', 'set', '2026', 'GFS');
  assert.equal(constant.scores[0].zscores.GFS, 0);
  assert.equal(constant.scores[0].value, 0);
  assert.equal(build(observations, '三亚', 'rise', '2026', 'GFS').scores.length, 0);
});

test('Glow metrics are independent, unscaled, and zero probability is retained', () => {
  assert.equal(build([glow], city, 'set', '2026', 'GLOW_QUALITY').scores[0].value, 67);
  assert.equal(build([glow], city, 'set', '2026', 'GLOW_PROBABILITY').scores[0].value, 0);
  assert.equal(Object.keys(build([glow], city, 'set', '2026', 'GLOW_QUALITY').stats).length, 0);
});

test('Glow potential adds a fourth standardized contribution, not its raw value or probability', () => {
  const original = ['GFS', 'EC', 'SUNSETHUE'].map((model, index) => ({...glow, model, quality: index / 10}));
  const before = build(original, city, 'set', '2026', 'combined');
  const input = [...original, {...glow, quality: 50}, {...glow, quality: 90, event_date: '2026-11-04'}];
  const after = build(input, city, 'set', '2026', 'combined');
  assert.equal(before.scores[0].value, 0);
  assert.equal(before.scores[0].complete, false);
  assert.equal(after.scores.length, 2);
  assert.equal(after.scores[0].value, -1);
  assert.equal(after.scores[1].value, 1);
  assert.equal(after.scores[0].zscores.GLOW_SUNSET, -1);
  assert.equal(Object.keys(after.scores[0].zscores).length, 4);
  assert.equal(after.stats.GLOW_SUNSET.n, 2);
  assert.equal(after.scores[0].complete, true);
  assert.equal(after.scores[1].complete, false);
  const changedProbability = build(input.map(item => ({...item, probability: 100})), city, 'set', '2026', 'combined');
  assert.equal(after.scores[0].value, changedProbability.scores[0].value);
  assert.equal(after.scores[1].value, changedProbability.scores[1].value);
  assert.equal(after.stats.GFS.n, before.stats.GFS.n);
});

test('one-day Glow sample contributes zero but is included and counted', () => {
  const result = build([glow], city, 'set', '2026', 'combined');
  assert.equal(result.scores[0].zscores.GLOW_SUNSET, 0);
  assert.equal(result.scores[0].value, 0);
  assert.equal(result.stats.GLOW_SUNSET.n, 1);
  assert.equal(result.scores[0].results.GLOW_SUNSET.quality, 67);
  assert.equal(result.scores[0].expectedModels.length, 4);
});

test('missing or stale Glow does not add zero samples or resurrect earlier scores', () => {
  const original = {city, event: 'set', event_date: '2026-11-03', model: 'GFS', quality: 0.3};
  const later = {...glow, status: 'unavailable', collected_at: '2026-11-03 17:50'};
  const result = build([original, later, glow], city, 'set', '2026', 'combined');
  assert.equal(result.stats.GLOW_SUNSET.n, 0);
  assert.equal(Object.keys(result.scores[0].zscores).length, 1);
  assert.equal(result.scores[0].complete, false);
  const unavailableOnly = build([later], city, 'set', '2026', 'combined');
  assert.equal(unavailableOnly.scores[0].value, null);
});

test('sunrise remains a three-model sum without any Glow contribution', () => {
  const input = ['GFS', 'EC', 'SUNSETHUE'].map(model => ({...glow, model, event: 'rise', quality: 0.5}));
  const result = build([...input, {...glow, event: 'rise'}], city, 'rise', '2026', 'combined');
  assert.equal(result.scores[0].expectedModels.length, 3);
  assert.equal(result.scores[0].complete, true);
  assert.equal(Object.hasOwn(result.stats, 'GLOW_SUNSET'), false);
});

test('missing or invalid Glow data stays null and is not rendered as zero', () => {
  for (const value of [null, undefined, NaN, Infinity, '60', -1, 101, true]) {
    const result = build([{...glow, probability: value}], city, 'set', '2026', 'GLOW_PROBABILITY');
    assert.equal(result.scores[0].value, null);
  }
  assert.equal(build([{...glow, status: 'unavailable'}], city, 'set', '2026', 'GLOW_QUALITY').scores[0].value, null);
});

test('latest daily snapshot wins, including a later unavailable record', () => {
  const later = {...glow, status: 'unavailable', collected_at: '2026-11-03 17:50'};
  assert.equal(build([later, glow], city, 'set', '2026', 'GLOW_QUALITY').scores[0].value, null);
});

test('Glow filters city, year and event without inventing sunrise or other locations', () => {
  assert.equal(build([glow], city, 'rise', '2026', 'GLOW_QUALITY').scores.length, 0);
  assert.equal(build([glow], '武汉', 'set', '2026', 'GLOW_QUALITY').scores.length, 0);
  assert.equal(build([glow], city, 'set', '2025', 'GLOW_QUALITY').scores.length, 0);
});

test('calendar default and tooltip show all four models, and individual Glow view still works', () => {
  const input = ['GFS', 'EC', 'SUNSETHUE'].map((model, index) => ({...glow, model, quality: index / 10}));
  const controls = {};
  for (const id of ['history-city', 'history-event', 'history-year', 'history-model']) {
    controls[id] = {value: '', add() {}, addEventListener(name, callback) { this[name] = callback; },
      querySelector() { return {}; }};
  }
  controls['history-city'].value = city;
  controls['history-event'].value = 'set';
  controls['history-year'].value = '2026';
  controls['history-model'].value = 'combined';
  for (const id of ['history-summary', 'history-detail', 'history-chart', 'history-scale', 'history-partial-label']) controls[id] = {};
  controls['history-data'] = {textContent: JSON.stringify([...input, glow])};
  let options;
  vm.runInContext(source, vm.createContext({
    document: {getElementById: id => controls[id]},
    Option: class {}, ResizeObserver: class {observe() {}},
    echarts: {init: () => ({setOption(value) { options = value; }, off() {}, on() {}, resize() {}})},
  }));
  const tooltip = options.tooltip.formatter({value: [glow.event_date, 0]});
  for (const model of ['GFS', 'EC', 'Sunsethue', 'Glow Sunset']) assert.ok(tooltip.includes(model), model);
  assert.ok(tooltip.includes('4/4 个模型'));
  assert.ok(tooltip.includes('Glow Sunset：67 分 · Z=0.00'));
  assert.ok(tooltip.includes('融合评分：'));
  assert.ok(!tooltip.includes('出现概率'));
  assert.ok(!tooltip.includes('预测更新'));
  assert.ok(!tooltip.includes('最近采集'));
  assert.ok(!tooltip.includes('不计入合成'));
  assert.ok(!tooltip.includes('模型不齐'));
  assert.equal((tooltip.match(/<div/g) || []).length, 5);
  assert.ok(controls['history-summary'].textContent.includes('四模型齐全'));
  assert.ok(controls['history-summary'].textContent.includes('仅有一天记录'));
  controls['history-model'].value = 'GLOW_PROBABILITY';
  controls['history-model'].change();
  assert.equal(options.series[0].data[0].value[1], 0);
  const individual = options.tooltip.formatter({value: [glow.event_date, 0]});
  assert.ok(individual.includes('出现概率：0%'));
});
