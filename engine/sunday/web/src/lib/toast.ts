import { reactive } from 'vue'

export interface Toast { id: number; text: string; kind: 'ok' | 'err' | 'info' }

const state = reactive<{ items: Toast[] }>({ items: [] })
let seq = 0

export function useToasts() { return state }

export function toast(text: string, kind: Toast['kind'] = 'info'): void {
  const id = ++seq
  state.items.push({ id, text, kind })
  setTimeout(() => {
    const i = state.items.findIndex((t) => t.id === id)
    if (i >= 0) state.items.splice(i, 1)
  }, 4500)
}

/** Wrap an async action: surface its error as a toast, return undefined on failure. */
export async function attempt<T>(fn: () => Promise<T>, ok?: string): Promise<T | undefined> {
  try {
    const r = await fn()
    if (ok) toast(ok, 'ok')
    return r
  } catch (e) {
    toast((e as Error).message || 'request failed', 'err')
    return undefined
  }
}
