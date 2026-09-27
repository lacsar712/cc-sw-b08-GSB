<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api.js'

const role = ref(localStorage.getItem('role') || '')
const jobs = ref([])
const packages = ref([])
const selected = ref(null)
const err = ref('')
const msg = ref('')
let timer

// 待签发 = 已结案且尚未打进包里的任务
const pendingSign = computed(() => {
  const signed = new Set(packages.value.map((p) => p.job_id))
  return jobs.value.filter((j) => j.status === 'done' && !signed.has(j.id))
})

async function refresh() {
  if (!localStorage.getItem('tok')) return
  try {
    const [j, p] = await Promise.all([api('/api/jobs'), api('/api/packages')])
    jobs.value = j
    packages.value = p
    err.value = ''
  } catch (e) {
    err.value = String(e.message || e)
  }
}

async function sign(job) {
  err.value = ''
  msg.value = ''
  try {
    const r = await api(`/api/jobs/${job.id}/sign`, { method: 'POST' })
    msg.value = `任务 #${job.id} 已签发为包 #${r.id}`
    await refresh()
  } catch (e) {
    err.value = String(e.message || e)
  }
}

async function openPackage(p) {
  err.value = ''
  try {
    selected.value = await api(`/api/packages/${p.id}`)
  } catch (e) {
    err.value = String(e.message || e)
  }
}

function fmtTime(t) {
  return t ? new Date(t).toLocaleString() : ''
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
    <h3>冻结台</h3>
    <p v-if="err" style="color:#b00020">{{ err }}</p>
    <p v-if="msg" style="color:#1a7f37">{{ msg }}</p>
    <div class="freeze-cols">
      <section class="col">
        <h4>待签发（已结案）</h4>
        <table v-if="pendingSign.length" border="1" cellpadding="6" style="border-collapse:collapse; width:100%;">
          <thead>
            <tr>
              <th>编号</th><th>灯种</th><th>标称</th><th>实测</th><th>结论</th><th v-if="role === 'writer'">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="j in pendingSign" :key="j.id">
              <td>{{ j.id }}</td>
              <td>{{ j.lamp }}</td>
              <td>{{ j.nominal_nm }}</td>
              <td>{{ j.measured_nm }}</td>
              <td>{{ j.verdict }}</td>
              <td v-if="role === 'writer'">
                <button type="button" @click="sign(j)">签发</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">暂无待签发的已结案任务</p>
      </section>

      <section class="col">
        <h4>已签发（只读导出包）</h4>
        <table v-if="packages.length" border="1" cellpadding="6" style="border-collapse:collapse; width:100%;">
          <thead>
            <tr>
              <th>包号</th><th>任务</th><th>灯种</th><th>结论</th><th>签发人</th><th>签发时间</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in packages"
              :key="p.id"
              style="cursor:pointer"
              :class="{ picked: selected && selected.id === p.id }"
              @click="openPackage(p)"
            >
              <td>{{ p.id }}</td>
              <td>#{{ p.job_id }}</td>
              <td>{{ p.lamp }}</td>
              <td>{{ p.verdict }}</td>
              <td>{{ p.signed_by }}</td>
              <td>{{ fmtTime(p.signed_at) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">暂无已签发的包</p>

        <div v-if="selected" class="pkg-detail">
          <h4>包内字段 · 包 #{{ selected.id }}（任务 #{{ selected.job_id }}）</h4>
          <p>灯种：{{ selected.lamp }}</p>
          <p>标称 nm：{{ selected.nominal_nm }}</p>
          <p>实测 nm：{{ selected.measured_nm }}</p>
          <p>结论：{{ selected.verdict }}</p>
          <p>理由：{{ selected.reason }}</p>
          <p>签发人：{{ selected.signed_by }}</p>
          <p>签发时间：{{ fmtTime(selected.signed_at) }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.freeze-cols {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.col {
  flex: 1;
  min-width: 0;
  padding: 12px;
  border: 1px solid #ccc;
}
.empty {
  color: #666;
  font-size: 13px;
}
.picked td {
  background: #e8f0fe;
}
.pkg-detail {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed #888;
  background: #fafafa;
}
.pkg-detail p {
  margin: 4px 0;
}
</style>
