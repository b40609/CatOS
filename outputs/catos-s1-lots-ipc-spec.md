# catOS S1：本地 Lot 数据结构与 IPC 意图契约

日期：2026-09-15。状态：**规格交付，尚未实现或执行测试**。

本次直接目标：给出第一阶段切片（Slice 1，S1）的具体代码规格与单元测试清单。不是多 Bot 交易功能验收，也不授权读取凭证、连接账户、交易、迁移现有数据库或执行 Git 工作。

## 1. 交接审查与决策边界

### 1.1 本次采用的产品方向

- 同一 USDT 本位永续合约（USDT-M SWAP）允许多个 Bot 的本地逻辑分仓（Local logical sub-positions / Virtual lots），支持同向和反向 Lot。
- 不等待普通分仓 API；不采用每方向最多一个 Bot；不采用每 Bot 一个独立子账户。
- 最终需要各 Bot 独立数量、成本、收益、保证金展示及止盈/止损（Take profit / Stop loss，TP/SL）。这不等于独立保证金、资金或强平隔离。
- 继续保持唯一主管程序（Supervisor）、单写入者、Decimal、固定 tag、原子风险预留、UNKNOWN 保留责任和账户风控锁存。
- 本次方向取代旧 P8 的“等待官方分仓后再研究”作为新研发路线；**不代表现有 v1 运行约束已被删除或安全迁移已经完成**。

### 1.2 摘要中必须纠正的内容

| 摘要说法 | 当前核对结果 | S1 处理 |
|---|---|---|
| 当前基线为 `3e41c97`，150 tests 全通过 | `WORK_PLAN.md:45,64` 中存在更晚的历史封版记录；首页另有 2026-09-15 未验证修改 | 不把任何历史通过数作为当前工作树验收；本轮不运行 Git 或测试 |
| 已实现日损默认值为 3% / 5% | `catos/risk.py:25–30` 为 10% / 20%；`AGENTS.md:37`、`WORK_PLAN.md:49` 一致 | 将本次摘要中的 3% / 5% 记录为新路线提出的目标值，不伪称既有值；S1 不修改默认、已存配置或 latch |
| 交易所每次新开仓天然形成独立成本 | 不能由成交次数推导原生独立子仓 | “一个开仓意图对应一个本地 Lot”是 catOS 会计归属规则，不是交易所保证 |
| net 或 long/short 可以无区别接入 | 两者的执行、减仓判断、对账及 P6 保护语义不同 | S1 的逻辑 `side` 与交易所 `posSide` 分离；执行模式后续定案 |
| 删除单 Bot 限制即可升级 | journal、执行归属、风险与保护均依赖该限制 | 增量隔离 S1，不直接删除 v1 检查 |
| 官方一定没有任何普通分仓 API | 本轮未完成覆盖全部官方接口的排除性核查 | 不依赖该 API 作为已定方向；不复述“已证实不存在”的绝对结论 |

现有禁止真实账户操作及模型分工依据：`AGENTS.md:20–22`。这不是停止设计的理由；本片不依赖账户访问。

## 2. S1 的最小范围

### 2.1 拟新增的实现文件

| 文件 | 责任 |
|---|---|
| `catos/lots.py` | 不可变领域类型、Lot 快照、三类意图、上下文校验、确定性标识 |
| `catos/ipc_lots.py` | 独立 v2 意图消息、严格字段校验、Decimal 文本编解码、规范化 |
| `tests/test_lots.py` | 领域约束、归属、版本、数量、稳定标识的合成单元测试 |
| `tests/test_ipc_lots.py` | v2 编解码、错误输入、warmup、v1 隔离测试 |

这四个文件是**实现目标**，本轮尚未创建。优先仅用标准库，不安装依赖。

### 2.2 明确不做

- 不修改 `ipc.VERSION=1`，不替换 SMA 策略的 `target_position`，不更改研究回测契约。
- 不接入 Worker 运行循环、checkpoint、ACK、多 Worker 调度或常驻服务。
- 不修改 `journal.py` 的 schema/ownership，不创建 Lot 表或第二套数据库，不迁移历史数据。
- 不实现订单发送、成交分配、均价推进、已实现损益结算、资金费率分摊或保证金分配。
- 不实现 Gross 风控引擎、实际风险预留、TP/SL 行情监控、P6 重构、Demo/Live 切换。
- 不把类型校验通过称为允许交易，不把稳定 ID 称为已实现持久化幂等。

### 2.3 为什么要隔离

具体失败情境：把 v2 的 `CLOSE_LOT` 直接转成现有净目标，可能在关闭本地多 Lot 时增加交易所空头；移除 ownership 主键却保留净仓成交累计，会把不同 Bot 的成本混在一起。

最小做法：先独立定义数据及协议，所有实际运行入口保持 v1。不为本片增加线程、调度器、迁移器或网络适配。验证成本只落在两个新测试模块和直接依赖的 v1 IPC 回归。

## 3. 数量、价格和标识规范

- `quantity`、`opened_qty`、`remaining_qty` 的单位统一为**合约张数**，不是币数或 USDT。
- 继续复用 `research.ContractSpec`（`research.py:48–60`）；`base_per_contract` 是已标准化的每张合约对应基础币数量，不能把 `ctMult` 单独当它。
- 数量不得用正负号表达方向；方向单独为 `"long"` 或 `"short"`。
- Python 领域层只接受有限 `Decimal`；禁止从 Float 隐式转换。线上 JSON 金额/数量必须是字符串，不能是 JSON 数字。
- 复用 `ipc.decimal_text` 的有界词法和范围：意图输入不超过 28 位数字、exponent >= -18、adjusted <= 18；派生快照不超过 50 位、exponent >= -148、adjusted <= 99。
- 每次数量整倍数运算在 `localcontext(research._CONTEXT)` 中执行，不修改调用方 Decimal context；派生金额越界一律拒绝，不截断或归零。
- `derived=True` 的调用者必须另查正负约束，不能依赖该分支的 `positive=True`（现有实现见 `ipc.py:45–59`）。S1 不顺手更改共用解析器。
- 一般标识用 `[A-Za-z0-9_-]{1,64}`；派生的 `intent_key`、`open_intent_key`、`lot_id` 进一步限定为 `[0-9a-f]{64}`，包括 CLOSE/UPDATE 引用的 lot_id。版本号/序号用 `type(x) is int`，拒绝 bool，范围遵循 `ipc.MAX_INTEGER`。
- 合约必须与父侧绑定的 `ContractSpec.inst_id` 完全相等；标识格式检验不证明真实市场存在该合约。

## 4. 领域类型

下列是待实现接口规格，不是可运行成品。全部 dataclass 使用 `frozen=True, slots=True`；所有 `__post_init__` 校验仅做纯计算，不读文件、环境、网络、数据库或时钟。

```python
Side = Literal["long", "short"]
Environment = Literal["local-sim", "demo", "live"]

@dataclass(frozen=True, slots=True)
class LotScope:
    account_ref: str
    environment: Environment

@dataclass(frozen=True, slots=True)
class LotProtection:
    trigger_price_type: Literal["mark"]
    take_profit: Decimal | None
    stop_loss: Decimal | None

@dataclass(frozen=True, slots=True)
class Lot:
    scope: LotScope
    bot_id: str
    inst_id: str
    lot_id: str
    open_intent_key: str
    side: Side
    opened_qty: Decimal
    remaining_qty: Decimal
    average_entry: Decimal
    realized_pnl: Decimal
    fees_paid: Decimal
    funding_paid: Decimal | None
    protection: LotProtection
    revision: int

@dataclass(frozen=True, slots=True)
class OpenLot:
    side: Side
    quantity: Decimal
    protection: LotProtection

@dataclass(frozen=True, slots=True)
class CloseLot:
    lot_id: str
    quantity: Decimal | None
    expected_revision: int

@dataclass(frozen=True, slots=True)
class UpdateLotProtection:
    lot_id: str
    protection: LotProtection
    expected_revision: int

LotIntent = OpenLot | CloseLot | UpdateLotProtection

@dataclass(frozen=True, slots=True)
class IntentContext:
    scope: LotScope
    bot_id: str
    contract: ContractSpec
    event_seq: int
    warmup: bool

@dataclass(frozen=True, slots=True)
class LotValidationView:
    lot: Lot | None
    opening_unresolved: bool
    closing_unresolved: bool

@dataclass(frozen=True, slots=True)
class ValidatedLotIntent:
    intent_key: str
    scope: LotScope
    bot_id: str
    inst_id: str
    lot_id: str
    intent: LotIntent
    resolved_quantity: Decimal | None
```

`LotScope` 不含账户 uid、API key 或凭证。`account_ref` 是应用本地不敏感代号；环境字段只用于数据隔离，不是授权标记。允许表示 `live` 不意味着运行 Live。

### 4.1 Lot 的语义与生命周期

1. **一个已接受 OPEN_LOT 意图对应一个 Lot 标识**。该意图的多次部分成交属于同一个 Lot，不是每个 fill 一个 Lot。
2. 同 Bot 再次加仓必须发新的 OPEN_LOT，并生成新 Lot；不得修改旧 Lot 的开仓归属。
3. 接受开仓意图仅产生意图记录和未来 Lot 标识；未成交不构造 `Lot`。首次确认成交后才有 Lot 快照。
4. `opened_qty > 0`，`0 <= remaining_qty <= opened_qty`；平均开仓价有限且正。方向必须有效。
5. `opened_qty` 是该开仓意图截至当前的累计确认成交量；开仓部分成交期间可以增长。`average_entry` 是该开仓批次确认成交的数量加权均价，不要求对齐 tick。
6. 平仓后 `opened_qty` 和原开仓均价保留，`remaining_qty` 减少；`remaining_qty=0` 的关闭快照保留审计数据，不直接删除或复用 ID。
7. S1 不存另一份 `status`，避免和数量冲突；是否仍有开仓/平仓/UNKNOWN 责任来自 `LotValidationView`，不能仅看 `remaining_qty` 判定可释放。
8. `revision >= 1`，之后每次确认成交、有效保护配置变更等原子状态更新递增；拒绝和重复交付不得递增。相同配置的已接受更新可记为 no-op，不递增，但仍需保存收据。S1 只比较 revision，不实现状态更新。
9. Lot 关闭不代表交易所、Bot 或合约所有权可以释放；后续必须等待所有关联订单、保护责任和对账终结。

**不变量校验分层**：构造器验证类型/数值/数量关系，以及 `open_intent_key` 和 `lot_id` 均为 64 字符小写十六进制且 `lot_id == make_lot_id(open_intent_key)`；不一致报 `lot_identity_mismatch`。`validate_lot(lot, contract)` 额外验证合约匹配、合约规格有效、数量与 lot_size 对齐、保护价格与 tick 对齐。已确认成交的剩余量允许低于 `min_size`；不得为了通过校验删除碎量。

### 4.2 收益与费用

- `realized_pnl`：该 Lot 已确认平仓的价格损益，尚未扣费和资金费率。正数收益、负数亏损。
- `fees_paid`：确认归属的净费用支出；正数支出、负数返佣。不能将返佣改成绝对值。
- `funding_paid`：确认归属的净资金费支出，正付负收；`None` 表示尚无完整分摊证据，不等于零。
- S1 接受并验证这些快照字段，不提供成交结算函数，也不通过构造器推测数字正确。
- 后续展示：`net_realized = realized_pnl - fees_paid - funding_paid`，仅在归属和资金费证据完整时可给确定值；否则显示未完成核算。
- 后续 Bot 数量应分别汇总 long 和 short，不能用一个带符号净量代替独立持仓。多空成本分别加权，不能混成一个均价。

### 4.3 保证金展示不伪装隔离

S1 不把 `margin` 固化为 Lot 事实字段。后续可提供只读展示对象，必须同时携带数值或 `None`、`basis`（分配/估算方法）、观察时点和完整性标记。缺证据显示未知，不默认零。

按名义金额除某个展示杠杆只能称估算，不能冒充交易所实际初始/维持保证金。账户权益、可用保证金和强平风险仍由账户级证据决定。分配方法及合计与账户差额如何解释，需在展示切片定案。

## 5. 三类意图的精确定义

### 5.1 OPEN_LOT

严格字段：`op, side, quantity, protection`，`op="OPEN_LOT"`。

- 数量正数、为 `lot_size` 整数倍且不低于 `min_size`。
- Worker 不指定 bot_id、account、环境、inst_id、lot_id、订单 ID、均价、费用、杠杆或 tag。
- 所有身份和合约由父侧 `IntentContext` 绑定；Supervisor 从稳定意图身份派生 Lot ID。
- `protection` 必须完整给出；全部关闭保护要显式传入两项 null，不使用隐式默认。
- 本片只支持市场执行意图语义，不增加 limit_price 或通用订单类型；实际委托转换后续实现。

### 5.2 CLOSE_LOT

严格字段：`op, lot_id, quantity, expected_revision`，`op="CLOSE_LOT"`。

- `quantity=null`：请求关闭当前版本的全部剩余数量；不是“未来自动追踪全部新增量”。解析时保留 null，父侧校验时解析成明确数量。
- `quantity` 为字符串：请求部分平仓；必须大于零、对齐步长且不超过剩余量。
- 必须存在 Lot，且 scope、环境、bot_id、inst_id 全部匹配父侧上下文；不能靠 Worker 自报归属。
- 必须匹配 `expected_revision`；旧版本即使数量仍足够也拒绝，不能静默缩量重试。
- 同 Lot 若 `opening_unresolved` 或 `closing_unresolved` 为真，普通 Worker 平仓请求暂拒，避免后到开仓成交或重叠平仓。UNKNOWN 算未决责任；账户紧急平仓不是此普通入口，后续另行整合。
- `remaining_qty=0` 拒绝新平仓。相同已提交意图的重放应先走收据查重，不能当成新平仓拒绝后再下新单。
- 不把“本地关闭 Lot”自动标成交易所 `reduceOnly=True`。
- 逻辑校验不因 `min_size` 拒绝已经存在的全部碎量平仓；对齐步长仍必须满足。交易所能否接受碎量、如何归并，留给执行适配，不能静默丢弃责任。

### 5.3 UPDATE_LOT_PROTECTION

严格字段：`op, lot_id, protection, expected_revision`，`op="UPDATE_LOT_PROTECTION"`。

- 指定 Lot 必须存在、归属匹配、未关闭，且版本一致。
- 普通配置更新在有未决开仓/平仓时暂拒，避免与部分成交、触发平仓并发解释；后续账户级 emergency 不经此入口。
- `protection` 为**全量替换**，不是 patch；缺字段拒绝，null 显式移除对应条件。
- 本地保护配置不改变 P6 的交易所灾难停损配置，也不能解除任何风险锁存。

### 5.4 保护字段及校验

```json
{"trigger_price_type":"mark","take_profit":"120","stop_loss":"90"}
```

以上为合成价格，不是交易建议。

- S1 建议将普通 Lot 保护触发价格来源限定为 `mark`，作为明确的协议选择；未接行情、不表示保护已激活。
- 非 null 的 TP/SL 必须正数且对齐 tick；零不是关闭开关。
- 两项均存在：long 要求 `stop_loss < take_profit`；short 要求 `take_profit < stop_loss`；等价拒绝。
- 不要求止损永远在开仓均价的亏损侧，允许移动止损保护已有利润。均价还可能由不同 tick 成交加权得到非 tick 值。
- 不以最新行情验证“有没有触发”；S1 没有行情证据。未来触发器应使用有时间戳及新鲜度的 mark，并明示触发后执行策略、停机风险和滑点。
- `take_profit=null, stop_loss=null` 是无普通本地保护，不等于无账户级风险控制。

## 6. IPC v2：独立意图消息，不替换 v1

进程间通信（Inter-process communication，IPC）复用现有四字节大端长度帧、UTF-8 和有界纯 JSON 编解码，继续禁止可执行反序列化。

S1 新消息只定义一个单向 `kind="lot_intents"`。不定义 v2 init/bar/result/checkpoint/ACK，也不声称现有 Worker 已经支持发出它。后续 Worker 接入切片统一决定完整握手和策略状态恢复。

```json
{
  "version": 2,
  "kind": "lot_intents",
  "generation": "worker-session-1",
  "seq": 3,
  "payload": {
    "intents": [
      {
        "op": "OPEN_LOT",
        "side": "long",
        "quantity": "2",
        "protection": {
          "trigger_price_type": "mark",
          "take_profit": "120",
          "stop_loss": "90"
        }
      }
    ]
  }
}
```

- 信封精确字段为 `version, kind, generation, seq, payload`；payload 只有 `intents`。
- `version` 必须是整数 2；`seq` 必须是正整数并匹配父侧当前事件；generation 必须与父侧当前会话相等。
- 本片每事件允许 0 或 1 个意图。空数组表示无操作；拒绝 null、对象冒充数组或多个意图。不引入批次部分接受规则。
- warmup 由父侧计算，不接受 Worker 上报；warmup 必须 `intents=[]`，任何非空意图都拒绝，也不保留延后执行。
- 每级对象都严格拒绝多字段/漏字段；不得通过“忽略未知字段”接受旧 target、tag、posSide、reduceOnly 等内容。
- 复用 `ipc.encode_frame/decode_payload/read_frame*`，不复用会强制 VERSION=1 的 `ipc.envelope/check_envelope`。
- 仍为 65536 字节正文、深度最多 8，拒绝重复键、Float、NaN/Infinity、无效 UTF-8、过长整数和截断帧。
- 无握手无自动降级：v1 解析器继续拒绝 v2；v2 解析器拒绝 v1。不能把 Lot 意图转换成旧 target 来凑兼容。

其他两类 payload 中的单条意图：

```json
{"op":"CLOSE_LOT","lot_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","quantity":null,"expected_revision":4}
```

```json
{"op":"UPDATE_LOT_PROTECTION","lot_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","protection":{"trigger_price_type":"mark","take_profit":null,"stop_loss":"105"},"expected_revision":4}
```

`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` 是合成引用示例，实际 OPEN 的 ID 由父侧生成并在后续确认/视图协议中回传，不要求 Worker 猜测。

## 7. 纯函数接口与拒绝语义

```python
# lots.py
class LotError(ValueError):
    code: str

validate_lot(lot: Lot, contract: ContractSpec) -> None
validate_protection(protection: LotProtection, side: Side,
                    contract: ContractSpec) -> None
validate_intent(intent: LotIntent, context: IntentContext,
                view: LotValidationView) -> ValidatedLotIntent
make_intent_key(context: IntentContext, output_index: int = 0) -> str
make_lot_id(open_intent_key: str) -> str

# ipc_lots.py
LOT_PROTOCOL_VERSION = 2
MAX_INTENTS_PER_EVENT = 1

intent_to_wire(intent: LotIntent) -> dict
intent_from_wire(value: dict) -> LotIntent
lot_to_wire(lot: Lot) -> dict
lot_from_wire(value: dict) -> Lot
encode_lot_message(intents: tuple[LotIntent, ...], *,
                   generation: str, seq: int) -> bytes
parse_lot_message(message: dict, *, generation: str, seq: int,
                  warmup: bool) -> tuple[LotIntent, ...]
canonical_intent(intent: LotIntent) -> bytes
```

补充契约：

- `intent_from_wire` 只构造领域对象；数量步长/归属/剩余量等依赖父侧的检查由 `validate_intent` 执行。`lot_from_wire` 验证快照精确字段及构造约束，合约相关校验由 `validate_lot` 执行。
- `lot_to_wire` 字段与 `Lot` 完全对应；scope 展开为精确的 `account_ref/environment`，protection 展开为第 5.4 节三字段，Decimal 转字符串，funding 未知为 null。不发送凭证。
- OPEN 使用 `LotValidationView(None, False, False)`；任何意外已有 Lot/未决标志都拒绝。其重放应由持久化收据处理，不覆盖既有 Lot。
- CLOSE/UPDATE 必须有 Lot，并验证快照及绑定；还必须明确检查 `intent.lot_id == view.lot.lot_id`，不匹配报 `lot_identity_mismatch`。同 Bot、同合约、同 revision 的另一 Lot 也不能替代目标。`validated.resolved_quantity`：OPEN 为请求量；CLOSE 为本次明确解析出的关闭量；UPDATE 为 None。
- `ValidatedLotIntent` 只是业务结构校验结果，不包括风控批准、保留额、幂等提交或执行授权。
- 领域错误用 `LotError(code)`，不得泄露其他 Bot 内容。协议入口将领域构造错误转换为 `ipc.ProtocolError`，保持可识别错误码，不吞异常归零。

建议固定领域错误码：`invalid_decimal`、`invalid_quantity`、`invalid_contract`、`invalid_protection`、`invalid_revision`、`warmup_intent_forbidden`、`lot_not_found`、`lot_scope_mismatch`、`lot_identity_mismatch`、`lot_closed`、`revision_conflict`、`lot_busy`、`over_close`、`invalid_view`。

协议错误继续使用现有 ProtocolError；未知 op、跨版本、字段不匹配和不合法帧不得进入领域校验。

## 8. 稳定标识、规范化与未来幂等接缝

### 8.1 标识

S1 一事件最多一意图，`output_index` 必须为 0。

`intent_key = SHA256` 的小写十六进制全文（64 字符）。哈希输入固定为：

```text
JSON array ["catos-lot-intent-v2", account_ref, environment,
            bot_id, inst_id, event_seq, 0]
```

编码参数固定 `ensure_ascii=True, separators=(",", ":")`，UTF-8，无 BOM/换行。

`lot_id = SHA256(JSON array ["catos-lot-v2", open_intent_key])`，相同编码。OPEN 的 Lot ID 不受成交次数影响。

- 不使用 Python `hash()`、当前时间、随机 UUID 或 generation 作为重放身份。
- generation 仅防止旧 Worker 会话消息误入；重启后同一持久化事件仍得相同意图 ID。
- `event_seq` 必须是该 Bot 稳定递增的持久化序号，重启不重置；已使用 bot_id 不能删除后重用序号。此持久化保证由后续集成实现，不是 S1 的能力。
- scope、bot、合约或 seq 改变应产生不同 key；同一个 key 的不同内容属于冲突，不生成第二笔交易。

### 8.2 内容规范化

`canonical_intent` 对已验证的类型调用 `intent_to_wire`，排序 JSON key，并规范化所有 Decimal 字符串。

- `"1" / "1.0" / "1e0" / "+1"` 应得到同一数值编码。
- 有效输入先做范围检查，再归一化；不能先去除尾零来让本应超精度输入绕过限制。
- 定点格式输出，去除小数末尾零和最终小数点；若为零统一 `"0"`。不得误删整数末尾的零。
- 不使用依赖全局 Decimal 精度的 `normalize()`；可由精确 `format(value, "f")` 加纯字符串处理生成。
- CLOSE 的 null 与某个确定数量保持不同语义，不能在内容指纹里把 null 改为当时剩余量。

### 8.3 后续提交顺序约束（本片不实现）

校验当前会话/事件 → 严格解码 → 用稳定 key 查已提交收据 → 相同规范内容返回原收据/不同内容拒绝 → 对新意图在单 writer 事务内重读 Lot/revision/未决责任 → 风控 → 原子预留/持久化/outbox → commit → ACK → 唯一执行出口。

事务边界外的 `validate_intent` 结果不得直接长期缓存后执行。多个 Bot 都看见相同可用预算时，后续单事务必须让第二笔看到第一笔预留。S1 不提供内存字典冒充该原子保证。

## 9. 后续金融与执行约束

以下约束用于防止 S1 数据设计误导后续实现；不是本轮功能。

### 9.1 Gross 与净额必须同时区分

```text
lot_exposure = remaining_qty * base_per_contract * fresh_mark
symbol_logical_gross = sum(lot_exposure for all owned long and short lots)
worst_logical_gross = confirmed_logical_gross
                    + unresolved_opening_remainder_notional
                    + accepted_but_unsent_opening_reservations
```

未成交、SUBMITTING、UNKNOWN 的增仓剩余责任仍计入；确认部分成交转入持仓后，只保留未成交余量，不把整单数量再加一次。未成交平仓不提前减 Gross；只有确认成交才可释放对应数量。不得把不同 Bot 多空直接抵销。

Gross 是策略活动预算，不是交易所精确保证金模型。后续还要独立验证真实交易所仓位、可用保证金、订单方向与执行阶段最坏曝险，未知责任禁增仓；不能以“本地 Gross 下降”代替所有检查。

### 9.2 net_mode 的反例

合成单位例子：A 多 1、B 空 1，本地 Gross=2、净额=0。若交易所净仓为 0，关闭 A 的本地多仓会令剩余本地净额变成 -1；为了与交易所对齐，可能需要新增卖出，而不是交易所 reduce-only。

因此同一句“减仓”在 Lot 层与交易所层不等价。net_mode 若配内部抵销，需要明确内部成交价、现金/费用归属和退出执行；不能把没有交易所成交的本地配对伪造成真实 fill。

建议下一执行切片先评估 `cross + long_short_mode` 的多空分侧聚合，同向由本地 Lots 分配；这不等于“每方向仅一个 Bot”。**此处只是建议，不改变现有 net_mode 配置或授权改账户模式。** 若坚持 net_mode，先设计内部抵销与风险口径，不能隐式兼容。

### 9.3 本地保护与 P6 的硬边界

Lot TP/SL 依赖主机、进程和行情；断线/掉电期间不能承诺执行。现有 P6 为每 Bot 的交易所整仓保护（`catos/protection.py:175–211`）；同合约多 Bot 下不能把该整仓逻辑当成某个 Lot 的保护，否则可能平掉其他 Bot。

将来上线前必须确定账户/方向聚合灾难保护与逐 Lot 本地保护如何共存，明确跨 Bot 影响与 UNKNOWN 门控。不得为了多 Bot 直接停用 P6，或者声称本地 TP/SL 提供同等离线保护。

### 9.4 日损与账户边界

本次目标文字中的 Soft 3%、Hard 5%，与现行默认 10%、20% 冲突。S1 不带门槛字段，Worker 无权修改账户参数。后续若迁移为 3% / 5%，须专门处理新建默认、既有账户已存值、审计和 latch；不能启动时覆盖旧配置，更不能清除锁存。

固定日初分母、Asia/Taipei（UTC+08:00）日界、外部资金流白名单、手动恢复约束继续保留。多 Bot 总盈亏不能替代已核实账户权益。拒绝“每 Bot 独立子账户”不自动撤销现有专用账户不得混用手动交易的规定。

## 10. S1 单元测试清单

全部为合成数据，无网络、凭证、SQLite、真实 Worker、真实行情或交易。以下编号是**计划用例**，不代表已创建测试函数数量或通过数。

### 10.1 `tests/test_lots.py`

| 编号 | 验证点与预期 |
|---|---|
| L01 | 同一合约 A/B 两个 long、C 一个 short 可同时表示，数量和成本互不覆盖 |
| L02 | 一个 Bot 可有多个同向及反向 Lot；无单方向单 Bot 假限制 |
| L03 | 构造器冻结；外部修改字段失败，嵌套保护对象也不可变 |
| L04 | opened_qty=0、remaining<0、remaining>opened、非正/非有限均价拒绝 |
| L05 | remaining=0 的关闭快照保留均价、费用与 ID；不存在未成交零成本 Lot |
| L06 | Float、NaN、Infinity、超范围 Decimal 拒绝；revision 的 bool/0/越界拒绝 |
| L07 | 均价非 tick 倍数可接受；数量非 lot_size 倍数拒绝 |
| L08 | OPEN 数量为正、步长及 min_size 合法；再加仓需新事件得到新 Lot ID |
| L09 | CLOSE 指定部分量和 null 全平，解析得到正确 resolved_quantity |
| L10 | CLOSE 为零/负数/不对齐/超剩余量拒绝；不自动截到剩余量 |
| L11 | CLOSE 全部碎量低于 min_size 可通过逻辑校验，仍不表示交易所会接受 |
| L12 | 其他 Bot、账户、环境或合约 Lot 一律 scope mismatch，无自动接管 |
| L13 | 不存在 Lot、已关闭 Lot、新请求旧 revision 分别拒绝 |
| L14 | opening_unresolved 或 closing_unresolved 时 CLOSE/UPDATE 暂拒；不产生副作用 |
| L15 | OPEN 配已有 Lot 或不一致 view 拒绝；missing Lot 与未决标志矛盾拒绝 |
| L16 | TP/SL 正数且 tick 对齐；零、负数、非有限、相等或错误顺序拒绝 |
| L17 | 止损可位于盈利侧；long/short 保护方向正确；一项 null 与双 null 有效 |
| L18 | 费用返佣为负合法；funding=None 不等于 0；有符号已实现损益合法 |
| L19 | 同持久化事件重算 key/lot_id 一致；账户/环境/Bot/合约/seq 改变 key 不同 |
| L20 | output_index 非 0 拒绝；标识恰好 64 字符、符合 token；不读取时钟或 generation |
| L21 | 全局 Decimal 精度改成 2/不同舍入模式，校验结果不变且外部 context 保持不变 |
| L22 | warmup 的所有非空意图在领域校验也拒绝；ValidatedLotIntent 不包含风险批准字段 |
| L23 | CLOSE/UPDATE 请求 Lot A，却给同 Bot/合约/revision 的 Lot B 快照，必须报 lot_identity_mismatch |
| L24 | Lot 快照的 lot_id 与 open_intent_key 派生结果不符，构造或反序列化拒绝；派生 ID 非 64 位小写十六进制也拒绝 |

### 10.2 `tests/test_ipc_lots.py`

| 编号 | 验证点与预期 |
|---|---|
| P01 | 三类意图 encode/decode 往返语义一致；Decimal 不经过 Float |
| P02 | Lot 快照含负费用/未知 funding、scope/保护嵌套时往返一致 |
| P03 | 空 intents 合法；null、非数组和两项以上拒绝 |
| P04 | OPEN/CLOSE/UPDATE 与 Lot/scope/protection 每一级漏字段、多字段拒绝 |
| P05 | bot_id/account/inst_id/tag/posSide/reduceOnly/target 注入拒绝 |
| P06 | version=1/未知版本、错误 kind/generation/seq、bool version/seq 拒绝 |
| P07 | warmup 只接受空数组；类型伪造 warmup 参数也拒绝 |
| P08 | v1 `ipc.check_envelope` 仍拒绝 v2；v2 拒绝 v1，旧 target 行为未改变 |
| P09 | 数量/价格为 JSON int、Float、bool、NaN、Infinity 或非法数字字符串拒绝 |
| P10 | 嵌套重复键、无效 UTF-8、非法 JSON、过深或过大帧拒绝 |
| P11 | 截断头/正文、分段读取、连续帧复用原 framing 行为，不新增第二种帧 |
| P12 | CLOSE null 经过 wire 后仍为 null，不能变成 "0" 或当时余量 |
| P13 | UPDATE 双 null 全量清除合法；漏字段不被解释为“保持原值” |
| P14 | 规范化 "1"/"1.0"/"1e0"/+1 相同，负零归零，整数 100 不被误改成 1 |
| P15 | 内容数字改变产生不同 canonical bytes；key 不随内容变化，留作重放冲突检测 |
| P16 | canonical CLOSE null 与明确数量不同；字典顺序不影响 canonical bytes |
| P17 | 极端小数先校验再规范化，无通过尾零消除绕过精度限制 |
| P18 | lot_from_wire 派生均价/累计量使用 derived 范围，另行验证正数；负均价不能漏过 |
| P19 | 错误 op/对象类型统一转可识别协议错误，无静默默认或部分解析结果 |
| P20 | 编码函数同样校验本地构造对象、seq/generation，不靠解码端补救 |

### 10.3 不在 S1 的集成用例

后续必须覆盖，但本片不能宣称通过：同 Lot 部分成交累计、fill 去重、重叠平仓预留、TP/SL 同 tick 只产生一次关闭、撤单/成交竞态、COMMIT 前后重启、ACK 丢失、UNKNOWN 重启对账、多个 Bot 共用预算竞争、P6 跨 Bot 影响、账户资金费分摊，以及净额模式下本地减仓增加交易所方向曝险。

## 11. 现有代码接缝与验收

| 位置（本轮静态行号） | 当前事实 | S1 处理 |
|---|---|---|
| `catos/ipc.py:13–20,86–176,189–201` | v1 与 framing/严格 JSON | 只复用底层编解码，不改 VERSION |
| `catos/ipc.py:324–360` | EventResult.target_position、SMA checkpoint | 不改；v2 完整 Worker 状态契约后续设计 |
| `catos/worker_host.py:27–39,138–178` | 父侧 Bot 绑定及每 Bot 一项在途 | 保留，后续扩展而不是放开身份自报 |
| `catos/journal.py:103–116,262–284` | 单 Bot ownership、单输出 index=0 | S1 不迁移、不放宽 |
| `catos/supervisor.py:28–40,170–204,495–538` | 单 Worker/唯一 writer/提交 ACK | S1 不接入运行 |
| `catos/execution.py:149–245` | fill 更新 owner 净仓 | 不拿来更新 Lot |
| `catos/risk.py:25–30,259–300` | 10%/20% 默认和净仓风险模型 | 不改配置、不用净仓校验代替 Lot 风控 |
| `catos/protection.py:175–211` | net 整仓 P6 保护 | 不映射到逐 Lot 本地保护 |

完成定义（Definition of done，DoD）：

1. 四个目标实现/测试文件只覆盖上述纯数据切片，无 I/O、交易、迁移、策略加载或运行接线。
2. 验证模型执行两个新模块及 `tests/test_ipc.py` 最小回归，按实际输出汇报；不运行全市场回测。
3. v1 的默认、ownership、旧策略接口、锁存和保护代码不因 S1 改动。
4. 完成即停止，不自动启动持久化、Gross 风控或 Demo/Live。

提供给验证模型的测试命令示例（**本轮未执行**；从项目根目录，以指定 Python 运行）：

```text
python -B -m unittest discover -s tests -p "test_lots.py" -v
python -B -m unittest discover -s tests -p "test_ipc_lots.py" -v
python -B -m unittest discover -s tests -p "test_ipc.py" -v
```

实际执行应使用已授权环境的 Python 绝对路径，且必须先确认新测试确实被发现；0 tests 不算验收。

下一步顺序：S1 纯数据实现 → 独立验证 → 再定执行模式及 P6 兼容、日损迁移策略 → 同 writer Lot 账本与重放 → Gross/执行归属闭环 → 本地保护及只读展示。不得在 S1 顺手完成后续切片。

## 12. 来源和本轮检查范围

- 本地工作区：`C:\Users\user\Desktop\CatOS_Astra - 複製`。源码、测试和项目约定静态读取日期：2026-09-15；未确认 Git HEAD，未运行项目验证。
- 本轮官方资料读取：[OKX API V5 / Get instruments](https://www.okx.com/docs-v5/en/#trading-account-rest-api-get-instruments)。返回内容提供 ctVal、ctMult、ctValCcy、ctType 和 lotSz 定义；lotSz 对衍生品以合约张数计。未取得完整 place-order 参数正文，因此不凭该片段给出 reduceOnly 适用模式的已核实结论。
- “不依赖普通分仓 API”来自本次用户方向，而非本轮全量 API 排除性审计。
- 加密衍生品有资金费、共享保证金、强平、停机及监管风险；合成测试不能证明账户可交易、行情真实或系统可实盘。

本轮实际交付仅此规格与项目记忆更新；业务源码、风控默认、运行配置和交易数据库未修改。
