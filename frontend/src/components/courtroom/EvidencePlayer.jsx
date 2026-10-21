import { useEffect, useMemo, useRef, useState } from 'react'
import PitchStage from '../match/PitchStage.jsx'
import EventCaption from '../match/EventCaption.jsx'
import Scorebug from '../match/Scorebug.jsx'
import BroadcastIcon from '../match/BroadcastIcon.jsx'
import { replayVisual } from '../../domain/replayVisual.js'
import { formatClock } from '../../domain/formatters.js'
import { scoreAt } from '../../domain/courtroom.js'

function useEvidencePlayback(timestamp, end, onSeek) {
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const cursor = useRef(timestamp)
  const seek = useRef(onSeek)
  useEffect(() => {
    cursor.current = timestamp
    seek.current = onSeek
  }, [timestamp, onSeek])
  useEffect(() => {
    if (!playing) return
    let frame,
      previous = null
    const advance = (now) => {
      if (previous === null) previous = now
      if (now - previous >= 30) {
        const next = Math.min(
          end,
          cursor.current + Math.min((now - previous) / 1000, 0.25) * speed,
        )
        cursor.current = next
        seek.current(next)
        previous = now
        if (next >= end) {
          setPlaying(false)
          return
        }
      }
      frame = window.requestAnimationFrame(advance)
    }
    frame = window.requestAnimationFrame(advance)
    return () => window.cancelAnimationFrame(frame)
  }, [playing, end, speed])
  return { playing, setPlaying, speed, setSpeed }
}

export default function EvidencePlayer({ trial, match, timestamp, onSeek, citedEventId }) {
  const clips = useMemo(() => {
    const { start, end } = trial.bounds
    const incident = trial.incidentTimestamp
    return [
      { id: 'buildup', label: 'Build-up', start, end: Math.min(end, incident) },
      {
        id: 'incident',
        label: 'The incident',
        start: Math.max(start, incident - 6),
        end: Math.min(end, incident + 12),
      },
      {
        id: 'aftermath',
        label: 'Aftermath',
        start: Math.max(start, incident),
        end,
      },
    ].filter((clip) => clip.end > clip.start)
  }, [trial.bounds, trial.incidentTimestamp])
  const [clipId, setClipId] = useState(() => {
    const incident = clips.find((item) => item.id === 'incident')
    return incident && timestamp >= incident.start && timestamp <= incident.end
      ? 'incident'
      : timestamp < (incident?.start ?? trial.incidentTimestamp)
        ? 'buildup'
        : 'aftermath'
  })
  const clip =
    clips.find((item) => item.id === clipId) || clips[0] || trial.bounds
  const playback = useEvidencePlayback(timestamp, clip.end, onSeek)
  const seekTo = (value) => {
    playback.setPlaying(false)
    onSeek(Math.max(clip.start, Math.min(value, clip.end)))
  }
  const current = replayVisual(trial.knownEvents, timestamp).event
  const completed = trial.knownEvents.filter(
    (event) => event.timestamp >= clip.start && event.timestamp <= timestamp,
  )
  const shots = completed.filter((event) => event.event_type === 'shot')
  const onTarget = shots.some(
    (event) => typeof event.metadata?.on_target !== 'boolean',
  )
    ? null
    : shots.filter((event) => event.metadata.on_target).length
  const passes = completed.filter((event) =>
    ['pass', 'cross'].includes(event.event_type),
  )
  const completedPasses = passes.some(
    (event) => !['complete', 'incomplete'].includes(event.metadata?.outcome),
  )
    ? null
    : passes.filter((event) => event.metadata.outcome === 'complete').length

  return (
    <section className="court-evidence" aria-label="Incident evidence replay">
      {citedEventId && <p className="citation-focus" role="status">Cited moment selected · {formatClock(trial.knownEvents.find((event) => event.event_id === citedEventId)?.timestamp ?? timestamp)}</p>}
      <div className="evidence-title-row">
        <span className="trial-overline">Match evidence</span>
        <span>Recorded through {formatClock(trial.bounds.end)}</span>
      </div>
      <div
        className="evidence-clip-tabs"
        role="group"
        aria-label="Evidence context"
      >
        {clips.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={item.id === clip.id}
            onClick={() => {
              playback.setPlaying(false)
              setClipId(item.id)
              onSeek(item.start)
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="court-evidence-screen">
        <Scorebug
          match={match}
          state={{ score: scoreAt(trial.knownEvents, timestamp) }}
          timestamp={timestamp}
        />
        <PitchStage
          events={trial.knownEvents}
          event={current}
          timestamp={timestamp}
          match={match}
        />
      </div>
      <EventCaption event={current} match={match} timestamp={timestamp} />
      <div className="evidence-transport">
        <button
          type="button"
          aria-label={playback.playing ? 'Pause evidence' : 'Play evidence'}
          onClick={() => {
            if (!playback.playing && timestamp >= clip.end) onSeek(clip.start)
            playback.setPlaying((value) => !value)
          }}
        >
          <BroadcastIcon name={playback.playing ? 'pause' : 'play'} />
        </button>
        <button
          type="button"
          aria-label="Restart evidence clip"
          onClick={() => seekTo(clip.start)}
        >
          <BroadcastIcon name="restart" size={15} />
        </button>
        <time>{formatClock(timestamp)}</time>
        <input
          type="range"
          aria-label="Seek evidence replay"
          aria-valuetext={formatClock(timestamp)}
          min={clip.start}
          max={clip.end}
          step="0.1"
          value={Math.max(clip.start, Math.min(timestamp, clip.end))}
          onChange={(event) => seekTo(Number(event.target.value))}
        />
        <time>{formatClock(clip.end)}</time>
        <button
          type="button"
          className="evidence-speed"
          aria-label={`Evidence speed ${playback.speed}x`}
          onClick={() => playback.setSpeed((speed) => (speed === 1 ? 0.5 : 1))}
        >
          {playback.speed}x
        </button>
      </div>
      <div className="evidence-observations" aria-label="Observed in this clip">
        <span>
          <b>{shots.length}</b> shots
        </span>
        <span>
          <b>{onTarget ?? 'N/A'}</b> on target
        </span>
        <span>
          <b>{completedPasses ?? 'N/A'}</b> completed passes
        </span>
        <small>Through {formatClock(timestamp)} · in this clip</small>
      </div>
    </section>
  )
}
