export type CourseStatus = 'paid' | 'free'
export type CourseState = 'open' | 'running' | 'archived'
export type RequestStatus = 'registered' | 'done' | 'rejected'

export interface Course {
  id: number
  name: string
  status: CourseStatus
  status_display: string
  price: string | null
  start_at: string
  end_at: string
  state: CourseState
  state_display: string
  is_participant: boolean
  can_edit: boolean
}

export interface CoursePayload {
  name: string
  status?: CourseStatus
  start_at: string
  price: string | null
}

export interface EnrollResult {
  result: 'enrolled' | 'payment'
  participant_id?: number
  payment_url?: string
}

export interface PublicParticipant {
  id: number
  full_name: string
  role: string
}

export interface AdminParticipant {
  id: number
  user_id: number
  full_name: string
  phone: string
  email: string
  enrolled_at: string
  method: 'self' | 'manual'
  method_display: string
  status: 'active' | 'excluded'
  status_display: string
  exclusion_reason: '' | 'request' | 'violation'
  exclusion_reason_display: string
  has_registered_request: boolean
}

export interface Candidate {
  id: number
  full_name: string
  phone: string
  email: string
  is_participant: boolean
}

export interface Refusable {
  id: number
  course: Course
  paid_amount: string | null
}

export interface MyRequest {
  id: number
  course_name: string
  created_at: string
  status: RequestStatus
  status_display: string
  refund_amount: string | null
}

export interface RequestListItem {
  id: number
  full_name: string
  course_name: string
  basis: 'participant' | 'violation'
  basis_display: string
  created_at: string
  status: RequestStatus
  status_display: string
}

export interface RequestDetail extends RequestListItem {
  reason: string
  phone: string
  email: string
  course: Course
  participant_active: boolean
  passed_percent: number
  before_start: boolean
  payment: {
    method: 'service' | 'offline'
    method_display: string
    amount: string
    paid_at: string
    transaction_id: string
  } | null
  refund: { amount: string; fpr: string; refunded_at: string } | null
  can_reject: boolean
}
