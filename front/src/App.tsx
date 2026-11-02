import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import FoodSpotLanding from './pages/FoodSpotLanding'
import Login from './pages/Login'
import Register from './pages/Register'
import Explore from './pages/Explore'
import SavedVideos from './pages/SavedVideos'
import SavedPlaces from './pages/SavedPlaces'
import { AuthProvider } from './contexts/AuthContext'
import { AnalysisProvider } from './contexts/AnalysisContext'
import ToastContainer from './components/common/ToastContainer'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AnalysisProvider>
          <Routes>
            <Route path="/" element={<FoodSpotLanding />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            <Route path="/home" element={<Navigate to="/explore" replace />} />
            <Route path="/explore" element={<Explore />} />
            <Route path="/saved-videos" element={<SavedVideos />} />
            <Route path="/saved-places" element={<SavedPlaces />} />

            <Route path="/history" element={<Navigate to="/explore" replace />} />
            <Route path="/settings" element={<Navigate to="/explore" replace />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <ToastContainer />
        </AnalysisProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App