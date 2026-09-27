<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'

const route = useRoute()
const router = useRouter()
const role = ref(localStorage.getItem('role') || '')
const job = ref(null)
const err = ref('')
const msg = ref('')
const editForm = ref({ nominal_nm: 0, measured_nm: 0 })
let timer

async function load() {
  err.value = ''
  try {
    const data = await api(`/api/jobs/${route.params.id}`)
    job.value = data
    editForm.value = { nominal_nm: data.nominal_nm, measured_nm: data.measured_nm }
  } catch (e) {
    err.value = String(e.message || e)
  }
}

async function rejudge() {
  err.value = ''
  msg.value = ''
  try {
    await api(`/api/jobs/${job.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify(editForm.value),
    })
    msg.value = '已重新入队，等待判定；总览现行行将刷新，已签发导出包不受影响。'
    await load()
  } catch (e) {
    err.value = String(e.message || e)
  }
}

onMounted(() => {
  role.value = localStorage.getItem('role') || ''
  load()
  timer = setInterval(() => {
    if (job.value && job.value.status === 'pending') load()
  }, 800)
})
onUnmounted(() => clearInterval(timer))
watch(() => route.params.id, load)
</script>

<template>
  <div>
    <p>
      <button type="button" @click="router.push('/')">返回总览</button>
      <button type="button" style="margin-left:8px" @click="router.push('/freeze')">前往冻结台</button>
    </p>
    <p v-if="err" style="color:#b00020">{{ err }}</p>
    <p v-if="msg" style="color:#0a7a2f">{{ msg }}</p>
    <section v-if="job" style="margin:16px 0; padding:12px; border:1px solid #ccc;">
      <h3>
        任务详情 #{{ job.id }}
        <span v-if="job.package_id" class="pkg-badge">已签发 · 导出包 #{{ job.package_id }}</span>
      </h3>
      <p>灯种：{{ job.lamp }}</p>
      <p>标称 nm：{{ job.nominal_nm }}</p>
      <p>实测 nm：{{ job.measured_nm }}</p>
      <p>状态：{{ job.status }}</p>
      <p>结论：{{ job.verdict }}</p>
      <p>理由：{{ job.reason }}</p>
    </section>
    <section
      v-if="job && role === 'writer' && job.status === 'done'"
      style="margin:16px 0; padding:12px; border:1px solid #ccc;"
    >
      <h3>改测重判</h3>
      <label>标称 nm <input type="number" step="0.01" v-model.number="editForm.nominal_nm" /></label>
      <label>实测 nm <input type="number" step="0.01" v-model.number="editForm.measured_nm" /></label>
      <button type="button" @click="rejudge">重新判定</button>
      <p v-if="job.package_id" class="hint">
        本任务已签发导出包 #{{ job.package_id }}：重判只更新总览现行行，包内字段保持签发版。
      </p>
    </section>
  </div>
</template>

<style scoped>
.pkg-badge {
  font-size: 12px;
  font-weight: 600;
  color: #0a4d8c;
  background: #e8f1fb;
  border: 1px solid #b8d2ec;
  border-radius: 4px;
  padding: 2px 6px;
  margin-left: 8px;
  vertical-align: middle;
}
.hint {
  color: #666;
  font-size: 13px;
}
</style>
