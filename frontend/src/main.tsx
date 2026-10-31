import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './context/AuthContext'
import { CallProvider } from './context/CallContext'
import { NotificationProvider } from './context/NotificationContext'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><BrowserRouter><AuthProvider><NotificationProvider><CallProvider><App /></CallProvider></NotificationProvider></AuthProvider></BrowserRouter></React.StrictMode>,
)
