import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../App'

const BACKEND = 'http://127.0.0.1:8000'

export default function Login({ auth, onAuthUpdate }) {
  const [garminEmail, setGarminEmail] = useState('')
  const [garminPassword, setGarminPassword] = useState('')
  const [garminLoading, setGarminLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('')
  const [error, setError] = useState('')
  const fileRef = useRef()
  const navigate = useNavigate()

  // Pass existing token to OAuth so the backend can associate the new auth
  const getAuthUrl = (service) => {
    const token = localStorage.getItem('mm_token') || ''
    return `${BACKEND}/api/auth/${service}${token ? `?token=${token}` : ''}`
  }

  const handleGarminLogin = async (e) => {
    e.preventDefault()
    setGarminLoading(true)
    setError('')
    try {
      const r = await apiFetch('/api/auth/garmin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: garminEmail || undefined,
          password: garminPassword || undefined,
        }),
      })
      const data = await r.json()
      if (!r.ok) {
        setError(data.error || 'Garmin login failed')
      } else {
        if (data.token) localStorage.setItem('mm_token', data.token)
        onAuthUpdate()
      }
    } catch {
      setError('Failed to connect to server')
    }
    setGarminLoading(false)
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploadStatus('Uploading...')
    setError('')

    const form = new FormData()
    form.append('file', file)

    try {
      const r = await apiFetch('/api/upload/activity', {
        method: 'POST',
        body: form,
      })
      const data = await r.json()
      if (!r.ok) {
        setError(data.error || 'Upload failed')
        setUploadStatus('')
      } else {
        if (data.token) localStorage.setItem('mm_token', data.token)
        setUploadStatus(`Uploaded: ${data.activity.name}`)
      }
    } catch {
      setError('Upload failed')
      setUploadStatus('')
    }
  }

  const canProceed = auth.spotify && (auth.strava || uploadStatus)

  return (
    <>
      <div className="card">
        <h2>Connect Your Accounts</h2>
        <div className="auth-grid">
          <div className="auth-option">
            <label>Activity Data</label>
            {auth.strava ? (
              <button className="btn btn-connected" disabled>&#10003; Strava connected</button>
            ) : (
              <a href={getAuthUrl('strava')} className="btn btn-strava">Connect Strava</a>
            )}
          </div>
          <div className="auth-option">
            <label>Music History</label>
            {auth.spotify ? (
              <button className="btn btn-connected" disabled>&#10003; Spotify connected</button>
            ) : (
              <a href={getAuthUrl('spotify')} className="btn btn-spotify">Connect Spotify</a>
            )}
          </div>
        </div>

        <div className="auth-option" style={{ marginBottom: '0.5rem' }}>
          <label>Heart Rate Data (optional)</label>
          {auth.garmin ? (
            <button className="btn btn-connected" disabled>&#10003; Garmin connected</button>
          ) : (
            <form onSubmit={handleGarminLogin} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <div className="input-group" style={{ flex: 1, minWidth: '140px', marginBottom: 0 }}>
                <input
                  type="email"
                  placeholder="Garmin email"
                  value={garminEmail}
                  onChange={e => setGarminEmail(e.target.value)}
                />
              </div>
              <div className="input-group" style={{ flex: 1, minWidth: '140px', marginBottom: 0 }}>
                <input
                  type="password"
                  placeholder="Garmin password"
                  value={garminPassword}
                  onChange={e => setGarminPassword(e.target.value)}
                />
              </div>
              <button type="submit" className="btn btn-garmin btn-sm" disabled={garminLoading}>
                {garminLoading ? 'Connecting...' : 'Connect Garmin'}
              </button>
            </form>
          )}
        </div>
      </div>

      <div className="separator">or upload activity file</div>

      <div className="card">
        <h2>Upload Activity File</h2>
        <p style={{ color: '#999', fontSize: '0.85rem', marginBottom: '1rem' }}>
          Upload a .gpx file exported from Strava or Garmin. Connect Spotify above for music matching.
        </p>
        <div className="upload-area" onClick={() => fileRef.current?.click()}>
          <input
            ref={fileRef}
            type="file"
            accept=".gpx"
            onChange={handleUpload}
            style={{ display: 'none' }}
          />
          <button className="btn btn-upload">Choose File</button>
          <p>Supports .gpx files</p>
        </div>
        {uploadStatus && <p style={{ color: '#1a7f37', marginTop: '0.75rem', fontSize: '0.85rem' }}>{uploadStatus}</p>}
      </div>

      {error && <p className="error" style={{ textAlign: 'center', marginTop: '0.5rem' }}>{error}</p>}

      <div className="actions">
        <button
          className="btn btn-primary"
          disabled={!canProceed}
          onClick={() => navigate('/activities')}
        >
          View Activities
        </button>
      </div>
      {!canProceed && (
        <p className="message">Connect Spotify + Strava (or upload a file) to get started</p>
      )}
    </>
  )
}
