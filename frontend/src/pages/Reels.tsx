import { ChangeEvent, FormEvent, useEffect, useRef, useState } from 'react'
import { Bookmark, Heart, LoaderCircle, MessageCircle, Plus, Send, Share2, Volume2, VolumeX, X } from 'lucide-react'
import { api, errorMessage } from '../services/api'
import { Page, Reel, ReelComment } from '../types'
import { useAuth } from '../context/AuthContext'
import Avatar from '../components/Avatar'
import { uploadMediaToBlob, usesDirectImageUploads } from '../services/blobUpload'
import './Reels.css'

const filters: Record<Reel['filter_name'], string> = {
  none: 'none', vivid: 'saturate(1.35) contrast(1.08)', mono: 'grayscale(1)',
  warm: 'sepia(.22) saturate(1.22)', vintage: 'sepia(.35) contrast(.9) saturate(.8)',
}

function ReelPlayer({ reel }: { reel: Reel }) {
  const { user } = useAuth()
  const [liked, setLiked] = useState(reel.liked_by_me)
  const [likes, setLikes] = useState(reel.likes_count)
  const [saved, setSaved] = useState(reel.saved_by_me)
  const [commentsOpen, setCommentsOpen] = useState(false)
  const [comments, setComments] = useState<ReelComment[]>([])
  const [comment, setComment] = useState('')
  const [muted, setMuted] = useState(true)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const rootRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const target = rootRef.current
    if (!target) return
    const observer = new IntersectionObserver(entries => {
      const visible = entries[0]?.intersectionRatio >= 0.65
      if (visible) void videoRef.current?.play().catch(() => {})
      else videoRef.current?.pause()
    }, { threshold: [0, 0.65, 1] })
    observer.observe(target)
    return () => observer.disconnect()
  }, [])
  const toggleLike = async () => {
    try {
      const { data } = liked ? await api.delete(`/reels/${reel.id}/like/`) : await api.post(`/reels/${reel.id}/like/`)
      setLiked(data.liked); setLikes(data.likes_count)
    } catch (cause) { setNotice(errorMessage(cause)) }
  }
  const toggleSave = async () => {
    try {
      if (saved) { await api.delete(`/reels/${reel.id}/save/`); setSaved(false) }
      else { await api.post(`/reels/${reel.id}/save/`); setSaved(true) }
    } catch (cause) { setNotice(errorMessage(cause)) }
  }
  const toggleComments = async () => {
    const opening = !commentsOpen; setCommentsOpen(opening)
    if (opening) try { const { data } = await api.get<ReelComment[]>(`/reels/${reel.id}/comments/`); setComments(data) } catch (cause) { setNotice(errorMessage(cause)) }
  }
  const sendComment = async (event: FormEvent) => {
    event.preventDefault(); if (!comment.trim()) return
    try { const { data } = await api.post<ReelComment>(`/reels/${reel.id}/comments/`, { content: comment.trim() }); setComments(items => [...items, data]); setComment('') }
    catch (cause) { setNotice(errorMessage(cause)) }
  }
  const share = async () => {
    setBusy(true)
    try { await api.post(`/reels/${reel.id}/share/`); await navigator.clipboard?.writeText(`${location.origin}/reels?reel=${reel.id}`); setNotice('Reel link copied.') }
    catch (cause) { setNotice(errorMessage(cause)) } finally { setBusy(false) }
  }
  return <article className="reel-item" ref={rootRef}>
    <video ref={videoRef} className="reel-video" src={reel.video_url} poster={reel.thumbnail_url || undefined} style={{ filter: filters[reel.filter_name] }} muted={muted} loop playsInline controls={false} onClick={() => setMuted(value => !value)} aria-label="Reel video. Tap to toggle sound"/>
    <button className="reel-sound" onClick={() => setMuted(value => !value)} aria-label={muted ? 'Turn sound on' : 'Mute reel'}>{muted ? <VolumeX/> : <Volume2/>}</button>
    <div className="reel-details"><div className="reel-author"><Avatar user={reel.author} size="sm"/><strong>{reel.author.full_name || reel.author.username}</strong><span>·</span><small>{new Date(reel.created_at).toLocaleDateString()}</small></div>{reel.caption && <p>{reel.caption}</p>}</div>
    <div className="reel-actions"><button className={liked ? 'active' : ''} onClick={toggleLike} aria-label={liked ? 'Unlike reel' : 'Like reel'}><Heart fill={liked ? 'currentColor' : 'none'}/><span>{likes}</span></button><button onClick={toggleComments} aria-label="View comments"><MessageCircle/><span>{reel.comments_count}</span></button><button onClick={share} disabled={busy} aria-label="Share reel">{busy ? <LoaderCircle className="spin"/> : <Share2/>}</button><button className={saved ? 'active' : ''} onClick={toggleSave} aria-label={saved ? 'Unsave reel' : 'Save reel'}><Bookmark fill={saved ? 'currentColor' : 'none'}/></button></div>
    {notice && <button className="reel-notice" onClick={() => setNotice('')}>{notice} <X size={13}/></button>}
    {commentsOpen && <div className="reel-comments"><header><strong>Comments</strong><button onClick={() => setCommentsOpen(false)} aria-label="Close comments"><X size={17}/></button></header><div className="reel-comment-list">{comments.length ? comments.map(item => <p key={item.id}><strong>{item.author.full_name || item.author.username}</strong> {item.content}</p>) : <small>Be the first to comment.</small>}</div><form onSubmit={sendComment}><input value={comment} onChange={event => setComment(event.target.value)} placeholder="Add a comment…" maxLength={1000}/><button disabled={!comment.trim()} aria-label="Send comment"><Send size={16}/></button></form></div>}
    <span className="sr-only">Signed in as {user?.username || 'guest'}</span>
  </article>
}

export default function Reels() {
  const { user } = useAuth()
  const [reels, setReels] = useState<Reel[]>([])
  const [loading, setLoading] = useState(true)
  const [showComposer, setShowComposer] = useState(false)
  const [video, setVideo] = useState<File | null>(null)
  const [thumbnail, setThumbnail] = useState<File | null>(null)
  const [caption, setCaption] = useState('')
  const [filterName, setFilterName] = useState<Reel['filter_name']>('none')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const videoPreviewRef = useRef<HTMLVideoElement>(null)
  const thumbnailPreview = useRef<string | null>(null)
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null)
  const loadReels = async () => {
    try { const { data } = await api.get<Page<Reel>>('/reels/'); setReels(data.results) }
    catch (cause) { setError(errorMessage(cause)) } finally { setLoading(false) }
  }
  useEffect(() => { loadReels() }, [])
  useEffect(() => {
    if (!video) { setVideoPreviewUrl(null); return }
    const url = URL.createObjectURL(video)
    setVideoPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [video])
  useEffect(() => () => { if (thumbnailPreview.current) URL.revokeObjectURL(thumbnailPreview.current) }, [])
  const chooseVideo = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null; event.currentTarget.value = ''
    if (!file) return
    if (!['video/mp4', 'video/webm'].includes(file.type) || file.size > 100 * 1024 * 1024) { setError('Choose an MP4 or WebM video up to 100 MB.'); return }
    const url = URL.createObjectURL(file)
    const probe = document.createElement('video'); probe.preload = 'metadata'; probe.src = url
    probe.onloadedmetadata = () => { URL.revokeObjectURL(url); if (probe.duration > 90) setError('Reels must be 90 seconds or shorter.'); else { setVideo(file); setError('') } }
    probe.onerror = () => { URL.revokeObjectURL(url); setError('This video could not be opened.') }
  }
  const chooseThumbnail = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null; event.currentTarget.value = ''
    if (!file) return
    if (!file.type.startsWith('image/') || file.size > 8 * 1024 * 1024) { setError('Choose an image thumbnail up to 8 MB.'); return }
    if (thumbnailPreview.current) URL.revokeObjectURL(thumbnailPreview.current)
    thumbnailPreview.current = URL.createObjectURL(file); setThumbnail(file); setError('')
  }
  const publish = async (event: FormEvent) => {
    event.preventDefault(); if (!video || !user) return
    setBusy(true); setError('')
    try {
      let body: FormData | Record<string, string>
      if (usesDirectImageUploads) {
        const videoUrl = await uploadMediaToBlob(video, user.id, 'reels')
        const bodyData: Record<string, string> = { uploaded_video_url: videoUrl, caption, filter_name: filterName }
        if (thumbnail) bodyData.uploaded_thumbnail_url = await uploadMediaToBlob(thumbnail, user.id, 'reel-thumbnails')
        body = bodyData
      } else {
        const form = new FormData(); form.append('uploaded_video', video); form.append('caption', caption); form.append('filter_name', filterName)
        if (thumbnail) form.append('uploaded_thumbnail', thumbnail)
        body = form
      }
      const { data } = await api.post<Reel>('/reels/', body, body instanceof FormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined)
      setReels(items => [data, ...items]); setShowComposer(false); setVideo(null); setThumbnail(null); setCaption(''); setFilterName('none')
    } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }
  return <div className="reels-page"><div className="reels-heading"><div><p className="eyebrow">SHORT & SWEET</p><h1>Reels</h1><p>Little films from the people you follow.</p></div><button className="button button-primary" onClick={() => { setShowComposer(true); setError('') }}><Plus size={17}/> Create reel</button></div>
    {error && !showComposer && <p className="form-error">{error}</p>}
    {loading ? <div className="reels-loading"><LoaderCircle className="spin"/></div> : reels.length ? <div className="reels-scroll" aria-label="Reels feed">{reels.map(reel => <ReelPlayer key={reel.id} reel={reel}/>)}</div> : <div className="empty-state card"><span className="empty-icon"><Plus/></span><h3>No reels from your circle yet</h3><p>Follow a few people or create the first reel.</p></div>}
    {showComposer && <div className="modal-backdrop" onClick={event => event.target === event.currentTarget && setShowComposer(false)}><form className="modal-card reel-compose" onSubmit={publish}>
      <div className="modal-heading"><div><p className="eyebrow">MAKE A LITTLE FILM</p><h2>Create a reel</h2></div><button type="button" className="icon-button" onClick={() => setShowComposer(false)} aria-label="Close"><X size={19}/></button></div>
      <label className="reel-file-pick">{video ? video.name : 'Choose a video · MP4 or WebM · up to 90 seconds'}<input type="file" accept="video/mp4,video/webm" onChange={chooseVideo}/></label>
      {video && videoPreviewUrl && <video ref={videoPreviewRef} className="reel-compose-preview" src={videoPreviewUrl} controls playsInline style={{ filter: filters[filterName] }}/>}
      <label className="reel-file-pick small">{thumbnail ? thumbnail.name : 'Choose a cover thumbnail (optional)'}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseThumbnail}/></label>
      {thumbnailPreview.current && <img className="reel-thumbnail-preview" src={thumbnailPreview.current} alt="Selected reel thumbnail"/>}
      <label>Caption<textarea value={caption} onChange={event => setCaption(event.target.value)} maxLength={2000} rows={3} placeholder="Write a caption…"/></label>
      <div className="reel-filter-picker"><strong>Filter</strong>{(Object.keys(filters) as Reel['filter_name'][]).map(name => <button key={name} type="button" className={filterName === name ? 'selected' : ''} onClick={() => setFilterName(name)}>{name}</button>)}</div>
      {error && <p className="form-error">{error}</p>}<div className="modal-footer"><button type="button" className="button button-secondary" onClick={() => setShowComposer(false)}>Cancel</button><button className="button button-primary" disabled={busy || !video}>{busy ? 'Publishing…' : 'Publish reel'}</button></div>
    </form></div>}
  </div>
}
