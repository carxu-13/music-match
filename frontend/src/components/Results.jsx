import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiFetch } from '../App'
import PaceChart from './PaceChart'

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

  // Compute overall activity stats
  const avgHr = tracks.length > 0
    ? Math.round(tracks.reduce((s, t) => s + (t.avg_hr || 0), 0) / tracks.filter(t => t.avg_hr).length) || null
    : null
  const totalDist = tracks.reduce((s, t) => s + (t.distance_mi || 0), 0)

  return (
    <>
      <Link to="/activities" className="back-link">&larr; Activities</Link>

      <div className="card">
        <h2>{activity.name}</h2>
        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', color: '#888', fontSize: '0.82rem' }}>
          <span>{activity.type}</span>
          <span>{Math.round(activity.duration_s / 60)} min</span>
          {activity.distance_m > 0 && <span>{(activity.distance_m / 1609.34).toFixed(1)} mi</span>}
          {avgHr && <span>Avg HR: {avgHr}</span>}
          {tracks.length > 0 && <span>{tracks.length} songs</span>}
        </div>
      </div>

      {tracks.length > 0 && (
        <PaceChart tracks={tracks} duration={activity.duration_s} />
      )}

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
                <th>Pace</th>
                <th>HR</th>
                <th>SPM</th>
                <th>BPM</th>
                <th>Dist</th>
                <th>Elev</th>
                <th style={{ fontSize: '0.6rem' }}>SPM/BPM</th>
              </tr>
            </thead>
            <tbody>
              {tracks.map((t, i) => {
                const ratio = t.cadence_to_bpm_ratio
                const ratioColor = ratio
                  ? ratio >= 0.95 && ratio <= 1.05 ? '#4CAF50'
                  : ratio >= 0.45 && ratio <= 0.55 ? '#2196F3'
                  : '#999'
                  : '#ccc'

                return (
                  <tr key={i}>
                    <td className="metric" style={{ whiteSpace: 'nowrap' }}>
                      {fmtTime(t.offset_start_s)}&ndash;{fmtTime(t.offset_end_s)}
                    </td>
                    <td>
                      <div className="track-name">{t.track}</div>
                      <div className="track-artist">{t.artist}</div>
                    </td>
                    <td className="metric metric-highlight">
                      {fmtPace(t.avg_speed_min_per_mile)}
                      {t.fastest_pace && (
                        <div style={{ fontSize: '0.65rem', color: '#999' }}>
                          best {fmtPace(t.fastest_pace)}
                        </div>
                      )}
                    </td>
                    <td className="metric">
                      {t.avg_hr ? Math.round(t.avg_hr) : '?'}
                      {t.max_hr && (
                        <div style={{ fontSize: '0.65rem', color: '#999' }}>
                          max {Math.round(t.max_hr)}
                        </div>
                      )}
                    </td>
                    <td className="metric">
                      {t.avg_spm ? Math.round(t.avg_spm) : '?'}
                    </td>
                    <td className="metric">
                      {t.bpm ? Math.round(t.bpm) : '?'}
                    </td>
                    <td className="metric">
                      {t.distance_mi ? `${t.distance_mi} mi` : '?'}
                    </td>
                    <td className="metric">
                      {t.elevation_gain_ft ? `${t.elevation_gain_ft} ft` : '-'}
                    </td>
                    <td className="metric" style={{ color: ratioColor, fontWeight: ratio ? 600 : 400 }}>
                      {ratio ? ratio.toFixed(2) : '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
