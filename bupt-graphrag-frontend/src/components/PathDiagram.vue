<script setup lang="ts">
import { ArrowLeft, ArrowRight, FileText, Globe, MapPin, ClipboardList, ShieldCheck, Building2 } from 'lucide-vue-next'
import type { GraphPath } from '../api/types'
import { edgeDirection, entityTypeLabel, relationLabel } from '../lib/presentation'
defineProps<{ path: GraphPath; selectedEdge: number }>()
defineEmits<{ select: [index: number] }>()
const icons: Record<string, unknown> = { Place: MapPin, Service: ClipboardList, Platform: Globe, Condition: ShieldCheck, Campus: Building2 }
</script>
<template>
  <div class="path-diagram">
    <template v-for="(node, i) in path.nodes" :key="path.id + '-' + i">
      <div :class="['path-node', 'node-' + node.type]"><span class="node-type"><component :is="icons[node.type]" :size="13" />{{ entityTypeLabel(node.type) }}</span><strong>{{ node.name }}</strong></div>
      <button v-if="path.edges[i]" :class="['path-edge', { selected: selectedEdge === i, invalid: edgeDirection(path, i) === 'invalid' }]" :aria-label="'查看' + node.name + '与' + path.nodes[i + 1]?.name + '之间' + relationLabel(path.edges[i].relation) + '的原文依据'" :aria-pressed="selectedEdge === i" @click="$emit('select', i)"><span>{{ relationLabel(path.edges[i].relation) }}</span><component :is="edgeDirection(path, i) === 'reverse' ? ArrowLeft : ArrowRight" :size="38" :stroke-width="1" /><small><FileText :size="10" />{{ path.edges[i].evidence_ids.length }} 条依据</small></button>
    </template>
  </div>
  <p class="path-readable sr-only"><span>关系路径：</span><template v-for="(node, i) in path.nodes" :key="i">{{ node.name }}<span v-if="path.edges[i]"> {{ edgeDirection(path, i) === 'reverse' ? '←' : '→' }} </span></template></p>
</template>
