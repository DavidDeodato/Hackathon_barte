export interface AssistantContext {period:string;batch_id:string|null;run_id:string|null}
export interface AssistantSource {id:string;label:string;url:string;period:string;run_id?:string;document_id?:string;row_numbers?:number[]}
export interface NavigationTarget {view:'documents'|'close'|'results';period?:string;batchId?:string;runId?:string;output?:string;documentId?:string;newClosing?:boolean}
export interface AssistantAction {id:string;kind:'navigate'|'process_close';label:string;target:Record<string,unknown>;target_label?:string;documents?:{id:string;name:string;role:string}[];requires_confirmation:boolean;status?:string;result?:{run_id?:string;status?:string}}
export interface AssistantMessage {id:string;role:'user'|'assistant';content:string;status:string;sources:AssistantSource[];actions:AssistantAction[];tool_events?:{tool:string;status:string}[]}
export interface Conversation {id:string;title:string;context:AssistantContext;messages:AssistantMessage[];updated_at:string}
export interface ContextCatalog {periods:string[];batches:{id:string;name:string;period:string;documents_count:number}[];runs:{run_id:string;period:string;batch_id:string|null;status:string;created_at:string}[]}
