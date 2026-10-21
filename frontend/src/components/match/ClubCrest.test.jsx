import { render } from '@testing-library/react'
import { expect, it } from 'vitest'
import ClubCrest from './ClubCrest.jsx'

const clubs = [
  ['Northbridge City', 'NBC', '#7c3aed', '#fbbf24'],
  ['Harbor Athletic', 'HBA', '#34d399', '#fbbf24'],
  ['Mossfield United', 'MSF', '#f97316', '#dbeafe'],
  ['Riverside Athletic', 'RIV', '#2563eb', '#fef3c7'],
  ['Ashcombe Rovers', 'ASH', '#ef4444', '#f5f5f5'],
  ['Briarhampton FC', 'BRI', '#22c55e', '#0f172a'],
]

it.each(clubs)('uses the same self-contained %s identity at fixture and scoreboard sizes', (name, shortName, color, secondaryColor) => {
  const club = Object.freeze({ name, shortName, color, secondaryColor })
  const { container } = render(<><ClubCrest club={club} /><ClubCrest club={club} small /></>)
  const symbols = container.querySelectorAll('svg')
  expect(symbols).toHaveLength(2)
  expect(symbols[0].outerHTML).toBe(symbols[1].outerHTML)
  expect(symbols[0].dataset.clubIdentity).not.toBe('monogram')
  expect(symbols[0].querySelectorAll('image, script, foreignObject, use, [href]')).toHaveLength(0)
  expect(symbols[0].textContent).toBe('') // No invented founding dates or tiny wordmarks.
  for (const wrapper of container.querySelectorAll('.club-crest')) {
    expect(wrapper.style.getPropertyValue('--club-color')).toBe(color)
    expect(wrapper.style.getPropertyValue('--club-secondary')).toBe(secondaryColor)
    expect(wrapper.getAttribute('aria-hidden')).toBe('true')
  }
})

it('gives the six existing clubs different vector artwork', () => {
  const { container } = render(<>{clubs.map(([name, shortName, color, secondaryColor]) => <ClubCrest key={name} club={{ name, shortName, color, secondaryColor }} />)}</>)
  const symbols = [...container.querySelectorAll('svg')]
  expect(new Set(symbols.map((symbol) => symbol.innerHTML)).size).toBe(6)
  expect(new Set(symbols.map((symbol) => symbol.dataset.clubIdentity)).size).toBe(6)
})

it.each(['A new fictional club', '__proto__'])('retains a safe monogram fallback for %s', (name) => {
  const { container } = render(<ClubCrest club={{ name, shortName: 'NEW', color: '#123456', secondaryColor: '#abcdef' }} small />)
  expect(container.querySelector('svg').dataset.clubIdentity).toBe('monogram')
  expect(container.querySelector('text').textContent).toBe('NEW')
})
