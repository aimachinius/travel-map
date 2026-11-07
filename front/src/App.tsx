import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import RootLayout from './layouts/RootLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import { AuthProvider } from './services/useAuth'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Layout dùng chung thanh Header cố định và Track lướt mượt mà cho Trang chủ & Khám phá */}
          <Route path="/" element={<RootLayout />} />
          <Route path="/explore" element={<RootLayout />} />
          <Route path="/liquid" element={<RootLayout />} />

          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route path="/home" element={<Navigate to="/explore" replace />} />

          {/* =========================================================================
              DEPRECATED / LEGACY ROUTES:
              Các trang cũ bên dưới đã được thay thế hoàn toàn bởi ngăn kéo kính thể lỏng
              (Liquid Glass Drawer: Liked Videos, Liked Places, History) trực tiếp trên /explore.
              Giữ lại các file mã nguồn cũ trong src/ để tham khảo, không xóa.
             ========================================================================= */}
          <Route path="/saved-videos" element={<Navigate to="/explore" replace />} />
          <Route path="/saved-places" element={<Navigate to="/explore" replace />} />
          <Route path="/history" element={<Navigate to="/explore" replace />} />
          <Route path="/settings" element={<Navigate to="/explore" replace />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
