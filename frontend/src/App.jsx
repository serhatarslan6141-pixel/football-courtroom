import './App.css'
import WelcomeScene from './scenes/WelcomeScene.jsx'
import MatchScene from './scenes/MatchScene.jsx'
import CourtroomScene from './scenes/CourtroomScene.jsx'
import { MatchSessionProvider } from './session/MatchSessionProvider.jsx'
import { useMatchSession } from './session/useMatchSession.js'

function AppScenes() {
  const { screen, goToWelcome, goToMatch } = useMatchSession()
  return (
    <div
      className={`app-shell${screen === 'match' ? ' match-shell' : screen === 'courtroom' ? ' court-shell' : ''}`}
    >
      {screen !== 'welcome' ? (
        <header className="topbar">
          <button
            type="button"
            className="brand button-brand"
            onClick={goToWelcome}
          >
            <span className="brand-mark">FC</span>
            <span>Football Courtroom</span>
          </button>

          {screen === 'match' ? (
            <div className="broadcast-header-actions">
              <span className="broadcast-simulated">Simulated Match</span>
              <button type="button" onClick={goToWelcome}>
                Exit to welcome ↗
              </button>
            </div>
          ) : (
            <div className="court-header-actions">
              <span className="court-session-label">
                A CASE IS BEFORE THE COURT
              </span>
              <button type="button" className="court-text" onClick={goToMatch}>
                Return to match <span aria-hidden="true">↗</span>
              </button>
            </div>
          )}
        </header>
      ) : null}

      {screen === 'welcome' ? <WelcomeScene /> : null}

      {screen === 'match' ? <MatchScene /> : null}
      {screen === 'courtroom' ? <CourtroomScene /> : null}
    </div>
  )
}

export default function App({ api }) {
  return (
    <MatchSessionProvider api={api}>
      <AppScenes />
    </MatchSessionProvider>
  )
}
