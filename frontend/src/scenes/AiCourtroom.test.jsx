import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from '../App.jsx'
import { aiCase, aiTrialResponse, AI_COPY } from '../test/aiTrialFixture.js'
import { deferred, events, matches, snapshot } from '../test/fixtures.js'

function makeApi(mode = 'live_ai') {
  return {
    listMatches: vi.fn(async () => ({ matches })),
    loadMatch: vi.fn(async (id) => ({ matchData: matches.find((match) => match.match_id === id), events })),
    loadSnapshot: vi.fn(async (id, time) => ({ ...snapshot(time, id), cases: time >= 10 ? [{ ...aiCase,
      match_id: id, case_id: id === 'a' ? aiCase.case_id : `case-${id}` }] : [] })),
    prepareTrial: vi.fn(async () => mode === 'live_ai' ? { status: 'confirmation_required', result: null }
      : { status: 'ready', result: aiTrialResponse(mode) }),
    generateAiTrial: vi.fn(async () => aiTrialResponse()),
  }
}
async function openTrial(api = makeApi(), strict = false) {
  render(strict ? <StrictMode><App api={api} /></StrictMode> : <App api={api} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Enter the match' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enter replay', exact: true }).disabled).toBe(false))
  await user.click(screen.getByRole('button', { name: 'Enter replay', exact: true }))
  fireEvent.change(screen.getByRole('slider', { name: 'Seek match replay' }), { target: { value: '15' } })
  await waitFor(() => expect(screen.getByLabelText('Match clock').textContent).toBe('00:15'))
  await user.click(screen.getByRole('tab', { name: /Cases/ }))
  await user.click(screen.getByRole('button', { name: /Open case/ }))
  return { api, user }
}
async function begin(user, confirm = true) {
  await user.click(screen.getByRole('button', { name: 'Begin trial' }))
  if (confirm) await user.click(await screen.findByRole('button', { name: 'Confirm & begin trial' }))
  await screen.findByRole('slider', { name: 'Seek evidence replay' })
}
async function voteStage(user) {
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  await user.click(screen.getByRole('button', { name: 'Make your call' }))
}
async function voteDefense(user) {
  await user.click(screen.getByRole('button', { name: 'Agree with the defense', exact: true }))
  await user.click(screen.getByRole('button', { name: 'Record my vote & hear the ruling' }))
}

it('has only Begin trial, with no requests from opening or StrictMode rerenders', async () => {
  const { api } = await openTrial(makeApi(), true)
  const room = document.querySelector('.court-room')
  expect(within(room).getByRole('button', { name: 'Begin trial' }).className).toBe('court-primary')
  expect(document.querySelectorAll('.court-room')).toHaveLength(1)
  expect(screen.queryByRole('button', { name: 'Generate AI Trial' })).toBeNull()
  expect(screen.queryByText('Recorded evidence', { exact: true })).toBeNull()
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.getByText('Behind the verdict').closest('details').open).toBe(false)
  expect(api.prepareTrial).not.toHaveBeenCalled()
  expect(api.generateAiTrial).not.toHaveBeenCalled()
})

it('keeps AI uncertainty accessible in evidence and argument disclosures', async () => {
  const { user, api } = await openTrial(makeApi('cached_ai'))
  await begin(user, false)
  const reading = screen.getByText('Limits of this reading').closest('details')
  expect(reading.open).toBe(false)
  await user.click(screen.getByText('Limits of this reading'))
  expect(reading.open).toBe(true)
  expect(reading.textContent).toContain(aiTrialResponse().evidence_agent.uncertainty)
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  const argument = screen.getByText('Limits of this argument').closest('details')
  expect(argument.open).toBe(false)
  await user.click(screen.getByText('Limits of this argument'))
  expect(argument.open).toBe(true)
  expect(argument.textContent).toContain(aiTrialResponse().prosecution.uncertainty)
  expect(api.generateAiTrial).not.toHaveBeenCalled()
})

it('requires charge confirmation, supports cancellation and reuses the non-billable lookup', async () => {
  const { user, api } = await openTrial()
  await user.click(screen.getByRole('button', { name: 'Begin trial' }))
  const dialog = await screen.findByRole('dialog')
  expect(dialog.textContent).toContain('small Azure API charge')
  expect(dialog.textContent).toContain('up to four model requests')
  expect(api.prepareTrial).toHaveBeenCalledExactlyOnceWith('a', 'case-a', 15)
  expect(api.generateAiTrial).not.toHaveBeenCalled()
  await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Begin trial' }))
  await begin(user)
  expect(api.prepareTrial).toHaveBeenCalledTimes(1)
  expect(api.generateAiTrial).toHaveBeenCalledExactlyOnceWith('a', 'case-a', 15)
})

it('handles native dialog Escape cancellation without requesting generation', async () => {
  const { user, api } = await openTrial()
  await user.click(screen.getByRole('button', { name: 'Begin trial' }))
  fireEvent(await screen.findByRole('dialog'), new Event('cancel', { cancelable: true }))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(api.generateAiTrial).not.toHaveBeenCalled()
})

it('locks rapid Begin/confirmation clicks and waits for genuine results before Evidence', async () => {
  const preparing = deferred(), generating = deferred(), api = makeApi()
  api.prepareTrial.mockReturnValue(preparing.promise)
  api.generateAiTrial.mockReturnValue(generating.promise)
  await openTrial(api, true)
  const button = screen.getByRole('button', { name: 'Begin trial' })
  act(() => { fireEvent.click(button); fireEvent.click(button); fireEvent.click(button) })
  expect(api.prepareTrial).toHaveBeenCalledTimes(1)
  expect(api.generateAiTrial).not.toHaveBeenCalled()
  expect(screen.queryByText(/The workflow is running on the backend/)).toBeNull()
  await act(async () => preparing.resolve({ status: 'confirmation_required', result: null }))
  const confirm = screen.getByRole('button', { name: 'Confirm & begin trial' })
  act(() => { fireEvent.click(confirm); fireEvent.click(confirm); fireEvent.click(confirm) })
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
  expect(screen.getByText(/Individual agent progress is not streamed/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Preparing the court…' }).disabled).toBe(true)
  expect(screen.queryByText('Submission validated')).toBeNull()
  expect(screen.queryByRole('slider', { name: 'Seek evidence replay' })).toBeNull()
  await act(async () => generating.resolve(aiTrialResponse()))
  expect(screen.getByRole('slider', { name: 'Seek evidence replay' })).toBeTruthy()
  expect(screen.getByText('Live AI analysis')).toBeTruthy()
  expect(screen.queryByText(AI_COPY.judge)).toBeNull()
})

it.each(['live_ai', 'cached_ai'])('uses %s in the original evidence, podiums and one sealed ruling', async (mode) => {
  const { user, api } = await openTrial(makeApi(mode))
  await begin(user, mode === 'live_ai')
  expect(screen.getByText(mode === 'cached_ai' ? 'Cached AI analysis' : 'Live AI analysis')).toBeTruthy()
  expect(api.generateAiTrial).toHaveBeenCalledTimes(mode === 'cached_ai' ? 0 : 1)
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.getByText(AI_COPY.evidence)).toBeTruthy()
  expect(screen.getByLabelText('Verified case evidence').textContent).toContain('Alpha: goals')
  await user.click(screen.getByText('Behind the verdict'))
  const trace = document.querySelector('.agent-trace')
  expect(within(trace).getAllByText('Submission validated')).toHaveLength(4)
  expect(within(trace).getByText('Handed to Defense')).toBeTruthy()
  expect(trace.textContent).toContain(mode === 'cached_ai' ? '0 model attempts' : '4 model attempts')
  expect(within(trace).getByText('Ruling and its evidence references sealed until your vote.')).toBeTruthy()
  const entries = trace.querySelectorAll(':scope > ol > li')
  expect(within(entries[1]).getByRole('button', { name: 'Review cited goal at 00:10' })).toBeTruthy()
  expect(within(entries[3]).queryByRole('button', { name: /Review cited/ })).toBeNull()
  await user.click(screen.getByText('Behind the verdict'))
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  expect(screen.getByRole('heading', { name: AI_COPY.prosecution })).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Hear the defense' }))
  expect(screen.getByRole('heading', { name: AI_COPY.defense })).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Make your call' }))
  expect(screen.queryByText(AI_COPY.judge)).toBeNull()
  expect(screen.getByRole('button', { name: /The ruling/ }).disabled).toBe(true)
  await voteDefense(user)
  expect(screen.getAllByText(AI_COPY.judge)).toHaveLength(1)
  expect(screen.getByText('PROSECUTION SUPPORTED')).toBeTruthy()
  expect(within(document.querySelector('.recorded-vote')).getByText('Agree with the defense')).toBeTruthy()
})

it('begins deterministic fallback automatically when disabled, without confirmation or generation', async () => {
  const { user, api } = await openTrial(makeApi('deterministic_fallback'))
  await begin(user, false)
  expect(screen.getByText('Deterministic fallback')).toBeTruthy()
  expect(screen.getByText(/AI is switched off/)).toBeTruthy()
  expect(screen.queryByRole('dialog')).toBeNull()
  await voteStage(user)
  await voteDefense(user)
  expect(screen.getByText('INCONCLUSIVE')).toBeTruthy()
  expect(screen.getByText(/No AI judge has evaluated this case/)).toBeTruthy()
  expect(api.generateAiTrial).not.toHaveBeenCalled()
})

it('keeps the courtroom usable with an older or missing backend connection', async () => {
  const api = makeApi()
  delete api.prepareTrial
  const { user } = await openTrial(api)
  await begin(user, false)
  expect(screen.getByText('Deterministic fallback')).toBeTruthy()
  await voteStage(user)
  await voteDefense(user)
  expect(screen.getByText('INCONCLUSIVE')).toBeTruthy()
  expect(api.generateAiTrial).not.toHaveBeenCalled()
})

it.each(['network', 'invalid_preparation', 'uncached_result'])('fails closed on %s during preparation', async (kind) => {
  const api = makeApi()
  if (kind === 'network') api.prepareTrial.mockRejectedValue(new Error('private-provider-body-and-token'))
  if (kind === 'invalid_preparation') api.prepareTrial.mockResolvedValue({ status: 'ready', result: null })
  if (kind === 'uncached_result') api.prepareTrial.mockResolvedValue({ status: 'ready', result: aiTrialResponse() })
  const { user } = await openTrial(api)
  await begin(user, false)
  expect(screen.getByRole('alert').textContent).toContain('no generation was requested')
  expect(document.body.textContent).not.toContain('private-provider-body-and-token')
  expect(api.generateAiTrial).not.toHaveBeenCalled()
})

it.each(['network', 'future', 'wrong_case', 'backend_failure'])('falls back after confirmed %s failure with no retry or secrets', async (kind) => {
  const response = aiTrialResponse(), api = makeApi()
  if (kind === 'network') api.generateAiTrial.mockRejectedValue(new Error('private-provider-body-and-token'))
  if (kind === 'future') response.prosecution.points[0].event_ids.push('later')
  if (kind === 'wrong_case') response.evidence.case_id = 'another-case'
  if (kind === 'backend_failure') {
    const fallback = aiTrialResponse('deterministic_fallback')
    fallback.error_category = 'timeout'
    api.generateAiTrial.mockResolvedValue(fallback)
  } else if (kind !== 'network') api.generateAiTrial.mockResolvedValue(response)
  const { user } = await openTrial(api)
  await begin(user)
  expect(screen.getByText('Deterministic fallback')).toBeTruthy()
  expect(document.body.textContent).not.toContain('private-provider-body-and-token')
  expect(screen.queryByText(AI_COPY.prosecution)).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  expect(screen.getByRole('heading', { name: 'Attacking evidence' })).toBeTruthy()
  expect(screen.queryByRole('button', { name: /cited.*00:20/ })).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Return to match', exact: true }))
  await user.click(screen.getByRole('tab', { name: /Cases/ }))
  await user.click(screen.getByRole('button', { name: /Open case/ }))
  await begin(user, false)
  expect(api.prepareTrial).toHaveBeenCalledTimes(1)
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('preserves citations, original replay position, session results and independent votes across return', async () => {
  const { user, api } = await openTrial()
  await begin(user)
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  const snapshots = api.loadSnapshot.mock.calls.length
  within(document.querySelector('.trial-stage')).getByRole('button', { name: 'Review cited goal at 00:10' }).focus()
  await user.keyboard('{Enter}')
  expect(screen.getByRole('slider', { name: 'Seek evidence replay' }).value).toBe('10')
  expect(document.activeElement.getAttribute('aria-label')).toBe('Evidence')
  expect(api.loadSnapshot).toHaveBeenCalledTimes(snapshots)
  await voteStage(user)
  await voteDefense(user)
  await user.click(screen.getByRole('button', { name: 'Back to the replay' }))
  expect(screen.getByLabelText('Match clock').textContent).toBe('00:15')
  expect(screen.getByRole('button', { name: 'Play', exact: true })).toBeTruthy()
  await user.click(screen.getByRole('tab', { name: /Cases/ }))
  await user.click(screen.getByRole('button', { name: /Open case/ }))
  expect(screen.queryByText(AI_COPY.judge)).toBeNull()
  await begin(user, false)
  await voteStage(user)
  expect(screen.getByRole('button', { name: 'Agree with the defense', exact: true }).getAttribute('aria-pressed')).toBe('true')
  expect(api.prepareTrial).toHaveBeenCalledTimes(1)
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('never attaches a late generation result or stage transition to another match', async () => {
  const api = makeApi(), pending = deferred()
  api.generateAiTrial.mockReturnValue(pending.promise)
  const { user } = await openTrial(api)
  await user.click(screen.getByRole('button', { name: 'Begin trial' }))
  await user.click(await screen.findByRole('button', { name: 'Confirm & begin trial' }))
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
  expect(screen.queryByText('Live AI analysis')).toBeNull()
  expect(screen.getByRole('button', { name: 'Begin trial' })).toBeTruthy()
  expect(screen.queryByRole('slider', { name: 'Seek evidence replay' })).toBeNull()
  expect(api.generateAiTrial).toHaveBeenCalledTimes(1)
})

it('shows actual partial handoffs while withholding discarded agent content and references', async () => {
  const result = aiTrialResponse('deterministic_fallback')
  result.error_category = 'invalid_agent_output'
  result.api_attempts = result.original_api_attempts = 2
  result.trace = [aiTrialResponse().trace[0], {
    agent: 'prosecution', status: 'failed', handoff_to: null,
    input_digest: 'a'.repeat(64), output_digest: null, error_category: 'invalid_agent_output',
  }]
  const api = makeApi()
  api.generateAiTrial.mockResolvedValue(result)
  const { user } = await openTrial(api)
  await begin(user)
  await user.click(screen.getByText('Behind the verdict'))
  const trace = document.querySelector('.agent-trace')
  expect(within(trace).getAllByText('Submission validated')).toHaveLength(1)
  expect(within(trace).getByText('Stopped; submission withheld')).toBeTruthy()
  await user.click(within(trace).getByText('Inspect Prosecution handoff'))
  expect(within(trace).getByText('Withheld')).toBeTruthy()
  expect(within(trace).queryByRole('button', { name: /Review cited/ })).toBeNull()
  expect(screen.queryByText(AI_COPY.prosecution)).toBeNull()
})
