import type { NavigateFunction } from 'react-router-dom'
import { flushSync } from 'react-dom'

/**
 * Điều hướng trượt trang siêu mượt mà sử dụng GPU Native View Transitions API + flushSync.
 * Hỗ trợ đảo chiều 2 chiều tuyệt đối:
 * - Đi tới (Trang chủ -> Explore): Trượt từ Phải sang Trái
 * - Quay về (Explore -> Trang chủ): Trượt NGƯỢC LẠI từ Trái sang Phải
 */
export function smoothSlideNavigate(
  navigate: NavigateFunction,
  to: string,
  options: { back?: boolean } = {},
) {
  const root = document.documentElement

  if (options.back) {
    root.classList.add('back-transition')
    root.setAttribute('data-direction', 'back')
  } else {
    root.classList.remove('back-transition')
    root.setAttribute('data-direction', 'forward')
  }

  // Native Browser View Transitions API
  if (typeof document !== 'undefined' && 'startViewTransition' in document) {
    const doc = document as unknown as {
      startViewTransition: (cb: () => void) => { finished: Promise<void> }
    }

    const transition = doc.startViewTransition(() => {
      flushSync(() => {
        navigate(to)
      })
    })

    transition.finished
      .catch(() => {})
      .finally(() => {
        root.classList.remove('back-transition')
        root.removeAttribute('data-direction')
      })
  } else {
    navigate(to)
  }
}

// Bắt sự kiện nút Back của trình duyệt để tự động lùi ngược chiều
if (typeof window !== 'undefined') {
  window.addEventListener('popstate', () => {
    document.documentElement.classList.add('back-transition')
    document.documentElement.setAttribute('data-direction', 'back')
    setTimeout(() => {
      document.documentElement.classList.remove('back-transition')
      document.documentElement.removeAttribute('data-direction')
    }, 400)
  })
}
