import { ChangeEvent, FormEvent, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ImagePlus, LoaderCircle, Send, X, Users, Sparkles } from 'lucide-react'
import { api, errorMessage } from '../services/api'
import { Page, Post, User } from '../types'
import { useAuth } from '../context/AuthContext'
import Avatar from '../components/Avatar'
import PostCard from '../components/PostCard'
import ImageCropper from '../components/ImageCropper'
import StoriesBar from '../components/StoriesBar'
import { uploadImageToBlob, usesDirectImageUploads } from '../services/blobUpload'

export default function Feed() {
  const { user }=useAuth()
  const [searchParams]=useSearchParams()
  const [posts,setPosts]=useState<Post[]>([])
  const [suggestions,setSuggestions]=useState<User[]>([])
  const [content,setContent]=useState('')
  const [images,setImages]=useState<File[]>([])
  const [previews,setPreviews]=useState<string[]>([])
  const [cropQueue,setCropQueue]=useState<File[]>([])
  const [cropIndex,setCropIndex]=useState(0)
  const [busy,setBusy]=useState(false)
  const [loading,setLoading]=useState(true)
  const [page,setPage]=useState(1)
  const [hasMore,setHasMore]=useState(false)
  const [error,setError]=useState('')
  const inputRef=useRef<HTMLInputElement>(null)
  const previewUrls=useRef<string[]>([])
  const fetchPosts=async(pageNo=1,append=false)=>{try{const {data}=await api.get<Page<Post>>(`/posts/?page=${pageNo}`);setPosts(prev=>{if(!append)return data.results;const known=new Set(prev.map(post=>post.id));return [...prev,...data.results.filter(post=>!known.has(post.id))]});setHasMore(Boolean(data.next));setPage(pageNo)}catch(e){setError(errorMessage(e))}finally{setLoading(false)}}
  const refreshLoadedPages=async(pageCount:number)=>{try{const refreshed:Post[]=[];const seen=new Set<number>();let hasNext=false;for(let pageNo=1;pageNo<=pageCount;pageNo++){const {data}=await api.get<Page<Post>>(`/posts/?page=${pageNo}`);data.results.forEach(post=>{if(!seen.has(post.id)){seen.add(post.id);refreshed.push(post)}});hasNext=Boolean(data.next);if(!hasNext)break}setPosts(refreshed);setHasMore(hasNext)}catch{/* Keep the current feed if a background refresh is temporarily unavailable. */}}
  useEffect(()=>{fetchPosts();api.get<Page<User>>('/users/').then(({data})=>setSuggestions(data.results.filter(person=>person.id!==user?.id&&!person.is_following).slice(0,4))).catch(()=>{})},[])
  useEffect(()=>{let refreshing=false;const refresh=()=>{if(document.visibilityState==='visible'&&!refreshing){refreshing=true;void refreshLoadedPages(page).finally(()=>{refreshing=false})}};const interval=window.setInterval(refresh,15000);window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);return()=>{window.clearInterval(interval);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh)}},[page])
  useEffect(()=>{const postId=searchParams.get('post');if(!postId)return;api.get<Post>(`/posts/${postId}/`).then(({data})=>setPosts(current=>[data,...current.filter(item=>item.id!==data.id)])).catch(()=>{});window.scrollTo({top:0,behavior:'smooth'})},[searchParams])
  useEffect(()=>()=>previewUrls.current.forEach(URL.revokeObjectURL),[])
  const chooseImages=(event:ChangeEvent<HTMLInputElement>)=>{
    const incoming=Array.from(event.target.files||[])
    const eligible=incoming.filter(file=>file.size<=8*1024*1024)
    const accepted=eligible.slice(0,Math.max(0,6-images.length))
    if(incoming.some(file=>file.size>8*1024*1024))setError('Images must be 8 MB or smaller.')
    else if(eligible.length>accepted.length)setError('A post can contain up to 6 images.')
    else setError('')
    if(accepted.length){setCropQueue(accepted);setCropIndex(0)}
    event.currentTarget.value=''
  }
  const advanceCrop=()=>{
    if(cropIndex+1>=cropQueue.length){setCropQueue([]);setCropIndex(0)}
    else setCropIndex(current=>current+1)
  }
  const applyCrop=(file:File)=>{
    const preview=URL.createObjectURL(file)
    previewUrls.current.push(preview)
    setImages(items=>[...items,file])
    setPreviews(items=>[...items,preview])
    advanceCrop()
  }
  const removeImage=(index:number)=>{const preview=previews[index];URL.revokeObjectURL(preview);previewUrls.current=previewUrls.current.filter(url=>url!==preview);setImages(items=>items.filter((_,i)=>i!==index));setPreviews(items=>items.filter((_,i)=>i!==index))}
  const submit=async(event:FormEvent)=>{event.preventDefault();if(!content.trim()&&!images.length)return;setBusy(true);setError('');try{let body:FormData|{content:string;uploaded_image_urls:string[]};if(usesDirectImageUploads){if(images.length&&!user)throw new Error('Please sign in again before uploading images.');const urls=await Promise.all(images.map(image=>uploadImageToBlob(image,user!.id,'posts')));body={content,uploaded_image_urls:urls}}else{const form=new FormData();form.append('content',content);images.forEach(image=>form.append('uploaded_images',image));body=form}const {data}=await api.post('/posts/',body,body instanceof FormData?{headers:{'Content-Type':'multipart/form-data'}}:undefined);setPosts(prev=>[data,...prev]);setContent('');setImages([]);previewUrls.current.forEach(URL.revokeObjectURL);previewUrls.current=[];setPreviews([])}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
  const removePost=(id:number)=>setPosts(items=>items.filter(post=>post.id!==id))
  const updatePost=(next:Post)=>setPosts(items=>items.map(post=>post.id===next.id?next:post))
  return <><div className="content-grid"><section className="feed-column"><div className="page-heading"><div><p className="eyebrow">YOUR LITTLE CORNER</p><h1>Good to see you, {user?.full_name?.split(' ')[0]||user?.username}.</h1><p className="muted">A fresh page, full of people you like.</p></div><span className="heading-spark"><Sparkles size={19}/></span></div><StoriesBar/>
    <form className="composer card" onSubmit={submit}><div className="composer-top"><Avatar user={user} size="md"/><textarea value={content} onChange={e=>setContent(e.target.value)} maxLength={5000} placeholder="What’s happening in your world?" aria-label="Write a post"/></div>{previews.length>0&&<div className="composer-previews">{previews.map((src,index)=><div className="composer-preview" key={src}><img src={src} alt="Upload preview"/><button type="button" onClick={()=>removeImage(index)} aria-label="Remove image"><X size={15}/></button></div>)}</div>}{error&&<p className="form-error">{error}</p>}<div className="composer-bottom"><div><button type="button" className="composer-tool" onClick={()=>inputRef.current?.click()}><ImagePlus size={17}/> Add photos</button><input ref={inputRef} className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={chooseImages}/><span className="composer-hint">{images.length?`${images.length}/6 photos`:'Share with your community'}</span></div><button className="button button-primary button-sm" disabled={busy||(!content.trim()&&!images.length)}>{busy?<LoaderCircle className="spin" size={16}/>:<Send size={15}/>} Post</button></div></form>
    <div className="feed-title-row"><h2>Your feed</h2><span><Users size={15}/> Latest from your community</span></div>
    {loading?<div className="skeleton-stack">{[1,2,3].map(row=><div className="skeleton-card" key={row}><div className="skeleton-line short"/><div className="skeleton-line"/><div className="skeleton-block"/></div>)}</div>:posts.length===0?<div className="empty-state card"><span className="empty-icon"><Sparkles/></span><h3>Your feed is waiting for a first post</h3><p>Say hello with a thought, a photo, or both.</p></div>:<div className="post-list">{posts.map(post=><PostCard key={post.id} initialPost={post} onDelete={removePost} onUpdate={updatePost}/>)}</div>}
    {!loading&&hasMore&&<button className="button button-secondary load-more" onClick={()=>fetchPosts(page+1,true)}><span>Load more stories</span></button>}
    </section><aside className="right-rail"><div className="rail-card welcome-card"><div className="welcome-icon"><Sparkles size={18}/></div><p className="eyebrow">A NOTE FROM LINKORA</p><h3>Make room for the good stuff.</h3><p>Share a small win, leave a thoughtful comment, or check in with someone you miss.</p></div><div className="rail-card people-card"><div className="rail-heading"><div><p className="eyebrow">GOOD PEOPLE</p><h3>Meet your neighbors</h3></div><Users size={18}/></div>{suggestions.length? suggestions.map(person=><a href={`/u/${person.username}`} className="suggestion" key={person.id}><Avatar user={person} size="sm"/><span><strong>{person.full_name||person.username}</strong><small>@{person.username}</small></span><span className="suggestion-plus">+</span></a>):<p className="muted rail-empty">You’re all caught up. Find more people in Explore.</p>}<a href="/search" className="text-link">Explore people <span>→</span></a></div><div className="rail-footer"><a href="/guidelines">Community guidelines</a><span>·</span><span>Made for meaningful moments</span><small>© Linkora 2026</small></div></aside></div>
    {cropQueue[cropIndex]&&<ImageCropper key={`${cropIndex}-${cropQueue[cropIndex].name}`} file={cropQueue[cropIndex]} index={cropIndex+1} total={cropQueue.length} onApply={applyCrop} onSkip={advanceCrop} onClose={()=>{setCropQueue([]);setCropIndex(0)}}/>}
  </>
}
