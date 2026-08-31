const form = document.getElementById("subscriptionForm");
const cityInput = document.getElementById("city");
const cityOptions = document.getElementById("cityOptions");
const threshold = document.getElementById("threshold");
const thresholdValue = document.getElementById("thresholdValue");
const thresholdLevel = document.getElementById("thresholdLevel");
const submitButton = document.getElementById("submitButton");
const formMessage = document.getElementById("formMessage");
const unsubscribeRequestForm = document.getElementById("unsubscribeRequestForm");
const unsubscribeEmail = document.getElementById("unsubscribeEmail");
const unsubscribeRequestButton = document.getElementById("unsubscribeRequestButton");
const unsubscribeMessage = document.getElementById("unsubscribeMessage");

function qualityLevel(value) {
  if (value <= 0) return "不烧";
  if (value <= 0.05) return "微微烧";
  if (value <= 0.2) return "小烧";
  if (value <= 0.4) return "小烧到中等烧";
  if (value <= 0.6) return "中等烧";
  if (value <= 0.8) return "中等烧到大烧";
  if (value <= 1.0) return "大烧";
  if (value <= 1.5) return "典型大烧";
  if (value <= 2.0) return "优质大烧";
  return "世纪大烧";
}

threshold.addEventListener("input", () => {
  thresholdValue.textContent = Number(threshold.value).toFixed(2);
  thresholdLevel.textContent = qualityLevel(Number(threshold.value));
});

let cityTimer;
cityInput.addEventListener("input", () => {
  clearTimeout(cityTimer);
  cityOptions.replaceChildren();
  const query = cityInput.value.trim();
  if (!query) return;
  cityTimer = setTimeout(async () => {
    try {
      const response = await fetch(`/api/cities?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      if (!response.ok) return;
      for (const city of data.cities || []) {
        const option = document.createElement("option");
        option.value = city;
        cityOptions.appendChild(option);
      }
    } catch (_) {
      // 提交时会显示明确的数据源错误。
    }
  }, 280);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.className = "form-message";
  formMessage.textContent = "";
  if (!form.reportValidity()) return;
  const data = new FormData(form);
  const models = data.getAll("models");
  if (models.length === 0) {
    formMessage.className = "form-message error";
    formMessage.textContent = "请至少选择一个预测模型";
    return;
  }
  submitButton.disabled = true;
  submitButton.textContent = "正在提交…";
  try {
    const response = await fetch("/api/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: data.get("email"),
        city: data.get("city"),
        event: data.get("event"),
        models,
        trigger_mode: data.get("trigger_mode"),
        threshold: Number(data.get("threshold")),
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "提交失败");
    formMessage.className = "form-message success";
    formMessage.textContent = result.message;
  } catch (error) {
    formMessage.className = "form-message error";
    formMessage.textContent = error.message || "网络错误，请稍后重试";
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "发送确认邮件";
  }
});

unsubscribeRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  unsubscribeMessage.className = "form-message";
  unsubscribeMessage.textContent = "";
  if (!unsubscribeRequestForm.reportValidity()) return;
  unsubscribeRequestButton.disabled = true;
  unsubscribeRequestButton.textContent = "正在发送…";
  try {
    const response = await fetch("/api/unsubscribe-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: unsubscribeEmail.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "提交失败");
    unsubscribeMessage.className = "form-message success";
    unsubscribeMessage.textContent = result.message;
  } catch (error) {
    unsubscribeMessage.className = "form-message error";
    unsubscribeMessage.textContent = error.message || "网络错误，请稍后重试";
  } finally {
    unsubscribeRequestButton.disabled = false;
    unsubscribeRequestButton.textContent = "发送退订邮件";
  }
});
