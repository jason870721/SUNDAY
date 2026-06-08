# Milestone 4.1 — 一個月 testnet running test RUNBOOK

> 配 [`README.md`](README.md) §7 + [`product-plan.md`](product-plan.md) §7。**全程 testnet（M4-D9）；防守先行（M4-D6）。**
> 目的：第一次讓 evva-swarm + Sunday 連續自主跑滿一個月，驗 ① swarm 耐久 ② 研究台機制 ③ **資訊 edge 的方向與幅度（ablation）**。**不是「跑一個月看賺多少」**——賺賠是 testnet 的、不計分；edge 的統計訊號才是產出。

---

## 0. 前置（一次性）

- docker postgres（:5432）+ redis（:6379）起著；`engine/.env` 有 testnet key（**永不 commit**）。
- evva service 起著（`:8888`），swarm space `sunday` 已 `evva swarm .` 載入新 roster。
- 確認 `evva-swarm.yml` 是研究台 roster（friday + analyst-flow/news + risk-monitor + reviewer）。

## 1. Pre-flight（開跑前 checklist）

```bash
cd engine && .venv/bin/uvicorn sunday.app:app --host 127.0.0.1 --port 7777   # 啟動（自動套 migrations）
```

- [ ] `GET /health` → `{db:true, redis:true}`。
- [ ] **封套保守**（M4-D6）：`GET /envelope` = 單筆 ≤1500 / 總曝險 ≤3000 / 槓桿 ≤3 / 回撤 5% / stop 0.02。不對就 `POST /envelope` 設定。
- [ ] **資訊層活著**：等 1-2 個 tick（~2 分鐘）後 `GET /desk` 三個標的有 funding/OI/基差值（非全 null）。
- [ ] **ablation 開**：`GET /ablation` 回得了（shadow 曲線開始累積）；若要做 info-ON/OFF 切分，設 `.env` 的 `INFO_OFF_SYMBOLS=SOLUSDT`（半籃子對照）後重啟。
- [ ] **dead-man wired**：friday 30m heartbeat 排程在跑；殺 Sunday 一次確認 friday 偵測並告警（V7）。
- [ ] **permission**：lever POST（/thesis·/strategy·/halt·/envelope）會跳審批；唯讀 GET allow-rule 放行（見 evva permission 設定）。
- [ ] RP-11/12 未實作 → 降級跑：事件全進 leader、leader 手動回信採納與否（記為已知限制）。

## 2. During（跑一個月）

- **每日**：reviewer cron（17:00）產出復盤——查 `/theses`·`/performance`·`/pnl`·`/ablation`，寫 playbook commentary + 交 friday 建議。
- **每週**：人工看 `GET /ablation` 中間對照（desk vs buy_hold/funding_carry，info-ON vs info-OFF realized）+ `/dashboard` Ablation 頁；記 incident log。
- **V8 注入測**（至少各一次）：
  ```bash
  # 假事件喚醒 swarm（經 evva webhook）——確認對應 analyst 醒來、走完 thesis 流程
  curl -sX POST http://127.0.0.1:8888/api/swarm/sunday/event \
    -H 'Content-Type: application/json' \
    -d '{"title":"notable: SOLUSDT · funding_extreme","body":"injected test: funding spiked","data":{"event_type":"funding_extreme"}}'
  ```
- **V5 成本**：每日記 token/run；平靜時段確認 swarm idle（`/desk` 無 notable → 無 webhook → 不燒 token）。
- **V7 dead-man**：自然或注入觸發 safe-mode（停 friday heartbeat ~90m）+ engine_degraded 各一次。

## 3. 監看端點（人 + agent 共用）

| 看什麼 | 端點 |
| --- | --- |
| 此刻哪裡有事 | `GET /desk` |
| 當前 thesis / 史 + 結果 | `GET /thesis?symbol=` · `GET /theses` |
| 風險 vs 封套 + 熔斷事件 | `GET /risk` |
| **edge 對照（生死線）** | `GET /ablation` |
| swarm 喚醒事件 | `GET /events` |
| User 面板 | `/dashboard`（Overview / Desk / Strategy / Risk / Reports / Ablation） |

## 4. Exit gate（一個月後產出三份）

1. **swarm 耐久報告**：V1（連續自主）/ V5（idle 不燒 token）/ V7（雙向 dead-man）在一個月真實時間下成立。
2. **研究台機制報告**：每條協作箭頭有佐證（事件→專責 analyst→friday 綜合→risk 踢館→拍板→directed 執行→reviewer 復盤），證據 = `.vero` messages + `/theses` + `/events` + commentary。
3. **ablation 報告**：`GET /ablation` 的 desk vs 基準 + **info-ON vs info-OFF** 風險調整對照 + per-thesis/per-driver 歸因。

**通過** = 機制正確 + ablation 顯示資訊層有**方向性**加值（即使幅度小、樣本小）。
**不通過不是失敗**——是「資訊 edge 假設被證偽」的寶貴結論，省下真錢。**轉真錢（Gate-2）gated on 這份報告（M4-D9）。**

## 5. 緊急處置

```bash
# 全平整個籃子 + invalidate 所有 thesis（kill-switch）
curl -sX POST http://127.0.0.1:7777/halt -H 'Content-Type: application/json' -d '{"reason":"<why>","mode":"flat"}'
# 只凍新倉、守既有 stop
curl -sX POST http://127.0.0.1:7777/halt -H 'Content-Type: application/json' -d '{"reason":"<why>","mode":"safe"}'
```

確定性風控（封套 / drawdown 熔斷）全程在 Python/交易所層自動運作，與 swarm 是否存活無關——swarm 掛掉 → Sunday 進 safe-mode 守舊倉。
