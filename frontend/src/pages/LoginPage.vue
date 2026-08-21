<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'ログインに失敗しました。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page auth-page">
    <h1 class="app-title">KAKEI</h1>
    <form class="card" @submit.prevent="submit">
      <label for="username">ユーザー名</label>
      <input id="username" v-model="username" type="text" autocomplete="username" required />
      <label for="password">パスワード</label>
      <input
        id="password"
        v-model="password"
        type="password"
        autocomplete="current-password"
        required
      />
      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn submit" type="submit" :disabled="loading">ログイン</button>
    </form>
    <p class="switch">
      アカウントがない方は
      <RouterLink to="/register">新規登録</RouterLink>
    </p>
  </div>
</template>

<style scoped>
.auth-page {
  padding-top: 15vh;
}

.app-title {
  text-align: center;
  color: var(--color-primary);
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
