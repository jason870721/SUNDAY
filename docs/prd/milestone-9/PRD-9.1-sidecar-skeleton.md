# PRD-9.1 — Phase 1：MCP sidecar 骨架 + spike 工具

> 目標：把「evva ↔ sidecar ↔ engine」整條鏈打通並可驗收。出 Phase 1 時系統還沒有任何
> 行為變更（settings.json 未 commit、prompts 未動）——這是純粹的新增面，隨時可棄。

## 1. 範圍

- `engine/sunday_mcp/` 新套件：行程進入點、FastMCP server、urllib client、整形/錯誤純函式的最小版。
- 3 個 spike 工具：`ping`、`markets_list`、`positions`——覆蓋「無 upstream 呼叫 / 唯讀小 payload / 唯讀含整形」三種形態。
- `GET /healthz`（sidecar 自身 + 對 engine `/health` 的 probe 結果）。
- `scripts/smoke-mcp.sh` + 單元測試。
- **非範圍**：其餘工具（Phase 2/3）、settings.json commit、prompt/skill 改動（Phase 4）。

## 2. 技術設計

### 2.1 依賴與行程

- `engine/pyproject.toml` 加 optional group（主依賴不動，invariant S7）：

  ```toml
  [project.optional-dependencies]
  mcp = ["mcp>=1.9"]   # 官方 python SDK；實作時釘到當下最新 minor（需 streamable HTTP 支援）
  ```

- 行程：`python -m sunday_mcp`。`__main__.py` 惰性 import `server.py`（唯一碰 SDK 的模組）；
  SDK 未安裝時印出一行安裝指引退出（exit 1），不 traceback。
- transport：**streamable HTTP**，`127.0.0.1:7780`，path `/mcp`。
  選 HTTP 不選 stdio 的原因：7 個 swarm 成員各有自己的 MCP manager，stdio 會 spawn 7 條
  python 子行程；HTTP 一個共享行程、可觀測、可獨立重啟。
- 環境變數（全部有預設，無 .env 耦合）：

  | var | default | 用途 |
  | --- | --- | --- |
  | `SUNDAY_BASE_URL` | `http://127.0.0.1:7777` | engine 位址 |
  | `SUNDAY_MCP_PORT` | `7780` | 監聽埠 |
  | `SUNDAY_MCP_UPSTREAM_TIMEOUT_S` | `20` | 單次 upstream 呼叫 timeout |

### 2.2 `client.py`（stdlib urllib，invariant S1/S5/S7）

```python
def call(method: str, path: str, *, query: dict | None = None, body: dict | None = None,
         agent: str | None = None, timeout: float | None = None) -> Reply
# Reply = dataclass(status: int, json: dict | list | None, text: str)
```

- JSON in/out；`agent` 非 None 時帶 `X-Agent` header。
- **重試規則（S5）**：僅 `GET` 且僅連線層失敗（`URLError`/timeout）重試一次（間隔 1s）；
  HTTP 4xx/5xx **不是**失敗——原樣回 `Reply`（agent 要讀 400 body）。非 GET 一律零重試。
- 測試縫：module-level `opener` 可注入（`tests/test_mcp_client.py` 用假 opener，無網路）。

### 2.3 `server.py`（FastMCP 組裝）

- `FastMCP("sunday", host="127.0.0.1", port=...)`；工具一律薄函式：
  `輸入(已由 SDK schema 驗過) → client.call → shaping/errors 純函式 → str`。
- 唯讀工具標 MCP tool annotations `readOnlyHint=true`（對 bypass mode 無作用，留給未來權限 hygiene）。
- custom route `GET /healthz` → `{"ok": true, "engine": {"reachable": bool, "status": int|null}}`
  （probe `GET /health`，500ms timeout，失敗不拋——healthz 永遠 200，內容說真話）。

### 2.4 Phase 1 工具規格

| 工具 | 輸入 schema | 行為 | 輸出 |
| --- | --- | --- | --- |
| `ping` | `{}` | 不打 upstream；回 sidecar 版本 + healthz 同款 engine probe | `sunday-mcp ok · engine reachable (200)` 一行 |
| `markets_list` | `sort?: enum[volume,change,symbol,last]=volume` · `order?: enum[desc,asc]=desc` · `search?: str` · `page?: int≥1=1` · `page_size?: int 1..20=10` | `GET /api/markets`（search → `?symbol=`） | 表格式行：`SYMBOL  last  24h%  volume_usd`，尾行 `page X · total Y · has_more` |
| `positions` | `{}` | `GET /api/account/positions?page_size=50` | 每倉一行：`SYMBOL side qty @entry mark roi% lev margin_mode liq_dist% TP/SL(sl_covers) memo(≤60字)`；空倉回 `no open positions` |

整形規則（`shaping.py` 純函式，Phase 2 全面沿用）：

- 數字裁切：價格保留交易所精度原樣（字串透傳），百分比 2 位小數，USD 量級用 `k/M` 後綴。
- `protection` 欄渲染：`TP✓ SL✓`、`SL✗(naked)`、`SL?(unknown)`（null ≠ 沒有，沿用引擎語義）。
- 任何整形函式輸入為引擎回的 dict、輸出為 str——**不碰 SDK 型別**（S7）。

### 2.5 錯誤呈現（`errors.py` 最小版）

- `Reply.status >= 400` → 工具**正常結果**（非 tool error）：`[sunday 400] <body 原文>`。
- 連線失敗（重試後仍敗）→ tool error：
  `sunday engine unreachable after retry — check GET /health; fall back to http_request if urgent (RUNBOOK)`。

## 3. 測試

| 檔案 | 內容 |
| --- | --- |
| `tests/test_mcp_client.py` | 假 opener：GET 連線失敗重試一次成功 / 二連敗丟錯；POST 連線失敗零重試；4xx 原樣回 Reply 不重試；X-Agent header 注入 |
| `tests/test_mcp_shaping.py` | markets/positions 整形：正常 / 空列表 / protection 三態（✓/✗/?）/ memo 截斷 |

全部 stdlib-only，`./scripts/run-tests.sh` 直接涵蓋（unittest discover 撿得到）。

`scripts/smoke-mcp.sh`（需 live engine + sidecar + `pip install -e '.[mcp]'`）：用 SDK 的
python client 連 `:7780/mcp` → `initialize` → `tools/list` 斷言 3 工具 → 呼叫 `ping` 與
`markets_list` 斷言非空輸出 → curl `/healthz` 斷言 `ok:true`。

## 4. 驗收清單

- [ ] `./scripts/run-tests.sh` 全綠（既有 187 + 新增；無 SDK 環境照跑）。
- [ ] `pip install -e '.[mcp]'` 後 `python -m sunday_mcp` 起得來；未裝 SDK 時一行指引退出。
- [ ] `scripts/smoke-mcp.sh` 綠（against live engine）。
- [ ] operator 本機放 `.evva/settings.json`（**不 commit**）重啟 evva：`/mcp` 面板顯示 `sunday`
      connected、tool count = 3；任一成員 `tool_search` 查得到 `mcp__sunday__positions` 並成功呼叫。
- [ ] 引擎目錄 `engine/sunday/` 零 diff（S2）。

## 5. 風險

| 風險 | 對策 |
| --- | --- |
| SDK streamable HTTP API 在 minor 版本間變動 | 實作時釘版 `mcp>=X.Y,<X.Y+1`；smoke 腳本就是升版回歸測試 |
| evva 對 server 斷線的重連行為未知 | Phase 1 驗收加一條手動測：殺 sidecar → 重啟 → 成員下一次呼叫是否自癒；結果記進 PRD-9.4 的 RUNBOOK 素材 |

— operator + Claude，2026-06-12
