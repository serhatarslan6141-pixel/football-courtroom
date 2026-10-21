import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from '../App.jsx'

const root = resolve(process.cwd(), '..')
const python = `${root}/.venv/phase4b/bin/python`
// The framework integration requires the documented Python 3.12 environment.
// Standalone frontend installations still run their ordinary mocked UI tests.
const fixture = existsSync(python) ? JSON.parse(execFileSync(python,
  [`${root}/backend/tests/export_courtroom.py`], {
    env: { ...process.env, PYTHONPATH: `${root}/backend` },
    maxBuffer: 32 * 1024 * 1024,
  }).toString()) : null

describe.skipIf(!fixture)('real framework → FastAPI → cinematic courtroom (no sockets)', () => {
  it.each(['live', 'cached', 'fallback'])('renders %s results through the five stages and preserves replay and voting', async (mode) => {
    const response = fixture[mode]
    const api = {
      listMatches: vi.fn(async () => ({ matches: [fixture.match] })),
      loadMatch: vi.fn(async () => ({ matchData: fixture.match, events: fixture.events })),
      loadSnapshot: vi.fn(async (_id, timestamp) => fixture.snapshots[String(timestamp)]),
      prepareTrial: vi.fn(async () => mode === 'cached'
        ? { status: 'ready', result: response } : fixture.preparation),
      generateAiTrial: vi.fn(async () => response),
    }
    render(<StrictMode><App api={api} /></StrictMode>)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Enter the match' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enter replay', exact: true }).disabled).toBe(false))
    await user.click(screen.getByRole('button', { name: 'Enter replay', exact: true }))
    fireEvent.change(screen.getByRole('slider', { name: 'Seek match replay' }), { target: { value: String(fixture.cutoff) } })
    await waitFor(() => expect(screen.getByLabelText('Match clock').textContent).toBe('41:42'))
    await user.click(screen.getByRole('tab', { name: /Cases/ }))
    await user.click(screen.getByRole('button', { name: /41:42.*Open case/s }))
    expect(api.prepareTrial).not.toHaveBeenCalled()
    expect(api.generateAiTrial).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Begin trial' }))
    if (mode !== 'cached') {
      await user.click(await screen.findByRole('button', { name: 'Confirm & begin trial' }))
    }
    await screen.findByRole('slider', { name: 'Seek evidence replay' })
    expect(screen.getByText(mode === 'live' ? 'Live AI analysis' : mode === 'cached' ? 'Cached AI analysis' : 'Deterministic fallback')).toBeTruthy()
    expect(api.generateAiTrial).toHaveBeenCalledTimes(mode === 'cached' ? 0 : 1)
    expect(document.querySelectorAll('.court-room')).toHaveLength(1)
    if (mode !== 'fallback') {
      expect(screen.getByText(response.evidence_agent.interpretation.interpretation)).toBeTruthy()
      expect(screen.getByLabelText('Verified case evidence').textContent).toContain(response.evidence_agent.observations[0].value)
    } else {
      expect(within(document.querySelector('.trial-status')).getByText(/An AI submission could not be verified/)).toBeTruthy()
      expect(screen.queryByText(fixture.live.prosecution.points[0].interpretation)).toBeNull()
    }
    await user.click(screen.getByText('Behind the verdict'))
    const trace = document.querySelector('.agent-trace')
    expect(within(trace).getAllByText('Submission validated')).toHaveLength(mode === 'fallback' ? 2 : 4)
    if (mode !== 'fallback') {
      expect(within(trace).getByText('Ruling and its evidence references sealed until your vote.')).toBeTruthy()
      const citation = within(trace).getAllByRole('button', { name: /Review cited/ })[0]
      await user.click(citation)
      const replay = screen.getByRole('slider', { name: 'Seek evidence replay' })
      expect(Number(replay.value)).toBeGreaterThanOrEqual(response.evidence.evidence_start)
      expect(Number(replay.value)).toBeLessThanOrEqual(response.evidence.evidence_cutoff)
    } else {
      expect(within(trace).getByText('Stopped; submission withheld')).toBeTruthy()
    }
    await user.click(screen.getByText('Behind the verdict'))
    await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
    if (mode !== 'fallback') expect(screen.getByRole('heading', { name: response.prosecution.points[0].interpretation })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Hear the defense' }))
    if (mode !== 'fallback') expect(screen.getByRole('heading', { name: response.defense.points[0].interpretation })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Make your call' }))
    expect(screen.queryByText(response.judge.findings[0].interpretation)).toBeNull()
    expect(screen.getByRole('button', { name: /The ruling/ }).disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Agree with the defense', exact: true }))
    await user.click(screen.getByRole('button', { name: 'Record my vote & hear the ruling' }))
    expect(screen.getByText(mode === 'fallback' ? 'INCONCLUSIVE' : 'PROSECUTION SUPPORTED')).toBeTruthy()
    expect(within(document.querySelector('.recorded-vote')).getByText('Agree with the defense')).toBeTruthy()
    if (mode !== 'fallback') expect(screen.getByText(response.judge.findings[0].interpretation)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Back to the replay/ }))
    await waitFor(() => expect(screen.getByLabelText('Match clock').textContent).toBe('41:42'))
    expect(api.prepareTrial).toHaveBeenCalledTimes(1)
    expect(api.generateAiTrial).toHaveBeenCalledTimes(mode === 'cached' ? 0 : 1)
  }, 15000)
})
