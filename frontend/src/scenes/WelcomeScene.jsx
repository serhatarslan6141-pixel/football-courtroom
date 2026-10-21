import { useMatchSession } from '../session/useMatchSession.js'
import BroadcastIcon from '../components/match/BroadcastIcon.jsx'
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
          <svg viewBox="0 0 520 560" fill="none">
            <rect width="520" height="560" fill="#1c2420" />
            <g fill="#233028"><path d="M40 40h88v480H40zm176 0h88v480h-88zm176 0h88v480h-88z" /></g>
            <g stroke="#a9b8a6" strokeWidth="1.2" opacity=".45">
              <path d="M40 40h440v480H40zM40 280h440M146 40v100h228V40M204 40v44h112V40M146 520V420h228v100M204 520v-44h112v44" />
              <circle cx="260" cy="280" r="66" />
              <path d="M207 140a60 60 0 0 0 106 0m-106 280a60 60 0 0 1 106 0" />
            </g>
            <path d="M93 386V235a167 167 0 0 1 334 0v151" stroke="#c9ad78" strokeWidth="2" />
            <path d="M79 401h362M67 414h386" stroke="#c9ad78" opacity=".6" />
            <circle cx="260" cy="269" r="107" fill="#1a211d" stroke="#c9ad78" />
            <circle cx="260" cy="269" r="96" stroke="#c9ad78" opacity=".28" />
            <g stroke="#e2cfaa" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M260 199v130m-33 7h66M199 237h122M260 214l-61 23m61-23 61 23M199 237l-28 51h56l-28-51zm122 0-28 51h56l-28-51z" />
              <path d="M171 288a28 19 0 0 0 56 0m66 0a28 19 0 0 0 56 0" />
            </g>
            <circle cx="260" cy="199" r="5" fill="#e2cfaa" />
            <path d="M40 40h25M40 40v25m440-25h-25m25 0v25M40 520h25m-25 0v-25m440 25h-25m25 0v-25" stroke="#d3b77b" strokeWidth="3" />
          </svg>
        </div>
      </div>
    </main>
  )
}
