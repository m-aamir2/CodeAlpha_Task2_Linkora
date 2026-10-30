import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ReactNode, useEffect } from 'react'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Feed from './pages/Feed'
import Profile from './pages/Profile'
import SearchPage from './pages/Search'
import Notifications from './pages/Notifications'
import Messages from './pages/Messages'
import Admin from './pages/Admin'
import Settings from './pages/Settings'
import Guidelines from './pages/Guidelines'
import { ForgotPassword, Login, Register } from './pages/Auth'

function Protected({children}:{children:ReactNode}){const {user}=useAuth();const location=useLocation();return user?children:<Navigate to="/login" replace state={{from:location.pathname}}/>}
function PublicAuth({children}:{children:ReactNode}){const {user}=useAuth();return user?<Navigate to="/" replace/>:children}
function Shell({children}:{children:ReactNode}){return <Layout>{children}</Layout>}
export default function App(){const {user}=useAuth();useEffect(()=>{document.title='Linkora — social, at your pace'},[]);return <Routes>
  <Route path="/login" element={<PublicAuth><Login/></PublicAuth>}/><Route path="/register" element={<PublicAuth><Register/></PublicAuth>}/><Route path="/forgot-password" element={<PublicAuth><ForgotPassword/></PublicAuth>}/>
  <Route path="/guidelines" element={<Shell><Guidelines/></Shell>}/>
  <Route path="/" element={<Protected><Shell><Feed/></Shell></Protected>}/><Route path="/u/:username" element={<Shell><Profile/></Shell>}/>
  <Route path="/search" element={<Protected><Shell><SearchPage/></Shell></Protected>}/><Route path="/notifications" element={<Protected><Shell><Notifications/></Shell></Protected>}/>
  <Route path="/messages" element={<Protected><Shell><Messages/></Shell></Protected>}/><Route path="/settings" element={<Protected><Shell><Settings/></Shell></Protected>}/>
  <Route path="/admin" element={<Protected><Shell>{user?.is_staff?<Admin/>:<Navigate to="/" replace/>}</Shell></Protected>}/>
  <Route path="*" element={<Navigate to="/" replace/>}/>
</Routes>}
