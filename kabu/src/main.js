import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setupAuthRedirect } from './api/client'
import './assets/main.css'

setupAuthRedirect(router)

createApp(App).use(createPinia()).use(router).mount('#app')
