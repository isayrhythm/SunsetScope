const map = L.map("map", { preferCanvas: true }).setView([19, 110], 7);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 10,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let cellLayer = L.layerGroup().addTo(map);
let allFeatures = [];
let allCells = [];

function colorForScore(score) {
  if (score >= 4) return "#b2182b";
  if (score >= 3) return "#ef8a62";
  if (score >= 2) return "#fddbc7";
  if (score >= 1) return "#d1e5f0";
  return "#67a9cf";
}

function fillOpacity(score) {
  if (score >= 4) return 0.74;
  if (score >= 3) return 0.58;
  if (score >= 2) return 0.38;
  if (score >= 1) return 0.18;
  return 0.06;
}

function formatValue(value, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (typeof value === "number") return `${Number(value.toFixed(2))}${suffix}`;
  return `${value}${suffix}`;
}

function renderDetails(props) {
  const rows = [
    ["Time", props.time],
    ["Score", `${props.score} / 5 (${props.label})`],
    ["Cloud", formatValue(props.cloud_cover, "%")],
    ["Low cloud", formatValue(props.cloud_cover_low, "%")],
    ["Mid cloud", formatValue(props.cloud_cover_mid, "%")],
    ["High cloud", formatValue(props.cloud_cover_high, "%")],
    ["Precip", formatValue(props.precipitation, " mm")],
    ["Temp", formatValue(props.temperature_2m, " C")],
    ["Dew point", formatValue(props.dew_point_2m, " C")],
    ["Visibility", formatValue(props.visibility, " m")],
    ["Wind", formatValue(props.wind_speed_10m, " km/h")],
    ["Pressure", formatValue(props.pressure_msl, " hPa")],
    ["CAPE", formatValue(props.cape)],
  ];
  document.getElementById("summary").innerHTML = rows
    .map(([key, value]) => `<div class="metric"><span>${key}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderCells(cells) {
  cellLayer.clearLayers();
  for (const feature of cells) {
    const coords = feature.geometry.coordinates[0].map(([lon, lat]) => [lat, lon]);
    const score = feature.properties.score;
    const polygon = L.polygon(coords, {
      stroke: false,
      fillColor: colorForScore(score),
      fillOpacity: fillOpacity(score),
    });
    polygon.on("click", () => renderDetails(feature.properties));
    polygon.bindTooltip(`${feature.properties.time}<br>score ${score}`, { sticky: true });
    cellLayer.addLayer(polygon);
  }
}

function setTime(time) {
  const cells = allCells.filter((feature) => feature.properties.time === time);
  renderCells(cells);
}

function addLegend() {
  const legend = L.control({ position: "bottomright" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "legend");
    const rows = [
      [4, "High"],
      [3, "Good"],
      [2, "Medium"],
      [1, "Low"],
      [0, "Very low"],
    ];
    div.innerHTML = rows
      .map(
        ([score, label]) =>
          `<div class="legend-row"><span class="swatch" style="background:${colorForScore(score)}"></span>${label}</div>`
      )
      .join("");
    return div;
  };
  legend.addTo(map);
}

fetch("/api/sunset-score")
  .then((response) => response.json())
  .then((data) => {
    allFeatures = data.features || [];
    allCells = data.cells || [];
    const times = [...new Set(allFeatures.map((feature) => feature.properties.time))].sort();
    const select = document.getElementById("timeSelect");

    for (const time of times) {
      const option = document.createElement("option");
      option.value = time;
      option.textContent = time;
      select.appendChild(option);
    }

    select.addEventListener("change", () => setTime(select.value));
    addLegend();

    if (times.length > 0) {
      setTime(times[0]);
      const bounds = L.latLngBounds(allFeatures.map((feature) => [feature.geometry.coordinates[1], feature.geometry.coordinates[0]]));
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.08));
    }

  })
  .catch((error) => {
    document.getElementById("summary").textContent = `Failed to load map data: ${error}`;
  });

function loadLatestUpdate() {
  fetch("/api/latest-update")
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data) return;
      document.getElementById("updateStatus").textContent =
        `Forecast ${data.forecast_date || "-"} | updated ${data.updated_at || "-"} | rows ${data.rows || "-"}`;
    })
    .catch(() => {});
}

const updateButton = document.getElementById("updateButton");
if (updateButton) {
  updateButton.addEventListener("click", () => {
    updateButton.disabled = true;
    document.getElementById("updateStatus").textContent = "Updating Hainan forecast...";
    fetch("/api/update/hainan", { method: "POST" })
      .then((response) => response.json())
      .then((result) => {
        if (result.status === "busy") {
          document.getElementById("updateStatus").textContent = "Update is already running.";
          return;
        }
        if (result.status === "error") {
          document.getElementById("updateStatus").textContent = `Update failed: ${result.message || "unknown error"}`;
          return;
        }
        document.getElementById("updateStatus").textContent = "Update complete. Refreshing map data...";
        window.location.reload();
      })
      .catch((error) => {
        document.getElementById("updateStatus").textContent = `Update failed: ${error}`;
      })
      .finally(() => {
        updateButton.disabled = false;
      });
  });
}

loadLatestUpdate();
