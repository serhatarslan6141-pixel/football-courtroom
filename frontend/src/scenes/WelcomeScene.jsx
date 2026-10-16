import { useMatchSession } from '../session/useMatchSession.js'

export default function WelcomeScene() {
  const { goToMatch } = useMatchSession()
  return (
    <main className="welcome-shell">
      <div className="welcome-hero">
        <div className="hero-badge">Football Courtroom</div>
        <h1>Every Moment Has Two Sides</h1>
        <p>A cinematic sports experience built around the moments that shape a game.</p>
        <button type="button" className="hero-button" onClick={goToMatch}>Enter the match</button>
        <span className="simulated-pill">Simulated Match</span>
      </div>
    </main>
  )
}
