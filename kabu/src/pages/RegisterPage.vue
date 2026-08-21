<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const password2 = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  if (password.value !== password2.value) {
    error.value = 'パスワードが一致しません。'
    return
  }
  loading.value = true
  try {
    await auth.register(username.value, password.value)
    router.push('/')
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.username?.[0] || data?.password?.[0] || data?.detail || '登録に失敗しました。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page auth-page">
    <h1 class="app-title">新規登録</h1>
    <p class="subtitle">作成したアカウントは KAKEI でも使えます</p>
    <form class="card" @submit.prevent="submit">
      <label for="username">ユーザー名</label>
      <input id="username" v-model="username" type="text" autocomplete="username" required />
      <label for="password">パスワード (8文字以上)</label>
      <input
        id="password"
        v-model="password"
        type="password"
        autocomplete="new-password"
        required
      />
      <label for="password2">パスワード (確認)</label>
      <input
        id="password2"
        v-model="password2"
        type="password"
        autocomplete="new-password"
        required
      />
      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn submit" type="submit" :disabled="loading">登録する</button>
    </form>
    <p class="switch">
      アカウントをお持ちの方は
      <RouterLink to="/login">ログイン</RouterLink>
    </p>
  </div>
</template>

<style scoped>
.auth-page {
  padding-top: 10vh;
}

.app-title {
  text-align: center;
  color: var(--color-primary);
  margin-bottom: 8px;
}

.subtitle {
  text-align: center;
  color: var(--color-text-sub);
  font-size: 0.85rem;
  margin-bottom: 24px;
}

.submit {
  margin-top: 20px;
}

.switch {
  text-align: center;
  margin-top: 16px;
  font-size: 0.9rem;
}

.switch a {
  color: var(--color-primary);
  font-weight: 600;
}
</style>
