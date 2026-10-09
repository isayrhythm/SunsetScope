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
