import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { apiFetch } from '../App'

export default function Activities() {
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAll, setShowAll] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    apiFetch('/api/activities')
      .then(r => r.json())
      .then(data => {
        setActivities(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const formatDuration = (s) => {
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    return h > 0 ? `${h}h ${m}m` : `${m}m`
  }

  const formatDate = (iso) => {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    })
  }

  if (loading) return <div className="loading">Loading activities...</div>

  const filtered = showAll ? activities : activities.filter(a => a.has_tracks)
  const hiddenCount = activities.length - activities.filter(a => a.has_tracks).length

  return (
    <>
      <Link to="/" className="back-link">&larr; Back</Link>

      <div className="card">
        <h2>Your Activities</h2>

        {hiddenCount > 0 && (
          <label style={{ fontSize: '0.85rem', color: '#888', cursor: 'pointer', display: 'block', marginBottom: '0.75rem' }}>
            <input
              type="checkbox"
              checked={showAll}
              onChange={e => setShowAll(e.target.checked)}
              style={{ marginRight: '0.5rem' }}
            />
            Show {hiddenCount} activit{hiddenCount === 1 ? 'y' : 'ies'} without Spotify tracks
          </label>
        )}

        {filtered.length === 0 ? (
          <p className="message">
            {activities.length === 0
              ? 'No activities found. Connect Strava or upload a file.'
              : 'No activities with Spotify tracks found. Make sure to cache your Spotify history before or after activities.'}
          </p>
        ) : (
          filtered.map(a => (
            <div
              key={a.id}
              className="activity-item"
              onClick={() => navigate(`/results/${a.id}`)}
              style={{ opacity: a.has_tracks ? 1 : 0.5 }}
            >
              <div>
                <div className="activity-name">{a.name}</div>
                <div className="activity-meta">
                  {formatDate(a.start_time)} &middot; {formatDuration(a.duration_s)}
                  {a.distance_m > 0 && ` \u00b7 ${(a.distance_m / 1609.34).toFixed(1)} mi`}
                </div>
              </div>
              <div className="activity-badges">
                <span className="badge badge-type">{a.type}</span>
                {a.source && <span className="badge badge-source">{a.source}</span>}
                <span className={`badge ${a.has_heartrate ? 'badge-hr' : 'badge-nohr'}`}>
                  {a.has_heartrate ? 'HR' : 'no HR'}
                </span>
                {a.has_tracks && <span className="badge badge-tracks">Tracks</span>}
              </div>
            </div>
          ))
        )}
      </div>
    </>
  )
}
