# 守则

约定以本文件为准。代码里只留短注释，像平时说话那样写。

Game1（`../Game1`）是封档的列强观察台，不要在那边续写，也不要把列国轮询、条约桌、模型代打搬过来。

---

## 总则

- **禁止随意添加新机制。** 先看现有字段能不能表达；能就用，不能再改守则。
- **禁止添加与已有机制相同的机制。** 同一件事只留一条路。事件开始等待只记在 `event_armed`，等到哪一回合只记在 `event_clock`。
- 新功能必须进本框架，不要另写绕过框架的脚本。
- 参数放 `src/config/`。不要在引擎里写死地名。
- 少写防御性编程。配置缺字段在加载时报错，不要用默认值糊过去。
- 注释短，说这行在干什么。说明书在本文件。

---

## 游戏是什么

玩家开局自定国家名、领袖和难度（`src/config/setup.yaml`）。开局疆域是宾夕法尼亚一块，图上其余美加一级政区无主。没有其他人类国家。模型只做**首席顾问**：读 briefing，输出一段话，引擎不解析、不执行。

开局窗口填完后才调用 `/api/new`。事件表目前是空的，世界不靠历史年表推进。

---

## 时间

引擎只认**回合**。年和月只在 `src/engine/time.py` 译给人看。

- 一回合多长只由 `game.yaml` 的 `time.turns_per_year` 决定。现在是 `12`，即一个月一回合。
- `年 = display_era_year + turn // turns_per_year`，`月 = turn % turns_per_year + 1`
- 现在 `start_turn: 4` 显示为 2056年5月；`end_turn: 500` 到点终局。
- 推进时间不读译文字段。状态只有 `state.turn`。

---

## 事件

三种触发与 Game1 相同，本版本**只用日历和因果**。不要写脉冲（`once: false`）。

一件事要发生：条件已齐；没有 delay、或已经等到该发生的那一回合；`condition` 成立；未绑定局势、或该局势还在进行。

### 1. 日历

- `at_turn: N`：只在第 N 回合检查。不要写 delay。
- 这一回合 `condition` 不成立，这件事就过了。

### 2. 因果 + delay

- 写了 `after`：所列事件都已进 `event_resolved`
- 或写了 `progress_complete`
- 或写了 `at_turn` **并且** 写了 delay（从第 N 回合起开始等）
- `after` / `progress_complete` 不要再叠单独的日历 `at_turn`（没有 delay 的那种）
- **必须写 delay**，且大于 0。数字，或 `{ min, max }` 且 min < max
- 开始等待记 `event_armed`；抽到「等到哪一回合」记 `event_clock`；到点后 condition 仍不成立则以后每回合再看，等待不重算

### 3. 脉冲

本版本禁止。加载时拒绝 `once: false`。

### 开局局势

`at_start: true`：开局就在。不要写 delay、日历或因果。

### 受众

- `audience: world`：世界简报，没有选项，进新闻栏
- `audience: player`：玩家抉择或即时效果。有 `options` 则进待决，无选项则当场执行
- 有选项的事件一律问玩家，不要写 `deciding_nation`

### 其它

- `after` 看 `event_resolved`
- `type: instant`：无选项，当场执行
- `type: option`：待抉择；未选则回合结束走 `default` 项（无 default 则第一项）
- `type: situation` / `type: progress`：局势。progress 必须写 `progress: { current, total }`
- `timeout_turns` 与 `timeout_option` 必须成对；到期按 timeout_option 结算
- 已取消：`mtth`、年/季窗口、`start_delay`、`repeat`、`power_rank`、`deciding_nation` 对象写法

配置：`src/config/events/world.yaml` 与 `player.yaml`。加载时校验。

---

## 地图

轮廓用标准 GeoJSON（经纬度），不要再投影成 SVG path。底图是 `src/maps/` 里的美加一级政区；`worldmap.yaml` 是配方，`python -m src.engine.worldmap` 写成 `src/maps/map.geojson`。引擎读这份 GeoJSON 的属性；界面用 MapLibre GL 画，几何只通过 `/api/map.geojson` 拉一次。

- 政区状态在 `state.provinces`：控制方、要塞等级
- 本国 `kind: home`，其余 `foreign`
- 效果 `occupy` / `fort` 改这里，不要另做一套占领表

---

## 内政

只有玩家点。种类、分类和消耗在场景 `domestic.yaml`。`category` 必须写在 `ui.yaml` 的 `category_order` 里。冷却记在 `state.cooldowns`。数字变化写在 `effects` 里，界面用数值拼名称，不要把加减写死在 `name` 里。

---

## 顾问

`src/agents/advisor.py`。把 `briefing` 和玩家问题交给模型，只回收文本。没有 Key 或 provider 为 mock 时返回固定句，游戏照常。禁止让顾问输出 JSON 行动。

---

## 存档

`saves/game.db`。默认名：`{前缀}_{场景简称}_{月日-时分}`。前缀在 `save.yaml`。

---

## 加载与运行

缺字段、坏 delay、旧事件字段，加载时拒绝。

`play.bat` / `python -m src` 默认 `http://127.0.0.1:8010`，不要和 Game1 的 8000 抢。界面不对时 Ctrl+Shift+R。
