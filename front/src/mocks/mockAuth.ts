export type MockUser = {
  fullName: string
  email: string
  password: string
}

const STORAGE_KEY = 'foodspot_mock_users'

export const DEFAULT_USERS: MockUser[] = [
  {
    fullName: 'Thành Hậu',
    email: 'demo@foodspot.vn',
    password: 'password123',
  },
  {
    fullName: 'Admin Food Spot',
    email: 'admin@foodspot.vn',
    password: 'password123',
  },
]

function getUsers(): MockUser[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    if (data) {
      const parsed = JSON.parse(data) as MockUser[]
      if (parsed.length > 0) return parsed
    }
    // Tự động khởi tạo tài khoản mẫu sẵn có
    saveUsers(DEFAULT_USERS)
    return DEFAULT_USERS
  } catch {
    return DEFAULT_USERS
  }
}

function saveUsers(users: MockUser[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(users))
  } catch {
    // Ignore storage quota error
  }
}

export function registerUser(
  fullName: string,
  email: string,
  password: string,
): { success: boolean; message: string } {
  const users = getUsers()
  const normalizedEmail = email.trim().toLowerCase()

  const exists = users.some(
    (user) => user.email.toLowerCase() === normalizedEmail,
  )

  if (exists) {
    return {
      success: false,
      message: 'Email này đã được đăng ký.',
    }
  }

  users.push({
    fullName: fullName.trim(),
    email: normalizedEmail,
    password,
  })

  saveUsers(users)

  return {
    success: true,
    message: 'Đăng ký thành công!',
  }
}

export function loginUser(
  email: string,
  password: string,
): { success: boolean; message: string; user?: Omit<MockUser, 'password'> } {
  const normalizedEmail = email.trim().toLowerCase()
  const users = getUsers()

  const user = users.find(
    (item) =>
      item.email.toLowerCase() === normalizedEmail &&
      item.password === password,
  )

  if (!user) {
    return {
      success: false,
      message: 'Email hoặc mật khẩu không chính xác.',
    }
  }

  const { password: _password, ...safeUser } = user

  try {
    localStorage.setItem('foodspot_mock_session', JSON.stringify(safeUser))
  } catch {
    // Ignore storage quota error
  }

  return {
    success: true,
    message: 'Đăng nhập thành công!',
    user: safeUser,
  }
}

export function logoutUser() {
  localStorage.removeItem('foodspot_mock_session')
}

export function getSessionUser(): Omit<MockUser, 'password'> | null {
  try {
    const data = localStorage.getItem('foodspot_mock_session')
    if (data) return JSON.parse(data)
  } catch {
    return null
  }
  return null
}
