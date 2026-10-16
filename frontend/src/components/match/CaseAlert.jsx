import { getCaseDisplayTitle } from '../../domain/formatters.js'
import BroadcastIcon from './BroadcastIcon.jsx'

export default function CaseAlert({ caseItem, match, onOpen }) {
  if (!caseItem) return null
  return (
    <div className="broadcast-case-alert" aria-live="polite">
      <button type="button" onClick={() => onOpen(caseItem)}>
        <span className="case-alert-icon">
          <BroadcastIcon name="court" size={22} />
        </span>
        <span>
          <small>NEW CASE · THE COURT IS OPEN</small>
          <strong>{getCaseDisplayTitle(caseItem, match)}</strong>
        </span>
        <BroadcastIcon name="arrow" />
      </button>
    </div>
  )
}
