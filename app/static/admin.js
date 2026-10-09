const subscriptionTable = document.querySelector('.subscription-table');
if (subscriptionTable) {
  const collator = new Intl.Collator('zh-CN', {numeric: true, sensitivity: 'base'});
  const tbody = subscriptionTable.querySelector('tbody');
  const originalOrder = new Map([...tbody.rows].map((row, index) => [row, index]));
  let sortedColumn = null;
  let ascending = true;
  function valueFor(row, column) {
    const cell = row.cells[column];
    if (column === 0) return cell.querySelector('strong').textContent.trim();
    if (column === 3) return Number(cell.textContent.trim());
    if (column === 4) {
      const text = cell.textContent.trim();
      return /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(text) ? text : '';
    }
    if (column === 6) return cell.querySelector('input').value.trim();
    return cell.textContent.trim().replace(/\s+/g, ' ');
  }
  subscriptionTable.querySelectorAll('.table-sort').forEach((button) => {
    button.addEventListener('click', () => {
      const column = Number(button.dataset.column);
      ascending = sortedColumn === column ? !ascending : true;
      sortedColumn = column;
      const rows = [...tbody.rows].sort((left, right) => {
        const a = valueFor(left, column), b = valueFor(right, column);
        // Keep missing reminder dates and empty notes at the bottom in both directions.
        if (a === '' && b !== '') return 1;
        if (b === '' && a !== '') return -1;
        const compared = column === 3 ? a - b : collator.compare(a, b);
        return compared ? compared * (ascending ? 1 : -1) : originalOrder.get(left) - originalOrder.get(right);
      });
      rows.forEach((row) => tbody.appendChild(row));
      subscriptionTable.querySelectorAll('.table-sort').forEach((other) => {
        const selected = other === button;
        other.closest('th').setAttribute('aria-sort', selected ? (ascending ? 'ascending' : 'descending') : 'none');
        other.querySelector('span').textContent = selected ? (ascending ? '↑' : '↓') : '↕';
      });
    });
  });
}

document.querySelectorAll('.subscription-note').forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    const feedback = form.querySelector('[role="status"]');
    button.disabled = true;
    feedback.textContent = '保存中…';
    try {
      const response = await fetch(`/admin/subscriptions/${encodeURIComponent(form.dataset.subscriptionId)}/note`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-SunsetScope-Admin': '1'},
        body: JSON.stringify({note: form.elements.note.value}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || '保存失败');
      feedback.textContent = result.message;
    } catch (error) {
      feedback.textContent = error.message || '保存失败，请重试';
    } finally {
      button.disabled = false;
    }
  });
});
