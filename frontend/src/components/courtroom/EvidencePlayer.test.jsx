import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import EvidencePlayer from './EvidencePlayer.jsx'
import { matches } from '../../test/fixtures.js'

it('shows unavailable recorded shot and pass outcomes as N/A rather than zero', () => {
  const trial = {
    bounds: { start: 0, end: 10 },
    incidentTimestamp: 5,
    knownEvents: [
      {
        event_id: 'pass',
        event_type: 'pass',
        timestamp: 1,
        team_id: 'home',
        x: 60,
        y: 50,
      },
      {
        event_id: 'shot',
        event_type: 'shot',
        timestamp: 5,
        team_id: 'home',
        x: 80,
        y: 50,
      },
    ],
  }
  render(
    <EvidencePlayer
      trial={trial}
      match={matches[0]}
      timestamp={5}
      onSeek={() => {}}
    />,
  )
  const observations = screen.getByLabelText(
    'Observed in this clip',
  ).textContent
  expect(observations).toContain('1 shots')
  expect(observations).toContain('N/A on target')
  expect(observations).toContain('N/A completed passes')
})
