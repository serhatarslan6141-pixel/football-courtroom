import './App.css'
import WelcomeScene from './scenes/WelcomeScene.jsx'
import MatchScene from './scenes/MatchScene.jsx'
import CourtroomScene from './scenes/CourtroomScene.jsx'
import { MatchSessionProvider } from './session/MatchSessionProvider.jsx'
import { useMatchSession } from './session/useMatchSession.js'

function AppScenes() {
  const { screen, selectedCase, goToWelcome, goToMatch, openCourtroom } =
    useMatchSession()
  return (
    <div className={screen === 'match' ? 'app-shell match-shell' : 'app-shell'}>
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
            <div className="header-actions">
              <button
                type="button"
                className="secondary-btn small"
                onClick={goToWelcome}
              >
                Welcome
              </button>
              <button
                type="button"
                className="secondary-btn small"
                onClick={goToMatch}
              >
                Match centre
              </button>
              {selectedCase ? (
                <button
                  type="button"
                  className="secondary-btn small"
                  onClick={() => openCourtroom(selectedCase)}
                >
                  Case room
                </button>
              ) : null}
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
