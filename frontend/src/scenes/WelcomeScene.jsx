import { useMatchSession } from '../session/useMatchSession.js'
import BroadcastIcon from '../components/match/BroadcastIcon.jsx'
import WelcomeIllustration from '../components/WelcomeIllustration.jsx'
import './WelcomeScene.css'

export default function WelcomeScene() {
  const { goToMatch } = useMatchSession()
  return (
    <main className="welcome-shell" id="main-content" tabIndex={-1}>
      <header className="welcome-masthead">
        <div className="brand"><span className="brand-mark" aria-hidden="true">FC</span><span>Football Courtroom</span></div>
      </header>
      <div className="welcome-composition">
        <div className="welcome-copy">
          <h1 aria-label="Every Moment Has Two Sides"><span>Every Moment</span><span>Has <em>Two Sides.</em></span></h1>
          <p className="welcome-description">Follow the match. Examine its defining moments. Hear both sides, then make your call.</p>
          <button type="button" className="hero-button" onClick={goToMatch}>Enter the match <BroadcastIcon name="arrow" /></button>
        </div>
        <div className="welcome-exhibit" aria-hidden="true">
          <WelcomeIllustration />
        </div>
      </div>
    </main>
  )
}
