<script setup>
import { useAuthStore } from './stores/auth'
import BottomNav from './components/BottomNav.vue'

const auth = useAuthStore()
</script>

<template>
  <RouterView />
  <BottomNav v-if="auth.user" />
</template>
