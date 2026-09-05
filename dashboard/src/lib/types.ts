export type Merchant = {
  id: string
  business_name: string
  slug: string
  business_type: string
  owner_name: string
  phone_number: string
  email: string
  address: string | null
  timezone: string
  is_active: boolean
}

export type Staff = { id: string; name: string; is_active: boolean; created_at: string }
export type BookingMode = 'APPOINTMENT' | 'BATCH' | 'CUSTOM_ORDER'

export type Service = {
  id: string
  title: string
  description: string | null
  category: string
  booking_mode: BookingMode
  price: string
  advance_token_amount: string
  duration_minutes: number | null
  max_capacity: number | null
  prep_lead_time_hours: number | null
  is_active: boolean
  staff_member_ids: string[]
}

export type CustomField = {
  id: string
  service_id: string
  field_label: string
  field_type: 'TEXT' | 'DROPDOWN' | 'BOOLEAN' | 'FILE_UPLOAD'
  options: string[] | null
  is_required: boolean
  display_order: number
}

export type OperatingHour = {
  id?: string
  day_of_week: number
  open_time: string | null
  close_time: string | null
  is_closed: boolean
}

export type BatchSchedule = {
  id: string
  service_id: string
  day_of_week: number
  start_time: string
  end_time: string
  max_capacity: number
  is_active: boolean
}
