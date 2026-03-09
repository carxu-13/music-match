import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { apiFetch } from '../App'

export default function Activities() {
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)
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

  return (
    <>
      <Link to="/" className="back-link">&larr; Back</Link>

      <div className="card">
        <h2>Your Activities</h2>
        {activities.length === 0 ? (
          <p className="message">No activities found. Connect Strava or upload a file.</p>
        ) : (
          activities.map(a => (
            <div
              key={a.id}
              className="activity-item"
              onClick={() => navigate(`/results/${a.id}`)}
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
              </div>
            </div>
          ))
        )}
      </div>
    </>
  )
}
