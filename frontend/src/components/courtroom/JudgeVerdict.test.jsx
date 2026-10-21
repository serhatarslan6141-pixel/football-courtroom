import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import JudgeVerdict from './JudgeVerdict.jsx'
import { adaptCourtroomResponse } from '../../domain/aiCourtroom.js'
import { aiCase, aiTrialResponse } from '../../test/aiTrialFixture.js'
import { events, matches } from '../../test/fixtures.js'

it('shows the lead finding once with citations, retains additional findings, and separates uncertainty', async () => {
  const response = aiTrialResponse()
  const extra = 'The defense identifies a limitation in how far the attacking pattern can be taken.'
  response.judge.findings.push({ ...response.judge.findings[0], interpretation: extra })
  const trial = adaptCourtroomResponse(response, aiCase, events, matches[0], 15)
  const onCite = vi.fn()
  render(<JudgeVerdict assessment={trial.assessment} trial={trial} vote="defense" onCite={onCite} onReturn={() => {}} />)
  expect(screen.getAllByText(response.judge.findings[0].interpretation)).toHaveLength(1)
  expect(document.querySelector('.ruling-reason').textContent).toBe(response.judge.findings[0].interpretation)
  expect(screen.getByText(extra)).toBeTruthy()
  const limits = screen.getByText(response.judge.uncertainty).closest('details')
  expect(limits.open).toBe(false)
  expect(screen.getByText('Confidence in this ruling: medium')).toBeTruthy()
  expect(screen.queryByText(/Cause and effect remain unproven/)).toBeNull()
  expect(within(document.querySelector('.recorded-vote')).getByText('Agree with the defense')).toBeTruthy()
  await userEvent.setup().click(screen.getAllByRole('button', { name: 'Review cited goal at 00:10' })[0])
  expect(onCite).toHaveBeenCalledExactlyOnceWith('goal')
})
