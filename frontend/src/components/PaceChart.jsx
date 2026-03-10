import { useState, useMemo } from 'react'
import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, ReferenceArea, ReferenceLine,
} from 'recharts'

const METRICS = {
  pace:  { label: 'Pace (min/mi)', color: '#4CAF50', key: 'pace', invert: true },
  hr:    { label: 'Heart Rate (bpm)', color: '#e53935', key: 'hr', invert: false },
  spm:   { label: 'Cadence (SPM)', color: '#1E88E5', key: 'spm', invert: false },
  bpm:   { label: 'Song BPM', color: '#FF9800', key: 'bpm', invert: false },
}

const BAND_COLORS = [
  'rgba(76, 175, 80, 0.07)',
  'rgba(33, 150, 243, 0.07)',
]

function fmtPace(val) {
  if (!val || val <= 0) return ''
  const m = Math.floor(val)
  const s = Math.round((val - m) * 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function fmtTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function PaceChart({ tracks, duration }) {
  const [activeMetrics, setActiveMetrics] = useState(['pace'])

  // Build a unified time-series dataset from all tracks
  const { chartData, songBands } = useMemo(() => {
    const points = []
    const bands = []

    tracks.forEach((t, idx) => {
      bands.push({
        x1: t.offset_start_s,
        x2: t.offset_end_s,
        label: t.track,
        artist: t.artist,
        color: BAND_COLORS[idx % 2],
        bpm: t.bpm,
      })

      // Use per-point series data if available, otherwise use averages
      const timeArr = t.time_series || []
      const paceArr = t.pace_series || []
      const hrArr = t.hr_series || []
      const spmArr = t.spm_series || []

      if (timeArr.length > 0) {
        timeArr.forEach((time, i) => {
          points.push({
            time,
            pace: paceArr[i] || null,
            hr: i < hrArr.length ? (hrArr[i] || null) : null,
            spm: i < spmArr.length ? (spmArr[i] || null) : null,
            bpm: t.bpm || null,
            songIdx: idx,
          })
        })
      } else {
        // Fallback: single point per song at midpoint
        const mid = (t.offset_start_s + t.offset_end_s) / 2
        points.push({
          time: mid,
          pace: t.avg_speed_min_per_mile || null,
          hr: t.avg_hr || null,
          spm: t.avg_spm || null,
          bpm: t.bpm || null,
          songIdx: idx,
        })
      }
    })

    points.sort((a, b) => a.time - b.time)
    return { chartData: points, songBands: bands }
  }, [tracks])

  if (!chartData.length) return null

  const toggleMetric = (key) => {
    setActiveMetrics(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    )
  }

  // Determine Y domain for active metrics
  const hasInverted = activeMetrics.some(k => METRICS[k]?.invert)

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    const songIdx = payload[0]?.payload?.songIdx
    const song = songIdx != null ? tracks[songIdx] : null

    return (
      <div style={{
        background: '#fff', border: '1px solid #e0e0e0', borderRadius: 8,
        padding: '0.6rem 0.8rem', fontSize: '0.8rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
      }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{fmtTime(label)}</div>
        {song && (
          <div style={{ color: '#888', marginBottom: 4, fontSize: '0.75rem' }}>
            {song.track} — {song.artist}
          </div>
        )}
        {payload.map((p, i) => {
          const metric = Object.values(METRICS).find(m => m.key === p.dataKey)
          const val = p.dataKey === 'pace' ? fmtPace(p.value) :
                      p.value != null ? Math.round(p.value) : '?'
          return (
            <div key={i} style={{ color: p.color }}>
              {metric?.label || p.dataKey}: <strong>{val}</strong>
              {p.dataKey === 'pace' && ' /mi'}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="card" style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#333' }}>
          Activity Chart
        </h3>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {Object.entries(METRICS).map(([key, m]) => (
            <button
              key={key}
              onClick={() => toggleMetric(key)}
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.72rem',
                fontWeight: 600,
                border: `2px solid ${m.color}`,
                borderRadius: 6,
                cursor: 'pointer',
                background: activeMetrics.includes(key) ? m.color : '#fff',
                color: activeMetrics.includes(key) ? '#fff' : m.color,
                transition: 'all 0.15s',
              }}
            >
              {m.label.split(' (')[0]}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />

          {/* Song background bands */}
          {songBands.map((band, i) => (
            <ReferenceArea
              key={i}
              x1={band.x1}
              x2={band.x2}
              fill={band.color}
              fillOpacity={1}
            />
          ))}

          {/* Song divider lines */}
          {songBands.slice(1).map((band, i) => (
            <ReferenceLine
              key={`div-${i}`}
              x={band.x1}
              stroke="#ddd"
              strokeDasharray="3 3"
            />
          ))}

          <XAxis
            dataKey="time"
            tickFormatter={fmtTime}
            tick={{ fontSize: 11, fill: '#999' }}
            axisLine={{ stroke: '#e0e0e0' }}
            tickLine={false}
          />

          {activeMetrics.map((key, i) => {
            const m = METRICS[key]
            return (
              <YAxis
                key={key}
                yAxisId={key}
                orientation={i === 0 ? 'left' : 'right'}
                reversed={m.invert}
                tick={{ fontSize: 11, fill: m.color }}
                axisLine={{ stroke: m.color }}
                tickLine={false}
                tickFormatter={key === 'pace' ? fmtPace : undefined}
                label={i < 2 ? {
                  value: m.label,
                  angle: -90,
                  position: i === 0 ? 'insideLeft' : 'insideRight',
                  style: { fill: m.color, fontSize: 11 },
                  offset: i === 0 ? 10 : -10,
                } : undefined}
                width={50}
                hide={i >= 2}
              />
            )
          })}

          <Tooltip content={<CustomTooltip />} />

          {activeMetrics.map(key => {
            const m = METRICS[key]
            return (
              <Line
                key={key}
                yAxisId={key}
                type="monotone"
                dataKey={m.key}
                stroke={m.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
                connectNulls
              />
            )
          })}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Song legend below chart */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.75rem',
        paddingTop: '0.5rem', borderTop: '1px solid #f0f0f0',
      }}>
        {songBands.map((band, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: '0.3rem',
            fontSize: '0.7rem', color: '#666', padding: '0.15rem 0.4rem',
            background: '#f7f8fa', borderRadius: 4,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: 2,
              background: i % 2 === 0 ? '#4CAF50' : '#2196F3',
              opacity: 0.4, flexShrink: 0,
            }} />
            <span style={{ fontWeight: 500, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {band.label}
            </span>
            {band.bpm && (
              <span style={{ color: '#999' }}>({Math.round(band.bpm)} BPM)</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
