# bilibili-fast-assistant

给 B 站的番剧 / 国创批量「点赞 / 投币 / 收藏」的桌面小工具，Python 3.12 + Flet。

> 目前「国创」和「番剧」两个分区已经能用：搜索 → 详情 → 选集 → 执行三连。
> 两边共用同一套 PGC 管线，只是靠 ``season_type`` 区分分区。

## 当前进度

已完成：

- 顶部分区栏：国创 / 番剧
- **扫码登录**：手机哔哩哔哩扫一下即可，不需要输入账号密码
- 登录后顶部显示**硬币余额**（替代原来的标语），并缓存昵称与头像
- 国创 / 番剧搜索，支持两种方式
  - **精准空降**：粘贴 BV / av / ep / ss 链接或 `b23.tv` 短链，只出 1 张卡片
  - **模糊搜索**：输入名字关键词，出多张卡片
  - 结果以卡片列表渲染（封面、评分、更新进度、地区 / 风格）
- 点击卡片进入详情：该作品的所有季 + 每一季的所有集 + 篇章分组
- 点赞 / 投币 / 收藏 选择器（投币支持像 B 站那样选 1 个还是 2 个）
- **逐集执行**：按集列出每个操作的状态框

状态框只有颜色变化，没有动画：

| 状态 | 样子 |
| --- | --- |
| 用户没勾这个操作 | 淡灰 |
| 排队中 | 普通白框 |
| 请求中 | 浅粉 |
| 之前已经操作过 | 粉色框线（不重复执行） |
| 成功 | 整框粉色 |
| 失败 | 整框红色 |

### 执行是怎么跑的（以及怎么防止被限流）

- **串行**：单线程、一集做完才做下一集，任何时刻只有一个请求在飞
- **先查后做**：动手前先看这一集有没有操作过，做过就标成"无需操作"，不重复请求
- **查不到就不做**：状态查询失败时跳过这一集，绝不"盲投"（投币是真扣硬币的）
- **三重限速**：
  1. 任意两次写请求之间至少间隔 0.7 秒，避免一集的三条请求挤成突发
  2. 每集之后额外停顿 0.8 秒 + 随机抖动，节奏不规律
  3. 一旦撞上风控就自动降速（间隔翻倍），**连续 3 次风控直接整批停下**
- 失败原因写入 `~/.config/bilibili-fast-assistant/failures.log`

## 关于登录

**不会让用户输入账号密码**，用的是 B 站官方的扫码登录：

1. 点右上角「扫码登录」，本地生成二维码
2. 用手机哔哩哔哩扫一下、在手机上点确认
3. 登录成功后 B 站下发 Cookie，我们只取其中必要的几个存到本机

几点说明：

- **不经过任何第三方服务器**。二维码是在本机用 `qrcode` 画的，
  登录请求直接发给 `passport.bilibili.com`，凭据直接写本地文件。
- 凭据文件在用户配置目录（Linux 是 `~/.config/bilibili-fast-assistant/credentials.json`），
  权限 `600`，只存 Cookie，不存账号密码。想退出登录点一下「退出」就会删掉。
- 为什么不用开放平台的 OAuth？开放平台的 `access_token` 只对开放平台自己的接口有效，
  而点赞 / 投币 / 收藏这些 Web 接口只认 Cookie（`SESSDATA` + `bili_jct`），
  两套凭证互不相通。

## 运行

```bash
# 安装依赖
uv sync

# 桌面模式
uv run flet run

# 或者
uv run bilibili-fast-assistant
```

> 首次运行 Flet 会准备桌面运行时，需要等一会儿。

### 以 Web 方式运行

```bash
# 浏览器里打开，默认监听 0.0.0.0（局域网可访问）
uv run flet run --web -r

# 只想本机访问
uv run flet run --web --host 127.0.0.1 -p 8550
```

## 目录结构

```
src/bilibili_fast_assistant/
├── config.py              # 接口地址、UA、超时等常量
├── theme.py               # B 站粉 + 白的配色与尺寸
├── main.py                # Flet 入口
├── assets/
│   └── icon.png           # 应用图标（由 tools/make_icon.py 生成）
├── api/                   # 所有网络请求
│   ├── http.py            #   统一 httpx 客户端（UA / Referer / 错误码）
│   ├── wbi.py             #   WBI 签名（搜索接口必须要）
│   ├── errors.py          #   异常类型与错误码文案
│   ├── search.py          #   搜索通道与 WBI 签名调用
│   └── bangumi.py         #   番剧 / 影视接口
├── models/                # 结构化数据
│   ├── bangumi.py         #   SearchCard / Episode / ArcGroup / SeasonDetail
│   └── actions.py         #   三连选择状态
├── services/              # 业务逻辑
│   ├── input_parser.py    #   把用户粘贴的东西解析成统一输入
│   ├── resolver.py        #   直达链接 -> season_id
│   ├── partition.py       #   两个分区的规则
│   ├── catalog.py         #   原始 JSON -> SeasonDetail（含篇章还原）
│   └── search_service.py  #   统一搜索入口
└── ui/
    ├── app.py             # 外壳：分区栏 + 内容区 + 导航
    ├── images.py          # 图片地址处理（CDN 缩略参数）
    ├── components/        # 卡片、状态占位、三连选择器
    └── views/             # 搜索页、详情页
```

## License
This project is licensed under the MIT License. See LICENSE for details.
