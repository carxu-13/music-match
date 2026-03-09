import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiFetch } from '../App'

export default function Results() {
  const { activityId } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch(`/api/analyze/${activityId}`)
      .then(r => {
        if (!r.ok) throw new Error('Analysis failed')
        return r.json()
      })
      .then(d => {
        setData(d)
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }, [activityId])

  const fmtTime = (s) => {
    s = Math.round(s)
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = s % 60
    return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }

  const fmtPace = (minPerMile) => {
    if (!minPerMile) return '?'
    const m = Math.floor(minPerMile)
    const s = Math.round((minPerMile - m) * 60)
    return `${m}:${String(s).padStart(2, '0')}`
  }

  if (loading) return <div className="loading">Analyzing activity...</div>
  if (error) return <div className="message error">{error}</div>

  const { activity, matched_tracks: tracks, message } = data

  return (
    <>
      <Link to="/activities" className="back-link">&larr; Activities</Link>

      <div className="card">
        <h2>{activity.name}</h2>
        <p style={{ color: '#999', fontSize: '0.85rem' }}>
          {activity.type} &middot; {Math.round(activity.duration_s / 60)} min
          {activity.distance_m > 0 && ` \u00b7 ${(activity.distance_m / 1609.34).toFixed(1)} mi`}
        </p>
      </div>

      {tracks.length === 0 ? (
        <div className="card">
          <p className="message">{message || 'No tracks matched this activity.'}</p>
        </div>
      ) : (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table className="results-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Song</th>
                <th>HR</th>
                <th>SPM</th>
                <th>BPM</th>
                <th>Pace</th>
              </tr>
            </thead>
            <tbody>
              {tracks.map((t, i) => (
                <tr key={i}>
                  <td className="metric">
                    {fmtTime(t.offset_start_s)}&ndash;{fmtTime(t.offset_end_s)}
                  </td>
                  <td>
                    <div className="track-name">{t.track}</div>
                    <div className="track-artist">{t.artist}</div>
                  </td>
                  <td className="metric">
                    {t.avg_hr ? Math.round(t.avg_hr) : '?'}
                  </td>
                  <td className="metric metric-highlight">
                    {t.avg_spm ? Math.round(t.avg_spm) : '?'}
                  </td>
                  <td className="metric">
                    {t.bpm ? Math.round(t.bpm) : '?'}
                  </td>
                  <td className="metric">
                    {fmtPace(t.avg_speed_min_per_mile)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
