import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import { ImagePlus, Plus, Send, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api, errorMessage } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { Page, Story, StoryReply, User } from '../types'
import Avatar from './Avatar'
import { uploadMediaToBlob, usesDirectImageUploads } from '../services/blobUpload'
import './StoriesBar.css'

type StoryGroup = { author: User; stories: Story[] }
const reactions = ['❤️', '😂', '😮', '😢', '👏', '🔥']

export default function StoriesBar() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [stories, setStories] = useState<Story[]>([])
  const [storiesLoaded, setStoriesLoaded] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [selected, setSelected] = useState<{ group: number; index: number } | null>(null)
  const [showComposer, setShowComposer] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [caption, setCaption] = useState('')
  const [reply, setReply] = useState('')
  const [replies, setReplies] = useState<StoryReply[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const groups = useMemo<StoryGroup[]>(() => {
    const map = new Map<number, StoryGroup>()
    stories.forEach(story => {
      const group = map.get(story.author.id) || { author: story.author, stories: [] }
      group.stories.push(story)
      map.set(story.author.id, group)
    })
    return [...map.values()].sort((a, b) => Number(b.author.id === user?.id) - Number(a.author.id === user?.id))
  }, [stories, user?.id])
  const ownGroupIndex = groups.findIndex(group => group.author.id === user?.id)
  const activeGroup = selected ? groups[selected.group] : null
  const activeStory = activeGroup?.stories[selected?.index || 0]
  const requestedAuthor = searchParams.get('story')

  const loadStories = async () => {
    try {
      const { data } = await api.get<Story[] | Page<Story>>('/stories/')
      setStories(Array.isArray(data) ? data : data.results)
    } catch (cause) { setError(errorMessage(cause)) }
    finally { setStoriesLoaded(true) }
  }
  useEffect(() => {
    loadStories()
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void loadStories() }, 30000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    if (!requestedAuthor || !storiesLoaded) return
    const groupIndex = groups.findIndex(group => group.author.id === Number(requestedAuthor))
    if (groupIndex >= 0) setSelected({ group: groupIndex, index: 0 })
    const next = new URLSearchParams(searchParams)
    next.delete('story')
    setSearchParams(next, { replace: true })
  }, [requestedAuthor, storiesLoaded, groups, searchParams, setSearchParams])
  useEffect(() => {
    if (!file) { setPreviewUrl(null); return }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])
  useEffect(() => {
    if (!activeStory) { setReplies([]); return }
    api.get<StoryReply[]>(`/stories/${activeStory.id}/replies/`).then(({ data }) => setReplies(data)).catch(() => setReplies([]))
  }, [activeStory?.id])

  const chooseFile = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0] || null
    event.currentTarget.value = ''
    if (!picked) return
    const video = picked.type.startsWith('video/') || /\.(mp4|webm)$/i.test(picked.name)
    if (video && picked.size > 100 * 1024 * 1024) { setError('Story videos must be 100 MB or smaller.'); return }
    if (!video && (!picked.type.startsWith('image/') || picked.size > 8 * 1024 * 1024)) { setError('Choose a photo up to 8 MB or a video up to 100 MB.'); return }
    if (video) {
      const url = URL.createObjectURL(picked)
      const probe = document.createElement('video'); probe.preload = 'metadata'; probe.src = url
      probe.onloadedmetadata = () => { URL.revokeObjectURL(url); if (probe.duration > 60) setError('Story videos must be 60 seconds or shorter.'); else { setFile(picked); setError('') } }
      probe.onerror = () => { URL.revokeObjectURL(url); setError('This video could not be opened.') }
    } else { setFile(picked); setError('') }
  }
  const createStory = async (event: FormEvent) => {
    event.preventDefault()
    if (!file || !user) return
    setBusy(true); setError('')
    try {
      const mediaType = file.type.startsWith('video/') || /\.(mp4|webm)$/i.test(file.name) ? 'video' : 'image'
      let body: FormData | Record<string, string>
      if (usesDirectImageUploads) {
        const url = await uploadMediaToBlob(file, user.id, 'stories')
        body = { media_type: mediaType, caption, uploaded_media_url: url }
      } else {
        const form = new FormData()
        form.append('media_type', mediaType); form.append('caption', caption); form.append('uploaded_media', file)
        body = form
      }
      await api.post('/stories/', body, body instanceof FormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined)
      setFile(null); setCaption(''); setShowComposer(false); await loadStories()
    } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }
  const react = async (emoji: string) => {
    if (!activeStory) return
    try {
      await api.post(`/stories/${activeStory.id}/reaction/`, { emoji })
      setStories(current => current.map(item => item.id === activeStory.id ? { ...item, reacted_by_me: true, reactions_count: item.reacted_by_me ? item.reactions_count : item.reactions_count + 1 } : item))
    } catch (cause) { setError(errorMessage(cause)) }
  }
  const sendReply = async (event: FormEvent) => {
    event.preventDefault()
    if (!activeStory || !reply.trim()) return
    try {
      const { data } = await api.post<StoryReply>(`/stories/${activeStory.id}/replies/`, { content: reply.trim() })
      setReplies(current => [...current, data]); setReply('')
    } catch (cause) { setError(errorMessage(cause)) }
  }
  const moveStory = (step: number) => {
    if (!selected || !activeGroup) return
    const nextIndex = selected.index + step
    if (nextIndex >= 0 && nextIndex < activeGroup.stories.length) { setSelected({ ...selected, index: nextIndex }); return }
    const nextGroup = selected.group + (step > 0 ? 1 : -1)
    if (nextGroup >= 0 && nextGroup < groups.length) setSelected({ group: nextGroup, index: step > 0 ? 0 : groups[nextGroup].stories.length - 1 })
    else setSelected(null)
  }

  return <>
    <section className="stories-bar" aria-label="Stories">
      <div className="story-own-slot"><button className="story-person story-add" type="button" onClick={() => ownGroupIndex >= 0 ? setSelected({ group: ownGroupIndex, index: 0 }) : setShowComposer(true)}>
        <span className={ownGroupIndex >= 0 ? 'story-ring' : 'story-avatar-wrap'}><Avatar user={user} size="lg"/><i><Plus size={15}/></i></span><span>{ownGroupIndex >= 0 ? 'Your story' : 'Add story'}</span>
      </button>{ownGroupIndex >= 0 && <button className="story-add-more" type="button" aria-label="Add another story" onClick={() => { setShowComposer(true); setError('') }}><Plus size={13}/></button>}</div>
      {groups.filter(group => group.author.id !== user?.id).map((group, groupIndex) => <button className="story-person" type="button" key={group.author.id} onClick={() => setSelected({ group: groups.indexOf(group), index: 0 })} aria-label={`View ${group.author.username}'s story`}>
        <span className="story-ring"><Avatar user={group.author} size="lg"/></span><span>{group.author.full_name?.split(' ')[0] || group.author.username}</span>
      </button>)}
    </section>
    {error && <p className="form-error story-error">{error}<button onClick={() => setError('')} aria-label="Dismiss">×</button></p>}
    {showComposer && <div className="modal-backdrop" onClick={event => event.target === event.currentTarget && setShowComposer(false)}><form className="modal-card story-compose" onSubmit={createStory}>
      <div className="modal-heading"><div><p className="eyebrow">A LITTLE MOMENT</p><h2>Add to your story</h2></div><button type="button" className="icon-button" onClick={() => setShowComposer(false)} aria-label="Close"><X size={19}/></button></div>
      <label className="story-upload">{file ? <span>{file.name}</span> : <><ImagePlus size={22}/><span>Choose a photo or video</span></>}<input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" onChange={chooseFile}/></label>
      {file && previewUrl && ((file.type.startsWith('video/') || /\.(mp4|webm)$/i.test(file.name)) ? <video className="story-compose-preview" src={previewUrl} controls/> : <img className="story-compose-preview" src={previewUrl} alt="Story preview"/>)}
      <label>Caption<input value={caption} onChange={event => setCaption(event.target.value)} maxLength={300} placeholder="Add a caption…"/></label>
      {error && <p className="form-error">{error}</p>}<div className="modal-footer"><button type="button" className="button button-secondary" onClick={() => setShowComposer(false)}>Cancel</button><button className="button button-primary" disabled={busy || !file}>{busy ? 'Sharing…' : 'Share story'}</button></div>
    </form></div>}
    {activeStory && activeGroup && <div className="story-viewer-backdrop" role="dialog" aria-modal="true" aria-label={`${activeGroup.author.username}'s story`} onClick={() => setSelected(null)}>
      <section className="story-viewer" onClick={event => event.stopPropagation()}>
        <div className="story-progress">{activeGroup.stories.map((story, index) => <i key={story.id} className={index <= selected!.index ? 'done' : ''}/>)}</div>
        <header className="story-viewer-header"><Avatar user={activeGroup.author} size="sm"/><strong>{activeGroup.author.full_name || activeGroup.author.username}</strong><time>{Math.max(0, Math.ceil((new Date(activeStory.expires_at).getTime() - Date.now()) / 3600000))}h</time><button className="icon-button" onClick={() => setSelected(null)} aria-label="Close story"><X size={20}/></button></header>
        {activeStory.media_type === 'video' ? <video className="story-media" src={activeStory.media_url} autoPlay muted playsInline controls/> : <img className="story-media" src={activeStory.media_url} alt={activeStory.caption || 'Story'}/>}
        {activeStory.caption && <p className="story-caption">{activeStory.caption}</p>}
        <button className="story-hit-area story-hit-left" onClick={() => moveStory(-1)} aria-label="Previous story"/><button className="story-hit-area story-hit-right" onClick={() => moveStory(1)} aria-label="Next story"/>
        <div className="story-interactions"><div className="story-reactions">{reactions.map(emoji => <button key={emoji} type="button" onClick={() => react(emoji)} aria-label={`React ${emoji}`}>{emoji}</button>)}<small>{activeStory.reactions_count || ''}</small></div><form onSubmit={sendReply}><input value={reply} onChange={event => setReply(event.target.value)} placeholder="Reply to story…" maxLength={1000}/><button aria-label="Send reply" disabled={!reply.trim()}><Send size={17}/></button></form></div>
        {!!replies.length && <div className="story-replies">{replies.slice(-3).map(item => <p key={item.id}><strong>{item.author.full_name || item.author.username}</strong> {item.content}</p>)}</div>}
      </section>
    </div>}
  </>
}
