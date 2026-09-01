# SunsetScope

SunsetScope 是一个轻量的朝霞、晚霞邮件订阅服务。用户最多选择两个地点，并设置事件、预测模型和鲜艳度阈值；系统从 sunsetbot 获取预测，持续保存每日鲜艳度，满足条件时发送邮件。

本项目不下载气象文件、不训练模型，也不需要 MySQL、PostgreSQL 或 SQLite。订阅和投递记录保存在一个本地 JSON 文件中。

## 功能

- 邮箱订阅与确认，确认链接可以重复访问
- 本地图片验证码；验证通过后才允许发送确认或退订邮件
- 从 sunsetbot 联想和校验可用地点
- 每个订阅支持一至两个地点
- 按地点、日期、朝/晚霞和模型持续保存每日预测鲜艳度，供年度总结使用
- 朝霞、晚霞分别订阅
- GFS、EC 单选或同时选择
- 多模型支持“任一达到就提醒”和“全部达到才提醒”
- `0.05～2.5` 鲜艳度阈值与实时等级说明
- 同一订阅、同一事件日期只提醒一次
- 邮件中分别列出各模型的预测值、时间和 AOD
- 邮件退订
- 首页申请退订管理邮件
- sunsetbot 故障时向管理员发送报告
- JSON 跨进程锁与原子写入，写入中断不会留下半个文件

## 工作流程

1. 用户在网页填写邮箱、一至两个地点、事件、模型和阈值，并完成图片验证码。
2. 服务端验证一次性验证码后才发送确认邮件，点击链接后订阅生效。
3. 定时任务只查询已激活订阅涉及的地点和模型，并更新每日预测记录。
4. 每个地点独立判断阈值；达到触发条件时发送提醒，并记录投递键防止重复发送。
5. 用户可以通过邮件中的链接退订。

## 鲜艳度等级

GFS 和 EC 使用 sunsetbot 输出的同一套鲜艳度指标，模型不同但等级含义相同。

| 鲜艳度 | 页面说明 |
| ---: | --- |
| `0` | 不烧 |
| `0～0.05` | 微微烧 |
| `0.05～0.20` | 小烧 |
| `0.20～0.40` | 小烧到中等烧 |
| `0.40～0.60` | 中等烧 |
| `0.60～0.80` | 中等烧到大烧 |
| `0.80～1.00` | 大烧 |
| `1.00～1.50` | 典型大烧 |
| `1.50～2.00` | 优质大烧 |
| `2.00～2.50` | 世纪大烧 |

订阅阈值最低为 `0.05`；前端和后端均拒绝 `0.00`，避免零阈值导致每天都满足提醒条件。

## 项目结构

```text
app/
├── main.py                 # FastAPI 页面与接口
├── config.py               # 环境变量配置
├── provider.py             # sunsetbot 数据适配
├── service.py              # 订阅、确认、退订和去重
├── store.py                # JSON 原子存储
├── mailer.py               # QQ SMTP 邮件
├── jobs.py                 # 预测检查任务
├── templates/              # 页面模板
└── static/                 # CSS、JavaScript 和图标
data/
└── store.json              # 运行后生成，不提交 Git
tests/                      # 标准库 unittest 测试
```

## 环境要求

- Python `3.9～3.13`
- 可访问 `https://sunsetbot.top/`
- 开启 SMTP 服务的 QQ 邮箱

直接依赖只有：

- FastAPI
- Uvicorn
- Jinja2
- Requests
- Pillow（仅用于在本机生成验证码图片）

## 安装

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 配置邮件

程序从环境变量读取配置，不会自动加载 `.env` 文件。`.env.example` 仅作为字段参考。

```powershell
$env:SUNSETSCOPE_BASE_URL='http://127.0.0.1:8000'
$env:SUNSETSCOPE_SMTP_USER='your-address@qq.com'
$env:SUNSETSCOPE_SMTP_PASSWORD='QQ邮箱授权码'
$env:SUNSETSCOPE_SMTP_FROM='your-address@qq.com'
```

完整配置：

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `SUNSETSCOPE_BASE_URL` | `http://127.0.0.1:8000` | 邮件确认、退订链接的公开地址 |
| `SUNSETSCOPE_STORE_PATH` | `data/store.json` | JSON 数据文件路径 |
| `SUNSETSCOPE_SOURCE_TIMEOUT` | `15` | 请求预测数据的超时秒数 |
| `SUNSETSCOPE_SMTP_HOST` | `smtp.qq.com` | SMTP 主机 |
| `SUNSETSCOPE_SMTP_PORT` | `465` | SMTP SSL 端口 |
| `SUNSETSCOPE_SMTP_USER` | 无 | SMTP 登录邮箱 |
| `SUNSETSCOPE_SMTP_PASSWORD` | 无 | QQ 邮箱授权码 |
| `SUNSETSCOPE_SMTP_FROM` | 同登录邮箱 | 发件人地址 |
| `SUNSETSCOPE_ADMIN_EMAIL` | 同登录邮箱 | 定时任务数据源故障报告收件人 |
| `SUNSETSCOPE_RATE_LIMIT_IP` | `20` | 单个 IP 在窗口内允许的邮件请求数 |
| `SUNSETSCOPE_RATE_LIMIT_EMAIL` | `5` | 单个邮箱在窗口内允许的邮件请求数 |
| `SUNSETSCOPE_RATE_LIMIT_WINDOW` | `3600` | 限流窗口秒数 |
| `SUNSETSCOPE_CAPTCHA_TTL` | `300` | 图片验证码有效期秒数 |
| `SUNSETSCOPE_CAPTCHA_ISSUE_LIMIT` | `60` | 单个 IP 每 10 分钟最多获取的验证码数 |
| `SUNSETSCOPE_CAPTCHA_ATTEMPT_LIMIT` | `30` | 单个 IP 每 10 分钟最多验证的次数 |

授权码不得写入源码、README、JSON 数据或 Git。公开部署时，`SUNSETSCOPE_BASE_URL` 必须改成用户可以访问的 HTTPS 域名，否则邮件中的确认链接会指向发件服务器自己的 `127.0.0.1`。

## 启动网页

设置环境变量后，在同一个 PowerShell 窗口运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

打开 <http://127.0.0.1:8000>。

JSON 存储针对轻量单机服务设计，Web 服务必须保持一个 worker。不要将 `--workers` 改为大于 `1`。

验证码完全在本机生成和校验，不依赖外部服务。验证码绑定请求 IP、5 分钟过期且只能验证一次；通过后才会进入邮件发送流程。验证码状态保存在 Web 进程内，因此重启服务后，已打开页面上的旧验证码会失效，刷新图片即可。

## 执行预测检查

```powershell
.\.venv\Scripts\python.exe -m app.jobs --event set --day today
.\.venv\Scripts\python.exe -m app.jobs --event rise --day tomorrow
```

- 当日晚霞：建议每天 `16:50` 执行 `--event set --day today`。
- 次日朝霞：建议前一晚 `23:00` 执行 `--event rise --day tomorrow`。

sunsetbot 公布的 GFS 大更新时间为 `07:30～08:30`、`19:30～20:30`，部分地区在 `13:30` 有小更新；EC 更新时间为 `04:00`、`10:00`、`16:00`、`22:00`。晚霞任务安排在 `16:50`，为 16:00 的 EC 更新留出 50 分钟；朝霞任务安排在前一晚 `23:00`，为 22:00 的 EC 更新留出一小时。

任务输出示例：

```text
queries=2 retries=0 recorded=2 sent=1 below=0 duplicates=1 unavailable=0 errors=0
```

- `queries`：向数据源查询的唯一“地点＋事件＋模型”组合数
- `retries`：首次数据源故障后，等待 5 分钟执行的重试次数
- `recorded`：本次成功写入或更新的每日预测记录数
- `sent`：本次发送数
- `below`：未达到订阅条件的订阅数
- `duplicates`：已经提醒过而跳过的订阅数
- `unavailable`：地点、模型或时段本身暂无预测；不视为数据源故障
- `errors`：数据源或邮件错误数；大于零时命令返回非零退出码

网络或数据源故障会在 5 分钟后重试一次；重试仍失败才向 `SUNSETSCOPE_ADMIN_EMAIL` 发送故障报告。地点本身暂无某模型预测计入 `unavailable`，不会等待或发送故障报告。

建议使用 Windows 任务计划程序、cron 或部署平台按上述两个时点运行。任务具有投递去重，多次运行不会为同一事件日期重复发信。不要在 Web 进程中额外启动定时循环。

Windows 任务计划程序可使用：

```text
程序：D:\workspace\SunsetScope\.venv\Scripts\python.exe
参数（晚霞）：-m app.jobs --event set --day today
参数（朝霞）：-m app.jobs --event rise --day tomorrow
起始于：D:\workspace\SunsetScope
```

环境变量必须配置在任务能够读取的账户或启动脚本中。

## JSON 数据

`data/store.json` 首次提交订阅时自动创建，包含：

- `subscriptions`：邮箱、地点、模型、阈值、确认状态和随机 token
- `deliveries`：已经成功发送的事件，用于去重
- `observations`：每日预测鲜艳度；同一“地点＋事件＋模型＋事件日期”只保留一条，并由更新时次覆盖

`observations` 保存地点、事件日期、模型、鲜艳度、AOD、事件时间、预报时次以及首次/最后记录时间。它记录的是 sunsetbot 的预测值，不是实际观测结果；年度总结时应按模型分别统计，避免把 GFS 与 EC 当作两天数据。

该文件包含邮箱等个人信息，已由 `.gitignore` 排除。备份或迁移时应按敏感数据处理。存储使用跨进程文件锁，允许一个 Web worker 与一个 `app.jobs` 任务安全交错写入；仍不要启动多个 Web worker，也不要让多个 `app.jobs` 任务长期重叠运行。

## 测试

测试只使用 Python 标准库，无需安装 pytest：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 数据来源与使用边界

预测来自 [sunsetbot](https://sunsetbot.top/) 的网页内部接口，并非有版本承诺的公开 API。`app/provider.py` 将外部字段变化隔离在适配层中，应用只查询实际订阅组合并缓存地点联想结果。

长期公开运营前，应取得数据站点许可、限制请求频率，并在邮件和页面中保留数据来源说明。预测仅供观赏参考。
