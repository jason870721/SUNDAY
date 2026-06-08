// Root app: shell layout (brand · ribbon · sidebar · main) + hash-routed views +
// global toasts. Starts the shared /status polling loop. Mounts onto #app.
import { createApp, computed } from './vue.js';
import { route } from './router.js';
import { startPolling } from './store.js';
import { Brand, Sidebar, Ribbon, Toasts } from './components.js';

import Overview from './views/overview.js';
import Desk from './views/desk.js';
import Strategy from './views/strategy.js';
import Risk from './views/risk.js';
import Ablation from './views/ablation.js';
import Reports from './views/reports.js';
import Manual from './views/manual.js';

const VIEWS = { overview: Overview, desk: Desk, strategy: Strategy, risk: Risk,
  ablation: Ablation, reports: Reports, manual: Manual };

const App = {
  components: { Brand, Sidebar, Ribbon, Toasts },
  setup() {
    const current = computed(() => VIEWS[route.value] || Overview);
    return { current };
  },
  template: `
    <div class="shell">
      <Brand/>
      <Ribbon/>
      <Sidebar/>
      <main class="main"><component :is="current"/></main>
    </div>
    <Toasts/>`,
};

startPolling(10000);
createApp(App).mount('#app');
