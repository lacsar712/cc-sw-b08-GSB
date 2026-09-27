<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api.js'

const role = ref(localStorage.getItem('role') || '')
const pending = ref([])
const issued = ref([])
const selectedId = ref(null)
const err = ref('')
const msg = ref('')
let timer

const selected = computed(() => issued.value.find((p) => p.id === selectedId.value) || null)

async function refresh() {
  if (!localStorage.getItem('tok')) return
  try {
    const data = await api('/api/freeze')
    pending.value = data.pending
    issued.value = data.issued
    err.value = ''
  } catch (e) {
    err.value = String(e.message || e)
  }
}

async function issue(job) {
  err.value = ''
  msg.value = ''
  try {
    const res = await api('/api/packages', {
      method: 'POST',
      body: JSON.stringify({ job_id: job.id }),
    })
    msg.value = `任务 #${job.id} 已签发：导出包 #${res.id} 已冻结灯种/标称/实测/结论/理由`
    selectedId.value = res.id
    await refresh()
  } catch (e) {
    err.value = String(e.message || e)
  }
}

async function download(pkg) {
  err.value = ''
  try {
    const token = localStorage.getItem('tok') || ''
    const r = await fetch(`/api/packages/${pkg.id}/export`, {
      headers: { Authorization: 'Bearer ' + token },
    })
    if (!r.ok) {
      const t = await r.json().catch(() => ({}))
      throw new Error(t.detail || r.statusText)
    }
    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `export-package-${pkg.id}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    err.value = String(e.message || e)
  }
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

onMounted(() => {
  role.value = localStorage.getItem('role') || ''
  refresh()
  timer = setInterval(refresh, 1000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div>
    <h2>冻结台 · 只读导出包</h2>
    <p v-if="err" style="color:#b00020">{{ err }}</p>
    <p v-if="msg" style="color:#0a7a2f">{{ msg }}</p>
    <div class="freeze-board">
      <section class="pane">
        <h3>待签发（已结案）</h3>
        <table v-if="pending.length" border="1" cellpadding="6" class="grid">
          <thead>
            <tr>
              <th>编号</th><th>灯种</th><th>标称</th><th>实测</th><th>结论</th><th>理由</th>
              <th v-if="role === 'writer'">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="j in pending" :key="j.id">
              <td>{{ j.id }}</td>
              <td>{{ j.lamp }}</td>
              <td>{{ j.nominal_nm }}</td>
              <td>{{ j.measured_nm }}</td>
              <td>{{ j.verdict }}</td>
              <td>{{ j.reason }}</td>
              <td v-if="role === 'writer'">
                <button type="button" @click="issue(j)">签发</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint">暂无待签发的已结案任务</p>
        <p v-if="role !== 'writer'" class="hint">巡检员可翻阅导出包，无签发权限。</p>
      </section>

      <section class="pane">
        <h3>已签发</h3>
        <table v-if="issued.length" border="1" cellpadding="6" class="grid">
          <thead>
            <tr>
              <th>包号</th><th>任务</th><th>灯种</th><th>结论</th><th>签发人</th><th>签发时间</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in issued"
              :key="p.id"
              :class="{ picked: p.id === selectedId }"
              style="cursor:pointer"
              @click="selectedId = p.id"
            >
              <td>#{{ p.id }}</td>
              <td>#{{ p.job_id }}</td>
              <td>{{ p.lamp }}</td>
              <td>{{ p.verdict }}</td>
              <td>{{ p.issued_by }}</td>
              <td>{{ fmtTime(p.issued_at) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint">暂无已签发的导出包</p>

        <div v-if="selected" class="pkg-detail">
          <h4>包内字段 · 导出包 #{{ selected.id }}（只读）</h4>
          <p>来源任务：#{{ selected.job_id }}</p>
          <p>灯种：{{ selected.lamp }}</p>
          <p>标称 nm：{{ selected.nominal_nm }}</p>
          <p>实测 nm：{{ selected.measured_nm }}</p>
          <p>结论：{{ selected.verdict }}</p>
          <p>理由：{{ selected.reason }}</p>
          <p>签发人：{{ selected.issued_by }}</p>
          <p>签发时间：{{ fmtTime(selected.issued_at) }}</p>
          <p class="hint">包内字段为签发那一刻的快照；之后改测重判只刷总览现行行，不回写本包。</p>
          <button type="button" @click="download(selected)">导出 JSON</button>
        </div>
        <p v-else-if="issued.length" class="hint">点击上方任一导出包查看包内字段。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.freeze-board {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.pane {
  flex: 1 1 380px;
  min-width: 340px;
  padding: 12px;
  border: 1px solid #ccc;
}
.grid {
  border-collapse: collapse;
  width: 100%;
}
tr.picked td {
  background: #e8f1fb;
}
.pkg-detail {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed #888;
  background: #fafcff;
}
.hint {
  color: #666;
  font-size: 13px;
}
</style>
