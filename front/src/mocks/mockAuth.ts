
export type MockUser = {
  fullName: string
  email: string
  password: string
}

const STORAGE_KEY = 'foodspot_mock_users'

function getUsers(): MockUser[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? JSON.parse(data) as MockUser[] : []
  } catch {
    return []
  }
}

function saveUsers(users: MockUser[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(users))
}

export function registerUser(
  fullName: string,
  email: string,
  password: string
): { success: boolean; message: string } {
  const users = getUsers()
  const normalizedEmail = email.trim().toLowerCase()

  const exists = users.some(
    user => user.email.toLowerCase() === normalizedEmail
  )

  if (exists) {
    return {
      success: false,
      message: 'Email này đã được đăng ký.'
    }
  }

  users.push({
    fullName: fullName.trim(),
    email: normalizedEmail,
    password
  })

  saveUsers(users)

  return {
    success: true,
    message: 'Đăng ký thành công!'
  }
}

export function loginUser(
  email: string,
  password: string
): { success: boolean; message: string; user?: Omit<MockUser, 'password'> } {
  const normalizedEmail = email.trim().toLowerCase()
  const users = getUsers()

  const user = users.find(
    item =>
      item.email.toLowerCase() === normalizedEmail &&
      item.password === password
  )

  if (!user) {
    return {
      success: false,
      message: 'Email hoặc mật khẩu không chính xác.'
    }
  }

  const { password: _password, ...safeUser } = user

  localStorage.setItem('foodspot_mock_session', JSON.stringify(safeUser))

  return {
    success: true,
    message: 'Đăng nhập thành công!',
    user: safeUser
  }
}

export function logoutUser() {
  localStorage.removeItem('foodspot_mock_session')
}
