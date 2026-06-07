# T4 — swarm wiring + e2e demo + 驗收 B1–B7

> 2.0 任務 **4/4** ｜ 共用契約見 [`README.md`](README.md) ｜ **依賴：T1–T3** ｜ 收尾任務，不新增功能

## 做什麼
把 dashboard 接回 swarm 迴路、照腳本跑一遍、打勾 milestone 級驗收 B1–B7。**只串接 / 跑通 / 驗證 / 補洞。**

### 1. analyst skill：加 commentary recipe
- `agents/sub/analyst/skills/query-sunday/SKILL.md` 加一條 `POST /commentary` recipe（§7.11：analyst 推市場動態給 User；**無害寫入、auto-allow、非交易 lever**）。
- 引導：analyst 評估完 regime、`send_message` 給 friday 之後，也 `POST /commentary` 留一則 **User-facing 市場脈絡**（這是諮詢角色唯一的寫入）。
- skill 經 RP-10 Web skill 管理；更新後成員下一輪即載入新版（agent 不自寫 skill）。

### 2. friday skill/prompt：`reason` 是給人看的
- `agents/main/friday/skills/operate-sunday/SKILL.md` 補一句：`/strategy` 的 `reason` 會**直接顯示在 User dashboard 的切換時間軸上**——寫成人看得懂的決策理由，不是內部代號。

### 3. e2e demo（testnet）
1. engine + swarm 起；瀏覽器開 `/dashboard`（先空著也行）。
2. 觸發一次 regime → friday 指派 analyst → analyst **`POST /commentary`**（feed 立刻出現一則）+ `send_message` 建議 → friday **`POST /strategy`（附 reason）** → dashboard 出現切換點 + reason 疊圖、倉位表更新。
3. 讓引擎跑一段 → 權益曲線累積點；平倉一次 → `/performance` 出現該策略的 realized。
4. 全程確認：dashboard 全由 Sunday（:7777）serve；evva 端零新增程式碼。

## 驗收（B1–B7，逐項打勾）
- [ ] **B1 權益曲線**：dashboard 顯示 testnet 權益折線。
- [ ] **B2 30 日 PnL**：realized + unrealized + equity 數字卡。
- [ ] **B3 倉位**：含 strategy / entry_reason / stop。
- [ ] **B4 歸因**：per-strategy realized / 筆數 / 勝率。
- [ ] **B5 切換理由疊圖**：切換點標在曲線 + `reason` 可見。
- [ ] **B6 commentary feed**：analyst 貼文顯示。
- [ ] **B7 D12 + testnet**：全由 Sunday 自服、evva 內零新增 Sunday code、全程 testnet。

## 不在本任務
- 2.1（telegram / 外部訊號源）、2.2（回測 / ML / 多策略）、2.3（真錢 / token 硬化）。
- 觀察記錄：dashboard 對「在耐久 run 期間觀測 1.1/1.2」是否好用 → 寫一句結論，餵後續里程碑。
