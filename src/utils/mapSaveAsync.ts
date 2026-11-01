/**
 * 后台保存：优先用 Web Worker 做 serializeMap，失败时回退主线程，保证保存永远可用。
 * 快照用 toRaw + postMessage 的结构化克隆，避免把 Vue 响应式 Proxy 传进 Worker。
 */
import { toRaw } from 'vue'
import { serializeMap } from './mapSerializer'

interface WorkerReply {
  id: number
  ok: boolean
  json?: string
  error?: string
}

let worker: Worker | null = null
let workerUnavailable = false
let seq = 0
const pending = new Map<number, { resolve: (json: string) => void; reject: (err: unknown) => void }>()

function syncSerialize(mapData: any): string {
  return JSON.stringify(serializeMap(mapData))
}

function handleWorkerFailure(err: unknown) {
  workerUnavailable = true
  for (const item of pending.values()) item.reject(err)
  pending.clear()
  worker?.terminate()
  worker = null
}

function ensureWorker(): Worker | null {
  if (worker || workerUnavailable) return worker
  try {
    worker = new Worker(new URL('./mapSaveWorker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (event: MessageEvent<WorkerReply>) => {
      const reply = event.data
      const item = pending.get(reply.id)
      if (!item) return
      pending.delete(reply.id)
      if (reply.ok && typeof reply.json === 'string') item.resolve(reply.json)
      else item.reject(new Error(reply.error || '地图序列化失败'))
    }
    worker.onerror = (event) => {
      handleWorkerFailure(event)
    }
  } catch {
    workerUnavailable = true
    worker = null
  }
  return worker
}

/** 序列化地图为 JSON 字符串（优先后台线程；Worker 不可用或失败时回退主线程） */
export async function serializeMapAsync(mapData: any): Promise<string> {
  const w = ensureWorker()
  if (!w) {
    try {
      return syncSerialize(mapData)
    } catch (err) {
      throw err
    }
  }

  const id = ++seq
  try {
    return await new Promise<string>((resolve, reject) => {
      pending.set(id, { resolve, reject })
      try {
        // 结构化克隆：Vue 的响应式 Proxy 不能直接 postMessage，先取原始对象
        w.postMessage({ id, mapData: toRaw(mapData) })
      } catch (err) {
        pending.delete(id)
        reject(err)
      }
    })
  } catch (err) {
    // Worker 出错（极少见）：退回主线程再试一次，绝不让保存直接失败
    try {
      return syncSerialize(mapData)
    } catch {
      throw err
    }
  }
}
