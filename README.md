# 校园商家 AI 增长助理

校园商家 AI 增长助理是一款面向学校周边小吃店、奶茶店、快餐店等小微商家的本地桌面运营工具。项目使用 PyQt5 + SQLite 实现，主打“老板每天打开软件，就知道今天怎么卖、发什么、复盘什么”。

当前版本是可运行的 MVP Demo，内置“东门小吃铺”示例数据，支持天气经营建议、AI 文案生成、活动策划、数据分析、评论回复和店铺设置。

## 主要功能

- Dashboard
  - 展示今日收入、到店人数、毛利和试用状态。
  - 展示每日日期、城市、实时/演示天气、温度范围、降水概率、风速和动态经营影响。
  - 今日任务支持勾选完成、自定义新增和删除。
  - AI 今日建议会结合天气、菜单套餐、活动和近 7 日经营数据生成。

- 内容生成
  - 支持今日促销方案、微信群文案、朋友圈文案、小红书标题与正文、抖音脚本、海报文案、评论回复、私域复购和会员召回。
  - 未配置 API Key 时自动使用本地 Mock 演示结果。
  - 已在 Prompt 和输出清洗中限制 Markdown / LaTeX 格式，生成结果以可直接复制发送的纯文本为主。

- 活动策划
  - 支持活动目标、主推套餐、发布时间和优惠规则设置。
  - 优惠规则包括立减、满减、折扣、固定套餐价、第二件优惠、赠品、限时券等。
  - 活动方案可保存，并参与后续数据分析和 AI 复盘。

- 数据分析
  - 支持每日收入、食材成本、人工成本、推广成本、优惠成本、其他成本、到店人数和核销数录入。
  - 自动计算总成本、毛利润、毛利率、客单价、单客成本和核销率。
  - 支持近 7 / 14 / 30 天和自定义时间范围统计。
  - 折线图支持鼠标悬停查看日期、指标和具体数值。
  - 支持套餐表现录入和活动/套餐效果对比。

- 评论回复
  - 支持好评、差评、咨询、催单等场景。
  - 差评回复会包含致歉、处理方案和私聊引导。

- 设置
  - 支持店铺基础信息、菜单、套餐、学校与天气、AI API 配置。
  - 支持 DeepSeek、OpenAI 和其他 OpenAI Chat Completions 兼容接口。
  - API Key 加密保存在本机，不在界面明文回显。

## Demo 数据

默认账号：

```text
账号：admin
密码：admin
```

首次启动时，`admin` 会初始化为“东门小吃铺”演示数据：

- 店铺地址：北京市海淀区学院路
- 主营业务：炸鸡、烤肠、饭团、关东煮、饮品
- 单品：香酥炸鸡排、烤肠、饭团、关东煮三件套、柠檬茶、热豆浆
- 套餐：
  - 鸡排柠檬茶套餐
  - 饭团关东煮豆浆套餐
  - 烤肠饭团套餐
  - 关东煮豆浆套餐
- 内置近 7 天收支数据、套餐表现数据、活动记录和今日任务。

如需恢复演示数据，可在“设置 -> 店铺信息”中点击“重置为东门小吃铺 Demo 数据”。

## 环境要求

推荐使用项目指定的 Conda 环境：

```text
DXapp101
```

Python 运行路径示例：

```powershell
D:\Anaconda\envs\DXapp101\python.exe
```

主要依赖包括：

- PyQt5
- requests
- pyqtgraph
- openpyxl
- PyMuPDF
- python-docx
- rapidocr_onnxruntime
- beautifulsoup4
- pytest
- pytest-qt

## 安装依赖

在项目根目录执行：

```powershell
D:\Anaconda\envs\DXapp101\python.exe -m pip install -r requirements.txt
```

如果依赖已安装，可以跳过此步骤。

## 启动软件

推荐直接运行：

```powershell
.\run.bat
```

也可以手动运行：

```powershell
D:\Anaconda\envs\DXapp101\python.exe app.py
```

## AI API 配置

进入“设置 -> AI API 配置”。

DeepSeek 默认配置：

```text
Provider: DeepSeek
Base URL: https://api.deepseek.com
Model Name: deepseek-chat
```

填写 API Key 后点击“测试连接”，成功后保存配置即可。

说明：

- API 接口使用 OpenAI 兼容的 `POST /chat/completions`。
- 未配置 API Key 时，系统使用本地 Mock AI，保证 Demo 可正常演示。
- API 调用失败时，会显示演示模式并回退到本地结果。
- 生成内容会尽量保持纯文本，避免 Markdown / LaTeX 格式。

## 天气说明

默认天气服务预留 Open-Meteo 接口。

Dashboard 支持：

- 刷新实时天气。
- 手动更新天气。
- 根据天气文本、温度、降水概率和风速动态生成经营影响。

例如：

- 雨天：建议热食、热饮、外带包装和提前备餐。
- 高温：建议冷饮、柠檬茶和清爽小吃。
- 降温：建议关东煮、热豆浆和热食套餐。
- 大风：建议提前通过微信群/朋友圈触达，主推快速打包套餐。

## 本地数据位置

应用数据默认保存在当前 Windows 用户的 LocalAppData 目录：

```text
%LOCALAPPDATA%\CampusGrowthAssistant
```

本项目不提供云同步，不会主动上传店铺数据。只有在刷新天气或配置 AI API 后，才会发起对应网络请求。

## 测试

运行全部测试：

```powershell
D:\Anaconda\envs\DXapp101\python.exe -m pytest tests -q
```

当前测试覆盖：

- 默认账号和 Demo 数据初始化。
- 天气经营影响动态变化。
- Prompt 和 AI 输出清洗。
- 今日任务新增、删除和完成状态。
- 财务指标和日期范围过滤。
- 套餐表现数据。
- 活动优惠规则保存。
- 数据分析图表基础逻辑。

## 项目结构

```text
.
├── app.py                         # 程序入口，当前转入 app_v2
├── app_v2.py                      # V2/V2.1 主界面与页面逻辑
├── run.bat                        # Windows 启动脚本
├── requirements.txt               # Python 依赖
├── campus_growth/
│   ├── core.py                    # 基础数据库、用户、设置与加密
│   ├── v2_store.py                # V2 数据模型、迁移、Demo 数据与业务读写
│   ├── ai_service.py              # 统一 AI 调用与 Mock 回退
│   ├── prompt_templates.py        # Prompt 模板
│   └── services/
│       ├── weather.py             # 天气接口、天气标签和经营影响
│       ├── ai_request.py          # OpenAI 兼容 Chat Completions 请求
│       └── calendar_service.py    # 校历文件解析能力
└── tests/                         # 自动化测试
```

## 常见问题

### 1. 没有 API Key 能不能运行？

可以。未配置 API Key 时，软件会进入演示模式，使用本地 Mock AI 生成内容。

### 2. 生成内容里为什么仍可能出现特殊符号？

当前已在 Prompt 和清洗逻辑中禁止 Markdown / LaTeX 常见格式。如果真实模型仍返回异常格式，复制前可以在结果框里手动编辑；后续可继续加强清洗规则。

### 3. 如何重置 Demo？

进入“设置 -> 店铺信息”，点击“重置为东门小吃铺 Demo 数据”。

### 4. 如何切换真实 AI？

进入“设置 -> AI API 配置”，选择 DeepSeek / OpenAI / 其他兼容接口，填写 Base URL、Model 和 API Key，测试连接成功后保存。

