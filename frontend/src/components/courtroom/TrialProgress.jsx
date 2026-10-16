import { TRIAL_STAGES } from '../../domain/courtroom.js'

export default function TrialProgress({ stage, furthest, onNavigate }) {
  const current = TRIAL_STAGES.findIndex((item) => item.id === stage)
  return (
    <nav className="trial-progress" aria-label="Trial progress">
      <ol>
        {TRIAL_STAGES.map((item, index) => (
          <li
            key={item.id}
            className={
              index === current
                ? 'is-current'
                : index < current
                  ? 'is-complete'
                  : ''
            }
          >
            <button
              type="button"
              disabled={index > furthest}
              aria-current={index === current ? 'step' : undefined}
              onClick={() => onNavigate(item.id)}
            >
              <span>
                {index < current ? '✓' : String(index + 1).padStart(2, '0')}
              </span>
              {item.label}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
