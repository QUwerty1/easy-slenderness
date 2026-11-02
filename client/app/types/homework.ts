export type HomeworkStatus = 'filling' | 'review' | 'reviewed' | 'unavailable' | 'not_completed'

export interface HomeworkDay {
  date: string
  report_id: number | null
  is_created: boolean
  available: boolean
  status: HomeworkStatus
  status_display: string
  is_completed: boolean | null
  meal_count: number
}

export interface HomeworkListParticipant {
  participant_id: number
  participant_name: string
  cells: (null | {
    date: string
    report_id: number | null
    status: HomeworkStatus
    status_display: string
    is_completed: boolean | null
    meal_count: number
  })[]
}

export interface HomeworkList {
  mode: 'participant' | 'tutor'
  course_id: number
  course_name: string
  days?: HomeworkDay[]
  dates?: string[]
  participants?: HomeworkListParticipant[]
}

export interface MealPhoto {
  id: number
  url: string
  uploaded_at?: string
}

export interface MealEntry {
  id: number
  water_drank: boolean
  breathing_practice: boolean
  feeling: 'hunger' | 'appetite'
  feeling_display: string
  photos: MealPhoto[]
  created_at: string
  updated_at: string
}

export interface HomeworkReport {
  id?: number
  report_date: string
  available: boolean
  is_created: boolean
  status?: HomeworkStatus
  status_display?: string
  message?: string
  participant_name?: string
  participant_comment: string
  tutor_comment: string
  is_completed: boolean | null
  meal_count: number
  meals: MealEntry[]
}
