import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PlatformBadge from '@/components/PlatformBadge'

describe('PlatformBadge', () => {
  it('renders the platform name capitalized', () => {
    render(<PlatformBadge platform="github" />)
    expect(screen.getByText('Github')).toBeInTheDocument()
  })

  it('applies correct colors for linkedin', () => {
    render(<PlatformBadge platform="linkedin" />)
    const el = screen.getByText('Linkedin')
    expect(el).toHaveStyle({ backgroundColor: '#EFF6FF', color: '#1D4ED8' })
  })

  it('applies correct colors for twitter', () => {
    render(<PlatformBadge platform="twitter" />)
    const el = screen.getByText('Twitter')
    expect(el).toHaveStyle({ backgroundColor: '#F0F9FF', color: '#0369A1' })
  })

  it('applies correct colors for github', () => {
    render(<PlatformBadge platform="github" />)
    const el = screen.getByText('Github')
    expect(el).toHaveStyle({ backgroundColor: '#F3F4F6', color: '#1F2937' })
  })

  it('applies correct colors for reddit', () => {
    render(<PlatformBadge platform="reddit" />)
    const el = screen.getByText('Reddit')
    expect(el).toHaveStyle({ backgroundColor: '#FFF7ED', color: '#C2410C' })
  })

  it('applies fallback colors for unknown platform', () => {
    render(<PlatformBadge platform="mastodon" />)
    const el = screen.getByText('Mastodon')
    expect(el).toHaveStyle({ backgroundColor: '#F3F4F6', color: '#374151' })
  })

  it('renders a verified check icon when verified is true', () => {
    const { container } = render(<PlatformBadge platform="github" verified />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })

  it('does not render a check icon when verified is false', () => {
    const { container } = render(<PlatformBadge platform="github" />)
    const svg = container.querySelector('svg')
    expect(svg).not.toBeInTheDocument()
  })

  it('handles mixed-case platform input', () => {
    render(<PlatformBadge platform="GitHub" />)
    // The label capitalizes first char, rest stays as-is: "GitHub" -> "GitHub" (already capitalized)
    // But colors lookup uses toLowerCase -> "github"
    const el = screen.getByText('GitHub')
    expect(el).toHaveStyle({ backgroundColor: '#F3F4F6', color: '#1F2937' })
  })
})
