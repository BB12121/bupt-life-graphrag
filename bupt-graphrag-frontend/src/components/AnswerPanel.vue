<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowRight, ArrowUpRight, Check, CheckCircle2, ChevronDown, Copy, Download, FileText, GitBranch, Info, LoaderCircle, MessageCircleQuestion, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-vue-next'
import type { Campus, Turn } from '../api/types'
import { useWorkspace } from '../stores/workspace'
import { campusLabel, evidenceTitle, exportTurn, shortCommit } from '../lib/presentation'
import { isDemo } from '../api/client'
import { renderExcerpt, splitAnswer } from '../lib/markdown'
import PathDiagram from './PathDiagram.vue'
const props = defineProps<{ turn: Turn }>(), store = useWorkspace()
const selectedPath = ref(''), selectedEdge = ref(0), selectedEvidence = ref(''), selectedAnswer = ref(0), choices = ref<Record<number, string>>({}), copying = ref(false), mobileTab = ref('answer')
const response = computed(() => props.turn.response), currentPath = computed(() => response.value?.paths.find(p => p.id === selectedPath.value) || response.value?.paths[0]), evidence = computed(() => response.value?.evidence.find(e => e.id === selectedEvidence.value) || response.value?.evidence[0]), currentEdge = computed(() => currentPath.value?.edges[selectedEdge.value])
const edgeEvidence = computed(() => response.value?.evidence.filter(e => currentEdge.value?.evidence_ids.includes(e.id)) || [])
watch(() => props.turn.id, () => { selectedPath.value = ''; selectedEdge.value = 0; selectedEvidence.value = ''; selectedAnswer.value = 0; choices.value = {}; mobileTab.value = 'answer' })
watch(response, value => { if (value) { selectedPath.value = value.paths[0]?.id || ''; selectedEvidence.value = value.evidence[0]?.id || '' } }, { immediate: true })
// Relative guide links in an answer resolve against the source file of its first evidence.
function answerSource(answer: { evidence_ids: string[] }) { return response.value?.evidence.find(e => e.id === answer.evidence_ids[0])?.source_url || '' }
function choosePath(id: string) { selectedPath.value = id; selectEdge(0) }
function selectEdge(index: number) { selectedEdge.value = index; selectedEvidence.value = currentPath.value?.edges[index]?.evidence_ids[0] || '' }
function chooseAnswer(index: number) { selectedAnswer.value = index; const a = response.value?.answers[index]; if (a?.path_ids[0]) choosePath(a.path_ids[0]); if (a?.evidence_ids[0]) selectedEvidence.value = a.evidence_ids[0] }
const canClarify = computed(() => response.value?.clarifications.every((_, i) => choices.value[i]))
function clarify() {
  if (!response.value || !canClarify.value) return
  const request = { ...props.turn.request, entity_bindings: { ...props.turn.request.entity_bindings } }
  response.value.clarifications.forEach((c, i) => { if (c.field === 'campus') request.campus = choices.value[i] as Campus; else request.entity_bindings[c.mention] = choices.value[i] })
  store.campus = request.campus; store.ask(request)
}
async function copyAnswer() { try { await navigator.clipboard.writeText((response.value?.answers.map(a => a.text).join('\n\n') || '') + '\n\n依据指南快照 ' + response.value?.source_commit); copying.value = true; store.notify('答案与来源版本已复制'); setTimeout(() => { copying.value = false }, 1800) } catch { store.notify('无法自动复制，请手动选择答案。') } }
const statusTitle = computed(() => ({ answered: '回答', partial: '部分结果', abstained: '暂时无法回答', needs_clarification: '请补充信息' }[response.value?.status || 'answered']))
const reasonText = computed(() => ({ no_evidence: '当前指南快照中没有找到足够依据。这并不意味着该服务不存在。', unknown_entity: '暂时无法确认这个名称，请尝试使用更完整的地点或服务名称。', unsupported_query: '当前能力暂不支持这类问题。可以简化问题，或到指南资料库查看相关正文。', realtime_unavailable: '指南快照无法确认现在是否营业、当前价格或实时余量，请通过对应服务的官方渠道核实。', search_truncated: '检索达到搜索限制，以下结果可能不完整。', conflicting_evidence: '指南中存在冲突，以下仅展示已有支持部分，请结合原文核查。' }[response.value?.reason || ''] || '请根据下方提示补充信息。'))
</script>
<template>
  <section id="answer-result" class="result-section" aria-live="polite" :aria-busy="turn.pending">

    <div v-if="turn.pending" class="answer-loading"><div class="loading-orbit"><LoaderCircle :size="25" class="spinning" /></div><p>正在查询…</p></div>
    <div v-else-if="turn.error" class="result-error"><TriangleAlert :size="26" /><h3>请求未完成</h3><p>{{ turn.error }}</p><button class="button secondary" :disabled="store.syncing || store.qaPending" @click="store.ask(turn.request)"><RefreshCw :size="15" />重试</button></div>
    <template v-else-if="response">
      <div v-if="store.status && response.knowledge_revision !== store.status.knowledge_revision" class="notice warning"><Info :size="17" /><p>资料已更新，此回答仍依据 REV {{ response.knowledge_revision }}。重新提问可使用新快照。</p></div>
      <div v-if="response.status === 'partial'" class="notice warning"><TriangleAlert :size="18" /><p>{{ reasonText }}</p></div>
      <div v-if="response.status === 'needs_clarification'" class="clarification-card"><MessageCircleQuestion :size="27" /><h3>{{ statusTitle }}</h3><fieldset v-for="(clarification, i) in response.clarifications" :key="i"><legend>{{ clarification.field === 'campus' ? '你想了解哪个校区？' : '“' + clarification.mention + '”指的是？' }}</legend><label v-for="option in clarification.options" :key="option.value" :class="['option-card', { chosen: choices[i] === option.value }]"><input v-model="choices[i]" type="radio" :name="'clarification-' + turn.id + '-' + i" :value="option.value" /><span>{{ option.label }}</span><Check v-if="choices[i] === option.value" :size="16" /></label></fieldset><button class="button primary" :disabled="!canClarify || store.qaPending || store.syncing" @click="clarify">确认并查询<ArrowRight :size="16" /></button></div>
      <div v-else-if="response.status === 'abstained'" class="abstained-card"><ShieldCheck :size="27" /><h3>{{ statusTitle }}</h3><p>{{ reasonText }}</p><RouterLink to="/documents" class="button secondary">查看指南<ArrowUpRight :size="15" /></RouterLink></div>
      <template v-else>
        <div class="mobile-result-tabs"><button v-for="tab in [['answer', '结论'], ['path', '路径'], ['evidence', '原文']]" :key="tab[0]" :class="{ active: mobileTab === tab[0] }" @click="mobileTab = tab[0]">{{ tab[1] }}</button></div>
        <div class="answer-grid"><div class="answer-main"><article :class="['answer-card', { 'mobile-hidden': mobileTab !== 'answer' }]"><div class="answer-card-top"><span class="verified-label"><CheckCircle2 :size="16" />{{ statusTitle }}</span><span class="pill">{{ campusLabel(turn.request.campus) }}</span></div><div v-for="(answer, i) in response.answers" :key="i" :class="['answer-text', { 'answer-selected': selectedAnswer === i }]" @click="chooseAnswer(i)"><p v-if="splitAnswer(answer.text).heading" class="answer-source-heading">指南原文 · {{ splitAnswer(answer.text).heading }}</p><div class="md-snippet" v-html="renderExcerpt(splitAnswer(answer.text).body, answerSource(answer))"></div><div class="inline-citations"><button v-for="id in answer.evidence_ids" :key="id" @click.stop="selectedEvidence = id; selectedAnswer = i"><FileText :size="11" />{{ '原文 ' + (response.evidence.findIndex(e => e.id === id) + 1) }}</button></div></div><p v-if="!response.answers.length" class="helper">当前仅确认了有限支持材料，尚无可直接呈现的结论。</p><div class="answer-tools"><span class="helper">{{ turn.request.mode === 'hybrid' ? '混合检索' : '向量检索' }}</span><div><button class="icon-button small" aria-label="复制答案" @click="copyAnswer"><component :is="copying ? Check : Copy" :size="15" /></button><button class="icon-button small" aria-label="导出回答与完整引用" @click="exportTurn(turn)"><Download :size="15" /></button></div></div></article>
          <article v-if="response.paths.length" :class="['path-card', { 'mobile-hidden': mobileTab !== 'path' }]"><div class="card-heading"><div><GitBranch :size="17" /><h3>关系路径</h3></div><span class="pill subtle">{{ response.paths.length }} 条路径</span></div><div class="path-tabs"><button v-for="(path, i) in response.paths" :key="path.id" :class="{ active: currentPath?.id === path.id, supporting: response.answers[selectedAnswer]?.path_ids.includes(path.id) }" @click="choosePath(path.id)"><span>路径 {{ i + 1 }}</span><span v-if="response.paths.some(p => p.branch_id === 1)">分支 {{ path.branch_id + 1 }}</span></button></div><PathDiagram v-if="currentPath" :path="currentPath" :selected-edge="selectedEdge" @select="selectEdge" /><div class="path-hint"><Info :size="13" /><span>点击关系查看原文，箭头表示事实方向。</span></div></article>
          <div v-else :class="['no-path-note', { 'mobile-hidden': mobileTab !== 'path' }]"><FileText :size="15" />此回答没有关系路径，请查看原文。</div>
        </div><aside :class="['evidence-card', { 'mobile-hidden': mobileTab !== 'evidence' }]"><div class="card-heading"><div><FileText :size="17" /><h3>原文</h3></div><span class="mono">{{ response.evidence.length }} 条</span></div><div class="evidence-tabs"><button v-for="(item, i) in response.evidence" :key="item.id" :class="{ active: evidence?.id === item.id, supporting: edgeEvidence.some(e => e.id === item.id) }" :aria-label="'查看依据 ' + (i + 1)" @click="selectedEvidence = item.id">{{ String(i + 1).padStart(2, '0') }}</button></div><template v-if="evidence"><div class="evidence-overline"><span class="source-square"></span>指南正文 · {{ evidenceTitle(evidence).split('/')[0] }}</div><h4>{{ evidenceTitle(evidence).split('/').pop() }}</h4><p class="evidence-heading">{{ evidence.heading }}</p><blockquote class="md-snippet" v-html="renderExcerpt(evidence.quote, evidence.source_url)"></blockquote><div class="evidence-location"><span class="mono">L{{ evidence.line_start }}–{{ evidence.line_end }}</span><span class="mono">{{ shortCommit(evidence.source_commit) }}</span></div><button class="button secondary full" @click="store.drawerEvidence = evidence">查看原文<ArrowUpRight :size="15" /></button></template><p v-else class="helper">当前没有可展示的原文依据。</p></aside></div>
      </template>
      <div v-if="response.warnings.length" class="answer-warnings"><Info :size="14" /><div><p v-for="(warning, i) in response.warnings" :key="i">{{ warning }}</p></div></div><div class="result-version mono">版本 {{ response.knowledge_revision }} · {{ shortCommit(response.source_commit) }} <span>·</span> {{ isDemo ? '示例回答' : '指南快照' }}</div>
    </template>
  </section>
</template>
