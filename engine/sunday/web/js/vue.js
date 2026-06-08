// Re-export the bits of Vue 3 we use from the vendored global build (window.Vue).
// This keeps every other module importing `from './vue.js'` instead of touching
// the global directly — one place to see the Vue surface we depend on, no build step.
const V = window.Vue;
if (!V) throw new Error('Vue global build failed to load (vendor/vue.global.prod.js)');

export const {
  createApp, reactive, ref, computed, watch, watchEffect,
  onMounted, onBeforeUnmount, onUnmounted, nextTick, h, defineComponent,
} = V;
