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
  billing: BillingSummary | null
}

export type BillingSummary = {
  effective_status: 'trialing' | 'active' | 'past_due' | 'expired' | 'cancelled'
  trial_ends_at: string
  days_left: number
  current_period_end: string | null
  cancel_at_period_end: boolean
  locked: boolean
  authorization_confirmed: boolean
  processing: boolean
}

export type BillingPayment = {
  razorpay_payment_id: string
  amount_paise: number
  currency: string
  status: string
  paid_at: string | null
}

export type BillingDetail = { summary: BillingSummary; payments: BillingPayment[] }

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
  allow_cancellations: boolean
  reschedule_cutoff_hours: number | null
  cancel_cutoff_hours: number
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

export type AgendaBooking = {
  booking_reference: string
  booking_date: string
  start_time: string
  end_time: string
  booking_status: 'CONFIRMED'
  service_title: string
  customer_name: string
  customer_phone: string
}

export type AgendaResponse = {
  today: string
  tomorrow: string
  timezone: string
  bookings: AgendaBooking[]
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
