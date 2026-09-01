const form = document.getElementById("subscriptionForm");
const cityInput = document.getElementById("city");
const cityOptions = document.getElementById("cityOptions");
const citySecondInput = document.getElementById("citySecond");
const citySecondOptions = document.getElementById("citySecondOptions");
const secondCityDetails = document.getElementById("secondCityDetails");
const threshold = document.getElementById("threshold");
const thresholdValue = document.getElementById("thresholdValue");
const thresholdLevel = document.getElementById("thresholdLevel");
const previewLevel = document.getElementById("previewLevel");
const previewValue = document.getElementById("previewValue");
const submitButton = document.getElementById("submitButton");
const formMessage = document.getElementById("formMessage");
const unsubscribeRequestForm = document.getElementById("unsubscribeRequestForm");
const unsubscribeEmail = document.getElementById("unsubscribeEmail");
const unsubscribeRequestButton = document.getElementById("unsubscribeRequestButton");
const unsubscribeMessage = document.getElementById("unsubscribeMessage");
const manageSubscription = document.getElementById("manageSubscription");
const captchaAnswer = document.getElementById("captchaAnswer");
const captchaImage = document.getElementById("captchaImage");
const captchaRefresh = document.getElementById("captchaRefresh");
const unsubscribeCaptchaAnswer = document.getElementById("unsubscribeCaptchaAnswer");
const unsubscribeCaptchaImage = document.getElementById("unsubscribeCaptchaImage");
const unsubscribeCaptchaRefresh = document.getElementById("unsubscribeCaptchaRefresh");
const triggerModeFieldset = document.getElementById("triggerModeFieldset");
const triggerAnyLabel = document.getElementById("triggerAnyLabel");
const triggerAllLabel = document.getElementById("triggerAllLabel");

let subscriptionCaptchaId = "";
let unsubscribeCaptchaId = "";

async function loadCaptcha(kind) {
  const isSubscription = kind === "subscription";
  const image = isSubscription ? captchaImage : unsubscribeCaptchaImage;
  const answer = isSubscription ? captchaAnswer : unsubscribeCaptchaAnswer;
  const refresh = isSubscription ? captchaRefresh : unsubscribeCaptchaRefresh;
  refresh.disabled = true;
  image.removeAttribute("src");
  image.alt = "验证码加载中";
  answer.value = "";
  if (isSubscription) subscriptionCaptchaId = "";
  else unsubscribeCaptchaId = "";
  try {
    const response = await fetch("/api/captcha", { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "验证码加载失败");
    image.src = result.image;
    image.alt = "验证码，点击更换";
    if (isSubscription) subscriptionCaptchaId = result.captcha_id;
    else unsubscribeCaptchaId = result.captcha_id;
  } catch (error) {
    image.alt = error.message || "验证码加载失败，点击重试";
  } finally {
    refresh.disabled = false;
  }
}

captchaRefresh.addEventListener("click", () => loadCaptcha("subscription"));
unsubscribeCaptchaRefresh.addEventListener("click", () => loadCaptcha("unsubscribe"));
manageSubscription.addEventListener("toggle", () => {
  if (manageSubscription.open && !unsubscribeCaptchaId) loadCaptcha("unsubscribe");
});
loadCaptcha("subscription");

function updateTriggerModeLabels() {
  const models = [...form.querySelectorAll('input[name="models"]:checked')].map((input) => input.value);
  triggerModeFieldset.hidden = models.length < 2;
  if (models.length < 2) return;
  triggerAnyLabel.textContent = `${models.join(" 或 ")} 达标`;
  triggerAllLabel.textContent = `${models.join(" 和 ")} 均达标`;
}

form.querySelectorAll('input[name="models"]').forEach((input) => {
  input.addEventListener("change", updateTriggerModeLabels);
});
updateTriggerModeLabels();

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

const skyStops = [
  { at: 0, top: "#52647b", mid: "#9ca6b3", bottom: "#d2c5bc", glow: "#d4a07d" },
  { at: 0.16, top: "#6e6687", mid: "#c08383", bottom: "#efad78", glow: "#f2a45d" },
  { at: 0.4, top: "#4b355f", mid: "#bc5369", bottom: "#ff8750", glow: "#ffc55f" },
  { at: 0.7, top: "#311c4d", mid: "#a72c60", bottom: "#ff6338", glow: "#ffd469" },
  { at: 1, top: "#180a2d", mid: "#751044", bottom: "#ff3d20", glow: "#ffe681" },
];

function hexToRgb(hex) {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function mixColor(from, to, amount) {
  const a = hexToRgb(from);
  const b = hexToRgb(to);
  const mixed = a.map((channel, index) => Math.round(channel + (b[index] - channel) * amount));
  return `rgb(${mixed.join(", ")})`;
}

function sceneColors(progress) {
  const upperIndex = skyStops.findIndex((stop) => stop.at >= progress);
  if (upperIndex <= 0) return skyStops[0];
  const upper = skyStops[upperIndex];
  const lower = skyStops[upperIndex - 1];
  const amount = (progress - lower.at) / (upper.at - lower.at);
  return {
    top: mixColor(lower.top, upper.top, amount),
    mid: mixColor(lower.mid, upper.mid, amount),
    bottom: mixColor(lower.bottom, upper.bottom, amount),
    glow: mixColor(lower.glow, upper.glow, amount),
  };
}

function updateThresholdScene() {
  const value = Number(threshold.value);
  const formatted = value.toFixed(2);
  const level = qualityLevel(value);
  const progress = Math.min(1, Math.max(0, value / 2.5));
  const colors = sceneColors(progress);
  thresholdValue.textContent = formatted;
  thresholdLevel.textContent = level;
  previewValue.textContent = formatted;
  previewLevel.textContent = level;
  document.documentElement.style.setProperty("--sky-top", colors.top);
  document.documentElement.style.setProperty("--sky-mid", colors.mid);
  document.documentElement.style.setProperty("--sky-bottom", colors.bottom);
  document.documentElement.style.setProperty("--glow", colors.glow);
  document.documentElement.style.setProperty("--glow-opacity", String(0.5 + progress * 0.5));
  document.documentElement.style.setProperty("--glow-blur", `${Math.round(40 + progress * 120)}px`);
  document.documentElement.style.setProperty("--scene-saturation", String(0.8 + progress));
  document.documentElement.style.setProperty("--cloud-opacity", String(0.16 + progress * 0.5));
  document.documentElement.style.setProperty("--cloud-saturation", String(0.5 + progress));
  document.documentElement.style.setProperty("--cloud-warmth", String(Math.round(progress * 100) + "%"));
  document.documentElement.style.setProperty("--card-alpha", String(0.9 - progress * 0.08));
  document.documentElement.style.setProperty("--card-shadow-size", `${Math.round(70 + progress * 35)}px`);
  document.documentElement.style.setProperty("--card-shadow-alpha", String(0.16 + progress * 0.12));
  document.documentElement.style.setProperty("--scene-progress", progress.toFixed(3));
}

threshold.addEventListener("input", updateThresholdScene);
updateThresholdScene();

const cityTimers = new WeakMap();
const cityRequestVersions = new WeakMap();

function bindCitySuggestions(input, options) {
  function clearOptions() {
    options.replaceChildren();
    options.hidden = true;
    input.setAttribute("aria-expanded", "false");
  }

  input.addEventListener("input", () => {
    clearTimeout(cityTimers.get(input));
    clearOptions();
    const query = input.value.trim();
    const version = (cityRequestVersions.get(input) || 0) + 1;
    cityRequestVersions.set(input, version);
    if (!query) return;
    cityTimers.set(input, setTimeout(async () => {
      try {
        const response = await fetch(`/api/cities?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        if (!response.ok || cityRequestVersions.get(input) !== version) return;
        for (const city of data.cities || []) {
          const option = document.createElement("button");
          option.type = "button";
          option.className = "city-suggestion";
          option.setAttribute("role", "option");
          option.textContent = city;
          option.addEventListener("pointerdown", (event) => event.preventDefault());
          option.addEventListener("click", () => {
            input.value = city;
            clearOptions();
            input.focus();
          });
          options.appendChild(option);
        }
        if (options.childElementCount) {
          options.hidden = false;
          input.setAttribute("aria-expanded", "true");
        }
      } catch (_) {
        // 提交时会显示明确的数据源错误。
      }
    }, 280));
  });
  input.addEventListener("blur", () => setTimeout(clearOptions, 160));
}

bindCitySuggestions(cityInput, cityOptions);
bindCitySuggestions(citySecondInput, citySecondOptions);
secondCityDetails.addEventListener("toggle", () => {
  if (secondCityDetails.open) {
    citySecondInput.focus();
    return;
  }
  citySecondInput.value = "";
  citySecondOptions.replaceChildren();
  citySecondOptions.hidden = true;
  cityRequestVersions.set(citySecondInput, (cityRequestVersions.get(citySecondInput) || 0) + 1);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.className = "form-message";
  formMessage.textContent = "";
  if (!form.reportValidity()) return;
  const data = new FormData(form);
  const models = data.getAll("models");
  const cities = [data.get("city"), data.get("city_second")]
    .map((city) => String(city || "").trim())
    .filter(Boolean);
  if (new Set(cities).size !== cities.length) {
    formMessage.className = "form-message error";
    formMessage.textContent = "两个订阅地点不能相同";
    return;
  }
  if (models.length === 0) {
    formMessage.className = "form-message error";
    formMessage.textContent = "请至少选择一个预测模型";
    return;
  }
  if (!subscriptionCaptchaId) {
    formMessage.className = "form-message error";
    formMessage.textContent = "验证码尚未加载，请点击图片重试";
    return;
  }
  submitButton.disabled = true;
  submitButton.classList.remove("sent");
  submitButton.textContent = "正在提交…";
  let submittedSuccessfully = false;
  try {
    const response = await fetch("/api/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: data.get("email"),
        cities,
        event: data.get("event"),
        models,
        trigger_mode: data.get("trigger_mode"),
        threshold: Number(data.get("threshold")),
        captcha_id: subscriptionCaptchaId,
        captcha_answer: captchaAnswer.value,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "提交失败");
    submittedSuccessfully = true;
    formMessage.className = "form-message";
    formMessage.textContent = "";
    submitButton.classList.add("sent");
    submitButton.textContent = result.message;
  } catch (error) {
    formMessage.className = "form-message error";
    formMessage.textContent = error.message || "网络错误，请稍后重试";
  } finally {
    await loadCaptcha("subscription");
    if (!submittedSuccessfully) {
      submitButton.disabled = false;
      submitButton.textContent = "发送确认邮件";
    }
  }
});

form.addEventListener("input", () => {
  if (!submitButton.classList.contains("sent")) return;
  submitButton.classList.remove("sent");
  submitButton.disabled = false;
  submitButton.textContent = "发送确认邮件";
});

unsubscribeRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  unsubscribeMessage.className = "form-message";
  unsubscribeMessage.textContent = "";
  if (!unsubscribeRequestForm.reportValidity()) return;
  if (!unsubscribeCaptchaId) {
    unsubscribeMessage.className = "form-message error";
    unsubscribeMessage.textContent = "验证码尚未加载，请点击图片重试";
    return;
  }
  unsubscribeRequestButton.disabled = true;
  unsubscribeRequestButton.textContent = "正在发送…";
  try {
    const response = await fetch("/api/unsubscribe-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: unsubscribeEmail.value,
        captcha_id: unsubscribeCaptchaId,
        captcha_answer: unsubscribeCaptchaAnswer.value,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "提交失败");
    unsubscribeMessage.className = "form-message success";
    unsubscribeMessage.textContent = result.message;
  } catch (error) {
    unsubscribeMessage.className = "form-message error";
    unsubscribeMessage.textContent = error.message || "网络错误，请稍后重试";
  } finally {
    await loadCaptcha("unsubscribe");
    unsubscribeRequestButton.disabled = false;
    unsubscribeRequestButton.textContent = "发送退订邮件";
  }
});
