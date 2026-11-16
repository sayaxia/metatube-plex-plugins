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
