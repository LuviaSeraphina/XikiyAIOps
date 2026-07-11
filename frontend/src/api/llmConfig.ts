// ============================================================
// LLM 配置 API — 模型选择 + API Key 管理
// 对齐后端 /api/system/llm-config
// ============================================================

import { BASE_URL, apiGet, apiPost } from './client'

/** 预设模型 */
export interface PresetModel {
  id: string
  label: string
  provider: string
  base_url: string
  hint?: string
  requires_key: boolean
}

/** 自定义预设 */
export interface CustomPreset {
  id: string
  label: string
  provider: string
  base_url: string
}

/** 当前 LLM 配置 */
export interface LlmConfig {
  provider: string
  base_url: string
  model: string
  api_key_set: boolean
}

/** GET /api/system/llm-config — 读取当前配置 + 预设列表 */
export function fetchLlmConfig(): Promise<{ code: number; data: { active_preset: string; current: LlmConfig; preset_configs: Record<string, { provider: string; base_url: string; model: string; api_key_set: boolean }>; custom_presets: CustomPreset[]; presets: PresetModel[] } }> {
  return apiGet('/system/llm-config')
}

/** POST /api/system/llm-config — 保存配置 */
export function saveLlmConfig(config: {
  preset_id: string
  label?: string
  provider: string
  base_url: string
  model: string
  api_key: string
}): Promise<{ code: number; message: string }> {
  return apiPost('/system/llm-config', config)
}

/** POST /api/system/llm-config/test — 连通测试 */
export function testLlmConfig(config: {
  provider: string
  base_url: string
  api_key: string
}): Promise<{ ok: boolean; status_code?: number; detail: string }> {
  return apiPost<{ code: number; data: { ok: boolean; status_code?: number; detail: string } }>('/system/llm-config/test', config).then(res => res.data)
}

/** POST /api/system/llm-config/models — 从 base_url 拉取可用模型列表 */
export function fetchModels(config: {
  base_url: string
  api_key: string
}): Promise<{ models: string[]; detail: string }> {
  return apiPost<{ code: number; data: { models: string[]; detail: string } }>('/system/llm-config/models', config).then(res => res.data)
}

/** POST /api/system/llm-config/preset — 新增自定义预设 */
export function addPreset(preset: {
  id: string
  label: string
  provider: string
  base_url: string
}): Promise<{ code: number; message: string }> {
  return apiPost('/system/llm-config/preset', preset)
}

/** DELETE /api/system/llm-config/preset/{id} — 删除自定义预设 */
export async function deletePreset(id: string): Promise<{ code: number; message: string }> {
  const res = await fetch(BASE_URL + '/system/llm-config/preset/' + id, { method: 'DELETE' })
  return res.json()
}
