import BroadcastIcon from './BroadcastIcon.jsx'

export default function ReplayTransport({
  playing,
  speed,
  disabled,
  busy,
  onPlayPause,
  onRestart,
  onSpeed,
  onSkip,
}) {
  return (
    <div className="replay-transport" role="group" aria-label="Replay controls">
      <div className="transport-main">
        <button
          type="button"
          className="transport-icon"
          aria-label="Previous event"
          onClick={() => onSkip(-1)}
          disabled={disabled}
        >
          <BroadcastIcon name="previous" />
        </button>
        <button
          type="button"
          className="transport-play"
          onClick={onPlayPause}
          disabled={disabled}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          <BroadcastIcon name={playing ? 'pause' : 'play'} />
          <span>{playing ? 'Pause' : 'Play'}</span>
        </button>
        <button
          type="button"
          className="transport-icon"
          aria-label="Next event"
          onClick={() => onSkip(1)}
          disabled={disabled}
        >
          <BroadcastIcon name="next" />
        </button>
        <button
          type="button"
          className="transport-restart"
          onClick={onRestart}
          disabled={disabled}
        >
          <BroadcastIcon name="restart" />
          <span>Restart</span>
        </button>
      </div>
      <div className="transport-right">
        <span className="transport-status" role="status">
          {busy
            ? 'Syncing replay…'
            : playing
              ? 'Replay in progress'
              : 'Replay paused'}
        </span>
        <div
          className="transport-speeds"
          role="group"
          aria-label="Replay speed"
        >
          {[0.5, 1, 2].map((value) => (
            <button
              type="button"
              key={value}
              aria-pressed={speed === value}
              onClick={() => onSpeed(value)}
            >
              {value}x
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
