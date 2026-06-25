# 校园商家 AI 增长助理 V2

面向学校周边小吃店、奶茶店和快餐店老板/店长的本地 PyQt 商家运营后台。V2 使用暖橙 SaaS 风格工作台，围绕天气、附近学校节点、菜单套餐、AI 内容和收支复盘提供可演示的完整闭环。

## 启动

```powershell
D:\Anaconda\envs\DXapp101\python.exe -m pip install -r requirements.txt
.\run.bat
```

也可以运行：

```powershell
D:\Anaconda\envs\DXapp101\python.exe app.py
```

默认账号：`admin` / `admin`。

首次启动 V2 时，`admin` 会一次性初始化为“东门小吃铺”Demo：北京市海淀区学院路、3 所附近学校、6 个单品、4 个套餐、6 个今日任务和 7 天收支数据。之后录入的数据不会被自动重置；设置页提供“重置为东门小吃铺 Demo 数据”操作。

## 功能

- Dashboard：天气影响、附近学校节点、可完成今日任务、AI 今日建议。
- 内容生成：促销方案、微信群、朋友圈、小红书、抖音、海报、评论回复、私域复购和会员召回；无 API Key 时使用完整 Mock 演示结果。
- 活动策划：选择客流目标、套餐、优惠和发布时间，生成可保存的活动方案。
- 数据分析：每日收入/成本 CRUD、毛利/客单价/核销率计算、近 7 日趋势和活动效果图、AI 复盘。
- 设置：店铺资料、菜单套餐、学校事件、天气服务预留、DeepSeek/OpenAI/兼容 API 配置。

## AI 配置

设置页默认提供 DeepSeek 预设：

- Provider：DeepSeek
- Base URL：`https://api.deepseek.com`
- Model：`deepseek-chat`

填写 API Key 后点击“测试连接”。Key 使用 Windows DPAPI 加密保存且不会在界面回显。未配置 Key 或接口失败时，界面明确显示演示模式并回退到本地 Mock AI。

## 数据位置与测试

本地数据默认保存在 `%LOCALAPPDATA%\CampusGrowthAssistant`。项目不会写入或上传店铺数据到第三方服务；只有启用天气刷新或配置 AI 后才会发起网络请求。

```powershell
D:\Anaconda\envs\DXapp101\python.exe -m pytest -q
```
