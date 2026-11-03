<template>
  <h1 class="page-title"><slot>{{ heading }}</slot></h1>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { stripSuffix } from '@/utils/pageTitle'

const route = useRoute()

/** Заголовок страницы: meta.h1, иначе meta.title без бренда. */
const heading = computed(() => {
  const meta = route.meta as { h1?: string; title?: string }
  return String(meta.h1 ?? stripSuffix(meta.title)).trim()
})
</script>
