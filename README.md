# MetaTube Plex Plug-ins（个人分支 / sayaxia fork）

Fork 自 [metatube-community/metatube-plex-plugins](https://github.com/metatube-community/metatube-plex-plugins)。

> **上游已长期停更，本仓库不跟随上游更新（不 pull、不 rebase），`main` 就是发布分支。**
> 通用用法、刮削源说明、命名规则仍以上游 Wiki 为准：<https://metatube-community.github.io/wiki/>

---

## 一、这个分支改了什么

**两处功能改动：角标（badge）按文件名后缀自动选图，类型标签（genres）同步判定结果。**

原版只有一个 `Badge URL` 输入框，值是全局的，而且只有「是否中文字幕」一个判定门：

```python
# 原版 __init__.py
badge = Prefs[KEY_BADGE_URL] if Prefs[KEY_ENABLE_BADGES] and chinese_subtitle_on else None
```

后果是 `-U` 结尾的片子永远没角标（`U` 不在词表里），`-UC` 也只能打同一张图。

改后按 `uc > u > c` 三级判定，词元从文件名取（按 `-` `_` 空格 分割、忽略大小写），「中文字幕」还会额外看同目录的裸字幕文件：

| 文件名 / 目录内容 | 判定 | 使用的图 | 预置项 |
|---|---|---|---|
| `ABP-321-UC.mp4`、`ABP-321-C-U.mp4`、`ABP-321-LTX-UC.mp4` | `uc` | `uc.png` 中文字幕+无码 | `badge_url_uc` |
| `ABP-321-LTX.mp4` + 同目录 `ABP-321-LTX.srt` 或 `ABP-321.srt` | `uc` | `uc.png` 中文字幕+无码 | `badge_url_uc` |
| `ABP-321-U.mp4` + 同目录 `ABP-321-U.srt` 或 `ABP-321.srt` | `uc` | `uc.png` 中文字幕+无码 | `badge_url_uc` |
| `ABP-321-U.mp4`、`ABP-321-UNCENSORED.mp4`、`ABP-321-LTX.mp4`、`ABP-321-BASICVSR.mp4` | `u` | `u.png` 无码破解 | `badge_url_u` |
| `ABP-321-C.mp4`、`-ch`、名字含「中文字幕」 | `c` | `zimu.png` 中文字幕 | `badge_url` |
| `ABP-321.mp4` + 同目录 `ABP-321.srt`（裸同名字幕） | `c` | `zimu.png` 中文字幕 | `badge_url` |
| `ABP-321.mp4` + 同目录 `ABP-321.chs.srt` / `.zh-CN.ass` | `c` | `zimu.png` 中文字幕 | `badge_url` |
| `ABP-321.mp4`、`SSIS-001-UHD.mp4`、字幕名对不上 | 无 | 不合成角标 | — |

两个概念先明确，否则容易配错：

- **无码标记**（`UNCENSORED_TAGS`）：`U`、`UNCENSORED`、`LTX`、`BASICVSR`、`BASICVSR++`。`LTX` 与 `BasicVSR++` 是 AI 修复马赛克的产物，`UNCENSORED` 是 `U` 的全拼，这五个词元都等同无码；但 `-UHD` 里的 `UHD` 表示分辨率，**不算**无码。
- **裸同名字幕**（`has_bare_subtitle()`）：同目录存在与视频同名、且**不带任何语言标记**的字幕，如 `ABP-321.mp4` 旁的 `ABP-321.srt` / `.ass` / `.sub` / `.vtt`（白名单 `ass / srt / ssa / smi / sub / psb / vtt`；`.txt` 与 `.idx` **故意排除**——前者常被用作说明/磁力/密码文件，后者必须配 `.sub` 才有意义，而 `.sub` 本身已在白名单内；忽略 `.nfo`，跳过 `.` `~` 开头的隐藏文件）。JAV 库里这类字幕基本都是中文，所以直接计入「有中文字幕」。带语言标记的 `ABP-321.chs.srt` 走另一条正则（`chs/chi/cht/zh/zho/zh-CN...`），两条都支持。
- **字幕名可以只写裸番号**（`subtitle_name_candidates()`）：匹配时会逐级剥掉尾部的 `-U` / `-LTX` / `-UC` / `-C` / `-BasicVSR`，所以 `ABP-321-LTX.mp4` 配 `ABP-321.srt` 或 `ABP-321.chs.srt` 同样算命中，不必把后缀抄进字幕名。反向不成立：`ABP-321.mp4` 不会被 `ABP-321-U.srt` 影响。

判定只用**视频所在目录**，不看 `Plex Support/Subtitles` 全局目录；文件名词元判定不需要文件系统，裸字幕判定需要路径可读（Plex 容器挂载对不上时自动降级为「无」）。

改动文件（4 个）：

| 文件 | 改动 |
|---|---|
| `MetaTube.bundle/Contents/Code/utils.py` | 新增 `get_badge_type()` / `get_badge_name()` / `has_bare_subtitle()` / `get_type_tags()` 与 `BADGE_TYPE_*`、`UNCENSORED_TAGS` 常量 |
| `MetaTube.bundle/Contents/Code/constants.py` | 新增 `KEY_BADGE_URL_U` / `KEY_BADGE_URL_UC` 与 `KEY_TYPE_TAG_*`、`TYPE_TAG_*` 文案常量 |
| `MetaTube.bundle/Contents/Code/__init__.py` | 先收集 `video_files` 算一次 `badge_type`，既用于 `?badge=` 也用于写 genres |
| `MetaTube.bundle/Contents/DefaultPrefs.json` | 新增两个 text 项，默认 `u.png` / `uc.png` |

提交：`064ef8c Feature: per-type badge (C / U / UC) selected by filename`，后续 `feat: -LTX / bare subtitle badge rules`。

### 后续修复（2026-11）

角标规则本身没变，改的是它在真实 Plex 环境下的存活能力。四个都是实测撞出来的：

| 现象 | 根因 | 修复 |
|---|---|---|
| 换完 bundle 后 Plex 里**完全看不到**这个刮削器，也没报错 | Plex 用 RestrictedPython 编译插件代码，**任何以下划线开头的标识符都会在编译期 SyntaxError**，`import utils` 跟着失败，整个 bundle 加载不起来。前端表现就是「目录里明明有，Plex 不认」 | 模块级变量与临时变量全部去掉前导下划线（`TEXT_TYPE` 而非 `_TEXT_TYPE`）；`_ = review.title` 这类占位赋值也删掉 |
| 角标全部不出现，日志 `global name 'any' is not defined` | Plex 沙箱的 `builtins` 被裁剪，没有 `any()`，也没有 `bytes()` | 无码词元判定改成显式 for 循环；str/bytes 判定改用 `sys.version_info` 分支，不做 `NameError` 探测 |
| 一部片有两个版本（`X.mp4` + `X-UC.mp4`），角标却判成「中文字幕」 | 「有中文字幕」原先作为**整条 item 的全局标记**传给每个文件：先遍历到普通版，因兄弟文件带字幕被判成 `c`，`-UC` 那份的标记反而被吃掉 | `get_badge_type_from_files()` 改成逐文件判定，`chinese_subtitle_on` 只对该文件成立时才作为 hint 传入 |
| 刷新后封面还是旧图 | 见下 |  |

**关于封面**：Plex 把海报的 `ratingKey` 定为图片 URL 的 `sha1`，并且**同一 URL 重复提交会被静默跳过**。加上海报容器在 PMS 1.40 上是 append-only（`posters.clear()` 没有这个方法、`validate_keys()` 空转、`del posters[k]` 只清内存、`DELETE /poster` 返回 404、`metadata.thumb` 不可写），插件在 `update()` 期间又拿不到新海报的 `ratingKey`（它要等 update 返回后才生成）。

所以本分支**只提交当前图、不尝试清理旧候选**，这是唯一不会越改越乱的行为。想把封面钉到最新那张，需要在刷新完成后从外部调：

```bash
PUT /library/metadata/{ratingKey}/poster?url=<url-encoded ratingKey>
```

每提交一次就多了张候选，只有角标真的变了（比如 `-U` 改成 `-UC`）才会多一张，需要时清一次即可。

---

## 二、安装

从 [Releases](https://github.com/sayaxia/metatube-plex-plugins/releases) 下载并解压到 Plex 的 `Plug-ins` 目录，然后**重启 Plex**：

| 环境 | 路径 |
|---|---|
| Docker / 群晖容器 | `/config/Library/Application Support/Plex Media Server/Plug-ins/` |
| Windows | `%LOCALAPPDATA%\Plex Media Server\Plug-ins\` |
| macOS | `~/Library/Application Support/Plex Media Server/Plug-ins/` |

- `MetaTube.bundle.zip` —— 必需，刮削 agent（`com.plexapp.agents.metatube`）
- `MetaTubeHelper.bundle.zip` —— 可选，把外挂字幕挂进 Plex（`find_local_subtitles`）

解压后目录层级必须是 `Plug-ins/MetaTube.bundle/Contents/...`，别多套一层。

---

## 三、设置项

管理 → 插件 → MetaTube → 高级：

| 设置项 | 默认值 | 说明 |
|---|---|---|
| Enable badges | 关 | 角标总开关 |
| Badge URL (Chinese subtitle) | `zimu.png` | `-C` 档；装本分支后**要改回 `zimu.png`**，旧版残留的 `u.png` 会让中字片显示无码 |
| Badge URL (Uncensored) | `u.png` | `-U` 档（新增） |
| Badge URL (Chinese subtitle + Uncensored) | `uc.png` | `-UC` 档（新增） |
| Enable type tags | 开 | 把判定结果写成 Plex「类型」标签（genres） |
| Type tag: Chinese subtitle | 空 = `中文字幕` | 想改成「中字」就填这里 |
| Type tag: Uncensored | 空 = `无码破解` | `-U` / `-LTX` / `-UNCENSORED` 用 |
| Type tag: extra for UC only | 空 = 不加 | 填 `中文无码` 则 UC 额外多一个标签 |

填裸文件名（`u.png`）走**服务端内嵌素材**，零网络开销；填 `https://...` 外链则由服务端抓取并缓存 30 分钟、容量 10。

> ⚠️ 服务端必须带这三张内嵌图（`metatube-sdk-go` 的 `imageutil/badge/`，v1.4.0 起就有）。
> 服务端**没有**对应素材时，`badge.Badge()` 会因抓取失败直接报错，整张海报请求失败，Plex 只会保留旧图 —— 表现就是「改了设置但海报没变」。

### 类型标签（genres）

详情页那行「姐姐 / 中文字幕 / 4K …」= `metadata.genres`，来源有三层：

1. **provider 返回的 genres**（javbus 抓的分类，如 `お姉さん`→姐姐、`ハイビジョン`→高清、`4K`），开启了翻译就按翻译结果显示；
2. **本插件追加**：`中文字幕`、`无码破解`（由 `get_type_tags()` 按角标规则生成）；
3. **Genre substitution 表**：可选，把日文分类替换成你想显示的字。

标签是与角标**共用一套判定**但相互独立：关掉 `Enable badges` 仍会有类型标签，反之亦然。UC 片默认拿「中文字幕 + 无码破解」两个标签（正交，方便筛选时「中文字幕」能覆盖 UC 片）；想要独立的「中文无码」标签，把 `Type tag: extra for UC only` 填上即可。

标签只在**刮削/刷新时**写入，改完设置同样需要 Refresh Metadata。

---

## 四、让角标生效 / 排错

角标是**刮削那一刻**由插件向服务端请求合成、再把结果写进 `metadata.posters` 的，不是每次浏览实时叠加。

| 现象 | 原因 |
|---|---|
| 高级设置里只有一个 `Badge URL` 框 | 装的还是原版，不是本分支 |
| 换了 bundle 但设置没变 | 没重启 Plex（DefaultPrefs 只在启动时合并） |
| Plug-ins 里有目录，但 Plex 里找不到这个刮削器 | 代码编译失败：`Logs/PMS Plugin Logs/com.plexapp.agents.metatube.log` 里会有 `SyntaxError`（最常见原因是标识符以 `_` 开头），修掉才会被加载 |
| `-U` / `-UC` 老片没变化 | 没重新刮削：右键 → Refresh Metadata，或重新 Match；刷新时选「替换全部」 |
| 角标很小一块 | 服务端把整块 1000×1000 画布缩到海报高度 1/5，丝带只占画布 31%，视觉宽度约海报高 6%，属正常 |
| 海报直接不显示 | 服务端拉外链超时/404，或用了不存在的图名 |
| 一部片有 `X.mp4` + `X-UC.mp4` 两个版本，角标只对应其中一版 | Plex 一个 movie 只有一张海报、一个角标；两个版本共用一个条目 id 时，角标必然只能表示其中一个。要么拆成两条，要么只保留一个版本 |

判定仍然**只看文件名**：不探测内嵌字幕轨。文件名干净但内嵌中字的片子不会打标（Plex 老式 agent 阶段拿不到可靠的流信息）。

---

## 五、构建 / 发布

`.github/workflows/release.yml`，格式与上游一致：

- 触发：push 到 `main` 且命中 `*.bundle/**` 或 workflow 文件；也可手动 `workflow_dispatch`
- 版本号：`v$(date -u '+%Y.%-m%d.%-H%M.0')-<shortsha>`，同时写入 bundle 内的 `VERSION` 文件（LICENSE 一并拷入）
- 产物：`MetaTube.bundle.zip`、`MetaTubeHelper.bundle.zip`
- Release：滚动 tag `bundle`，`prerelease: false`

本地手动打包（与 CI 等价）：

```bash
cp LICENSE MetaTube.bundle/ && cp LICENSE MetaTubeHelper.bundle/
echo v0.0.0-dev > VERSION
cp VERSION MetaTube.bundle/ && cp VERSION MetaTubeHelper.bundle/
zip -r MetaTube.bundle.zip MetaTube.bundle/
zip -r MetaTubeHelper.bundle.zip MetaTubeHelper.bundle/
```

---

## 六、维护备忘（写给未来的自己）

- **运行环境是 Python 2.7**（Plex Framework 2）。不能写 f-string、`pathlib`、py3 专属语法；`localmedia.py` 里还在用 `has_key()`，别顺手“现代化”。
- Plex 侧可用对象：`Agent.Movies` / `metadata` / `media` / `Prefs` / `Proxy` / `Log`；本地调试靠 `plexhints`（未安装时走 else 分支导入）。
- 改完必须自测：`utils.get_badge_type()` 对 `-C / -U / -UC / -LTX / -UHD` 等样例的判断，可用桩模块绕过 `constants.py` 对 `plexhints` 的依赖。
- 已知但未修的问题（上游遗留）：`requests.Session` 无 timeout；`translate_text` 在全局锁内 `sleep(1s)`；演员头像逐个请求 Gfriends（N+1）；`score * 2.0` 隐含 5 分制假设。
- 关联仓库：服务端镜像用 [sayaxia/metatube-sdk-go](https://github.com/sayaxia/metatube-sdk-go)（含 LTX 后缀归一化 + 三张内嵌角标）。

---

## 七、许可

沿用上游 [LICENSE](./LICENSE)（MIT）。`MetaTube` 名称与原始代码版权归 metatube-community 所有。
