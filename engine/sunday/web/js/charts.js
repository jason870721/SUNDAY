// TradingView lightweight-charts factories (vendored). Two charts:
//   makeEquityChart  — equity line + strategy-switch markers (the D14 reason overlay)
//   makeMarketChart  — OHLCV candlesticks + volume
// Both degrade to null if the lib failed to load; views render a fallback note.

const LWC = window.LightweightCharts;
export const hasCharts = () => !!LWC;

// lightweight-charts renders the time axis in UTC; shift by the local tz offset so
// the axis matches the local wall-clock times shown everywhere else in the UI.
const TZ = -new Date().getTimezoneOffset() * 60;
const toSec = (ms) => Math.floor(ms / 1000) + TZ;

const THEME = {
  layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#8b97a7', fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace' },
  grid: { vertLines: { color: 'rgba(30,38,50,0.6)' }, horzLines: { color: 'rgba(30,38,50,0.6)' } },
  rightPriceScale: { borderColor: '#1e2632' },
  timeScale: { borderColor: '#1e2632', timeVisible: true, secondsVisible: false },
  crosshair: { mode: LWC ? LWC.CrosshairMode.Normal : 0, vertLine: { color: '#3a4656', labelBackgroundColor: '#222c3a' }, horzLine: { color: '#3a4656', labelBackgroundColor: '#222c3a' } },
  autoSize: false,
};

// strictly-ascending, unique-time series (lightweight-charts requires it).
function clean(points) {
  const m = new Map();
  for (const p of points) if (p && Number.isFinite(p.time)) m.set(p.time, p);
  return [...m.values()].sort((a, b) => a.time - b.time);
}

function base(container) {
  const chart = LWC.createChart(container, {
    ...THEME,
    width: container.clientWidth,
    height: container.clientHeight || 320,
  });
  const ro = new ResizeObserver(() => chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 320 }));
  ro.observe(container);
  return {
    chart,
    destroy() { try { ro.disconnect(); chart.remove(); } catch { /* already gone */ } },
    fit() { chart.timeScale().fitContent(); },
  };
}

export function makeEquityChart(container) {
  if (!LWC) return null;
  const b = base(container);
  const line = b.chart.addAreaSeries({
    lineColor: '#5ccfe6', topColor: 'rgba(92,207,230,0.18)', bottomColor: 'rgba(92,207,230,0.01)',
    lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
  });

  // Floating tooltip: hovering a switch marker shows its strategy + reason (D14).
  const tip = document.createElement('div');
  tip.className = 'chart-tip';
  tip.style.cssText = 'position:absolute;display:none;pointer-events:none;z-index:5;max-width:280px;'
    + 'background:#18202e;border:1px solid #2a3543;border-radius:8px;padding:8px 10px;font:12px var(--font-sans);'
    + 'box-shadow:0 8px 24px rgba(0,0,0,.5)';
  container.appendChild(tip);
  let byTime = new Map();
  const COLORS = { momentum: '#5ccfe6', mean_reversion: '#c792ea', flat: '#8b97a7' };

  b.chart.subscribeCrosshairMove((param) => {
    const s = param.time != null ? byTime.get(param.time) : null;
    if (!s || !param.point) { tip.style.display = 'none'; return; }
    tip.innerHTML = `<div style="font-weight:700;color:${COLORS[s.strategy] || '#f0b90b'}">→ ${s.strategy}`
      + ` <span style="color:#5e6b7d;font-weight:400">· ${s.set_by || ''}</span></div>`
      + `<div style="color:#9aa7b8;margin-top:3px;line-height:1.45">${(s.reason || '(無理由)').replace(/[<>&]/g, '')}</div>`;
    tip.style.display = 'block';
    const x = Math.min(param.point.x + 14, container.clientWidth - tip.clientWidth - 8);
    tip.style.left = Math.max(4, x) + 'px';
    tip.style.top = Math.max(4, param.point.y + 12) + 'px';
  });

  return {
    ...b,
    destroy() { try { tip.remove(); } catch { /* gone */ } b.destroy(); },
    // curve = [[ts_ms, equity], ...]; switches = [{set_at_ms, strategy, reason, set_by}, ...]
    setData(curve, switches) {
      const data = clean((curve || []).map(([ms, eq]) => ({ time: toSec(ms), value: Number(eq) })));
      line.setData(data);
      const times = data.map((d) => d.time);
      const nearest = (t) => (times.length ? times.reduce((best, x) => (Math.abs(x - t) < Math.abs(best - t) ? x : best), times[0]) : t);
      byTime = new Map();
      const markers = clean((switches || []).map((s) => {
        const t = nearest(toSec(s.set_at_ms));
        byTime.set(t, s);
        return { time: t, position: 'belowBar', color: COLORS[s.strategy] || '#f0b90b', shape: 'arrowUp', text: s.strategy };
      }));
      if (markers.length) line.setMarkers(markers);
      b.fit();
    },
  };
}

export function makeCompareChart(container) {
  if (!LWC) return null;
  const b = base(container);
  const COLORS = { desk: '#5ccfe6', buy_hold: '#8b97a7', funding_carry: '#f0b90b' };
  const series = {};
  return {
    ...b,
    // data = { desk: [[ms,v],...], buy_hold: [...], funding_carry: [...] }
    setData(data) {
      for (const [name, curve] of Object.entries(data || {})) {
        if (!series[name]) {
          series[name] = b.chart.addLineSeries({
            color: COLORS[name] || '#c792ea', lineWidth: 2, priceLineVisible: false,
            lastValueVisible: true, title: name,
          });
        }
        series[name].setData(clean((curve || []).map(([ms, v]) => ({ time: toSec(ms), value: Number(v) }))));
      }
      b.fit();
    },
  };
}

export function makeMarketChart(container) {
  if (!LWC) return null;
  const b = base(container);
  const candles = b.chart.addCandlestickSeries({
    upColor: '#2ebd85', downColor: '#f6465d', borderUpColor: '#2ebd85', borderDownColor: '#f6465d',
    wickUpColor: '#2ebd85', wickDownColor: '#f6465d',
  });
  const vol = b.chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '', color: '#2a3440' });
  b.chart.priceScale('').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  return {
    ...b,
    // ohlcv = [[ts_ms, o, h, l, c, v], ...]
    setData(ohlcv) {
      const rows = clean((ohlcv || []).map((r) => ({ time: toSec(r[0]), open: +r[1], high: +r[2], low: +r[3], close: +r[4], volume: +r[5] })));
      candles.setData(rows.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
      vol.setData(rows.map(({ time, open, close, volume }) => ({ time, value: volume, color: close >= open ? 'rgba(46,189,133,0.4)' : 'rgba(246,70,93,0.4)' })));
      b.fit();
    },
  };
}
