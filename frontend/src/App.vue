<template>
  <TopNavbar v-if="$route.path !== '/login'" />
  <router-view />
</template>
<script setup lang="ts">
import TopNavbar from './components/layout/TopNavbar.vue'
</script>
