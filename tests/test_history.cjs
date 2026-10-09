const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({document: {getElementById: () => null}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/history.js'), 'utf8'), context);
const item = (date, model, quality) => ({city: '三亚', event: 'set', event_date: date, model, quality});
const observations = [
  ...['GFS', 'EC', 'SUNSETHUE'].map(model => item('2026-09-01', model, 0)),
  ...['GFS', 'EC', 'SUNSETHUE'].map(model => item('2026-09-02', model, 1)),
  item('2026-09-03', 'GFS', 0.5),
  item('2025-09-01', 'GFS', 99),
  {...item('2026-09-04', 'EC', 99), city: '武汉'},
];
const result = context.buildHistoryScores(observations, '三亚', 'set', '2026', 'combined');
assert.equal(result.scores.length, 3);
assert.equal(result.stats.GFS.n, 3);
assert.ok(Math.abs(result.scores[0].value - (-Math.sqrt(1.5) - 2)) < 1e-10);
assert.ok(Math.abs(result.scores[1].value - (Math.sqrt(1.5) + 2)) < 1e-10);
assert.equal(result.scores[2].value, 0);
assert.equal(result.scores[2].complete, false);
const constant = context.buildHistoryScores([item('2026-09-01','GFS',0)], '三亚','set','2026','GFS');
assert.equal(constant.scores[0].zscores.GFS, 0);
assert.equal(constant.scores[0].value, 0);
assert.equal(context.buildHistoryScores(observations,'三亚','rise','2026','GFS').scores.length, 0);
console.log('History score tests passed');
