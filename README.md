# SunsetScope

SunsetScope 是一个用于预测晚霞潜力的气象分析项目。当前仓库处于探索和原型阶段，重点是从 ECMWF Open Data 获取预报数据，围绕指定地点和日落时段提取气象要素，并用规则模型给出晚霞潜力评分。

## 一句话

```text
SunsetScope = 全国晚霞潜力图 + 次日提醒服务 + 基于真实社交观察信号持续校正的预测系统
```

## 先看这里

如果你第一次进入这个项目，先只记住这几件事：

- 当前主线是：阶段 1 先做“全国晚霞潜力图 + 次日提醒服务”。
- 当前代码原型已经能跑通“海南区域预报下载 + 规则打分 + 网页展示”。
- 当前还没有完成全国图、提醒服务、小红书弱标签、机器学习训练。

最常用命令：

```bash
pdm install
pdm run web
```

更新明天的海南数据：

```powershell
$env:SUNSETSCOPE_PROXY_URL='http://127.0.0.1:7897'
pdm run python -m scripts.update_hainan_forecast --proxy http://127.0.0.1:7897
```

脚本入口索引在 [scripts/README.md](/D:/workspace/SunsetScope/scripts/README.md)。

## 当前边界

当前已经有的能力：

- 海南区域网页展示
- 明天的海南预报下载与打分
- ERA5 真值下载
- ERA5 GRIB 转 CSV

当前还没有的能力：

- 全国晚霞潜力图
- 真正可用的提醒服务
- 小红书弱标签采集与统计
- 机器学习训练与线上预测

## 当前目标

- 每日从 ECMWF 获取预报数据。
- 针对目标地点的日落时段，估计云量、降水、温湿度、风和气压等条件。
- 先用规则模型判断晚霞潜力，后续再引入机器学习模型做更细粒度的时间预测。
- 最终通过网页把预测结果展示给用户。

## 产品路线

项目的长期目标不是只做一个“天气打分页面”，而是做一套晚霞观测与提醒服务。当前已经有了最小闭环原型：下载预报、规则打分、网页展示。经过收敛后，项目主线明确分成三个阶段：

### 阶段 1：全国晚霞潜力图 + 次日提醒服务

这是当前最优先的产品目标。核心不是先把模型做到多复杂，而是先让用户能用起来：

- 做出全国范围的晚霞潜力图，而不再只局限于海南。
- 支持查看今天和明天，至少把“次日是否值得期待”做清楚。
- 建立最小提醒链路，让用户不用每天手动打开网页。
- 先用规则模型和现有气象数据跑通产品闭环。

阶段 1 的成功标准是：

- 用户能在网页上查看全国范围的晚霞潜力分布。
- 用户能订阅地点，并在次日有较高概率时收到提醒。
- 即使规则还不完美，产品也已经具备实际使用价值。

### 阶段 2：引入小红书弱标签，校正评分

当阶段 1 跑起来之后，下一步重点不是继续手写更多规则，而是补真实世界反馈信号。

- 爬取“小红书地区 + 晚霞/火烧云”笔记量。
- 统计某地区某天是否出现显著异常热度。
- 把异常热度作为弱监督标签，校正当前规则评分。
- 逐步回答“哪些天气条件真的会对应用户能感知到的晚霞事件”。

阶段 2 的核心不是追求物理上绝对精确的晚霞定义，而是建立一层“用户真实观察到并愿意传播”的事件标签。

### 阶段 3：训练机器学习模型替代部分硬规则

等阶段 2 积累到一定标签之后，再开始系统性训练模型。

- 用历史 forecast + 周边格点信息 + 规则特征构造训练样本。
- 用小红书弱标签或后续人工确认标签作为 `y`。
- 训练表格模型或时空模型，逐步替代一部分硬规则。
- 最终让模型学习“什么样的天气结构更容易形成值得观看和传播的晚霞”。

阶段 3 的目标不是完全抛弃规则，而是让规则退到 baseline 和解释层，模型负责更复杂的时空关系。

### 当前范围

基于上面的阶段划分，当前项目只聚焦阶段 1。也就是说：

- 当前最重要的是全国图和提醒服务。
- 小红书弱标签属于下一阶段工作。
- 机器学习训练属于再下一阶段工作。

这样做的好处是可以避免项目一开始同时铺开前端、推送、爬虫、标签、训练、评估，导致每一条线都做不深。

### 1. 前端展示

当前网页只覆盖海南、只展示一天、交互非常轻。按照阶段 1 的目标，前端建议逐步扩展成：

- 地区范围：从海南扩展到全国，至少支持省级和城市级查看。
- 时间范围：不仅展示明天，也展示今天、未来 2 到 3 天，以及历史回看。
- 地图表达：继续保留颜色分区，但增加城市搜索、定位、时间滑块、图层切换和评分解释。
- 点位详情：除了 `score`，还展示 `cloud_cover_low`、`west_low_cloud_index`、`cloud_cover_mid`、`cloud_cover_high`、降水、风、更新时间、模型来源。
- 结果层级：不要只给一个分数，最好分成“观赏潜力”“火烧云强度潜力”“稳定性/可信度”三类信息。

前端的最终目标不是替代专业气象图，而是让普通用户快速知道：

- 今天/明天哪里可能出晚霞。
- 这个判断为什么成立。
- 这个判断的可信度高不高。

### 2. 推送服务

阶段 1 就应该开始做主动提醒能力，而不是只让用户自己打开网页看。推送通道可以分层设计：

- 第一层：邮件提醒。
- 第二层：短信提醒。
- 第三层：微信公众号模板消息或服务号通知。
- 第四层：电话语音提醒，作为高优先级或付费提醒。

推送逻辑不要简单按“分数超过阈值就发”，而要加入订阅条件：

- 用户订阅的地点。
- 用户关心的时间窗，例如 18:00 到 19:30。
- 推送阈值，例如 `score >= 3.5`。
- 推送频率限制，例如一天最多 1 次或 2 次。
- 二次确认机制，例如只有连续两次更新都高分才提醒。

建议把推送系统设计成独立模块，至少包含：

- `subscription`：用户订阅关系。
- `candidate_alert`：某地点某时间窗是否达到提醒条件。
- `delivery`：不同通道的发送记录。
- `feedback`：用户是否点击、是否觉得准确。

### 3. 数据与标签

当前规则模型只是在“根据天气条件猜晚霞”。阶段 2 的关键任务，就是补充真实世界标签。

你现在提出的“小红书地区 + 晚霞/火烧云笔记数”是一个很合理的弱监督入口。建议把它定义成：

- `observation proxy label`
- 即：不是直接证明“某地某时一定出现了晚霞”，而是作为“这一天该地区很可能出现了值得拍照传播的晚霞事件”的近似标签。

建议的小红书标签流程：

- 以“地区关键词 + 晚霞/火烧云”搜当天笔记。
- 统计每天笔记数、互动数、去重后的作者数。
- 对每个地区建立时间序列基线。
- 当某天笔记数显著高于平时均值时，标为“高概率晚霞日”。

不要直接用“有几篇笔记”做二元标签，建议做成分级标签：

- 0：无明显异常。
- 1：略高于平时。
- 2：显著高于平时。
- 3：异常爆发，极可能有强晚霞事件。

后续还可以补充其他弱标签来源：

- 微博关键词。
- 抖音/快手公开视频数量。
- 天气摄影社群签到。
- 用户主动反馈“今天这里真的有/没有晚霞”。

### 4. 机器学习路线

规则模型适合阶段 1 启动，但阶段 3 建议把它逐步降级成 baseline 和解释工具，主预测交给机器学习模型。

建议的训练样本结构：

```text
样本 = 某地区 + 某一天 + 某个傍晚时间窗

输入：
- 目标格点及周边格点的 forecast 特征
- 傍晚前若干小时的气象演变
- west_low_cloud_index 这类人工构造特征
- 日落时间、季节、地理位置

标签：
- 小红书晚霞笔记异常度
- 或未来补充的人工确认标签
```

机器学习阶段的目标不是完全抛弃气象解释，而是：

- 用模型自动学习周边区块和时间演化的关系。
- 减少人工硬规则的局限。
- 让模型捕捉“什么样的云场组合更容易出火烧云”，而不是手写每一条规则。

推荐分两步：

- 第一步：做表格模型 baseline，例如 LightGBM / XGBoost。
- 第二步：做时空模型，例如把周边格点做成 patch，再尝试 CNN / Transformer / 时序模型。

规则模型在机器学习时代仍然有用：

- 作为特征工程。
- 作为冷启动方案。
- 作为解释层，让用户知道模型为什么判断这个地区高分。

### 5. 数据可靠性与评估

这个项目的难点不是“下载气象数据”，而是“定义什么叫真的有晚霞”。因此评估必须分层：

- 气象层：规则和模型是否正确识别了适合出晚霞的天气条件。
- 事件层：是否真的发生了用户感知明显的晚霞事件。
- 产品层：用户是否愿意因此打开页面或收到提醒。

建议评估指标不要只看回归误差，至少还要看：

- 高分日 precision。
- 高分日 recall。
- 提醒点击率。
- 用户主观反馈准确率。

## 当前内容

```text
.
├── README.md
├── scripts/
│   ├── README.md
│   ├── update_hainan_forecast.py
│   ├── score_china_forecast.py
│   ├── sunset_grid_score.py
│   ├── download_open_meteo_tile_forecast.py
│   ├── download_open_meteo_china_forecast.py
│   ├── build_training_table.py
│   ├── modeling_config.py
│   ├── sunset_rules.py
│   └── legacy/
│       └── download_open_forecast.py
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
- `scripts/README.md`：脚本索引。先看这个文件，再决定跑哪个脚本。
- `data/raw/forecast/smoke_msl_proxy.grib2`：ECMWF Open Data 预报下载测试样本。
- `data/raw/truth/era5_sanya_20260401.grib`：ERA5 三亚附近小区域真值下载测试样本。
- `atmosphere/sunset.ipynb`：早期实验 notebook，仅作为参考资料，后续开发不再直接修改这个目录。
- `atmosphere/*.grib2`：已下载的 ECMWF GRIB2 气象数据样例。
- `atmosphere/*.idx`：`cfgrib` 读取 GRIB2 时生成的索引文件。

## 脚本索引

如果你只想知道“现在该跑哪个脚本”，先看 [scripts/README.md](/D:/workspace/SunsetScope/scripts/README.md)。

当前建议记住的入口只有这几个：

- `pdm run web`：启动网页。
- `pdm run python -m scripts.update_hainan_forecast --proxy http://127.0.0.1:7897`：下载明天的海南数据并更新网页。
- `pdm run python -m scripts.score_china_forecast ...`：对已有 CSV 重打分。
- `pdm run python -m scripts.download_era5_truth ...`：下 ERA5 真值。

已经挪到 `scripts/legacy/` 的脚本表示“保留参考价值，但不属于当前主流程”。当前已迁移：

- `scripts/legacy/download_open_forecast.py`：早期 ECMWF Open Data 直下 GRIB 脚本。

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

- `scripts/legacy/download_open_forecast.py`：下载 ECMWF Open Data 的近期预报数据。当前主要保留作参考，不属于网页主流程。
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

在 Linux/macOS 本机终端里，如果代理就跑在这台机器自己身上，写法是：

```bash
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
```

服务器上是否需要代理取决于服务器网络：

- 如果服务器可以直接访问 `https://data.ecmwf.int` 和 `https://cds.climate.copernicus.eu`，不需要设置代理。
- 如果服务器也需要代理，把 `127.0.0.1:7897` 换成服务器自己可用的代理地址。
- 如果代理跑在你本地电脑上，服务器不能直接使用你电脑上的 `127.0.0.1:7897`，因为服务器里的 `127.0.0.1` 指的是服务器自己，不是你的电脑。

如果要让服务器借用本地电脑的 VPN，推荐用 SSH 反向端口转发。从本地电脑连接服务器时运行：

```bash
ssh -R 7897:127.0.0.1:7897 user@server
```

保持这个 SSH 会话不断开，然后在服务器里设置：

```bash
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
```

这时服务器访问自己的 `127.0.0.1:7897`，流量会通过 SSH 隧道转回你本地电脑的 Clash Verge 代理。只要你本地 VPN/代理还开着，而且这条 SSH 会话没断，服务器就能借你的本地网络访问 GitHub、Open-Meteo 等外网；一旦本地 VPN 关闭或 SSH 会话断开，这条链路就失效。

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

Linux 上如果只跑当前 Web 展示和 Open-Meteo 更新流程，通常这一条就够了。  
如果后面还要读取 ERA5 / GRIB 文件，再额外安装系统级 ecCodes。Debian/Ubuntu 常见写法：

```bash
sudo apt-get update
sudo apt-get install -y libeccodes-dev
```

如果还需要运行 notebook 和地图绘图：

```bash
pdm install -G notebook -G plot
```

下载近期 ECMWF Open Data 预报。PowerShell 中包含 `2d` 这类参数时要加引号：

```bash
pdm run python -m scripts.legacy.download_open_forecast \
  --steps "0/72/3" \
  --params "tcc,lcc,mcc,hcc,tp,2t,2d,10u,10v,msl" \
  --target data/raw/forecast/latest.grib2
```

如果只想测试三亚傍晚附近的少量 step：

```bash
pdm run python -m scripts.legacy.download_open_forecast \
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

## Web MVP

当前 Web 最小闭环使用：

```text
FastAPI + Jinja2 + Leaflet
```

最小启动方式：

```bash
pdm install
pdm run web
```

默认访问地址：

```text
http://127.0.0.1:8000
```

如果本机访问 Open-Meteo 需要代理，启动前先带上：

```powershell
$env:SUNSETSCOPE_PROXY_URL='http://127.0.0.1:7897'
pdm run web
```

Linux/macOS 写法只适用于代理本来就在这台 Linux/macOS 机器上，或者你已经做了上面的 `ssh -R` 反向端口转发：

```bash
export SUNSETSCOPE_PROXY_URL=http://127.0.0.1:7897
pdm run web
```

如果 Linux 服务器本身可以直连 Open-Meteo，最简单的方式是不设置 `SUNSETSCOPE_PROXY_URL`，直接：

```bash
pdm run web
```

先下载中国区域采样网格的 Open-Meteo ECMWF IFS 预报：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'

pdm run python -m scripts.download_open_meteo_china_forecast `
  --date 2026-04-27 `
  --grid-step 2.0 `
  --batch-size 50 `
  --batch-sleep 3 `
  --raw-csv data/raw/forecast/china_open_meteo_ecmwf_20260427.csv
```

再把预报 CSV 转成晚霞评分地图数据：

```bash
pdm run python -m scripts.score_china_forecast \
  --input data/raw/forecast/china_open_meteo_ecmwf_20260427.csv \
  --score-hours "18,19,20" \
  --grid-step 2.0 \
  --output data/app/sunset_score_china.json
```

启动网页：

```bash
pdm run web
```

打开：

```text
http://127.0.0.1:8000
```

当前地图支持两种下载方式：

- 采样点模式：`download_open_meteo_china_forecast.py`，适合快速覆盖大范围。
- tile 模式：`download_open_meteo_tile_forecast.py`，适合下载 HRES 高分辨率小区域，例如海南。

海南周边高分辨率示例：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'

pdm run python -m scripts.download_open_meteo_tile_forecast `
  --date 2026-04-27 `
  --south 17 `
  --west 108 `
  --north 21 `
  --east 112 `
  --tile-size 2 `
  --tile-sleep 15 `
  --retries 5 `
  --retry-sleep 45 `
  --output data/raw/forecast/hainan_open_meteo_ecmwf_20260427.csv
```

再打分生成网页数据：

```bash
pdm run python -m scripts.score_china_forecast \
  --input data/raw/forecast/hainan_open_meteo_ecmwf_20260427.csv \
  --score-hours "18,19,20" \
  --cell-size 0.08 \
  --output data/app/sunset_score_china.json
```

也可以直接运行规范化的每日更新管线。它会下载明天的海南预报、保存归档、打分，并更新网页当前数据：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'

pdm run python -m scripts.update_hainan_forecast `
  --proxy http://127.0.0.1:7897
```

输出目录：

```text
data/collections/hainan/YYYY-MM-DD/forecast.csv
data/collections/hainan/YYYY-MM-DD/sunset_score.json
data/collections/hainan/YYYY-MM-DD/metadata.json
data/app/sunset_score_china.json
data/app/latest_update.json
```

网页也提供手动更新按钮，会调用：

```text
POST /api/update/hainan
```

这个按钮默认更新“明天”的海南数据，日期按 `Asia/Shanghai` 计算。例如 2026-04-27 晚上点击，会更新 `2026-04-28`。

如果本机访问 Open-Meteo 需要代理，启动 Web 服务时也要把代理一起带进去，否则网页能打开，但点击“更新海南”会失败。Windows PowerShell 示例：

```powershell
$env:SUNSETSCOPE_PROXY_URL='http://127.0.0.1:7897'
pdm run web
```

Linux/macOS 示例：

```bash
export SUNSETSCOPE_PROXY_URL=http://127.0.0.1:7897
pdm run web
```

如果机器本身可以直连 Open-Meteo，就不要设置 `SUNSETSCOPE_PROXY_URL`。当前实现中，Web 更新接口会优先使用这个变量；未设置时走直连。

如果希望 Web 服务挂着时每天自动更新，可以启动前设置：

```powershell
$env:SUNSETSCOPE_AUTO_UPDATE='1'
$env:SUNSETSCOPE_DAILY_UPDATE_AT='06:10'
$env:SUNSETSCOPE_PROXY_URL='http://127.0.0.1:7897'
pdm run web
```

这里的启动逻辑只会注册下一次定时任务，不会在 Web 服务刚启动时立刻下载。比如当前时间已经过了 `06:10`，它会等到明天 `06:10` 再执行；当前时间还没到 `06:10`，它会等到今天 `06:10`。如果不设置 `SUNSETSCOPE_AUTO_UPDATE=1`，Web 服务只负责展示和手动更新，不会自动下载。

这适合本地开发。长期运行更推荐用系统定时任务调用 `scripts.update_hainan_forecast`，例如 Windows Task Scheduler 或服务器上的 cron/systemd timer，这样不会受 Web 进程重启影响。

页面支持 18:00、19:00、20:00 本地时间切换，展示晚霞潜力色斑。HRES 的原始点位不是简单规则经纬网，因此网页当前用小矩形色斑展示评分区域；后续可再做后端插值生成更平滑的 PNG overlay。

Open-Meteo 免费非商用条款有每分钟、每小时和每日请求限制；HRES 大范围请求还会受到单请求 location 数限制。全中国 HRES `bounding_box` 会超过 1000 locations，所以当前下载器采用多点采样和分批请求。若遇到 `429 Too Many Requests`，增大 `--batch-sleep`、减小 `--batch-size`，或等待一分钟后重试。

当前评分规则是保守规则 baseline：

- 只要有明显降水，直接 0 分。
- 低云过多、总云量过厚会限制最高分。
- 除了格点本身的 `cloud_cover_low`，当前还额外计算 `west_low_cloud_index`，专门衡量目标点西边 4 格、南北各 1 格的加权低云情况；这个指标用于近似判断“日落方向是否被西边低云挡住”。
- 中云和高云都很少时不能高分，因为缺少晚霞所需的云层载体。
- 只有高云、几乎没有中云时，分数会被压低；当前规则已经不再允许单靠稀薄高云拿到高分。
- 无降水、低云少、中高云适中、能见度较好时才会高分。

网页右侧详情当前会显示这些关键字段：

- `Low cloud`：当前格点整体低云覆盖率。
- `West low cloud`：西边加权低云指数，更接近日落方向低云风险。
- `Mid cloud` / `High cloud`：当前格点中云和高云覆盖率。

## 当前状态

项目目前还不是完整应用，主要是数据和规则模型的验证 notebook。已有数据和代码足够继续推进到模块化整理、定时下载和前端展示。

当前仓库已经包含一份实际跑通的海南数据快照：

```text
data/collections/hainan/2026-04-28/
data/collections/hainan/2026-04-29/
data/app/latest_update.json
data/app/sunset_score_china.json
```

当前 `data/app/latest_update.json` 和 `data/app/sunset_score_china.json` 已经指向 `2026-04-29` 的网页展示结果。

因此在 Linux 上直接 `git clone` 后，只要安装好依赖，就可以先把网页跑起来看现有结果；不必等第一次下载成功之后才能打开页面。
