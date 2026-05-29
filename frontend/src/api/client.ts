export const BASE_URL = '/api'

/**
 * GET 请求封装
 * @param path   API 路径，如 '/dashboard/summary'
 * @param params 可选的 query 参数
 */
export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(BASE_URL + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

/**
 * POST 请求封装
 * @param path API 路径
 * @param body JSON 请求体
 */
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE_URL + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}
