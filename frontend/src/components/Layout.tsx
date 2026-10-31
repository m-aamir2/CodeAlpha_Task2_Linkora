import { FormEvent, ReactNode, useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Bell, Clapperboard, Compass, Home, LogOut, Mail, Menu, Moon, Search, Settings, Shield, Sun, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationContext'
import Avatar from './Avatar'

const links = [
  { to: '/', label: 'Home', icon: Home }, { to: '/reels', label: 'Reels', icon: Clapperboard }, { to: '/search', label: 'Explore', icon: Compass },
  { to: '/notifications', label: 'Notifications', icon: Bell }, { to: '/messages', label: 'Messages', icon: Mail },
]

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const { unread } = useNotifications()
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  useEffect(() => { setMobileOpen(false); setSearch('') }, [location.pathname])
  const submitSearch = (event: FormEvent) => { event.preventDefault(); if (search.trim()) navigate(`/search?q=${encodeURIComponent(search.trim())}`) }
  const doLogout = async () => { await logout(); navigate('/login') }
  const sidebar = <>
    <NavLink to="/" className="brand"><span className="brand-mark">l</span><span>Linkora<span className="brand-period">.</span></span></NavLink>
    <form className="quick-search" onSubmit={submitSearch}><Search size={17}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search Linkora" aria-label="Search Linkora"/></form>
    <nav className="side-nav" aria-label="Main navigation">
      {links.map(({to,label,icon:Icon}) => <NavLink key={to} to={to} className={({isActive})=>`nav-link ${isActive?'active':''}`}><span className="nav-icon"><Icon size={19}/>{label==='Notifications' && unread>0 && <i className="nav-dot"/>}</span><span>{label}</span>{label==='Notifications' && unread>0 && <small className="nav-count">{unread>99?'99+':unread}</small>}</NavLink>)}
    </nav>
    <div className="sidebar-bottom">
      {user?.is_staff && <NavLink className={({isActive})=>`nav-link ${isActive?'active':''}`} to="/admin"><span className="nav-icon"><Shield size={19}/></span><span>Admin studio</span></NavLink>}
      <NavLink className={({isActive})=>`nav-link ${isActive?'active':''}`} to="/settings"><span className="nav-icon"><Settings size={19}/></span><span>Settings</span></NavLink>
      <NavLink className="sidebar-user" to={`/u/${user?.username}`}><Avatar user={user} size="sm"/><span className="sidebar-user-copy"><strong>{user?.full_name || user?.username}</strong><small>@{user?.username}</small></span><span className="online-dot"/></NavLink>
      <button className="nav-link quiet-button" onClick={()=>setDark(v=>!v)}><span className="nav-icon">{dark?<Sun size={19}/>:<Moon size={19}/>}</span><span>{dark?'Light mode':'Dark mode'}</span></button>
      <button className="nav-link quiet-button logout-link" onClick={doLogout}><span className="nav-icon"><LogOut size={19}/></span><span>Log out</span></button>
    </div>
  </>
  return <div className="app-shell">
    <aside className="sidebar">{sidebar}</aside>
    <header className="mobile-header"><button className="icon-button" onClick={()=>setMobileOpen(v=>!v)} aria-label="Open menu">{mobileOpen?<X size={20}/>:<Menu size={20}/>}</button><NavLink to="/" className="brand"><span className="brand-mark">l</span><span>Linkora<span className="brand-period">.</span></span></NavLink><NavLink to={`/u/${user?.username}`}><Avatar user={user} size="sm"/></NavLink></header>
    {mobileOpen && <div className="mobile-menu">{sidebar}</div>}
    <main className="main-area"><div className="mobile-search"><form className="quick-search" onSubmit={submitSearch}><Search size={17}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search people and posts"/></form></div>{children}</main>
    <nav className="mobile-tabs" aria-label="Mobile navigation">{links.filter(item=>item.to!=='/messages').map(({to,label,icon:Icon})=><NavLink key={to} to={to} aria-label={label} className={({isActive})=>`mobile-tab ${isActive?'active':''}`}><Icon size={20}/>{label==='Notifications'&&unread>0&&<i className="mobile-count">{unread>99?'99+':unread}</i>}</NavLink>)}<NavLink to="/messages" aria-label="Messages" className={({isActive})=>`mobile-tab ${isActive?'active':''}`}><Mail size={20}/></NavLink></nav>
  </div>
}
