# SunsetScope

SunsetScope 是一个用于预测晚霞潜力的气象分析项目。当前仓库处于探索和原型阶段，重点是从 ECMWF Open Data 获取预报数据，围绕指定地点和日落时段提取气象要素，并用规则模型给出晚霞潜力评分。

## 当前目标

- 每日从 ECMWF 获取预报数据。
- 针对目标地点的日落时段，估计云量、降水、温湿度、风和气压等条件。
- 先用规则模型判断晚霞潜力，后续再引入机器学习模型做更细粒度的时间预测。
- 最终通过网页把预测结果展示给用户。

## 当前内容

```text
.
├── README.md
├── scripts/
│   ├── build_training_table.py
│   ├── modeling_config.py
│   └── sunset_rules.py
├── data/
│   └── raw/
│       ├── forecast/smoke_msl_proxy.grib2
│       └── truth/era5_sanya_20260401.grib
└── atmosphere/
    ├── sunset.ipynb
    ├── sanya_sunset_bundle.grib2
    ├── aifs_single_cloud_layers_0p25.grib2
    ├── ifs_fc_cloud_layers_global.grib2
    ├── data.grib2
    └── *.idx
```

核心文件：

- `scripts/`：后续建模、数据处理和训练相关代码的主要位置。
- `data/raw/forecast/smoke_msl_proxy.grib2`：ECMWF Open Data 预报下载测试样本。
- `data/raw/truth/era5_sanya_20260401.grib`：ERA5 三亚附近小区域真值下载测试样本。
- `atmosphere/sunset.ipynb`：早期实验 notebook，仅作为参考资料，后续开发不再直接修改这个目录。
- `atmosphere/*.grib2`：已下载的 ECMWF GRIB2 气象数据样例。
- `atmosphere/*.idx`：`cfgrib` 读取 GRIB2 时生成的索引文件。

## 数据来源

当前使用 ECMWF Open Data：

- 数据集入口：https://www.ecmwf.int/en/forecasts/datasets
- Python 客户端：`ecmwf-opendata`

notebook 中已经尝试过两类数据：

- IFS forecast：总云量、降水、2 米温度、2 米露点、10 米风、海平面气压等变量。
- AIFS Single：总云量、低云、中云、高云、降水、风和气压等变量，分辨率示例为 `0p25`。

## 主要流程

1. 获取 ECMWF 最新可用预报时次。
2. 将本地目标时间，比如明天 18:00 和 19:00，对齐到 ECMWF 可用的 `step`。
3. 下载目标变量到 GRIB2 文件。
4. 用 `xarray` + `cfgrib` 读取 GRIB2。
5. 对三亚点位进行最近邻抽样，当前默认点位为：
   - 纬度：`18.25`
   - 经度：`109.50`
6. 在日落窗口内计算晚霞潜力评分。
7. 对整张格点场计算评分，并用 `cartopy` 绘制地图。

## 建模思路

晚霞模型不能只使用预报数据训练。预报数据适合作为模型输入 `X`，但标签 `y` 和测试评估需要来自真实气象数据或真实晚霞记录。

推荐的数据组织方式是按“某次预报对应某个未来日落时段”建立样本：

```text
样本 = 某个起报时次 + 某个目标日落时间 + 某个目标地点

输入 X：
- ECMWF 历史预报数据
- 目标点及周边 3x3 或 5x5 格点
- 日落前后若干 step
- tcc, lcc, mcc, hcc, tp, 2t, 2d, 10u, 10v, msl 等变量

标签 y：
- 真实观测气象数据计算出的晚霞潜力标签
- 或人工/照片标注的真实晚霞等级
```

训练和测试时都不能把真实数据放进输入特征。正确关系是：

```text
历史预报数据 -> 模型预测晚霞概率/评分 -> 对比真实观测或真实晚霞标签
```

第一阶段如果没有照片或人工标注，可以用真实气象数据构造 proxy label：

```text
真实云量适中 + 无明显降水 + 低云不厚 + 中高云适中 -> 晚霞潜力较高
```

这个标签代表“真实天气条件下的晚霞潜力”，不等于真实照片意义上的“确实出现了晚霞”。后续若能接入照片、人工记录或社交媒体标注，应优先把它们作为更接近最终目标的标签。

### 当前建模脚本

`scripts/` 下已经准备了第一版建模基础代码：

- `scripts/download_open_forecast.py`：下载 ECMWF Open Data 的近期预报数据。
- `scripts/download_era5_truth.py`：下载 CDS/ERA5 小时级再分析数据，用作真实天气标签来源。
- `scripts/download_open_meteo_historical_forecast.py`：下载 Open-Meteo Historical Forecast 点位历史预报，用作冷启动历史 forecast 输入。
- `scripts/check_data_access.py`：检查本地下载依赖和 CDS 凭据是否齐全。
- `scripts/modeling_config.py`：默认站点、目标变量、时间列和格点窗口配置。
- `scripts/sunset_rules.py`：基于真实气象条件生成晚霞评分和三分类标签。
- `scripts/build_training_table.py`：把历史预报表和真实观测表合并成训练表。

### 数据下载

本项目后续会同时使用两类 EC 数据：

- 预报数据：来自 ECMWF Open Data，用作模型输入 `X`。这类数据主要面向当前和未来几天预报，适合日常预测服务；公开门户上的历史保留时间有限，长期历史预报需要另找归档来源。
- 真实天气数据：优先使用 ERA5 hourly single levels 再分析数据，用作标签 `y` 和测试评估。ERA5 是小时级、全球覆盖、从 1940 年至今的再分析数据，但通常有约 5 天延迟。

为了避免只靠从今天开始积累 ECMWF Open Data，项目也可以用 Open-Meteo Historical Forecast 做冷启动历史 forecast 输入。它从 2022 年起提供历史预报点位数据，并包含晚霞判断很重要的云层变量：

```text
cloud_cover
cloud_cover_low
cloud_cover_mid
cloud_cover_high
precipitation
temperature_2m
dew_point_2m
wind_speed_10m
wind_direction_10m
pressure_msl
```

这个数据源用于补足历史 forecast 训练输入，不替代 ERA5 真实天气标签。实时预测仍优先使用 ECMWF Open Data。

检查本地环境：

```bash
python -m scripts.check_data_access
```

### 网络代理

如果浏览器能访问 ECMWF/CDS，但命令行下载一直卡住，通常是因为 VPN 只接管了浏览器或系统流量，Python/PDM 没有自动走代理。

当前 Windows 机器上 Clash Verge 的本地 HTTP 代理端口是 `127.0.0.1:7897`。在 PowerShell 里运行下载命令前，先设置：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
```

这两个变量只对当前 PowerShell 窗口有效。新开终端后需要重新设置。

在 Linux/macOS 或服务器的 bash/zsh 里，写法是：

```bash
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
```

服务器上是否需要代理取决于服务器网络：

- 如果服务器可以直接访问 `https://data.ecmwf.int` 和 `https://cds.climate.copernicus.eu`，不需要设置代理。
- 如果服务器也需要代理，把 `127.0.0.1:7897` 换成服务器可用的代理地址。
- 如果代理跑在你本地电脑上，服务器不能直接使用你电脑上的 `127.0.0.1:7897`，因为服务器里的 `127.0.0.1` 指的是服务器自己。

如果要让服务器借用本地电脑的 VPN，推荐用 SSH 反向端口转发。从本地电脑连接服务器时运行：

```bash
ssh -R 7897:127.0.0.1:7897 user@server
```

保持这个 SSH 会话不断开，然后在服务器里设置：

```bash
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
```

这时服务器访问自己的 `127.0.0.1:7897`，流量会通过 SSH 隧道转回你本地电脑的 Clash Verge 代理。

也可以让 Clash Verge 开启“允许局域网连接”，然后服务器使用你本地电脑的局域网 IP：

```bash
export HTTP_PROXY=http://你的电脑局域网IP:7897
export HTTPS_PROXY=http://你的电脑局域网IP:7897
```

这种方式需要处理防火墙和局域网暴露问题，安全性和稳定性通常不如 SSH 反向转发。

安装依赖：

```bash
pdm install
```

如果还需要运行 notebook 和地图绘图：

```bash
pdm install -G notebook -G plot
```

下载近期 ECMWF Open Data 预报。PowerShell 中包含 `2d` 这类参数时要加引号：

```bash
pdm run python -m scripts.download_open_forecast \
  --steps "0/72/3" \
  --params "tcc,lcc,mcc,hcc,tp,2t,2d,10u,10v,msl" \
  --target data/raw/forecast/latest.grib2
```

如果只想测试三亚傍晚附近的少量 step：

```bash
pdm run python -m scripts.download_open_forecast \
  --steps "18,19" \
  --params "tcc,tp,2t,2d" \
  --target data/raw/forecast/sanya_smoke.grib2
```

下载 ERA5 真实天气数据前，需要在 CDS 网站登录、获取 API key，并在用户目录创建 `.cdsapirc`：

```text
url: https://cds.climate.copernicus.eu/api
key: <PERSONAL-ACCESS-TOKEN>
```

同时需要在 ERA5 数据集页面手动同意数据条款。然后可以下载三亚附近某一天日落前后的小时级再分析数据：

```bash
pdm run python -m scripts.download_era5_truth \
  --start-date 2026-04-01 \
  --end-date 2026-04-01 \
  --hours "9/12/1" \
  --area "19.5,108.5,17.0,111.0" \
  --target data/raw/truth/era5_sanya_20260401.grib
```

上述 ERA5 时间是 UTC。三亚使用 UTC+8，因此本地 17:00-20:00 大约对应 UTC 09:00-12:00。

CDS 请求是后台队列任务。如果不想让命令行一直等待任务完成，可以只提交请求：

```bash
pdm run python -m scripts.download_era5_truth \
  --start-date 2026-04-01 \
  --end-date 2026-04-01 \
  --hours "9/12/1" \
  --area "19.5,108.5,17.0,111.0" \
  --submit-only
```

这个命令会打印 CDS 返回的 `request_id` 和 `state`，不会下载文件。之后可以在 CDS 网页的请求列表里查看状态并手动下载。

如果只想生成请求参数，后面自己复制到网页或其它脚本里使用：

```bash
pdm run python -m scripts.download_era5_truth \
  --start-date 2026-04-01 \
  --end-date 2026-04-01 \
  --hours "9/12/1" \
  --area "19.5,108.5,17.0,111.0" \
  --request-json data/requests/era5_sanya_20260401.json
```

`--request-json` 不会提交任务，也不会下载数据。

如果 CDS 网页或 `--submit-only` 已经显示请求成功，可以按 request id 下载结果文件：

```bash
pdm run python -m scripts.download_era5_truth \
  --request-id 6e5818c6-e2f9-4320-9680-0a2422618187 \
  --target data/raw/truth/era5_sanya_20260401.grib
```

这个模式会读取本机 `.cdsapirc`，自动设置新版 ECMWF datastores client 需要的认证信息，然后调用 `download_results(request_id, target)` 下载已完成的结果。Windows PowerShell 下如果需要 VPN，运行前仍要先设置：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
```

`build_training_table.py` 当前接受 CSV 或 Parquet 表格。

下载 Open-Meteo Historical Forecast 点位历史预报示例：

```bash
pdm run python -m scripts.download_open_meteo_historical_forecast \
  --start-date 2024-04-01 \
  --end-date 2024-04-01 \
  --latitude 18.25 \
  --longitude 109.50 \
  --model ecmwf_ifs025 \
  --output data/raw/forecast/open_meteo_sanya_20240401.csv \
  --raw-json data/raw/forecast/open_meteo_sanya_20240401.json
```

Open-Meteo 请求的是点位时间序列，不是完整格点场；适合先快速构建历史 forecast baseline。后续如果要用目标点周边格点，需要对周边多个经纬度点分别请求并合并。

预报表至少需要这些列：

```text
run_time_utc, valid_time_utc, latitude, longitude
```

并尽量包含这些变量列：

```text
tcc, lcc, mcc, hcc, tp, t2m, d2m, u10, v10, msl
```

真实观测表至少需要：

```text
valid_time_utc
```

如果没有现成标签，真实观测表应包含可用于规则打分的变量，例如：

```text
tcc, lcc, mcc, hcc, tp, t2m, d2m, u10, v10
```

生成训练表示例：

```bash
python -m scripts.build_training_table \
  --forecast data/raw/forecast_history.csv \
  --truth data/raw/truth_history.csv \
  --output data/processed/training_table.csv
```

如果真实观测表已经有人工作好的标签列：

```bash
python -m scripts.build_training_table \
  --forecast data/raw/forecast_history.csv \
  --truth data/raw/truth_history.csv \
  --label-column sunset_label \
  --output data/processed/training_table.csv
```

当前脚本会从目标点附近选取 `3x3` 格点，即 `--grid-window 1`，并对每个预报变量生成 `mean/min/max/std` 特征。后续可以继续扩展为多 step 特征、日落时间特征、太阳高度角特征和真正的模型训练脚本。

## 当前评分规则

当前规则模型仍是原型版本，主要用于建立基线。

### 点位评分 `sunset_glow_score_v1`

输入变量：

- `tcc`：总云量
- `tp`：总降水
- `2t` / `t2m`：2 米温度
- `2d` / `d2m`：2 米露点

基本逻辑：

- 云量适中加分，过晴或过阴扣分。
- 傍晚明显降水扣分。
- 温度和露点差较大时，认为空气更通透，适当加分。

输出标签：

- `晚霞潜力较高`
- `可能有普通晚霞/落日云`
- `晚霞潜力较低`

### 格点评分 `sunset_score_field_v1`

AIFS 版本额外考虑：

- `lcc`：低云量
- `mcc`：中云量
- `hcc`：高云量
- `u10` / `v10`：10 米风
- `msl`：海平面气压

基本逻辑：

- 低云过多扣分。
- 中高云适中加分，过厚扣分。
- 强风弱扣分。
- 相对高压弱加分。
- 得分会截断到非负值，示例中可进一步限制到 `0..5`。

## 运行环境

notebook 元数据中当前内核为：

- Python：`3.10.19`
- Kernel：`Python (weather)`

建议依赖：

```bash
pip install ecmwf-opendata xarray cfgrib eccodes pandas numpy matplotlib cartopy jupyter jupyter-black
```

注意：`cfgrib` 依赖 ECMWF ecCodes。不同系统安装方式可能不同，若 `pip install eccodes` 后仍无法读取 GRIB2，需要额外安装系统级 ecCodes。

## 使用方式

进入项目目录后启动 Jupyter：

```bash
jupyter lab
```

打开：

```text
atmosphere/sunset.ipynb
```

按 notebook 单元顺序运行即可复现实验流程。

当前 notebook 中有一处读取数据使用了旧的绝对路径：

```python
xr.open_dataset(
    "/share/org/YZWL/yzbsl_luotao/d2l/atmosphere/sanya_sunset_bundle.grib2",
    engine="cfgrib",
)
```

在本仓库中应改为相对路径：

```python
xr.open_dataset("atmosphere/sanya_sunset_bundle.grib2", engine="cfgrib")
```

如果当前工作目录已经是 `atmosphere/`，则使用：

```python
xr.open_dataset("sanya_sunset_bundle.grib2", engine="cfgrib")
```

## 后续计划

- 不再修改 `atmosphere/`，只把其中已验证的思路迁移到正式代码。
- 在 `scripts/` 中继续整理下载、读取、评分、样本构造和模型训练逻辑。
- 明确目标地点、日落时间计算和时区处理。
- 建立训练样本：使用目标点及周边 `3x3` 或 `5x5` 格点，结合过去多日气象数据。
- 接入真实气象数据或人工晚霞标签，避免只用预报数据自我训练。
- 评估机器学习模型是否能从 6 小时间隔预报中补足更细粒度的傍晚天气状态。
- 建立晚霞规则和模型输出的融合方案。
- 开发网页展示界面，包括地图、点位预测、评分解释和更新时间。

## 当前状态

项目目前还不是完整应用，主要是数据和规则模型的验证 notebook。已有数据和代码足够继续推进到模块化整理、定时下载和前端展示。
