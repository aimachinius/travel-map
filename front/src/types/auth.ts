export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  avatar_url: string | null
  is_active: boolean
  created_at: string
}

export interface LoginRequest {
  username_or_email: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  full_name?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}
