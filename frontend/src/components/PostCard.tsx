import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Heart, MessageCircle, MoreHorizontal, Pencil, Send, Share2, Trash2, Flag, X, Users } from 'lucide-react'
import { api, errorMessage } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { Comment, Post, User } from '../types'
import Avatar from './Avatar'
import EditPostModal from './EditPostModal'
import { timeAgo } from '../utils'

export default function PostCard({ initialPost, onDelete, onUpdate }: { initialPost: Post; onDelete?: (id:number)=>void; onUpdate?: (post:Post)=>void }) {
  const [post, setPost] = useState(initialPost)
  const [commentsOpen, setCommentsOpen] = useState(false)
  const [comments, setComments] = useState<Comment[]>([])
  const [comment, setComment] = useState('')
  const [commentBusy, setCommentBusy] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [editing, setEditing] = useState(false)
  const [likedUsers, setLikedUsers] = useState<User[]>([])
  const [likesOpen, setLikesOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const { user } = useAuth()
  const navigate = useNavigate()
  const ownPost = user?.id === post.author.id || user?.is_staff
  const update = (next:Post) => { setPost(next); onUpdate?.(next) }
  const toggleLike = async () => {
    if (!user) return navigate('/login')
    try { const {data}=post.liked_by_me?await api.delete(`/posts/${post.id}/like/`):await api.post(`/posts/${post.id}/like/`); update({...post,liked_by_me:data.liked,likes_count:data.likes_count}) }
    catch(e) { setNotice(errorMessage(e)) }
  }
  const loadComments = async () => {
    const {data}=await api.get(`/posts/${post.id}/comments/`); setComments(data.results || data)
  }
  const toggleComments = async () => { const opening=!commentsOpen; setCommentsOpen(opening); if (opening) await loadComments().catch(e=>setNotice(errorMessage(e))) }
  const addComment = async (event:FormEvent) => {
    event.preventDefault(); if(!comment.trim())return
    setCommentBusy(true)
    try { const {data}=await api.post(`/posts/${post.id}/comments/`,{content:comment.trim()}); setComments(items=>[...items,data]);setComment('');update({...post,comments_count:post.comments_count+1}) }
    catch(e){setNotice(errorMessage(e))} finally{setCommentBusy(false)}
  }
  const editPost = () => setEditing(true)
  const deletePost = async () => { if(!window.confirm('Delete this post? This cannot be undone.'))return;try{await api.delete(`/posts/${post.id}/`);onDelete?.(post.id)}catch(e){setNotice(errorMessage(e))} }
  const showLikedUsers = async () => { setLikesOpen(v=>!v); if(!likesOpen)try{const {data}=await api.get(`/posts/${post.id}/likes/`);setLikedUsers(data.results||data)}catch(e){setNotice(errorMessage(e))} }
  const sharePost = async () => { if(busy)return;setBusy(true);try{await api.post(`/posts/${post.id}/share/`);await navigator.clipboard?.writeText(`${location.origin}/?post=${post.id}`);update({...post,shares_count:post.shares_count+1});setNotice('Post link copied to clipboard.')}catch(e){setNotice(errorMessage(e))}finally{setBusy(false)} }
  const reportPost = async () => { if(!user)return navigate('/login');const reason=window.prompt('Why are you reporting this post? (spam, harassment, harmful content, other)');if(!reason?.trim())return;try{await api.post('/reports/',{target_type:'post',target_post:post.id,reason:reason.trim().slice(0,80)});setNotice('Thanks. Your report has been sent for review.')}catch(e){setNotice(errorMessage(e))} }
  const removeComment = async (item:Comment) => {try{await api.delete(`/comments/${item.id}/`);setComments(current=>current.filter(row=>row.id!==item.id));update({...post,comments_count:Math.max(0,post.comments_count-1)})}catch(e){setNotice(errorMessage(e))}}
  const editComment = async (item:Comment) => {const value=window.prompt('Edit your comment',item.content);if(value===null||!value.trim())return;try{const {data}=await api.patch(`/comments/${item.id}/`,{content:value.trim()});setComments(current=>current.map(row=>row.id===item.id?data:row))}catch(e){setNotice(errorMessage(e))}}
  return <article className="post-card">
    <div className="post-header"><button className="avatar-button" onClick={()=>navigate(`/u/${post.author.username}`)}><Avatar user={post.author}/></button><div className="post-author"><button onClick={()=>navigate(`/u/${post.author.username}`)} className="text-button"><strong>{post.author.full_name || post.author.username}</strong></button><span>@{post.author.username} <i>·</i> {timeAgo(post.created_at)}</span></div><button className="icon-button more-button" aria-label="Post options" onClick={()=>setShowMenu(v=>!v)}><MoreHorizontal size={20}/></button>{showMenu&&<div className="post-menu">{ownPost?<><button onClick={()=>{setShowMenu(false);editPost()}}><Pencil size={15}/> Edit post</button><button className="danger-text" onClick={()=>{setShowMenu(false);deletePost()}}><Trash2 size={15}/> Delete post</button></>:<button onClick={()=>{setShowMenu(false);reportPost()}}><Flag size={15}/> Report post</button>}</div>}</div>
    {post.content&&<div className="post-copy">{post.content.split(/(#[\w]+)/g).map((part,i)=>part.startsWith('#')?<button className="hashtag" key={i} onClick={()=>navigate(`/search?q=${encodeURIComponent(part)}`)}>{part}</button>:<span key={i}>{part}</span>)}</div>}
    {!!post.images.length&&<div className={`post-media media-${Math.min(post.images.length,4)}`}>{post.images.slice(0,4).map((image,index)=><a key={image.id} href={image.url} target="_blank" rel="noreferrer" className={`post-image image-${index}`}><img src={image.url} alt={image.alt_text||'Post image'} loading="lazy"/>{index===3&&post.images.length>4&&<span>+{post.images.length-4}</span>}</a>)}</div>}
    <div className="post-stats"><button aria-label={`View people who liked this post (${post.likes_count})`} onClick={showLikedUsers}>{post.likes_count.toLocaleString()} {post.likes_count===1?'like':'likes'}</button><button onClick={toggleComments}>{post.comments_count} {post.comments_count===1?'comment':'comments'}</button><span>{post.shares_count} {post.shares_count===1?'share':'shares'}</span></div>
    {likesOpen&&<div className="liked-people-popover"><div className="liked-people-heading"><strong><Users size={14}/> Liked by</strong><button onClick={()=>setLikesOpen(false)} aria-label="Close likes"><X size={15}/></button></div>{likedUsers.length?likedUsers.map(person=><button className="liked-person" key={person.id} onClick={()=>navigate(`/u/${person.username}`)}><Avatar user={person} size="sm"/><span><strong>{person.full_name||person.username}</strong><small>@{person.username}</small></span></button>):<p className="empty-inline">No likes yet.</p>}</div>}
    <div className="post-actions"><button className={post.liked_by_me?'liked':''} onClick={toggleLike}><Heart size={19} fill={post.liked_by_me?'currentColor':'none'}/><span>{post.liked_by_me?'Liked':'Like'}</span></button><button onClick={toggleComments}><MessageCircle size={19}/><span>Comment</span></button><button onClick={sharePost} disabled={busy}><Share2 size={18}/><span>Share</span></button></div>
    {notice&&<div className="inline-notice" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Dismiss"><X size={14}/></button></div>}
    {commentsOpen&&<section className="comments-panel"><div className="comments-list">{comments.length===0?<p className="empty-inline">Be the first to leave a note.</p>:comments.map(item=><div className="comment-row" key={item.id}><button className="avatar-button" onClick={()=>navigate(`/u/${item.author.username}`)}><Avatar user={item.author} size="sm"/></button><div className="comment-bubble"><div><strong>{item.author.full_name||item.author.username}</strong><time>{timeAgo(item.created_at)}</time></div><p>{item.content}</p></div>{user?.id===item.author.id&&<button className="icon-button comment-delete" onClick={()=>editComment(item)} aria-label="Edit comment"><Pencil size={14}/></button>}{(user?.id===item.author.id||user?.is_staff)&&<button className="icon-button comment-delete" onClick={()=>removeComment(item)} aria-label="Delete comment"><Trash2 size={14}/></button>}</div>)}</div><form className="comment-form" onSubmit={addComment}><Avatar user={user} size="sm"/><input value={comment} onChange={e=>setComment(e.target.value)} placeholder="Write a comment…" maxLength={2000}/><button className="send-button" disabled={commentBusy||!comment.trim()} aria-label="Send comment"><Send size={17}/></button></form></section>}
    {editing&&<EditPostModal post={post} onClose={()=>setEditing(false)} onSave={update}/>}
  </article>
}
