import { useEffect, useRef } from 'react'

export default function TrialConfirmation({ onConfirm, onCancel, returnFocus }) {
  const dialog = useRef(null)
  const cancelButton = useRef(null)
  useEffect(() => {
    const element = dialog.current
    const previous = returnFocus.current
    element.showModal()
    cancelButton.current.focus()
    return () => {
      element.close()
      if (previous?.isConnected) previous.focus({ preventScroll: true })
    }
  }, [returnFocus])
  return <dialog ref={dialog} className="trial-confirmation" aria-labelledby="confirmation-title"
    aria-describedby="confirmation-charge" onCancel={(event) => { event.preventDefault(); onCancel() }}>
    <span className="trial-overline">THE COURT IS READY TO CONVENE</span>
    <h2 id="confirmation-title">Begin the four-agent trial?</h2>
    <p id="confirmation-charge">This case is not cached. Generating its analysis may incur a small Azure API charge,
      using up to four model requests. Nothing is generated until you confirm.</p>
    <p>The agents will examine only this case’s verified match facts. Your vote remains your own, and the ruling stays sealed until you vote.</p>
    <div>
      <button ref={cancelButton} type="button" className="court-text" onClick={onCancel}>Cancel</button>
      <button type="button" className="court-primary" onClick={onConfirm}>Confirm &amp; begin trial</button>
    </div>
  </dialog>
}
