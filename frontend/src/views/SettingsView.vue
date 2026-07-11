<template>
  <div class="settings-view">
    <header class="settings-header">
      <div>
        <h1 class="settings-title">模型配置</h1>
        <p class="settings-subtitle">选择 LLM 模型并配置 API Key</p>
      </div>
      <span class="config-status" :class="{ configured: hasValidConfig }">
        <span class="status-dot" />
        {{ hasValidConfig ? '已配置' : '未配置' }}
      </span>
    </header>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
        <circle cx="12" cy="12" r="10" opacity="0.3"/><path d="M12 2a10 10 0 0 1 10 10"/>
      </svg>
      加载配置中...
    </div>

    <template v-else>
      <!-- ====== 预设模型选择 ====== -->
      <section class="section">
        <div class="section-header">
          <h2 class="section-title">预设模型</h2>
          <button
            class="manage-btn"
            :class="{ active: manageMode }"
            @click="manageMode = !manageMode"
          >
            <svg v-if="!manageMode" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            {{ manageMode ? '完成' : '管理' }}
          </button>
        </div>
        <div class="preset-grid" :class="{ 'manage-mode': manageMode }">
          <!-- 内置预设 -->
          <button
            v-for="preset in presets"
            :key="preset.id"
            class="preset-card"
            :class="{ active: selectedPresetId === preset.id, 'disabled-card': manageMode }"
            @click="!manageMode && selectPreset(preset)"
          >
            <div class="preset-icon" :class="providerClass(preset.id)">
              <img :src="getIconSrc(preset.id)" :alt="preset.label" />
            </div>
            <div class="preset-info">
              <span class="preset-label">{{ preset.label }}</span>
              <span class="preset-url">{{ preset.base_url }}</span>
            </div>
            <span class="feasibility-badge" :class="getFeasibilityState(preset.id)">
              <span class="feasibility-dot">
                <svg v-if="getFeasibilityState(preset.id) === 'ok'" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                <svg v-else-if="getFeasibilityState(preset.id) === 'fail'" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
                <span v-else class="feasibility-ring"></span>
              </span>
              <span class="feasibility-text">{{ { ok: '正常', fail: '异常', unconfigured: '未配置' }[getFeasibilityState(preset.id)] }}</span>
            </span>
            <span v-if="manageMode" class="lock-badge" title="内置预设不可删除">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </span>
            <span v-if="!manageMode && activePresetId === preset.id" class="check-mark">
              <span class="check-label">正在使用</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </span>
          </button>
          <!-- 自定义预设 -->
          <transition-group name="card-anim">
            <button
              v-for="cp in customPresets"
              :key="cp.id"
              class="preset-card custom-card"
              :class="{ active: selectedPresetId === cp.id, 'manage-active': manageMode }"
              @click="!manageMode && selectCustomPreset(cp)"
            >
              <div class="preset-icon custom-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
              </div>
              <div class="preset-info">
                <span class="preset-label">{{ cp.label }}</span>
                <span class="preset-url">{{ cp.base_url }}</span>
              </div>
              <span class="feasibility-badge" :class="getFeasibilityState(cp.id)">
                <span class="feasibility-dot">
                  <svg v-if="getFeasibilityState(cp.id) === 'ok'" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <svg v-else-if="getFeasibilityState(cp.id) === 'fail'" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                  <span v-else class="feasibility-ring"></span>
                </span>
                <span class="feasibility-text">{{ { ok: '正常', fail: '异常', unconfigured: '未配置' }[getFeasibilityState(cp.id)] }}</span>
              </span>
              <button v-if="manageMode" class="delete-btn" @click.stop="handleDeletePreset(cp.id)" title="删除此预设">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
              <span v-if="!manageMode && activePresetId === cp.id" class="check-mark">
                <span class="check-label">正在使用</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </span>
            </button>
          </transition-group>
          <!-- 添加预设按钮 (管理模式下隐藏) -->
          <transition name="card-anim">
            <button v-if="!manageMode" class="preset-card add-card" @click="handleAddPresetQuick">
              <div class="add-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
              </div>
              <div class="preset-info">
                <span class="preset-label">添加自定义 Provider</span>
              </div>
            </button>
          </transition>
        </div>
      </section>

      <!-- ====== 自定义配置 ====== -->
      <section class="section">
        <h2 class="section-title">连接配置</h2>

        <div class="form-grid">
          <!-- Provider Name (用户自定义) -->
          <div class="form-field full">
            <label>供应商名称</label>
            <input
              v-model="form.provider_name"
              class="form-input"
              placeholder="DeepSeek"
            />
          </div>

          <!-- Base URL -->
          <div class="form-field full">
            <label>API 请求地址</label>
            <div>
              <input
                v-model="form.base_url"
                class="form-input"
                placeholder="https://api.deepseek.com"
              />
              <p v-if="presetHint" class="field-hint">{{ presetHint }}</p>
            </div>
          </div>

          <!-- API Key -->
          <div class="form-field full">
            <label>API Key</label>
            <div class="key-field">
              <input
                v-model="form.api_key"
                :type="showKey ? 'text' : 'password'"
                class="form-input"
                :placeholder="hasSavedKey ? '已保存 (留空保持不变)' : '请输入 API Key'"
              />
              <button
                v-if="form.api_key"
                class="toggle-key"
                @click="showKey = !showKey"
                :title="showKey ? '隐藏' : '显示'"
              >
                <svg v-if="showKey" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            </div>
            <div v-if="fetchModelsError" class="error-card">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>{{ fetchModelsError }}</span>
            </div>
          </div>

          <!-- Model -->
          <div class="form-field full">
            <label>
              模型名称
              <button 
                type="button" 
                class="fetch-models-btn" 
                @click="fetchModelsFromApi" 
                :disabled="fetchingModels || !form.base_url"
                :title="!form.base_url ? '请先填写 API 请求地址' : '从 API 获取可用模型列表'"
              >
                <svg v-if="fetchingModels" class="spinning" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10" opacity="0.3"/><path d="M12 2a10 10 0 0 1 10 10"/>
                </svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                {{ fetchingModels ? '获取中...' : '获取模型列表' }}
              </button>
            </label>
            <select 
              v-if="availableModels.length > 0" 
              v-model="form.model" 
              class="form-input"
            >
              <option value="" disabled>请选择模型</option>
              <option v-for="model in availableModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <div v-else class="model-input-wrapper">
              <input
                v-model="form.model"
                class="form-input"
                placeholder="输入API key后请点击上方按钮获取模型列表，或手动输入模型名称"
              />
            </div>
            <p v-if="availableModels.length > 0" class="field-hint">已从 API 获取 {{ availableModels.length }} 个可用模型</p>
          </div>
        </div>
      </section>

      <!-- ====== 操作栏 ====== -->
      <section class="actions">
        <button class="btn btn-test" :disabled="testing" @click="handleTest">
          <svg v-if="testing" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
            <circle cx="12" cy="12" r="10" opacity="0.3"/><path d="M12 2a10 10 0 0 1 10 10"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          {{ testing ? '测试中...' : '连通测试' }}
        </button>

        <button class="btn btn-save" :disabled="saving" @click="handleSave">
          <svg v-if="saving" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
            <circle cx="12" cy="12" r="10" opacity="0.3"/><path d="M12 2a10 10 0 0 1 10 10"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>
          </svg>
          {{ saving ? '保存中...' : '保存配置并使用' }}
        </button>
      </section>

      <!-- ====== 测试结果 ====== -->
      <transition name="fade">
        <div v-if="testResult" class="test-result" :class="testResult.ok ? 'success' : 'error'">
          <span class="result-icon">{{ testResult.ok ? '✓' : '✗' }}</span>
          <span>{{ testResult.detail }}</span>
        </div>
      </transition>

      <!-- ====== 保存结果 ====== -->
      <transition name="fade">
        <div v-if="saveMessage" class="save-message success">
          <span class="result-icon">✓</span>
          <span>{{ saveMessage }}</span>
        </div>
      </transition>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { fetchLlmConfig, saveLlmConfig, testLlmConfig, fetchModels, addPreset, deletePreset } from '@/api/llmConfig'
import type { PresetModel, LlmConfig, CustomPreset } from '@/api/llmConfig'

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const showKey = ref(false)
const fetchingModels = ref(false)
const availableModels = ref<string[]>([])
const fetchModelsError = ref('')

const presets = ref<PresetModel[]>([])
const customPresets = ref<CustomPreset[]>([])
const currentConfig = ref<LlmConfig | null>(null)

const form = ref({
  provider_name: 'DeepSeek',
  provider: 'deepseek',
  base_url: 'https://api.deepseek.com',
  model: '',
  api_key: '',
})

const selectedPresetId = ref('')
const activePresetId = ref('')
const testResult = ref<{ ok: boolean; detail: string } | null>(null)
const saveMessage = ref('')

const hasValidConfig = computed(() => {
  const c = currentConfig.value
  return c ? (c.provider !== '' && c.model !== '') : false
})

const hasSavedKey = ref(false)

// ═══════════════════════════════════════════
// 预设可用性 (feasibility)
// ═══════════════════════════════════════════
// 规则:
//   正常 = 连通测试通过 + 模型在列表中
//   异常 = 连通测试失败 或 模型不在列表中
//   隐藏 = 未测试 或 凭证/模型变更后未重新测试
//
// 触发条件:
//   - api_key / base_url 变动 → connOk 重置为 null（隐藏）
//   - model 变动 → modelOk 重算（有列表则检查，无列表则置 null）
//   - 保存 → 不影响 feasibility
//   - 连通测试 → 一站式设置 connOk + modelOk
//   - 获取模型列表 → 仅设置 modelOk
// ═══════════════════════════════════════════

const FEASIBILITY_STORAGE_KEY = 'xikiy_preset_feasibility'
const MODELS_STORAGE_KEY = 'xikiy_preset_models'

function loadFromStorage<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback } catch { return fallback }
}
function saveToStorage(key: string, val: unknown) {
  try { localStorage.setItem(key, JSON.stringify(val)) } catch { /* ignore */ }
}

interface FeasibilityEntry { modelOk: boolean | null; connOk: boolean | null }
const presetFeasibility = ref<Record<string, FeasibilityEntry>>(loadFromStorage(FEASIBILITY_STORAGE_KEY, {}))
const presetModelLists = ref<Record<string, string[]>>(loadFromStorage(MODELS_STORAGE_KEY, {}))

function getFeasibilityState(presetId: string): 'ok' | 'fail' | 'unconfigured' {
  const f = presetFeasibility.value[presetId]
  // 未进行过任何检测 → 未配置
  if (!f || (f.modelOk === null && f.connOk === null)) return 'unconfigured'
  // 两项都通过 → 正常
  if (f.modelOk === true && f.connOk === true) return 'ok'
  // 其余 → 异常
  return 'fail'
}

function ensureEntry(pid: string): FeasibilityEntry {
  if (!presetFeasibility.value[pid]) presetFeasibility.value[pid] = { modelOk: null, connOk: null }
  return presetFeasibility.value[pid]
}

// 重算当前预设 modelOk（有模型列表时检查，否则置 null）
function refreshModelOk() {
  const pid = selectedPresetId.value; if (!pid) return
  const e = ensureEntry(pid)
  const models = presetModelLists.value[pid]
  e.modelOk = (models && models.length > 0) ? models.includes(form.value.model) : null
}

// 重置当前预设 connOk
function resetConnOk() {
  const pid = selectedPresetId.value; if (!pid) return
  ensureEntry(pid).connOk = null
}

// ── watchers: 凭证变更自动重置 ──
watch(() => form.value.api_key, resetConnOk)
watch(() => form.value.base_url, () => { resetConnOk(); availableModels.value = []; fetchModelsError.value = '' })
watch(() => form.value.model, refreshModelOk)

// 持久化
watch(presetFeasibility, () => saveToStorage(FEASIBILITY_STORAGE_KEY, presetFeasibility.value), { deep: true })
watch(presetModelLists, () => saveToStorage(MODELS_STORAGE_KEY, presetModelLists.value), { deep: true })

// 管理模式
const manageMode = ref(false)

// 当前选中的预设提示信息
const presetHint = computed(() => {
  if (!selectedPresetId.value) return ''
  const preset = presets.value.find(p => p.id === selectedPresetId.value)
  return preset?.hint || ''
})

function providerClass(p: string) {
  return `provider-${p}`
}

function getIconSrc(id: string): string {
  const iconMap: Record<string, string> = {
    deepseek: new URL('../assets/icons/deepseek.svg', import.meta.url).href,
    qwen: new URL('../assets/icons/qwen.svg', import.meta.url).href,
    doubao: new URL('../assets/icons/doubao.svg', import.meta.url).href,
  }
  return iconMap[id] || ''
}

function selectPreset(preset: PresetModel) {
  selectedPresetId.value = preset.id
  testResult.value = null
  saveMessage.value = ''
  availableModels.value = presetModelLists.value[preset.id] || []
  fetchModelsError.value = ''
  loadConfig(preset.id)
}

function selectCustomPreset(cp: CustomPreset) {
  selectedPresetId.value = cp.id
  form.value.provider = cp.provider
  form.value.base_url = cp.base_url
  form.value.model = ''
  form.value.api_key = ''
  form.value.provider_name = cp.label
  testResult.value = null
  saveMessage.value = ''
  availableModels.value = presetModelLists.value[cp.id] || []
  fetchModelsError.value = ''
  hasSavedKey.value = false
}

async function handleAddPresetQuick() {
  // 生成3位随机ID (小写字母+数字)
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  const id = 'custom_' + Array.from({ length: 3 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
  const label = id
  try {
    await addPreset({
      id,
      label,
      provider: 'openai',
      base_url: '',
    })
    // 立即更新本地自定义预设列表
    customPresets.value.push({ id, label, provider: 'openai', base_url: '' })
    // 切换到新预设
    selectCustomPreset({ id, label, provider: 'openai', base_url: '' })
    // 同步后端 active_preset 状态
    await loadConfig(id)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : '添加失败')
  }
}

async function handleDeletePreset(id: string) {
  if (!confirm('确定删除此自定义 Provider？')) return
  try {
    await deletePreset(id)
    if (selectedPresetId.value === id) {
      await loadConfig('deepseek')
    } else {
      await loadConfig()
    }
    // 如果没有自定义预设了，自动退出管理模式
    if (customPresets.value.length === 0) {
      manageMode.value = false
    }
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : '删除失败')
  }
}

async function handleTest() {
  testing.value = true
  testResult.value = null

  // 尚未拉取过模型列表：先自动拉取，确保 feasibility 能完整计算
  if (availableModels.value.length === 0 && form.value.base_url) {
    fetchingModels.value = true
    fetchModelsError.value = ''
    try {
      const modelsRes = await fetchModels({
        base_url: form.value.base_url,
        api_key: form.value.api_key,
      })
      if (modelsRes.models && modelsRes.models.length > 0) {
        availableModels.value = modelsRes.models
        presetModelLists.value[selectedPresetId.value] = modelsRes.models
        saveToStorage(MODELS_STORAGE_KEY, presetModelLists.value)
        if (form.value.model && !modelsRes.models.includes(form.value.model)) {
          form.value.model = modelsRes.models[0]
        } else if (!form.value.model && modelsRes.models.length > 0) {
          form.value.model = modelsRes.models[0]
        }
      } else {
        fetchModelsError.value = modelsRes.detail || '未获取到模型列表'
      }
    } catch {
      fetchModelsError.value = '获取模型列表失败'
    } finally {
      fetchingModels.value = false
    }
  }

  const startTime = Date.now()
  try {
    const res = await testLlmConfig({
      provider: form.value.provider,
      base_url: form.value.base_url,
      api_key: form.value.api_key,
    })
    const latency = Date.now() - startTime
    if (res.ok) {
      testResult.value = { ok: true, detail: `连通测试正常 (${latency}ms)` }
    } else {
      testResult.value = res
    }
    // 更新当前预设的 feasibility（连通性 + 模型匹配）
    const pid = selectedPresetId.value
    if (pid) {
      ensureEntry(pid).connOk = res.ok
      refreshModelOk()
    }
  } catch (e: unknown) {
    testResult.value = { ok: false, detail: e instanceof Error ? e.message : '测试失败' }
    const pid = selectedPresetId.value
    if (pid) {
      ensureEntry(pid).connOk = false
      refreshModelOk()
    }
  } finally {
    testing.value = false
  }
}

async function fetchModelsFromApi() {
  if (!form.value.base_url) {
    fetchModelsError.value = '请先填写 API 请求地址'
    return
  }
  fetchingModels.value = true
  fetchModelsError.value = ''
  availableModels.value = []
  try {
    const res = await fetchModels({
      base_url: form.value.base_url,
      api_key: form.value.api_key,
    })
    if (res.models && res.models.length > 0) {
      availableModels.value = res.models
      presetModelLists.value[selectedPresetId.value] = res.models
      saveToStorage(MODELS_STORAGE_KEY, presetModelLists.value)
      // 如果当前有 model 值且在列表中，保持选中
      if (form.value.model && !res.models.includes(form.value.model)) {
        form.value.model = res.models[0]
      } else if (!form.value.model && res.models.length > 0) {
        form.value.model = res.models[0]
      }
      // 刷新当前预设的模型可用性
      refreshModelOk()
    } else {
      fetchModelsError.value = res.detail || '未获取到模型列表'
    }
  } catch (e: unknown) {
    fetchModelsError.value = e instanceof Error ? e.message : '获取模型列表失败'
  } finally {
    fetchingModels.value = false
  }
}

async function handleSave() {
  saving.value = true
  saveMessage.value = ''
  try {
    const res = await saveLlmConfig({
      preset_id: selectedPresetId.value || 'deepseek',
      label: form.value.provider_name,
      provider: form.value.provider,
      base_url: form.value.base_url,
      model: form.value.model,
      api_key: form.value.api_key,
    })
    saveMessage.value = res.message || '配置已保存'
    await loadConfig()
    // 保存后立即验证连通性 + 模型匹配，更新 feasibility
    await runFeasibilityCheck()
  } catch (e: unknown) {
    saveMessage.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

// 从 handleTest 抽取的纯检测逻辑（无 UI 状态切换）
async function runFeasibilityCheck() {
  const pid = selectedPresetId.value
  if (!pid || !form.value.base_url) return

  // 先拉取模型列表
  try {
    const modelsRes = await fetchModels({
      base_url: form.value.base_url,
      api_key: form.value.api_key,
    })
    if (modelsRes.models && modelsRes.models.length > 0) {
      availableModels.value = modelsRes.models
      presetModelLists.value[pid] = modelsRes.models
      if (!modelsRes.models.includes(form.value.model) && modelsRes.models.length > 0) {
        form.value.model = modelsRes.models[0]
      }
    }
  } catch { /* 模型列表获取失败不阻断 */ }

  // 再测连通性
  try {
    const res = await testLlmConfig({
      provider: form.value.provider,
      base_url: form.value.base_url,
      api_key: form.value.api_key,
    })
    ensureEntry(pid).connOk = res.ok
  } catch {
    ensureEntry(pid).connOk = false
  }

  // 刷新 modelOk
  refreshModelOk()
}

async function loadConfig(presetIdToLoad?: string) {
  try {
    const res = await fetchLlmConfig()
    presets.value = res.data.presets
    customPresets.value = res.data.custom_presets || []
    currentConfig.value = res.data.current
    const targetPresetId = presetIdToLoad || res.data.active_preset
    activePresetId.value = res.data.active_preset

    // 从 preset_configs 获取目标预设的配置
    const presetConfig = res.data.preset_configs?.[targetPresetId]
    if (presetConfig) {
      form.value.provider = presetConfig.provider
      form.value.base_url = presetConfig.base_url
      form.value.model = presetConfig.model
      form.value.api_key = '' // 不回显 key
      hasSavedKey.value = presetConfig.api_key_set
    } else {
      // 回退到 current
      form.value.provider = res.data.current.provider
      form.value.base_url = res.data.current.base_url
      form.value.model = res.data.current.model
      form.value.api_key = ''
      hasSavedKey.value = res.data.current.api_key_set
    }

    // 匹配预设
    const match = res.data.presets.find((p) => p.id === targetPresetId)
    if (match) {
      selectedPresetId.value = match.id
      form.value.provider_name = match.label
    } else {
      // 检查是否为自定义预设
      const customMatch = res.data.custom_presets?.find((cp) => cp.id === targetPresetId)
      if (customMatch) {
        selectedPresetId.value = customMatch.id
        form.value.provider_name = customMatch.label
      } else {
        selectedPresetId.value = ''
        const nameMap: Record<string, string> = { deepseek: 'DeepSeek', qwen: 'Qwen', openai: 'OpenAI 兼容' }
        form.value.provider_name = nameMap[form.value.provider] || form.value.provider
      }
    }
    // 恢复缓存的模型列表
    availableModels.value = presetModelLists.value[selectedPresetId.value] || []
  } catch (e) {
    console.error('加载 LLM 配置失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.settings-view {
  padding: 28px 36px;
  overflow-y: auto;
  height: 100%;
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.settings-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary, #e8e8f0);
  margin: 0;
}

.settings-subtitle {
  font-size: 13px;
  color: var(--text-primary, #1a1b2e);
  opacity: 0.6;
  margin: 4px 0 0;
}

.config-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.config-status.configured {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* ── Loading ── */
.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary, #8a8da0);
  padding: 40px 0;
  justify-content: center;
}

/* ── Sections ── */
.section {
  margin-bottom: 28px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1a1b2e);
  letter-spacing: 0.5px;
  margin: 0;
}

/* ─ Section header row ── */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.manage-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary, #8a8da0);
  background: transparent;
  border: 1px solid var(--border-subtle, #e5e7eb);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.manage-btn:hover {
  color: var(--color-accent, #4d6bfe);
  border-color: var(--color-accent, #4d6bfe);
}
.manage-btn.active {
  color: #ef4444;
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

/* ── Preset Grid ── */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.preset-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-subtle, #e5e7eb);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  text-align: left;
  color: var(--text-primary, #1f2937);
}
.preset-card:hover {
  background: var(--bg-card-hover, #f9fafb);
  border-color: #d1d5db;
}
.preset-card.active {
  border-color: var(--color-accent, #4d6bfe);
  background: rgba(77, 107, 254, 0.05);
}

/* ── Card animation (enter/leave/move) ── */
.card-anim-enter-active,
.card-anim-leave-active {
  transition: all 0.3s ease;
}
.card-anim-enter-from {
  opacity: 0;
  transform: scale(0.9);
}
.card-anim-leave-to {
  opacity: 0;
  transform: scale(0.9);
}
.card-anim-move {
  transition: transform 0.3s ease;
}

/* ─ Manage mode states ── */
.preset-card.disabled-card {
  opacity: 0.5;
  cursor: default;
  pointer-events: none;
}
.preset-card.manage-active {
  border-color: #fca5a5;
  background: rgba(239, 68, 68, 0.03);
}
.preset-card.manage-active:hover {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.06);
}

.delete-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ef4444;
  border: none;
  border-radius: 50%;
  color: #fff;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 1px 4px rgba(239, 68, 68, 0.3);
  z-index: 2;
}
.delete-btn:hover {
  background: #dc2626;
  transform: scale(1.1);
}

.preset-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.preset-icon img {
  width: 24px;
  height: 24px;
  object-fit: contain;
}

/* 自定义预设星标 */
.custom-icon {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.15), rgba(99, 102, 241, 0.15));
  color: #a855f7;
}

.preset-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.preset-label {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.preset-url {
  font-size: 10px;
  color: var(--text-dim, #555870);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.local-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
  margin-left: auto;
  flex-shrink: 0;
}

/* ── 预设可用性指示器 ── */
.feasibility-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 5px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  flex-shrink: 0;
}
.feasibility-badge.ok {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}
.feasibility-badge.fail {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.feasibility-badge.unconfigured {
  background: rgba(156, 163, 175, 0.1);
  color: #9ca3af;
}
.feasibility-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
/* unconfigured 纯 CSS 空心圆，完美居中 */
.feasibility-ring {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
}
.feasibility-badge.ok .feasibility-dot {
  background: #22c55e;
  color: #fff;
}
.feasibility-badge.fail .feasibility-dot {
  background: #ef4444;
  color: #fff;
}
.feasibility-badge.unconfigured .feasibility-dot {
  background: #9ca3af;
  color: #fff;
}
.feasibility-text {
  white-space: nowrap;
}

.check-mark {
  position: absolute;
  top: 8px;
  right: 8px;
  color: var(--color-accent, #6366f1);
  display: flex;
  align-items: center;
  gap: 3px;
}
.check-label {
  font-size: 10px;
  font-weight: 500;
  color: var(--color-accent, #4d6bfe);
  white-space: nowrap;
}

.lock-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  color: var(--text-dim, #9ca3af);
  opacity: 0.7;
}

/* ─ Custom preset card ── */
.custom-card {
  border-style: dashed;
}

/* ─ Add card ── */
.add-card {
  border-style: dashed;
  justify-content: center;
  color: var(--text-secondary, #8a8da0);
}
.add-card:hover {
  border-color: var(--color-accent, #4d6bfe);
  color: var(--color-accent);
}
.add-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(77, 107, 254, 0.06);
}

/* ── Form ── */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.form-field.full {
  grid-column: 1 / -1;
}

.form-input {
  width: 100%;
  padding: 12px 14px;
  background: var(--bg-input, #1a1b2e);
  border: 1px solid var(--border-subtle, rgba(255,255,255,0.08));
  border-radius: 8px;
  color: var(--text-primary, #e8e8f0);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}
.form-input:focus {
  border-color: var(--color-accent, #6366f1);
}
.form-input::placeholder {
  color: var(--text-dim, #9ca3af);
  opacity: 0.7;
}

.field-hint {
  font-size: 11px;
  color: var(--text-primary, #1a1b2e);
  opacity: 0.7;
  margin: 6px 0 0;
  font-style: italic;
}

.error-card {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0 0;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #ef4444;
  font-size: 13px;
  line-height: 1.5;
}
.error-card svg {
  flex-shrink: 0;
  color: #ef4444;
}

.fetch-models-btn {
  float: right;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11px;
  color: var(--color-accent, #6366f1);
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
  margin-left: auto;
}

.fetch-models-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.3);
}

.fetch-models-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.model-input-wrapper {
  position: relative;
}

.form-field label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary, #1a1b2e);
  margin-bottom: 6px;
}

select.form-input {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238a8da0' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}

.key-field {
  position: relative;
}
.toggle-key {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-dim, #555870);
  cursor: pointer;
  padding: 4px;
  display: flex;
}
.toggle-key:hover {
  color: var(--text-secondary, #8a8da0);
}

/* ── Actions ── */
.actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-test {
  background: var(--bg-card, #ffffff);
  color: var(--text-primary, #1f2937);
  border: 1px solid var(--border-subtle, #e5e7eb);
}
.btn-test:hover:not(:disabled) {
  background: var(--bg-card-hover, #f9fafb);
}

.btn-save {
  background: var(--color-accent, #4d6bfe);
  color: #fff;
}
.btn-save:hover:not(:disabled) {
  filter: brightness(1.1);
}

/* ── Results ── */
.test-result,
.save-message {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.test-result.success,
.save-message.success {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  border: 1px solid rgba(34, 197, 94, 0.2);
}
.test-result.error {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.2);
}
.result-icon {
  font-weight: 700;
}

/* ── Spinner ── */
.spinning {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Transitions ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
