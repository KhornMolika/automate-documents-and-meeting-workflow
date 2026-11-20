export interface Role {
  id: string
  role_name: string
  description?: string | null
}

export interface Department {
  id: string
  department_code: string
  name: string
  faculty: string
}

export interface AuthUser {
  id: string
  email: string
  full_name: string
  student_or_staff_id?: string | null
  department_id?: string | null
  is_active: boolean
  is_superuser: boolean
  roles: Role[]
  department?: Department | null
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  refresh_token?: string | null
  user: AuthUser
}

export interface Category {
  id: string
  code: string
  name: string
  description?: string | null
}

export interface DocumentVersion {
  id: string
  version_number: number
  file_name: string
  file_size_bytes: number
  mime_type: string
  sha256_checksum: string
  abstract_summary?: string | null
  extracted_entities?: string | null
  created_at: string
}

export interface WorkspaceDocument {
  id: string
  title: string
  category?: Category | null
  department_id: string
  academic_year: string
  current_version: number
  drive_file_id?: string | null
  drive_web_link?: string | null
  is_archived: boolean
  created_at: string
  updated_at: string
  latest_version?: DocumentVersion | null
  versions: DocumentVersion[]
}

export interface AgendaItem {
  id: string
  item_order: number
  title: string
  description?: string | null
  duration_minutes: number
}

export interface Decision {
  id: string
  agenda_topic?: string | null
  decision_text: string
  context_notes?: string | null
  order_index: number
}

export interface ActionItem {
  id: string
  task_description: string
  responsible_person_id?: string | null
  raw_assignee_name?: string | null
  deadline?: string | null
  status: string
  sheets_row_index?: number | null
  created_at: string
}

export interface MeetingSummary {
  id: string
  executive_summary: string
  discussion_highlights?: string | null
  mom_doc_id?: string | null
  mom_doc_link?: string | null
  is_verified: boolean
  verified_by?: string | null
  verified_at?: string | null
  decisions: Decision[]
  action_items: ActionItem[]
}

export interface Meeting {
  id: string
  title: string
  description?: string | null
  scheduled_start: string
  scheduled_end: string
  calendar_event_id?: string | null
  meet_link?: string | null
  department_id: string
  status: string
  created_at: string
  participant_count: number
  agendas: AgendaItem[]
  summary?: MeetingSummary | null
}

export interface TranscriptSegment {
  id: string
  speaker_label: string
  start_timestamp: number
  end_timestamp: number
  original_text: string
  translated_text?: string | null
  confidence_score: number
  language_detected: string
  created_at: string
}

export interface DashboardMeeting {
  id: string
  title: string
  status: string
  scheduled_start: string
  scheduled_end: string
  participants: number
  agenda: { title: string, duration_minutes: number }[]
  transcript_count: number
  summary: {
    id: string
    is_verified: boolean
    decisions_count: number
    action_items_count: number
  } | null
}

export interface DashboardActionItem {
  id: string
  task: string
  assignee?: string | null
  deadline?: string | null
  status: string
  meeting_id: string
  meeting_title: string
}

export interface DashboardDecision {
  id: string
  text: string
  agenda_topic?: string | null
  meeting_id: string
  meeting_title: string
  date: string
}

export interface Dashboard {
  documents_count: number
  meetings_count: number
  open_action_items_count: number
  mom_turnaround_minutes: number | null
  live_meeting: DashboardMeeting | null
  next_meeting: DashboardMeeting | null
  recent_documents: WorkspaceDocument[]
  action_items: DashboardActionItem[]
  recent_decisions: DashboardDecision[]
}

export interface MomPayload {
  executive_summary: string
  discussion_points: string[]
  decisions: {
    agenda_topic?: string | null
    decision_text: string
    context_notes?: string | null
  }[]
  action_items: {
    task_description: string
    assignee_name?: string | null
    deadline?: string | null
    confidence_score?: number
  }[]
}

export interface MinutesOfMeeting {
  meeting_title: string
  executive_summary: string
  discussion_points: string[]
  decisions: {
    agenda_topic?: string | null
    decision_text: string
    context_notes?: string | null
  }[]
  action_items: {
    task_description: string
    assignee_name?: string | null
    deadline?: string | null
    confidence_score?: number
  }[]
}
