/**
 * Command and Audit Log Contract
 * Ensuring idempotency, request_id tracking, and logging of control commands
 */

export type CommandType =
  | 'create_strategy'
  | 'allocate_bot'
  | 'start_bot'
  | 'stop_bot'
  | 'reload_state';

export type CommandStatus = 'pending' | 'success' | 'failed' | 'uncertain';

/**
 * Strict command storage contract:
 * Stored in sessionStorage/localStorage before POST, removed only on confirmed response
 */
export interface PendingCommand {
  path: string;
  body: Record<string, any>; // must contain 32-char hex request_id
  build: string;             // X-CatOS-Build
  instance: string;          // X-CatOS-Instance
  timestamp: string;
}

export interface CommandRecord {
  request_id: string;
  command_type: CommandType;
  body: Record<string, any>;
  timestamp: string;
  status: CommandStatus;
  build_id?: string;
  instance_id?: string;
  response?: Record<string, any>;
  error_code?: string;
  error_message?: string;
}

export interface AuditLogItem {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  category: 'SUPERVISOR' | 'WORKER' | 'RISK' | 'ORDER' | 'SYSTEM';
  message: string;
  details?: Record<string, any>;
}

