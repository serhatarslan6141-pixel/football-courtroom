import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from '../App.jsx'
import { aiCase, aiTrialResponse, AI_COPY } from '../test/aiTrialFixture.js'
import { deferred, events, matches, snapshot } from '../test/fixtures.js'

function makeApi(result = aiTrialResponse()) {
  return {
    listMatches: vi.fn(async () => ({ matches })),
    loadMatch: vi.fn(async (id) => ({ matchData: matches.find((match) => match.match_id === id), events })),
    loadSnapshot: vi.fn(async (id, time) => ({ ...snapshot(time, id), cases: time >= 10 ? [{ ...aiCase,
      match_id: id, case_id: id === 'a' ? aiCase.case_id : `case-${id}` }] : [] })),
    generateAiTrial: vi.fn(async () => result),
  }
}
async function openTrial(api = makeApi(), { strict = false, timestamp = 15 } = {}) {
  render(strict ? <StrictMode><App api={api} /></StrictMode> : <App api={api} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Enter the match' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enter replay', exact: true }).disabled).toBe(false))
  await user.click(screen.getByRole('button', { name: 'Enter replay', exact: true }))
  fireEvent.change(screen.getByRole('slider', { name: 'Seek match replay' }), { target: { value: String(timestamp) } })
  await waitFor(() => expect(screen.getByLabelText('Match clock').textContent).toBe(`00:${timestamp}`))
  await user.click(screen.getByRole('tab', { name: /Cases/ }))
  await user.click(screen.getByRole('button', { name: /Open case/ }))
  return { api, user }
}
async function generate(user) {
  await user.click(screen.getByRole('button', { name: 'Generate AI Trial' }))
  await screen.findByText(/^(Live AI trial|Cached AI trial)$/)
}
async function evidenceStage(user) {
  await user.click(screen.getByRole('button', { name: 'Begin trial' }))
}
async function voteStage(user) {
  await evidenceStage(user)
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  await user.click(screen.getByRole('button', { name: 'Make your call' }))
}

it('never generates on navigation or StrictMode rerenders, and prevents rapid duplicate clicks', async () => {
  const pending = deferred(), api = makeApi()
  api.generateAiTrial.mockReturnValue(pending.promise)
  const { user } = await openTrial(api, { strict: true })
  expect(api.generateAiTrial).not.toHaveBeenCalled()
  const button = screen.getByRole('button', { name: 'Generate AI Trial' })
  act(() => { fireEvent.click(button); fireEvent.click(button); fireEvent.click(button) })
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
  expect(api.generateAiTrial).toHaveBeenCalledWith('a', 'case-a', 15)
  expect(screen.getByText(/Individual agent progress is not streamed/)).toBeTruthy()
  expect(screen.queryByText('Submission validated')).toBeNull()
  await evidenceStage(user)
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
  await act(async () => pending.resolve(aiTrialResponse()))
  expect(screen.getByText('Live AI trial')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'AI trial ready' }).disabled).toBe(true)
  expect(screen.queryByText(AI_COPY.judge)).toBeNull()
})

it.each(['live_ai', 'cached_ai'])('presents %s evidence and opposing arguments with real trace information', async (source) => {
  const { user } = await openTrial(makeApi(aiTrialResponse(source)))
  await generate(user)
  expect(screen.getByText(source === 'cached_ai' ? 'Cached AI trial' : 'Live AI trial')).toBeTruthy()
  await user.click(screen.getByText('How the AI reached this decision'))
  const trace = document.querySelector('.agent-trace')
  expect(within(trace).getAllByText('Submission validated')).toHaveLength(4)
  expect(within(trace).getByText('Handed to Defense')).toBeTruthy()
  expect(trace.textContent).toContain(source === 'cached_ai' ? '0 model attempts' : '4 model attempts')
  await evidenceStage(user)
  expect(screen.getByText(AI_COPY.evidence)).toBeTruthy()
  expect(screen.getByLabelText('Verified case evidence').textContent).toContain('Alpha: goals')
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  expect(screen.getByRole('heading', { name: AI_COPY.prosecution })).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Hear the defense' }))
  expect(screen.getByRole('heading', { name: AI_COPY.defense })).toBeTruthy()
})

it('keeps the AI ruling sealed until a separate, independent user vote', async () => {
  const { user, api } = await openTrial()
  await generate(user)
  await voteStage(user)
  expect(screen.queryByText('PROSECUTION SUPPORTED')).toBeNull()
  expect(screen.queryByText(AI_COPY.judge)).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Agree with the defense', exact: true }))
  expect(screen.queryByText(AI_COPY.judge)).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Record my vote & hear the ruling' }))
  expect(screen.getByText('PROSECUTION SUPPORTED')).toBeTruthy()
  expect(screen.getByText(AI_COPY.judge)).toBeTruthy()
  expect(within(document.querySelector('.recorded-vote')).getByText('Agree with the defense')).toBeTruthy()
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('seeks a cited moment inside the case window and preserves the original replay position', async () => {
  const { user, api } = await openTrial()
  await generate(user)
  await evidenceStage(user)
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  const snapshots = api.loadSnapshot.mock.calls.length
  await user.click(screen.getByRole('button', { name: 'Review cited goal at 00:10' }))
  expect(screen.getByRole('slider', { name: 'Seek evidence replay' }).value).toBe('10')
  expect(screen.getByText('Cited moment selected · 00:10')).toBeTruthy()
  expect(api.loadSnapshot).toHaveBeenCalledTimes(snapshots)
  await user.click(screen.getByRole('button', { name: 'Return to match', exact: true }))
  expect(screen.getByLabelText('Match clock').textContent).toBe('00:15')
  expect(screen.getByRole('button', { name: 'Play', exact: true })).toBeTruthy()
  await user.click(screen.getByRole('tab', { name: /Cases/ }))
  await user.click(screen.getByRole('button', { name: /Open case/ }))
  expect(screen.getByText('Live AI trial')).toBeTruthy()
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('reports backend fallback honestly and keeps the entire deterministic trial usable', async () => {
  const { user, api } = await openTrial(makeApi(aiTrialResponse('deterministic_fallback')))
  await user.click(screen.getByRole('button', { name: 'Generate AI Trial' }))
  await screen.findByText('Recorded-evidence fallback')
  expect(screen.getByText(/AI is switched off/)).toBeTruthy()
  expect(screen.queryByText('Live AI trial')).toBeNull()
  await voteStage(user)
  expect(screen.getByRole('heading', { name: /Where do you stand/ })).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Not enough evidence', exact: true }))
  await user.click(screen.getByRole('button', { name: 'Record my vote & hear the ruling' }))
  expect(screen.getByText('INCONCLUSIVE')).toBeTruthy()
  expect(screen.getByText(/No AI judge has evaluated this case/)).toBeTruthy()
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it.each(['network', 'future', 'wrong_case'])('uses recorded evidence after %s failure without retries or leaking error text', async (kind) => {
  const response = aiTrialResponse(), api = makeApi(response)
  if (kind === 'network') api.generateAiTrial.mockRejectedValue(new Error('private-provider-body-and-token'))
  if (kind === 'future') response.prosecution.points[0].event_ids.push('later')
  if (kind === 'wrong_case') response.evidence.case_id = 'another-case'
  const { user } = await openTrial(api)
  await user.click(screen.getByRole('button', { name: 'Generate AI Trial' }))
  expect((await screen.findByRole('alert')).textContent).toContain('could not be confirmed or verified')
  expect(document.body.textContent).not.toContain('private-provider-body-and-token')
  expect(screen.queryByText(AI_COPY.prosecution)).toBeNull()
  await evidenceStage(user)
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  expect(screen.getByRole('heading', { name: 'Attacking evidence' })).toBeTruthy()
  expect(screen.queryByRole('button', { name: /cited.*00:20/ })).toBeNull()
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('does not attach a late response to another match and never regenerates on return', async () => {
  const api = makeApi(), pending = deferred()
  api.generateAiTrial.mockReturnValue(pending.promise)
  const { user } = await openTrial(api)
  await user.click(screen.getByRole('button', { name: 'Generate AI Trial' }))
  await user.click(screen.getByRole('button', { name: 'Return to match', exact: true }))
  await user.click(screen.getByRole('button', { name: /Change fixture/ }))
  await user.click(screen.getByRole('button', { name: 'Select Gamma vs Delta' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enter replay', exact: true }).disabled).toBe(false))
  await user.click(screen.getByRole('button', { name: 'Enter replay', exact: true }))
  fireEvent.change(screen.getByRole('slider', { name: 'Seek match replay' }), { target: { value: '15' } })
  await waitFor(() => expect(screen.getByLabelText('Match clock').textContent).toBe('00:15'))
  await user.click(screen.getByRole('tab', { name: /Cases/ }))
  await user.click(screen.getByRole('button', { name: /Open case/ }))
  await act(async () => pending.resolve(aiTrialResponse()))
  expect(screen.queryByText('Live AI trial')).toBeNull()
  expect(screen.getByRole('button', { name: 'Generate AI Trial' }).disabled).toBe(false)
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('keeps a previously recorded vote when AI arrives afterwards', async () => {
  const { user } = await openTrial()
  await voteStage(user)
  await user.click(screen.getByRole('button', { name: 'Agree with the defense', exact: true }))
  await user.click(screen.getByRole('button', { name: 'Record my vote & hear the ruling' }))
  await generate(user)
  expect(screen.getByText('PROSECUTION SUPPORTED')).toBeTruthy()
  expect(within(document.querySelector('.recorded-vote')).getByText('Agree with the defense')).toBeTruthy()
})

it('supports keyboard generation and citation review', async () => {
  const { user, api } = await openTrial()
  screen.getByRole('button', { name: 'Generate AI Trial' }).focus()
  await user.keyboard('{Enter}')
  await screen.findByText('Live AI trial')
  await evidenceStage(user)
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  screen.getByRole('button', { name: 'Review cited goal at 00:10' }).focus()
  await user.keyboard('{Enter}')
  expect(screen.getByRole('slider', { name: 'Seek evidence replay' }).value).toBe('10')
  expect(document.activeElement.getAttribute('aria-label')).toBe('Evidence')
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('shows actual partial handoffs and withheld output in recorded fallback', async () => {
  const result = aiTrialResponse('deterministic_fallback')
  result.error_category = 'invalid_agent_output'
  result.api_attempts = result.original_api_attempts = 2
  result.trace = [aiTrialResponse().trace[0], {
    agent: 'prosecution', status: 'failed', handoff_to: null,
    input_digest: 'a'.repeat(64), output_digest: null, error_category: 'invalid_agent_output',
  }]
  const { user } = await openTrial(makeApi(result))
  await user.click(screen.getByRole('button', { name: 'Generate AI Trial' }))
  await screen.findByText('Recorded-evidence fallback')
  await user.click(screen.getByText('How the AI reached this decision'))
  const trace = document.querySelector('.agent-trace')
  expect(within(trace).getAllByText('Submission validated')).toHaveLength(1)
  expect(within(trace).getByText('Stopped; submission withheld')).toBeTruthy()
  await user.click(within(trace).getByText('Inspect Prosecution handoff'))
  expect(within(trace).getByText('Withheld')).toBeTruthy()
  expect(screen.queryByText(AI_COPY.prosecution)).toBeNull()
})
