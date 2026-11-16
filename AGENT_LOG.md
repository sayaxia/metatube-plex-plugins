# AGENT_LOG — MetaTube Plex 插件（LTX fork）

**追加式日志。任何智能体改完代码，都要在文件末尾追加一条，不删改旧条目。**

- 一条记录 = 一次完整改动（一个主题）。
- 字段固定：改动 / 文件 / 验证 / 部署·发版 / 待办·风险。
- 日志里**不写**真实番号、内网 IP、密钥值、含用户名的绝对路径。

格式模板：

```markdown
## YYYY-MM-DD HH:MM · <智能体名> · <一句话标题>
- 改动：
- 文件：
- 验证：
- 部署/发版：
- 待办/风险：
```

---

## 2026-11-15 21:04 · WorkBuddy · 中文元数据三层保底（未提交、未部署）

- 改动：
  - L1 结果校验 `utils.looks_translated()`：假名占比 >15% 判未翻译、页面残渣判污染、长度异常判失败；2%~15% 假名（人名）放行但记日志。
  - L2 引擎降级 `translator.follow_up_engines()`：主引擎失败或译文不合格时按 `translation_fallback_engines` 顺序换引擎，凭据从"引擎名.参数=值"表取。
  - L3 翻译记忆 `translator.tm_*`（`Core.storage` 下 `translation_memory.json`）：成功译文永久复用，断网/额度耗尽不再写日文，上限 4000 条、单条 800 字、20s 批量落盘。
  - 大模型兜底 `translator.try_llm()`：**仅**在标题被 L1 判"污染"时使用，受 `translation_llm_budget` 累计字符上限约束（一次性池、不恢复）。
  - 失败分类：网络/额度类只换备用引擎，绝不消耗 llm 池；只有"返回垃圾中文"才升级到 llm。
  - 百度 AI 双模型：偏好项 `translation_baidu_llm` 选 nmt / llm，显式 `baidu-model-type` 参数优先。
- 文件：
  `MetaTube.bundle/Contents/Code/{__init__.py,constants.py,translator.py,utils.py}`、
  `MetaTube.bundle/Contents/DefaultPrefs.json`、`README.md`；
  回归测试 `<工作区>/_subrule/test_translation_rule.py`（30 项）。
- 验证：`test_translation_rule.py` 30 项全过；`test_badge_rule.py` 75 项全过；
  `check_plex_sandbox.py` 通过；`py_compile` 通过。
- 部署/发版：**没有**。线上（NAS Plex）仍是 2026-11-12 的热修版，
  `translator.py` 线上 3.2 KB / 本地 13.8 KB。未提交、未推送、未部署。
- 待办/风险：
  - 这 6 个文件的改动还在工作区，等用户决定提交与部署时机。
  - 部署后要观察翻译失败率与 llm 池消耗，确认不再出现"中文被日文覆盖"。

---

## 2026-11-12 23:53 · WorkBuddy · 百度 AI 双模型热修（已部署到 NAS）

- 改动：给 baiduai 引擎加 nmt/llm 切换开关，旧 `Preferences` 文件缺键时安全回退到机翻，不让 KeyError 打断翻译。
- 文件：`constants.py`（`KEY_TRANSLATION_BAIDU_LLM`）、`translator.py`（`baidu_llm_switch()`）、
  `utils.py`（`resolve_model_type()`）、`DefaultPrefs.json`（布尔项追加到末尾）。
- 验证：`py_compile` + 沙箱检查 + Plex 偏好界面能看到开关。
- 部署/发版：**已热修到 NAS**（每个文件留有 `.bak.20261112_2355` 备份），未提交、未推送。
- 待办/风险：热修与仓库分叉，需并入正式提交（`b70e3a7` 已包含这部分，但未推送）。

---

## 2026-11-08 · WorkBuddy · Plex 沙箱命名修复 + 角标规则

- 改动：`_subrule`/正则助手等模块级下划线命名改为非下划线，修复 `SyntaxError: "_XXX" is an invalid variable name`；角标判定支持叠加工具标记与点号分隔；`-U`/`-LTX`/`_LTX`/`__restored`/`-BasicVSR++` 统一按无码破解处理；FC2 全部归入 `FC2` 合集。
- 文件：`utils.py`、`constants.py`、`__init__.py`、`scripts/check_plex_sandbox.py`（新增）。
- 验证：`test_badge_rule.py` 75 项全过；`check_plex_sandbox.py --self-test` 通过；CI Verify 通过。
- 部署/发版：Release `v2026.1108.*`（`86b2c28` 之后）。
- 待办/风险：坏版 `v2026.1107.1841.0-61d83ea` 的 Release 与 tag 已删除，commit 留在历史里。

---

## 2026-11-16 22:45 · WorkBuddy · 建立多智能体交接文档

- 改动：新增本文件与 [`AGENTS.md`](AGENTS.md)，明确"当前有未提交未部署改动"的状态、沙箱铁律、
  验证清单、热修与发版流程、文档更新义务。
- 文件：`AGENTS.md`、`AGENT_LOG.md`。
- 验证：逐项核对仓库真实状态（HEAD `b70e3a7`、fork/main `86b2c28`、6 个文件未提交、
  NAS 线上文件体积与 mtime）。
- 部署/发版：无，仅文档。
- 待办/风险：这批未提交改动的提交与部署时机仍待用户决定。

---

## 2026-11-16 22:33 · WorkBuddy · 项目目录迁移到 C:/Script/metatube

- 改动：仓库从 `<工作区>/tools/mt-plex-plugins` 迁到 `C:/Script/metatube/metatube-plex-plugins`，
  与服务端仓库 `metatube-server-ltx` 同级；离线回归测试迁到 `C:/Script/metatube/_tools/_subrule`，
  三个测试脚本里的插件路径已相应调整（`../../metatube-plex-plugins`）。
- 文件：`AGENTS.md`（工作目录、目录布局、测试命令）、本日志；仓库外 `_tools/_subrule/*.py`。
- 验证：搬迁后 `git status` 与迁移前一致——**6 个文件的未提交改动完整保留**；
  `test_badge_rule.py` 75 项、`test_translation_rule.py` 30 项、`test_subtitle_rule.py` 3 项、
  `check_plex_sandbox.py` 8 文件全过。
- 部署/发版：无。那批三层翻译保底代码**仍未提交、仍未部署**到 NAS。
- 待办/风险：提交与部署时机仍待用户决定；测试脚本已硬编码新路径，再次搬目录要同步改。

## 2026-11-16 23:10 · WorkBuddy · 临时目录约定（temp/）

- 改动：新增约定——排障/试运行/一次性验证产生的脚本、日志 dump、截图一律写
  `C:/Script/metatube/temp/`（仓库外，不受 git 管理），**不要写进仓库**；确认要保留的再挪回
  项目合适位置（脚本 → `scripts/`，回归用例 → `_tools/_subrule`）；**每次 push 前清一遍 temp**。
  写入 `AGENTS.md` 铁律第 9 条、目录布局图、§5 验证清单末尾；`temp/README.md` 与
  根目录 `交接提示词.md` 同步。
- 文件：`AGENTS.md`、本日志；仓库外 `C:/Script/metatube/temp/README.md`、`C:/Script/metatube/交接提示词.md`。
- 验证：文档改动，无代码影响；工作区里那 6 个「三层翻译保底」文件**原样保留，未动**。
- 部署/发版：无。仍未提交、未部署（见 §0 警示）。

## 2026-11-16 23:15 · WorkBuddy · 本地 README 与 GitHub README 分离

- 改动（用户要求）：每轮改动写进**仓库外** `C:/Script/metatube/本地README.md`
  （**绝不上传 GitHub**，禁止 `git add -f`）；`README.md` 只写成品当前真实具备的能力，
  本地加过又删掉的功能、被否掉的方案、事故复盘都不进 GitHub README。
  本仓库的轮次（三层保底未提交未部署、百度 AI 双模型未推送、沙箱命名修复已发布、
  PMS 1.40 换封面放弃）已回填到该文件的「插件仓库」章节。
  `AGENTS.md` 铁律新增第 10 条、§9 文档义务表加一行；`.gitignore` 加本地 README 防呆。
- 文件：`AGENTS.md`、`.gitignore`、本日志；仓库外 `本地README.md`、`交接提示词.md`。
- 验证：`git check-ignore -v 本地README.md` 命中；文档改动，无代码影响；
  那 6 个未提交的「三层翻译保底」文件**原样保留未动**。
- 部署/发版：无。

## 2026-11-16 23:15 · WorkBuddy · 整仓推送并产出新 Release（v2026.1116.1517.0）

- 改动：把本地 5 个提交推到 `fork/main`（`86b2c28..f1acd5f`）。因为其中 `b70e3a7` 改了 bundle，
  `release.yml` 自动产出 Release **`v2026.1116.1517.0-f1acd5f`**
  （`MetaTube.bundle.zip` 646.2 KB、`MetaTubeHelper.bundle.zip` 6.9 KB），
  即「Plex 面板可选 BaiduAI `nmt`/`llm` 模型」这个功能**正式进了 GitHub 发行版**（此前只热修 NAS）。
- 文件：无代码改动（仅推送既有提交）；本日志。
- 验证：Actions `Publish Plex Plug-in Bundle` run `43894672269` completed/success；
  Release 资产齐全；工作区剩余 6 个「三层翻译保底」文件**原样保留未动**。
- 部署/发版：GitHub 侧已发布。**NAS 上的插件仍是 11-12 的热修版**，要上 646.2 KB 的新 bundle
  需手动覆盖 + 重启 Plex（不要只说"已部署"）。
- 待办/风险：三层翻译保底仍未提交；一旦提交并部署，需同步删掉 `AGENTS.md` 第 0 节的未提交警示。

## 2026-11-16 23:54 · Doubao · 三层翻译保底补提交 + 热修上线（线上 = HEAD）

- 改动：
  - 把工作区遗留的 6 个文件（中文元数据三层保底）补成一个提交 `7c0b7e9`，工作区恢复干净。
  - 提交前脱敏：README 日志示例里的真实番号改成 `<番号>` 占位。
  - 按热修流程覆盖线上 5 个文件（`__init__.py`、`constants.py`、`translator.py`、`utils.py`、`DefaultPrefs.json`），
    覆盖前逐个备份为 `<文件名>.bak.20261116_2354`。
  - 顺带纠正文档口径：此前记的「线上仍是 11-12 热修版、未部署新版」不准确——按内容哈希比对，
    线上此前的内容已与上一版 Release（`v2026.1116.1517.0-f1acd5f`）一致，只是行尾不同。
- 文件：`MetaTube.bundle/Contents/Code/{__init__.py,constants.py,translator.py,utils.py}`、
  `MetaTube.bundle/Contents/DefaultPrefs.json`、`README.md`、`AGENTS.md`、本日志。
- 验证：
  - 覆盖前：`py_compile` 通过、`check_plex_sandbox.py` 8 文件无下划线命名、`_subrule` 角标 75 / 翻译 30 / 字幕 3 全过。
  - 覆盖后：归一化（CRLF→LF）后逐文件 SHA-256 比对，`Contents` 下 8 个关键文件
    **NAS / HEAD / 工作区三者完全一致**；线上 `DefaultPrefs.json` 已含三个新键
    （`translation_fallback_engines` / `translation_fallback_parameters` / `translation_llm_budget`）。
- 部署/发版：**已部署到线上**（在 Plex 停止期间覆盖）。**未推送 GitHub**：`fork/main` 仍停在 `5c494de`，
  `main` 领先 1 个提交，未触发新 Release。
- 待办/风险：
  - 覆盖后必须重启/启动 Plex 才加载新代码与偏好；启动后确认日志无 `Exception starting plug-in`，
    且偏好界面能看到三个新设置项。
  - push 与发版待 SAYA 决定；发版前按 §3 流程补 Release 说明与 README 合并。
  - 线上 bundle 根 `VERSION` 仍是 11-07 的遗留标记（`v2026.1107.1841.0-61d83ea`），判断线上版本以文件比对为准。
## 2026-11-17 00:11 · Doubao · 修 Plex 沙箱字符串遍历崩溃（线上实测发现）

- 改动：
  - 线上首轮刷新实测抛出 `AttributeError: 'unicode' object has no attribute '__iter__'`，
    根因是 `utils.charset_ratio` 里的 `for ch in text`：RestrictedPython 把 `for` 编译成
    `x.__iter__()`，py2 的 `unicode` 没有 `__iter__`（`str` 有）。
  - 改为 `for index in range(len(text))` + `text[index]` 下标遍历，语义不变；
    异常发生时是中止写回，没有把元数据写坏。
- 文件：`MetaTube.bundle/Contents/Code/utils.py`、`AGENTS.md`（§0 状态、§8 已知坑加一条）、本日志；
  仓库外 `_tools/_subrule/test_translation_rule.py`（新增 `Py2Unicode` 替身用例，30 → 31 项）。
- 验证：
  - 离线：`py_compile` / `check_plex_sandbox.py`（8 文件）/ 角标 75 / 翻译 31 / 字幕 3 全过。
  - 用例有效性：反向验证过——旧写法在 `Py2Unicode` 替身下确实抛 `TypeError`，不是摆设。
  - 线上：覆盖 `utils.py`（备份 `.bak.20261117_0011`）后，Plex 的 file watcher 自动重载插件
    （进程 ID 变了，无需手动重启），再刷新同一测试条目：
    BaiduAI 返污染被 L1 拒 → Baidu 同样被拒 → DeepL 403 → 大模型兜底 37 字符 →
    标题变干净中文、简介中文、`translation_memory.json` 生成（204 字节）。
- 部署/发版：已覆盖线上，线上 = HEAD（`_tools/compare_bundle.py` 逐文件一致）。
- 待办/风险：
  - DeepL 备用引擎返回 403（未配 `deepl.auth_key`），需要时在 `translation_fallback_parameters`
    里补 `deepl.auth_key=...`。
  - 大模型兜底是一次性池，`translation_llm_budget` 默认 30000 字符，批量刷新前先看已用多少。
## 2026-11-17 00:20 · Doubao · 整仓推送并产出 Release v2026.1116.1607.0

- 改动：把本地 6 个提交推到 `fork/main`（`5c494de..b6aec9e`）：
  三层翻译保底 `7c0b7e9`、文档修正 `b2ec18e`/`f2bf690`/`82cf306`、沙箱遍历修复 `8d87d61`、坑记录 `b6aec9e`。
  其中 `*.bundle/**` 有变动，`release.yml` 自动产出 Release **`v2026.1116.1607.0-b6aec9e`**。
- 文件：无新增代码改动；`AGENTS.md` §0/§3 同步为已推送状态、本日志。
- 验证：
  - Actions `Publish Plex Plug-in Bundle`（`b6aec9e`）completed / **success**。
  - Release 资产：`MetaTube.bundle.zip` 666856 字节（651.1 KB）、`MetaTubeHelper.bundle.zip` 7029 字节。
  - 下载发布 zip 解包，与本地 HEAD 归一化（CRLF→LF）后逐文件 SHA-256 比对：6 个关键文件 **全部 SAME**。
- 部署/发版：GitHub 侧已发布；线上 Plex 已在同一版本（直接覆盖部署，未用 zip 整包替换）。
- 待办/风险：线上 bundle 根的遗留 `VERSION`/`LICENSE` 仍未更新（不影响运行）；
  下次若要整包替换，注意先停 Plex 再覆盖，避免带着旧 `__pycache__`。
## 2026-11-17 00:16 · Doubao · 查清插件设置怎么"记住"API + DeepL 额度用尽

- 改动：无代码改动，纯文档（三条坑写进 `AGENTS.md` §8）。
- 查了什么：读 NAS 上 `Plug-in Support/Preferences/com.plexapp.agents.metatube.xml`（39783 字节，
  31 个字段），对照 `DefaultPrefs.json`（34 个字段），确认：
  - 枚举在 XML 里存的是**下标**：`translation_engine=5` → `BaiduAI`；`translation_mode=4` → `Title and Summary`。
  - `translation_engine_parameters` 目前是 `baidu-app-id=…,baidu-app-key=…`（值未记录、未打印）。
  - 三个新翻译键不在 XML 里，由 Plex 加载时用 DefaultPrefs 的默认值补齐。
  - 面板是静态表单：切引擎只改枚举自身，不会改写参数框 —— 这解释了用户看到的"切换引擎 API 不变"。
- 待办/风险：DeepL 免费额度已用尽（用户决定 2026-12 再补），期间每次调用固定 403；
  `translation_fallback_parameters` 里也没有 `deepl.auth_key`，补额度时要一起补。