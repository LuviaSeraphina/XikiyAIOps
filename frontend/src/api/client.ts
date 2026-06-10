// ============================================================
// API 客户端 — 统一 HTTP 封装
// 所有请求必须通过此模块，禁止在组件/Store 中直接 fetch
// ============================================================

const BASE_URL = '/api'
const DEFAULT_TIMEOUT = 30_000 // 30 秒

/** API 错误（含 HTTP 状态码） */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** 根据 HTTP 状态码生成友好消息 */
function httpMessage(status: number): string {
  switch (status) {
    case 400: return '请求参数有误'
    case 401: return '未登录或会话已过期'
    case 403: return '没有权限执行此操作'
    case 404: return '请求的资源不存在'
    case 429: return '请求过于频繁，请稍后重试'
    case 500: return '服务器内部错误'
    case 502: return '网关错误'
    case 503: return '服务暂不可用'
    default:  return `请求失败 (${status})`
  }
}

/** 带超时的 fetch */
async function request(
  url: string,
  init: RequestInit = {},
  timeout: number = DEFAULT_TIMEOUT,
  externalSignal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  // 外部信号也联动取消
  if (externalSignal) {
    if (externalSignal.aborted) {
      clearTimeout(timer)
      throw new DOMException('已取消', 'AbortError')
    }
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  try {
    const res = await fetch(url, { ...init, signal: controller.signal })
    return res
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw e // 保留 AbortError 给上层判断
    }
    throw new ApiError('网络连接失败，请检查网络', 0)
  } finally {
    clearTimeout(timer)
  }
}

/** 统一处理响应：ok → JSON，否则抛 ApiError */
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new ApiError(httpMessage(res.status), res.status)
  }
  try {
    return (await res.json()) as T
  } catch {
    throw new ApiError('响应格式异常', res.status)
  }
}

/**
 * GET 请求
 * @param path   绝对路径，如 '/chat/history'
 * @param params 可选 query 参数
 * @param timeoutMs 超时毫秒
 * @param signal 可选的 AbortSignal，用于组件卸载时取消请求
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, string>,
  timeoutMs?: number,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(BASE_URL + path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== '') {
        url.searchParams.set(k, v)
      }
    }
  }
  const res = await request(url.toString(), {}, timeoutMs, signal)
  return handleResponse<T>(res)
}

/**
 * POST 请求
 * @param path 绝对路径，如 '/chat/send'
 * @param body JSON 请求体
 * @param timeoutMs 超时毫秒
 */
export async function apiPost<T>(
  path: string,
  body: unknown,
  timeoutMs?: number,
): Promise<T> {
  const res = await request(
    BASE_URL + path,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    timeoutMs,
  )
  return handleResponse<T>(res)
}

export { BASE_URL }
