// Minimal hash router — the SPA has five fixed sections, so a dependency-free
// hash switch beats pulling in vue-router (keeps the no-build footprint small).
import { ref } from './vue.js';

export const ROUTES = [
  { name: 'overview', label: 'Overview', zh: '總覽', icon: 'grid' },
  { name: 'desk', label: 'Desk', zh: '研究台', icon: 'radar' },
  { name: 'strategy', label: 'Strategy', zh: '策略', icon: 'pulse' },
  { name: 'risk', label: 'Risk', zh: '風險', icon: 'shield' },
  { name: 'ablation', label: 'Ablation', zh: '驗證', icon: 'bars' },
  { name: 'reports', label: 'Reports', zh: '報告', icon: 'feed' },
  { name: 'manual', label: 'Manual', zh: '手冊', icon: 'book' },
];

const NAMES = new Set(ROUTES.map((r) => r.name));

function parseHash() {
  const n = (location.hash || '').replace(/^#\/?/, '').split('?')[0];
  return NAMES.has(n) ? n : 'overview';
}

export const route = ref(parseHash());

window.addEventListener('hashchange', () => { route.value = parseHash(); });

export function go(name) {
  if (location.hash !== '#/' + name) location.hash = '#/' + name;
  else route.value = name;
}
