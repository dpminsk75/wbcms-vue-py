import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.css'
import './assets/css/site.css'
import './assets/css/gridv.css'
import './assets/css/menu.css'
import './assets/css/wb-ui.css'
import { VueQueryPlugin } from '@tanstack/vue-query'

import router from './router'
const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin)
app.mount('#app')
