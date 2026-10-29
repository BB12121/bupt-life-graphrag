export type Campus = 'shahe' | 'haidian' | null
export type EntityCampus = 'shahe' | 'haidian' | 'shared' | 'unknown'
export type Mode = 'hybrid' | 'vector'
export interface GuideDocument { id: string; title: string; source_path: string; source_commit: string; source_url: string }
export interface DocumentDetail { document: GuideDocument; text: string }
export interface Entity { id: string; type: 'Campus' | 'Place' | 'Service' | 'Platform' | 'Condition'; name: string; aliases: string[]; campus: EntityCampus; url: string | null }
export interface Edge { subject_id: string; relation: 'LOCATED_IN' | 'PROVIDES' | 'USES_PLATFORM' | 'REQUIRES'; object_id: string; evidence_ids: string[] }
export interface Evidence { id: string; doc_id: string; source_commit: string; source_path: string; heading: string; line_start: number; line_end: number; quote: string; source_url: string }
export interface GraphPath { id: string; branch_id: number; nodes: Entity[]; edges: Edge[] }
export interface Answer { text: string; entity_ids: string[]; path_ids: string[]; evidence_ids: string[] }
export interface GeneratedAnswer { text: string; model: string; evidence_ids: string[] }
export interface Clarification { field: 'campus' | 'entity_bindings'; mention: string; options: { value: string; label: string }[] }
export interface QARequest { question: string; campus: Campus; mode: Mode; entity_bindings: Record<string, string>; generate?: boolean }
export interface QAResponse { status: 'answered' | 'partial' | 'abstained' | 'needs_clarification'; reason: string | null; knowledge_revision: number; source_commit: string; answers: Answer[]; paths: GraphPath[]; evidence: Evidence[]; warnings: string[]; clarifications: Clarification[]; generated?: GeneratedAnswer | null }
export interface KnowledgeStatus { repository: string; source_commit: string | null; knowledge_revision: number; document_count: number; last_synced_at: string | null }
export interface SyncResult { source_commit: string; knowledge_revision: number; added: number; updated: number; deleted: number; pending_count: number; changed: boolean }
export interface Turn { id: string; request: QARequest; response: QAResponse | null; pending: boolean; elapsedMs: number; error: string | null }
