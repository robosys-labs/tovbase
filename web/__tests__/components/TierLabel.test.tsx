import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import TierLabel from '@/components/TierLabel'

describe('TierLabel', () => {
  it('renders "Excellent" for score >= 850', () => {
    render(<TierLabel score={900} />)
    expect(screen.getByText('Excellent')).toBeInTheDocument()
  })

  it('renders "Good" for score 700-849', () => {
    render(<TierLabel score={750} />)
    expect(screen.getByText('Good')).toBeInTheDocument()
  })

  it('renders "Fair" for score 550-699', () => {
    render(<TierLabel score={600} />)
    expect(screen.getByText('Fair')).toBeInTheDocument()
  })

  it('renders "Poor" for score 350-549', () => {
    render(<TierLabel score={400} />)
    expect(screen.getByText('Poor')).toBeInTheDocument()
  })

  it('renders "Untrusted" for score < 350', () => {
    render(<TierLabel score={100} />)
    expect(screen.getByText('Untrusted')).toBeInTheDocument()
  })

  it('uses the tier prop when provided instead of computing from score', () => {
    render(<TierLabel score={100} tier="Excellent" />)
    expect(screen.getByText('Excellent')).toBeInTheDocument()
  })

  it('applies the correct color for Excellent tier', () => {
    render(<TierLabel score={900} />)
    const el = screen.getByText('Excellent')
    expect(el).toHaveStyle({ color: '#10b981' })
  })

  it('applies the correct color for Fair tier', () => {
    render(<TierLabel score={600} />)
    const el = screen.getByText('Fair')
    expect(el).toHaveStyle({ color: '#f59e0b' })
  })

  it('applies the correct color for Untrusted tier', () => {
    render(<TierLabel score={100} />)
    const el = screen.getByText('Untrusted')
    expect(el).toHaveStyle({ color: '#6b7280' })
  })
})
