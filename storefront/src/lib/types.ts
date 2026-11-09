export type BookingMode = "APPOINTMENT" | "BATCH" | "CUSTOM_ORDER";
export type CustomFieldType = "TEXT" | "DROPDOWN" | "BOOLEAN" | "FILE_UPLOAD";

export type CustomField = {
  id: string;
  service_id: string;
  field_label: string;
  field_type: CustomFieldType;
  options: string[] | null;
  is_required: boolean;
  display_order: number;
};

export type Service = {
  id: string;
  title: string;
  description: string | null;
  category: string;
  booking_mode: BookingMode;
  price: string;
  advance_token_amount: string;
  duration_minutes: number | null;
  max_capacity: number | null;
  prep_lead_time_hours: number | null;
  custom_fields: CustomField[];
};

export type Storefront = {
  merchant: {
    business_name: string;
    slug: string;
    business_type: string;
    logo_url: string | null;
    cover_image_url: string | null;
    address: string | null;
    timezone: string;
    accepting_bookings: boolean;
  };
  categories: string[];
  services: Service[];
};

export type AvailabilitySlot = {
  start_time: string;
  end_time: string;
  available: boolean;
  available_staff?: { id: string; name: string }[];
  batch_schedule_id?: string;
  max_capacity?: number;
  remaining_capacity?: number;
  business_open_time?: string;
  business_close_time?: string;
};

export type Availability = {
  service_id: string;
  booking_mode: BookingMode;
  date: string;
  available_slots: AvailabilitySlot[];
  earliest_allowed_at: string | null;
};

export type BookingResult = {
  management_token: string;
  booking_reference: string;
  booking_status: "CONFIRMED";
  booking_date: string;
  start_time: string;
  end_time: string;
  staff_member_id: string | null;
  batch_schedule_id: string | null;
};

export type ManagedBooking = {
  booking_reference: string;
  service_id: string;
  merchant_id: string;
  merchant_slug: string;
  booking_mode: BookingMode;
  booking_date: string;
  start_time: string;
  end_time: string;
  booking_status: "CONFIRMED" | "CANCELLED" | "COMPLETED" | "NO_SHOW" | "EXPIRED" | "PENDING_PAYMENT";
  service_title: string;
  business_name: string;
  timezone: string;
  can_cancel: boolean;
  can_reschedule: boolean;
};
