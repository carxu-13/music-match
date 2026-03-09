import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useSearchParams } from 'react-router-dom'
import Login from './components/Login'
import Activities from './components/Activities'
import Results from './components/Results'
import './App.css'

// Helper to make authed API calls
export function apiFetch(path, opts = {}) {
  const token = localStorage.getItem('mm_token') || ''
  return fetch(path, {
    ...opts,
    headers: {
      ...opts.headers,
      'Authorization': `Bearer ${token}`,
    },
  })
}

function AppContent() {
  const [auth, setAuth] = useState({ strava: false, spotify: false, garmin: false })
  const [flash, setFlash] = useState('')
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const fetchAuthStatus = () => {
    apiFetch('/api/auth/status')
      .then(r => r.json())
      .then(setAuth)
      .catch(() => {})
  }

  useEffect(() => {
    // Check for token from OAuth callback
    const tokenParam = searchParams.get('token')
    if (tokenParam) {
      localStorage.setItem('mm_token', tokenParam)
    }

    const authResult = searchParams.get('auth')
    if (authResult) {
      const service = authResult.replace('_ok', '')
      setFlash(`${service.charAt(0).toUpperCase() + service.slice(1)} connected successfully`)
      setTimeout(() => setFlash(''), 4000)
      navigate('/', { replace: true })
    }

    fetchAuthStatus()
  }, [])

  return (
    <div className="app">
      <header>
        <h1>Music Match</h1>
        <p className="subtitle">Match your workout music to your performance data</p>
      </header>

      {flash && (
        <div className="success-toast">
          <span className="check">&#10003;</span> {flash}
        </div>
      )}

      <Routes>
        <Route path="/" element={<Login auth={auth} onAuthUpdate={fetchAuthStatus} />} />
        <Route path="/activities" element={<Activities />} />
        <Route path="/results/:activityId" element={<Results />} />
      </Routes>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}

export default App
