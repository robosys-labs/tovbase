import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ScoreBadge from '@/components/ScoreBadge'

describe('ScoreBadge', () => {
  it('renders the score number', () => {
    render(<ScoreBadge score={815} />)
    expect(screen.getByText('815')).toBeInTheDocument()
  })

  it('renders the tier label for the given score', () => {
    render(<ScoreBadge score={815} />)
    expect(screen.getByText('Good')).toBeInTheDocument()
  })

  it('renders "Excellent" tier for score >= 850', () => {
    render(<ScoreBadge score={900} />)
    expect(screen.getByText('Excellent')).toBeInTheDocument()
  })

  it('renders "Fair" tier for score 550-699', () => {
    render(<ScoreBadge score={600} />)
    expect(screen.getByText('Fair')).toBeInTheDocument()
  })

  it('renders "Poor" tier for score 350-549', () => {
    render(<ScoreBadge score={400} />)
    expect(screen.getByText('Poor')).toBeInTheDocument()
  })

  it('renders "Untrusted" tier for score < 350', () => {
    render(<ScoreBadge score={100} />)
    expect(screen.getByText('Untrusted')).toBeInTheDocument()
  })

  it('applies the correct color for an Excellent score', () => {
    render(<ScoreBadge score={900} />)
    const scoreEl = screen.getByText('900')
    // getTierColor("Excellent") returns "#10b981"
    expect(scoreEl).toHaveStyle({ color: '#10b981' })
  })

  it('applies the correct color for a Poor score', () => {
    render(<ScoreBadge score={400} />)
    const scoreEl = screen.getByText('400')
    // getTierColor("Poor") returns "#ef4444"
    expect(scoreEl).toHaveStyle({ color: '#ef4444' })
  })

  it('respects the size prop', () => {
    const { container } = render(<ScoreBadge score={750} size={100} />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper).toHaveStyle({ width: '100px', height: '100px' })
  })
})
