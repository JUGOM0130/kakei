<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useGroupStore } from '../stores/group'
import { useLedgerStore } from '../stores/ledger'

const auth = useAuthStore()
const groupStore = useGroupStore()
const ledger = useLedgerStore()
const router = useRouter()

const groupName = ref('')
const inviteCode = ref('')
const groupError = ref('')
const copied = ref(false)

const myShare = ref(50)
const shareSaved = ref(false)

const newMethod = ref('')
const methodError = ref('')

const partner = computed(() => groupStore.partner)

onMounted(async () => {
  await Promise.all([groupStore.fetch(), ledger.fetchPaymentMethods(true)])
  if (groupStore.me) myShare.value = groupStore.me.share_percent
})

async function createGroup() {
  groupError.value = ''
  if (!groupName.value.trim()) return
  try {
    await groupStore.create(groupName.value.trim())
  } catch (e) {
    groupError.value = e.response?.data?.detail || '作成に失敗しました。'
  }
}

async function joinGroup() {
  groupError.value = ''
  if (!inviteCode.value.trim()) return
  try {
    await groupStore.join(inviteCode.value.trim())
    if (groupStore.me) myShare.value = groupStore.me.share_percent
  } catch (e) {
    groupError.value = e.response?.data?.detail || '参加に失敗しました。'
  }
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(groupStore.group.invite_code)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    /* http では clipboard API が使えない環境があるため無視 */
  }
}

async function saveShare() {
  await groupStore.updateShare(Number(myShare.value))
  shareSaved.value = true
  setTimeout(() => (shareSaved.value = false), 1500)
}

async function leaveGroup() {
  if (!confirm('グループから退出しますか?\n(共有した記録は残ります)')) return
  await groupStore.leave()
}

async function addMethod() {
  methodError.value = ''
  if (!newMethod.value.trim()) return
  try {
    await api.post('/payment-methods/', { name: newMethod.value.trim() })
    newMethod.value = ''
    await ledger.fetchPaymentMethods(true)
  } catch (e) {
    methodError.value =
      e.response?.data?.name?.[0] || e.response?.data?.detail || '追加に失敗しました。'
  }
}

async function renameMethod(m) {
  const name = prompt('支払方法の名前', m.name)
  if (!name || name === m.name) return
  try {
    await api.patch(`/payment-methods/${m.id}/`, { name })
    await ledger.fetchPaymentMethods(true)
  } catch (e) {
    alert(e.response?.data?.name?.[0] || '変更に失敗しました。')
  }
}

async function removeMethod(m) {
  if (!confirm(`「${m.name}」を削除しますか?`)) return
  try {
    await api.delete(`/payment-methods/${m.id}/`)
    await ledger.fetchPaymentMethods(true)
  } catch (e) {
    alert(e.response?.data?.detail || '削除に失敗しました。')
  }
}

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">設定</h1>

    <!-- グループ -->
    <h2 class="section-label">グループ (共有・折半)</h2>
    <div class="card">
      <template v-if="!groupStore.group">
        <p class="hint">
          家族とグループを作ると、支払いを共有して折半・割合精算ができます。
        </p>
        <label for="g-name">新しいグループを作る</label>
        <div class="inline-form">
          <input id="g-name" v-model="groupName" type="text" placeholder="例: 我が家" maxlength="50" />
          <button class="btn btn-small" @click="createGroup">作成</button>
        </div>
        <label for="g-code">招待コードで参加する</label>
        <div class="inline-form">
          <input id="g-code" v-model="inviteCode" type="text" placeholder="例: 3F2A9C01" maxlength="8" />
          <button class="btn btn-small" @click="joinGroup">参加</button>
        </div>
        <p v-if="groupError" class="error-message">{{ groupError }}</p>
      </template>

      <template v-else>
        <div class="group-head">
          <strong>{{ groupStore.group.name }}</strong>
          <button class="btn btn-secondary btn-small" @click="leaveGroup">退出</button>
        </div>

        <template v-if="!partner">
          <label>招待コード (相手に伝えて「参加」してもらう)</label>
          <div class="inline-form">
            <code class="invite-code">{{ groupStore.group.invite_code }}</code>
            <button class="btn btn-secondary btn-small" @click="copyCode">
              {{ copied ? 'コピー済' : 'コピー' }}
            </button>
          </div>
        </template>

        <div class="members">
          <div v-for="m in groupStore.group.members" :key="m.id" class="member">
            <span>{{ m.username }}{{ m.is_me ? ' (自分)' : '' }}</span>
            <span class="share">負担 {{ m.share_percent }}%</span>
          </div>
        </div>

        <label for="g-share">デフォルト負担割合 (自分)</label>
        <div class="inline-form">
          <input
            id="g-share"
            v-model="myShare"
            type="number"
            inputmode="numeric"
            min="0"
            max="100"
            class="share-input"
          />
          <span class="share-rest">% (相手 {{ 100 - Number(myShare || 0) }}%)</span>
          <button class="btn btn-small" @click="saveShare">{{ shareSaved ? '保存済' : '保存' }}</button>
        </div>
        <p class="hint">共有支払いを登録するときの初期値です。1件ごとに変更もできます。</p>
        <p v-if="groupError" class="error-message">{{ groupError }}</p>
      </template>
    </div>

    <!-- 支払方法 -->
    <h2 class="section-label">支払方法 (現金・カード)</h2>
    <div class="card">
      <div class="inline-form">
        <input v-model="newMethod" type="text" placeholder="例: カードA" maxlength="50" />
        <button class="btn btn-small" @click="addMethod">追加</button>
      </div>
      <p v-if="methodError" class="error-message">{{ methodError }}</p>
      <div v-for="m in ledger.paymentMethods" :key="m.id" class="row">
        <span class="name" @click="renameMethod(m)">{{ m.name }}</span>
        <button class="btn btn-secondary btn-small" @click="renameMethod(m)">名前</button>
        <button class="btn btn-danger btn-small" @click="removeMethod(m)">削除</button>
      </div>
    </div>

    <!-- その他 -->
    <h2 class="section-label">その他</h2>
    <div class="card">
      <RouterLink to="/categories" class="link-row">🏷️ カテゴリを管理する ›</RouterLink>
    </div>
    <button class="btn btn-secondary logout" @click="logout">ログアウト</button>
  </div>
</template>

<style scoped>
.section-label {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin: 16px 0 6px;
}

.hint {
  font-size: 0.8rem;
  color: var(--color-text-sub);
}

.inline-form {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}

.inline-form input[type='text'] {
  flex: 1;
}

.inline-form .btn {
  flex-shrink: 0;
}

.group-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.invite-code {
  flex: 1;
  font-size: 1.3rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  background: var(--color-bg);
  border-radius: 8px;
  padding: 8px 12px;
  text-align: center;
}

.members {
  margin: 12px 0 4px;
}

.member {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
}

.member:last-child {
  border-bottom: none;
}

.share {
  color: var(--color-text-sub);
  font-size: 0.85rem;
}

.share-input {
  width: 90px;
  text-align: right;
}

.share-rest {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  white-space: nowrap;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
}

.row:last-child {
  border-bottom: none;
}

.row .name {
  flex: 1;
  font-weight: 600;
  cursor: pointer;
}

.link-row {
  display: block;
  text-decoration: none;
  color: inherit;
  font-weight: 600;
  padding: 4px 0;
}

.logout {
  margin-top: 16px;
}
</style>
