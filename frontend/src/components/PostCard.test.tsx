import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PostCard from './PostCard'
import { Post } from '../types'

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn(), post: vi.fn(), delete: vi.fn(), patch: vi.fn() } }))
vi.mock('../services/api', () => ({ api: apiMock, errorMessage: () => 'Request failed' }))
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, username: 'alex', full_name: 'Alex Morgan', is_staff: false } }) }))

const post: Post = {
  id: 7,
  author: { id: 1, username: 'alex', full_name: 'Alex Morgan', bio: '', location: '', website: '', avatar_url: null, cover_url: null, created_at: '2026-01-01T00:00:00Z', posts_count: 1, followers_count: 0, following_count: 0, is_following: false, is_staff: false },
  content: 'A sunny afternoon #weekend', is_public: true, images: [], likes_count: 0, comments_count: 0, liked_by_me: false, shares_count: 0, hashtags: ['weekend'], created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

describe('PostCard', () => {
  beforeEach(() => { vi.clearAllMocks() })
  it('likes and unlikes through the API and reflects the returned count', async () => {
    const user = userEvent.setup()
    apiMock.post.mockResolvedValue({ data: { liked: true, likes_count: 1 } })
    apiMock.delete.mockResolvedValue({ data: { liked: false, likes_count: 0 } })
    render(<MemoryRouter><PostCard initialPost={post}/></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: 'Like' }))
    expect(apiMock.post).toHaveBeenCalledWith('/posts/7/like/')
    expect(await screen.findByRole('button', { name: 'Liked' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Liked' }))
    await waitFor(() => expect(apiMock.delete).toHaveBeenCalledWith('/posts/7/like/'))
    expect(await screen.findByRole('button', { name: 'Like' })).toBeInTheDocument()
  })

  it('loads comments and submits a new comment', async () => {
    const user = userEvent.setup()
    apiMock.get.mockResolvedValue({ data: [] })
    apiMock.post.mockResolvedValue({ data: { id: 91, post: 7, author: { id: 2, username: 'jamie', full_name: 'Jamie Lee' }, parent: null, content: 'Lovely!', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' } })
    render(<MemoryRouter><PostCard initialPost={post}/></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: 'Comment' }))
    const input = await screen.findByPlaceholderText('Write a comment…')
    await user.type(input, 'Lovely!')
    fireEvent.click(screen.getByRole('button', { name: 'Send comment' }))
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/posts/7/comments/', { content: 'Lovely!' }))
    expect(await screen.findByText('Lovely!')).toBeInTheDocument()
  })

  it('opens the post editor and saves caption and photo replacement fields', async () => {
    const user = userEvent.setup()
    apiMock.patch.mockResolvedValue({ data: { ...post, content: 'Updated with a new photo' } })
    render(<MemoryRouter><PostCard initialPost={post}/></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: 'Post options' }))
    await user.click(screen.getByRole('button', { name: 'Edit post' }))
    const caption = screen.getByLabelText('Caption')
    await user.clear(caption)
    await user.type(caption, 'Updated with a new photo')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(apiMock.patch).toHaveBeenCalled())
    const [url, body] = apiMock.patch.mock.calls[0]
    expect(url).toBe('/posts/7/')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('content')).toBe('Updated with a new photo')
    expect(body.get('replace_images')).toBe('false')
    expect(await screen.findByText('Updated with a new photo')).toBeInTheDocument()
  })
})
