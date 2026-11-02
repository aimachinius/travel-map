import { apiClient } from './client'
import type { LoginRequest, LoginResponse, RegisterRequest, User } from '../types/auth'

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return apiClient<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function register(data: RegisterRequest): Promise<User> {
  return apiClient<User>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getMe(): Promise<User> {
  return apiClient<User>('/api/v1/auth/me', {
    method: 'GET',
  })
}
