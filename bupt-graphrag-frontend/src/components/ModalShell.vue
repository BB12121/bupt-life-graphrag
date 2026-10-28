<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { X } from 'lucide-vue-next'
defineProps<{ title: string; drawer?: boolean; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>(), dialog = ref<HTMLDialogElement | null>(null)
let previous: HTMLElement | null = null
onMounted(() => { previous = document.activeElement as HTMLElement; dialog.value?.showModal() })
onUnmounted(() => { previous?.focus() })
</script>
<template>
  <dialog ref="dialog" :class="['modal', { 'is-drawer': drawer, 'is-wide': wide }]" :aria-label="title" @cancel.prevent="emit('close')" @click="e => { if (e.target === dialog) emit('close') }">
    <div class="modal-header"><div><h2>{{ title }}</h2></div><button class="icon-button" aria-label="关闭面板" @click="emit('close')"><X :size="20" /></button></div>
    <div class="modal-body"><slot /></div>
  </dialog>
</template>
