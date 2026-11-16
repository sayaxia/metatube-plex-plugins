# AGENTS.md — MetaTube Plex 插件（LTX fork）

> **任何智能体在改这个仓库之前，必须先读完本文件。**
> 改完之后必须同步更新本文件里受影响的部分，并在 [`AGENT_LOG.md`](AGENT_LOG.md) 追加一条记录。
>
> 最后更新：2026-11-16 · 维护者：SAYA

---

## 0. 当前状态（开工前先看）

| 项 | 状态 |
|---|---|
| 分支 / 远端 | `fork/main` = `5c494de`（对应最新 Release `v2026.1116.1517.0-f1acd5f`）；本地 `main` 领先若干提交（自 `7c0b7e9` 三层保底起，含文档修正），**均未推送**。具体 HEAD 以 `git log -1` 为准 |
| 工作区 | **干净**，无未提交改动（此前那批「未提交未部署」的改动已提交并上线） |
| 线上 Plex | **已热修上线**：`Contents/Code` 的 5 个文件 + `DefaultPrefs.json` 与 HEAD 逐字节一致（2026-11-16 23:54 覆盖，备份后缀 `.bak.20261116_2354`） |
| 与远端差 | 本地领先 `fork/main`（`5c494de`），**尚未 push、未触发新 Release** |

开工提醒：

- 线上代码与 HEAD 已一致；动手前先 `git diff` / 跑一次 §5，确认没有反向差异或工作区残留。
- 线上 bundle 根目录的 `VERSION`（内容 `v2026.1107.1841.0-61d83ea`）和 `LICENSE` 是 11-07 整包安装的遗留标记，**不代表当前线上版本**；判断线上版本一律以 `Contents/Code` 文件内容比对为准（比对脚本见仓库外 `temp/compare_bundle.py`）。
- 文件名/番号类真实数据不得进提交（README 里的日志示例已用 `<番号>` 占位）。

---

## 1. 这是什么

Plex 影视元数据代理插件（`MetaTube.bundle`），从 MetaTube 服务端刮削番号信息，并负责：

- 番号识别与文件名解析（含 `-LTX` / `-U` / `-UC` / `__restored` / `-BasicVSR++` 等工具后缀）
- 海报角标（`u` / `uc` / `zimu`）+ 类型标签（无码破解 / 中文无码）
- 中文翻译（多引擎，百度系含 nmt / llm 两种模型）
- FC2 合集归组、字幕判定、多版本文件处理

服务端是本工作区里的 `metatube/` 仓库（fork），两者**API 契约耦合**，改一边要确认另一边。

---

## 2. 铁律（不可协商）

1. **Plex 的 RestrictedPython 会拒绝模块级下划线命名。** 任何**模块级变量/函数名不能以 `_` 开头**
   （`__init__` 等 dunder 除外），否则整个 bundle 启动即报
   `SyntaxError: "_XXX" is an invalid variable name`，插件直接消失。
   `py_compile` **查不出这个错**，改完必跑 `scripts/check_plex_sandbox.py` 和 `_subrule/test_badge_rule.py`。
2. **插件运行在 Python 2.7。** 禁止 f-string、海象运算符、`print()` 当函数以外的 py3-only 语法
   （dict/set 推导式在 2.7 可用）。本机没有 py2，只能靠 `py_compile`（py3）+ 人工审查。
3. **`DefaultPrefs.json` 的枚举值只能追加到末尾。** Plex 按**索引**保存用户选择，插到中间会让
   已保存的设置错位。新增 bool/文本项追加到数组末尾。
4. **不擅自 push / 发版。** 本地 commit 可以；推 GitHub、触发 Release 必须先拿到明确同意。
   注意远端：`origin` 是上游（只读），**推 `fork`**。
5. **提交前脱敏。** 真实番号、内网 IP/主机名、含用户名的绝对路径、密钥 一律不进提交内容。
6. **不打印密钥。** 翻译凭据存在 Plex 偏好与参数表里；调试日志只打"字段是否存在"，不打值。
7. **改完必须验证**（见 §5），验证没过不许说"完成"。
8. **一个改动一个主题。**
9. **临时文件只放 `C:/Script/metatube/temp/`。** 排障、试运行、一次性脚本、日志 dump、截图、
   验证产物，一律写到这个目录；**不要写进仓库、不要放桌面**。用完确认「确实需要保留」的，
   再挪进项目里合适的位置（脚本进 `scripts/`、回归测试进对应测试目录）。**每次 push 前清一遍 temp**，
   确认过期的直接删——仓库里出现临时文件同样算不合格（见验证清单）。
10. **本地 README 与 GitHub README 严格分开。** 每轮改动记在仓库外的
    `C:/Script/metatube/本地README.md`（**绝不上传 GitHub**，也禁止 `git add -f` 强加）。
    GitHub 的 `README*.md` / `FORK.md` 只写**成品当前真实具备的能力**；本地加过又删掉的功能、
    试过又否掉的方案、事故复盘一律**不进** GitHub README，只在本地 README 留一条
    「加了什么 / 为什么撤 / 撤到哪儿」。

---

## 3. 仓库与分支

| 项 | 值 |
|---|---|
| 工作目录 | `C:/Script/metatube/metatube-plex-plugins` |
| `origin` | `metatube-community/metatube-plex-plugins`（**上游，只读**） |
| `fork` | `sayaxia/metatube-plex-plugins`（**推这里**） |
| 分支 | `main`（当前跟踪 `origin/main`，push 时显式写 `fork main`） |
| 已发布版本 | 最新 Release `v2026.1116.1517.0-f1acd5f`（对应 `f1acd5f`，`MetaTube.bundle.zip` 646.2 KB）；本地 `7c0b7e9` 领先且**未推送** |

**目录布局**（`C:/Script/metatube/` 下）：

```
metatube-server-ltx/     本仓库（服务端）
metatube-plex-plugins/   Plex 插件仓库（姊妹项目）
_tools/                  build-win.sh 构建脚本、metatube-win/ exe 运行时、_subrule/ 离线回归测试
temp/                    临时目录：排障/试运行产生的脚本、dump、截图全放这里（不放仓库内）
```

**发版机制**：push 到 main 且改动命中 `*.bundle/**` 或 `scripts/check_plex_sandbox.py` 时，
`release.yml` 自动打 tag `vYYYY.MMDD.HHMM.0-<sha>` 并发布 Release（zip 包）。一个提交一个 Release。

---

## 4. 目录地图

```
MetaTube.bundle/
├── Contents/
│   ├── Code/
│   │   ├── __init__.py      Agent 主体：Start/ValidatePrefs/MetaTubeAgent（search/update）
│   │   ├── api_client.py    与服务端 HTTP 通信
│   │   ├── constants.py     所有常量与偏好键名（KEY_*）
│   │   ├── provider_id.py   provider 标识
│   │   ├── translator.py    翻译层：引擎选择、降级、翻译记忆(L3)、llm 兜底
│   │   └── utils.py         文件名词号解析、角标类型判定、字幕判定、译文校验(L1)
│   ├── DefaultPrefs.json    偏好项（枚举只能追加末尾）
│   ├── Info.plist           bundle 元信息
│   └── Libraries/Shared/    内嵌第三方库（certifi/chardet/requests…，不要手改）
MetaTubeHelper.bundle/       辅助 bundle
scripts/check_plex_sandbox.py  RestrictedPython 命名检查（CI 前置）
```

关键函数索引：

| 位置 | 职责 |
|---|---|
| `utils.parse_filename` / `get_badge_type` | 文件名 → 番号 / 角标类型 |
| `utils.looks_translated` | L1 译文校验：假名占比、垃圾中文、长度异常 |
| `translator.translate_text` | 翻译主入口：L2 引擎降级 + L3 翻译记忆 |
| `translator.follow_up_engines` / `engine_parameters` | 备用引擎顺序与参数表 |
| `translator.try_llm` / `llm_budget` | 大模型兜底（**仅限标题被判污染**，受累计字符上限约束） |
| `translator.baidu_llm_switch` | 百度 nmt / llm 模型开关（读偏好，缺键安全回退） |
| `__init__.MetaTubeAgent.search/update` | 刮削与写回 Plex |

---

## 5. 验证清单（提交前必跑）

```bash
# 语法（py3 解释器，仅语法层）
python -m py_compile MetaTube.bundle/Contents/Code/*.py

# RestrictedPython 命名检查（AST，能抓 py_compile 抓不到的下划线变量）
python scripts/check_plex_sandbox.py            # 另可用 --self-test 自检

# 角标 / 字幕 / 翻译三层保底 回归测试（不依赖 Plex、不联网）
python C:/Script/metatube/_tools/_subrule/test_badge_rule.py         # 75 项，含静态扫描
python C:/Script/metatube/_tools/_subrule/test_translation_rule.py   # L1/L2/L3 共 30 项
python C:/Script/metatube/_tools/_subrule/test_subtitle_rule.py
```

`_subrule/` 在 `C:/Script/metatube/_tools/_subrule`（不在仓库内），是这三个 bundle 逻辑的离线回归测试。
改了角标/翻译规则却不动测试，等于没改。

**push 前另清一遍 `C:/Script/metatube/temp/`**：排障脚本、日志 dump、截图、一次性验证产物只放那里，
过期即删；确认要长期保留的再挪进仓库（脚本进 `scripts/`、回归用例进 `_tools/_subrule`）。

---

## 6. 部署到 Plex（热修流程）

线上插件目录（SMB 共享，实际主机名见本地交接文档）：

```
\\<NAS-A>\Plex\...\Plug-ins\MetaTube.bundle\Contents\Code\
```

步骤：

1. **先备份**：把要覆盖的文件复制成 `<文件名>.bak.<YYYYMMDD_HHMM>` 放在同目录
   （历史备份命名示例：`translator.py.bak.20261112_2355`）。
2. 复制新文件过去（只覆盖改动的文件，不要整个目录 rsync 覆盖，避免带上 `__pycache__`）。
3. **重启 Plex 插件**才生效：改 `DefaultPrefs.json` 的枚举/新增偏好项必须重启 Plex 进程，
   只 reload 插件不够。
4. 验证：Plex 日志里搜 `MetaTube`，确认没有 `Exception starting plug-in`；偏好界面能看到新开关；
   拿一个条目手动刷新，确认标题/简介是中文。

⚠️ 热修是**应急手段**：改完必须回到仓库补提交，否则线上与仓库分叉。
2026-11-16 那批「三层翻译保底」已按这个流程走完（补提交 `7c0b7e9` + 覆盖 5 个文件 + 重启 Plex），
线上与 HEAD 一致；以后再热修照同一套走，并在 `AGENT_LOG.md` 写清备份后缀与验证命令。

---

## 7. 与服务端的契约

| 插件调用 | 服务端接口 | 备注 |
|---|---|---|
| 搜索/详情 | `/v1/movie/search`、`/v1/movie/{provider}/{id}` | provider 名要存在于服务端 |
| 翻译 | `/v1/translate` | 参数表里的 `baidu-model-type` 等原样透传 |
| 角标素材 | 服务端内嵌 `imageutil/badge/` 三张图 | 服务端缺素材时整张海报请求失败，Plex 保留旧图 |

服务端 `v1.4.0` 起才带角标内嵌图；服务端必须用 `-tags experimental` 构建才有实验池 provider。

---

## 8. 已知坑

- **翻译额度是硬约束**：额度耗尽后旧逻辑会把日文原文写回 Plex（2026-11-12 事故，2889 条被覆盖）。
  这就是三层保底存在的原因，不要简化掉 L1 校验。
- **假名比例阈值**：日文标题里也有汉字，不能靠"有没有汉字"判断；当前规则是"含假名必翻"。
- **角标依赖文件名**：角标由文件名后缀推导，改规则要同步 `test_badge_rule.py`。
- **同番号双版目录**会让整目录改名 SKIP（重名冲突），属正确行为。
- **多版本**：`C` / `UC` / `U` / `LTX` 大概率互斥，优先级 `LTX > UC > U > C > 无后缀`；
  判断冗余前先比码率，被删方码率更高要降级为"人工确认"。
- **Plex 会缓存插件代码**：覆盖文件后若行为没变，重启 Plex 而不是反复改代码。

---

## 9. 文档更新义务

| 改了什么 | 必更文档 |
|---|---|
| 任何改动 | `AGENT_LOG.md` 追加一条 |
| 新增/修改偏好项 | 本文件 §2/§4、`README.md` 偏好说明、`DefaultPrefs.json` |
| 角标 / 番号 / 字幕规则 | 本文件 §8、`README.md` 规则表、`_subrule/` 对应用例 |
| 翻译逻辑 | 本文件 §4/§8、`README.md` 翻译章节、`_subrule/test_translation_rule.py` |
| 部署方式、发版流程 | 本文件 §3/§6 |
| 每轮完整改动、试过又撤掉的方案 | 仓库外 `C:/Script/metatube/本地README.md`（**绝不提交**） |

---

## 10. 多智能体协作规则

- **开工前**：`git status --short` + `git diff --stat` → 读 `AGENT_LOG.md` 最后 3 条。
  这里经常有别人未提交的改动，务必先看清。
- **禁止** `git add -A` / `git checkout .` / `git reset --hard` / `git stash`。
- 提交只加自己改的文件，提交信息用 `feat/fix/docs(scope):` 前缀。
- 与服务端仓库联动改动时，两边 `AGENT_LOG.md` 都要记，并互相引用 commit 号。
