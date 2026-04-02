import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SearchBar from '@/components/SearchBar'

// Mock next/navigation
const pushMock = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
}))

describe('SearchBar', () => {
  beforeEach(() => {
    pushMock.mockClear()
  })

  it('renders an input and submit button', () => {
    render(<SearchBar />)
    expect(screen.getByPlaceholderText(/paste any profile link/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run report/i })).toBeInTheDocument()
  })

  it('navigates to report page on form submission with a handle', () => {
    render(<SearchBar />)
    const input = screen.getByPlaceholderText(/paste any profile link/i)
    fireEvent.change(input, { target: { value: 'sarahchen' } })
    fireEvent.click(screen.getByRole('button', { name: /run report/i }))

    expect(pushMock).toHaveBeenCalledWith('/report/sarahchen')
  })

  it('strips @ prefix from handles', () => {
    render(<SearchBar />)
    const input = screen.getByPlaceholderText(/paste any profile link/i)
    fireEvent.change(input, { target: { value: '@sarahchen' } })
    fireEvent.click(screen.getByRole('button', { name: /run report/i }))

    expect(pushMock).toHaveBeenCalledWith('/report/sarahchen')
  })

  it('extracts handle from a URL', () => {
    render(<SearchBar />)
    const input = screen.getByPlaceholderText(/paste any profile link/i)
    fireEvent.change(input, { target: { value: 'https://github.com/sarahchen' } })
    fireEvent.click(screen.getByRole('button', { name: /run report/i }))

    expect(pushMock).toHaveBeenCalledWith('/report/sarahchen')
  })

  it('does not navigate when input is empty', () => {
    render(<SearchBar />)
    fireEvent.click(screen.getByRole('button', { name: /run report/i }))

    expect(pushMock).not.toHaveBeenCalled()
  })

  it('does not navigate when input is only whitespace', () => {
    render(<SearchBar />)
    const input = screen.getByPlaceholderText(/paste any profile link/i)
    fireEvent.change(input, { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: /run report/i }))

    expect(pushMock).not.toHaveBeenCalled()
  })
})
