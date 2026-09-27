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
const editMeasured = ref(0)
let timer
let initializedFor = null

async function load() {
  err.value = ''
  try {
    job.value = await api(`/api/jobs/${route.params.id}`)
    if (initializedFor !== job.value.id) {
      initializedFor = job.value.id
      editMeasured.value = job.value.measured_nm
    }
  } catch (e) {
    err.value = String(e.message || e)
  }
}

async function saveMeasured() {
  err.value = ''
  msg.value = ''
  try {
    await api(`/api/jobs/${route.params.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ measured_nm: editMeasured.value }),
    })
    msg.value = '已改实测，重新入队等待判定'
    await load()
  } catch (e) {
    err.value = String(e.message || e)
  }
}

onMounted(() => {
  role.value = localStorage.getItem('role') || ''
  job.value = null
  load()
  timer = setInterval(load, 1000)
})
onUnmounted(() => clearInterval(timer))
watch(() => route.params.id, () => {
  job.value = null
  load()
})
</script>

<template>
  <div>
    <p>
      <button type="button" @click="router.push('/')">返回总览</button>
    </p>
    <p v-if="err" style="color:#b00020">{{ err }}</p>
    <p v-if="msg" style="color:#1a7f37">{{ msg }}</p>
    <section v-if="job" style="margin:16px 0; padding:12px; border:1px solid #ccc;">
      <h3>任务详情 #{{ job.id }}</h3>
      <p>灯种：{{ job.lamp }}</p>
      <p>标称 nm：{{ job.nominal_nm }}</p>
      <p>实测 nm：{{ job.measured_nm }}</p>
      <p>状态：{{ job.status }}</p>
      <p>结论：{{ job.verdict }}</p>
      <p>理由：{{ job.reason }}</p>
    </section>
    <section v-if="job && role === 'writer'" style="margin:16px 0; padding:12px; border:1px solid #ccc;">
      <h4>改实测重判</h4>
      <label>实测 nm <input type="number" step="0.01" v-model.number="editMeasured" /></label>
      <button type="button" @click="saveMeasured">保存并重判</button>
    </section>
  </div>
</template>
