import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Feed from './Feed'
import { Post, User } from '../types'

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../services/api', () => ({ api: apiMock, errorMessage: () => 'Request failed' }))
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, username: 'alex', full_name: 'Alex Morgan' } }) }))
vi.mock('../components/PostCard', () => ({ default: ({ initialPost }: { initialPost: Post }) => <article>{initialPost.content}</article> }))

const author: User = {
  id: 2, username: 'jamie', full_name: 'Jamie Lee', bio: '', location: '', website: '', avatar_url: null,
  cover_url: null, created_at: '2026-01-01T00:00:00Z', posts_count: 1, followers_count: 1,
  following_count: 0, is_following: true, is_staff: false,
}
const newPost: Post = {
  id: 11, author, content: 'A new post from someone you follow', is_public: false, images: [], likes_count: 0,
  comments_count: 0, liked_by_me: false, shares_count: 0, hashtags: [], created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('Following feed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('automatically fetches and displays new followed-account posts', async () => {
    let feedReads = 0
    apiMock.get.mockImplementation(async (path: string) => {
      if (path === '/stories/') return { data: [] }
      if (path === '/users/') return { data: { results: [] } }
      feedReads += 1
      return { data: { count: feedReads === 1 ? 0 : 1, next: null, previous: null, results: feedReads === 1 ? [] : [newPost] } }
    })

    render(<MemoryRouter><Feed /></MemoryRouter>)
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('Your feed is waiting for a first post')).toBeInTheDocument()

    await act(async () => { await vi.advanceTimersByTimeAsync(15000) })
    expect(screen.getByText('A new post from someone you follow')).toBeInTheDocument()
    expect(feedReads).toBeGreaterThan(1)
  })
})
