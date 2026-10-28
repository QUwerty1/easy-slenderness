export type Role = 'user' | 'participant' | 'tutor' | 'admin'

export type Stage = 'anon' | 'pre2fa' | 'setup2fa' | 'authed'

export type LoginNext = 'home' | '2fa' | '2fa_setup'

export interface User {
  id: number
  full_name: string
  phone: string
  email: string
  role: Role
  role_display: string
  totp_enabled: boolean
  requires_2fa: boolean
}

export interface RegisterPayload {
  full_name: string
  phone: string
  email: string
  password: string
  pd_consent: boolean
}

export interface ProfilePayload {
  full_name: string
  phone: string
  email: string
  current_password: string
}

export interface TotpSetup {
  secret: string
  otpauth_uri: string
  qr_svg: string
}
