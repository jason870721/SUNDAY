// Shared presentational + layout components (no-build Vue: plain objects + template
// strings). Views compose these. Keeps each view focused on data + wiring.
import * as fmt from './format.js';
import { ROUTES, route, go } from './router.js';
import { store, refreshStatus, lever, dismiss } from './store.js';
import { api } from './api.js';

// --- inline icon set (24x24 stroke) ---------------------------------------
const ICONS = {
  grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
  pulse: '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  feed: '<path d="M4 6h16M4 12h16M4 18h10"/>',
  book: '<path d="M5 4h13v16H6a2 2 0 0 1-1-1.7zM8 4v15"/>',
  swap: '<path d="M16 4l4 4-4 4M20 8H8M8 20l-4-4 4-4M4 16h12"/>',
  chat: '<path d="M4 5h16v11H8l-4 4z"/>',
  alert: '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 16.5h.01"/>',
  bell: '<path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  heart: '<path d="M12 20s-7-4.5-7-9a4 4 0 0 1 7-2 4 4 0 0 1 7 2c0 4.5-7 9-7 9z"/>',
  power: '<path d="M12 4v8M7.5 7a7 7 0 1 0 9 0"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-4l-2 2M4 13a8 8 0 0 0 14 4l2-2"/><path d="M4 5v4h4M20 19v-4h-4"/>',
  check: '<path d="M5 13l4 4L19 7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  play: '<path d="M8 5l11 7-11 7z"/>',
  scale: '<path d="M12 4v16M5 8h14M5 8l-2 5a3 3 0 0 0 6 0zM19 8l-2 5a3 3 0 0 0 6 0z"/>',
  radar: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 12l6-3"/>',
  bars: '<path d="M5 20V12M10 20V6M15 20V9M20 20V4"/>',
};

export const Icon = {
  props: { name: String, size: { type: [Number, String], default: 18 } },
  computed: { paths() { return ICONS[this.name] || ''; } },
  template: `<svg class="ic" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="paths"></svg>`,
};

// --- layout: brand / sidebar / ribbon -------------------------------------
export const Brand = {
  template: `<div class="brand"><span class="sun">☀</span><span class="name">SUNDAY</span><span class="tag">terminal</span></div>`,
};

export const Sidebar = {
  components: { Icon },
  data() { return { routes: ROUTES }; },
  computed: { active() { return route.value; } },
  methods: { go },
  template: `
    <nav class="side">
      <div v-for="r in routes" :key="r.name" class="nav-item" :class="{active: active===r.name}" @click="go(r.name)">
        <Icon :name="r.icon"/>
        <span class="lbl">{{ r.label }}</span>
        <span class="zh">{{ r.zh }}</span>
      </div>
      <div class="spacer"></div>
      <div class="foot">engine · 127.0.0.1:7777<br>testnet · loopback<br>levers → same API as swarm</div>
    </nav>`,
};

export const ConfirmModal = {
  components: { Icon },
  props: { open: Boolean, title: String, danger: Boolean, confirmText: { type: String, default: '確認' }, busy: Boolean },
  emits: ['confirm', 'cancel'],
  template: `
    <div v-if="open" class="scrim" @click.self="$emit('cancel')">
      <div class="modal">
        <div class="mh"><Icon v-if="danger" name="alert" :size="18" style="color:var(--down)"/><h3>{{ title }}</h3></div>
        <div class="mb"><slot/></div>
        <div class="mf">
          <button class="btn ghost" @click="$emit('cancel')" :disabled="busy">取消</button>
          <button class="btn" :class="danger?'danger':'primary'" @click="$emit('confirm')" :disabled="busy">
            <span v-if="busy" class="ld"></span>{{ confirmText }}
          </button>
        </div>
      </div>
    </div>`,
};

export const Ribbon = {
  components: { Icon, ConfirmModal },
  data() { return { killOpen: false, killBusy: false, killMode: 'flat' }; },
  computed: {
    st() { return store.status || {}; },
    err() { return store.statusError; },
    mode() { return this.st.mode || '—'; },
    modeTone() { return this.mode === 'active' ? 'up' : this.mode === 'halted' ? 'down' : this.mode === 'safe' ? 'warn' : ''; },
    hbOk() { return this.st.swarm_heartbeat_ok; },
    hbClass() { return this.hbOk === false ? 'bad' : this.hbOk === true ? 'ok' : ''; },
    hbText() { return this.hbOk === false ? 'stale' : this.hbOk === true ? 'live' : '—'; },
    updated() { return store.lastStatusAt ? fmt.time(store.lastStatusAt) : '—'; },
    equity() { return fmt.money(this.st.equity); },
    strat() { return this.st.strategy || '—'; },
    symbol() { return this.st.symbol || '—'; },
  },
  methods: {
    refresh() { refreshStatus(); },
    async doKill() {
      this.killBusy = true;
      const r = await lever(() => api.halt({ reason: 'User kill-switch via dashboard', mode: this.killMode }), 'Halt sent · mode=' + this.killMode);
      this.killBusy = false;
      if (r) this.killOpen = false;
    },
  },
  template: `
    <div class="ribbon">
      <div class="stat"><span class="k">Mode</span><span class="v" :class="modeTone">{{ mode }}</span></div>
      <div class="stat"><span class="k">Market</span><span class="v">{{ symbol }} · <span class="warn">{{ strat }}</span></span></div>
      <div class="stat"><span class="k">Equity USDT</span><span class="v">{{ equity }}</span></div>
      <span class="grow"></span>
      <span v-if="err" class="badge" style="color:var(--down);border-color:rgba(246,70,93,.4)" :title="err"><span class="dot bad"></span>engine unreachable</span>
      <span class="badge"><span class="dot" :class="hbClass"></span>swarm {{ hbText }}</span>
      <span class="dim mono" style="font-size:11px">upd {{ updated }}</span>
      <button class="btn ghost sm" @click="refresh" title="refresh status"><Icon name="refresh" :size="15"/></button>
      <button class="btn danger sm" @click="killOpen=true"><Icon name="power" :size="15"/>KILL</button>
      <ConfirmModal :open="killOpen" :busy="killBusy" danger title="Kill-switch · POST /halt"
        :confirmText="'Halt ('+killMode+')'" @cancel="killOpen=false" @confirm="doKill">
        <p>對 Sunday 下達 halt。確定性風控仍在，但這會凍結/平掉倉位——這是 agent 也能拉的同一根 lever。</p>
        <div class="seg" style="margin-top:6px">
          <button :class="{on:killMode==='flat'}" @click="killMode='flat'">flat · 全平</button>
          <button :class="{on:killMode==='safe'}" @click="killMode='safe'">safe · 凍新倉</button>
        </div>
      </ConfirmModal>
    </div>`,
};

// --- presentational primitives --------------------------------------------
export const Panel = {
  props: { title: String, hint: String, flush: Boolean },
  template: `
    <section class="panel" :class="{flush}">
      <div class="ph" v-if="title || $slots.head">
        <h2 v-if="title">{{ title }}</h2>
        <span class="grow"></span>
        <slot name="head"/>
        <span class="hint" v-if="hint">{{ hint }}</span>
      </div>
      <div class="pb"><slot/></div>
    </section>`,
};

export const Kpi = {
  props: { k: String, v: [String, Number], sub: String, tone: String },
  template: `<div class="kpi" :class="tone"><div class="k">{{ k }}</div><div class="v">{{ v }}</div><div class="sub" v-if="sub">{{ sub }}</div></div>`,
};

export const Gauge = {
  props: { label: String, ratio: Number, value: String, cap: String },
  computed: {
    pctW() { const r = this.ratio; return r == null ? 0 : Math.max(2, Math.min(100, r * 100)); },
    tone() { const r = this.ratio || 0; return r >= 1 ? 'bad' : r >= 0.8 ? 'warn' : ''; },
  },
  template: `
    <div class="gauge">
      <div class="gh"><span class="gk">{{ label }}</span><span class="gv" :class="tone">{{ value }}<span class="dim" v-if="cap"> / {{ cap }}</span></span></div>
      <div class="bar" :class="tone"><span :style="{width: pctW+'%'}"></span></div>
    </div>`,
};

export const VoteBar = {
  props: { vote: Object },
  computed: {
    dirClass() { return this.vote.vote === 'long' ? 'long' : this.vote.vote === 'short' ? 'short' : 'flat'; },
    barColor() { return this.vote.vote === 'long' ? 'var(--up)' : this.vote.vote === 'short' ? 'var(--down)' : 'var(--fg-mut)'; },
    nameClass() { return this.vote.strategy === 'momentum' ? 'mom' : this.vote.strategy === 'mean_reversion' ? 'mr' : 'flat'; },
    confW() { return Math.max(3, Math.min(100, (this.vote.confidence || 0) * 100)); },
    inds() { return Object.entries(this.vote.indicators || {}).map(([k, v]) => k + ' ' + v).join('  ·  '); },
  },
  template: `
    <div class="vote">
      <div><span class="tag" :class="nameClass">{{ vote.strategy }}</span> <span class="tag" :class="dirClass" style="margin-left:4px">{{ vote.vote }}</span></div>
      <div class="vbar"><span :style="{width: confW+'%', background: barColor}"></span></div>
      <div class="vmeta">{{ (vote.confidence*100).toFixed(0) }}%</div>
      <div style="grid-column:1/-1" class="rationale">{{ vote.rationale }}<span v-if="inds" class="dim mono" style="display:block;margin-top:4px;font-size:11px">{{ inds }}</span></div>
    </div>`,
};

export const Empty = {
  props: { msg: { type: String, default: '尚無資料' } },
  template: `<div class="empty"><slot>{{ msg }}</slot></div>`,
};

export const Toasts = {
  computed: { items() { return store.toasts; } },
  methods: { dismiss },
  template: `
    <div class="toasts">
      <div v-for="t in items" :key="t.id" class="toast" :class="t.kind">
        <span class="bar"></span>
        <span class="msg grow">{{ t.msg }}</span>
        <button class="x" @click="dismiss(t.id)">×</button>
      </div>
    </div>`,
};
