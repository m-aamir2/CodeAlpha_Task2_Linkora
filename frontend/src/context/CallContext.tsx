import { createContext, ReactNode, useContext, useEffect, useRef, useState } from 'react'
import { Camera, CameraOff, Mic, MicOff, Phone, PhoneOff, Volume2, VolumeX } from 'lucide-react'
import { api, errorMessage } from '../services/api'
import { Call, User } from '../types'
import { useAuth } from './AuthContext'
import Avatar from '../components/Avatar'
import './CallContext.css'

type CallContextValue = { startCall: (recipient: User, conversation: number, kind: 'audio'|'video') => Promise<void> }
const CallContext = createContext<CallContextValue | null>(null)
const terminalStatuses = new Set(['rejected', 'ended', 'missed'])
const iceServers: RTCIceServer[] = (() => {
  try {
    const configured = import.meta.env.VITE_ICE_SERVERS
    return configured ? JSON.parse(configured) as RTCIceServer[] : [{ urls: 'stun:stun.l.google.com:19302' }]
  } catch { return [{ urls: 'stun:stun.l.google.com:19302' }] }
})()

export function CallProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [call, setCall] = useState<Call | null>(null)
  const [incoming, setIncoming] = useState<Call | null>(null)
  const [localStream, setLocalStream] = useState<MediaStream | null>(null)
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null)
  const [muted, setMuted] = useState(false)
  const [cameraOff, setCameraOff] = useState(false)
  const [speakerOn, setSpeakerOn] = useState(true)
  const [callError, setCallError] = useState('')
  const peer = useRef<RTCPeerConnection | null>(null)
  const localStreamRef = useRef<MediaStream | null>(null)
  const callRef = useRef<Call | null>(null)
  const pendingLocal = useRef<RTCIceCandidateInit[]>([])
  const pendingRemote = useRef<RTCIceCandidateInit[]>([])
  const signalCursor = useRef(0)
  const remoteDescriptionSet = useRef(false)
  const remoteAudio = useRef<HTMLAudioElement>(null)
  const remoteVideo = useRef<HTMLVideoElement>(null)
  const localVideo = useRef<HTMLVideoElement>(null)
  const closeTimer = useRef<number | null>(null)

  useEffect(() => { callRef.current = call }, [call])
  useEffect(() => { if (remoteAudio.current) { remoteAudio.current.srcObject = remoteStream; remoteAudio.current.muted = !speakerOn } }, [remoteStream, speakerOn])
  useEffect(() => { if (remoteVideo.current) remoteVideo.current.srcObject = remoteStream }, [remoteStream])
  useEffect(() => { localStreamRef.current = localStream }, [localStream])
  useEffect(() => { if (localVideo.current) localVideo.current.srcObject = localStream }, [localStream])

  const disposePeer = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current)
    peer.current?.close(); peer.current = null
    localStreamRef.current?.getTracks().forEach(track => track.stop())
    localStreamRef.current = null
    callRef.current = null; pendingLocal.current = []; pendingRemote.current = []; signalCursor.current = 0; remoteDescriptionSet.current = false
    setLocalStream(null); setRemoteStream(null); setCall(null); setIncoming(null)
    setMuted(false); setCameraOff(false); setSpeakerOn(true)
  }
  const makePeer = (stream: MediaStream) => {
    const connection = new RTCPeerConnection({ iceServers })
    stream.getTracks().forEach(track => connection.addTrack(track, stream))
    connection.ontrack = event => setRemoteStream(event.streams[0] || new MediaStream([event.track]))
    connection.onicecandidate = event => {
      if (!event.candidate) return
      const candidate = event.candidate.toJSON()
      const active = callRef.current
      if (active) void api.post(`/calls/${active.id}/signals/`, { candidate }).catch(() => {})
      else pendingLocal.current.push(candidate)
    }
    peer.current = connection
    return connection
  }
  const flushLocalCandidates = (callId: number) => {
    const candidates = pendingLocal.current.splice(0)
    candidates.forEach(candidate => void api.post(`/calls/${callId}/signals/`, { candidate }).catch(() => {}))
  }
  const flushRemoteCandidates = async () => {
    const connection = peer.current
    if (!connection?.remoteDescription) return
    remoteDescriptionSet.current = true
    const candidates = pendingRemote.current.splice(0)
    for (const candidate of candidates) await connection.addIceCandidate(candidate).catch(() => {})
  }
  const getMedia = async (kind: Call['kind']) => navigator.mediaDevices.getUserMedia({ audio: true, video: kind === 'video' })

  const startCall = async (recipient: User, conversation: number, kind: Call['kind']) => {
    setCallError('')
    if (callRef.current || incoming) { setCallError('Finish the current call before starting another.'); return }
    try {
      const stream = await getMedia(kind)
      localStreamRef.current = stream
      setLocalStream(stream)
      const connection = makePeer(stream)
      const offer = await connection.createOffer()
      await connection.setLocalDescription(offer)
      const { data } = await api.post<Call>('/calls/', { recipient: recipient.id, conversation, kind, offer: connection.localDescription?.toJSON() })
      callRef.current = data; setCall(data); flushLocalCandidates(data.id)
    } catch (cause) {
      peer.current?.close(); peer.current = null
      localStreamRef.current?.getTracks().forEach(track => track.stop())
      localStreamRef.current = null
      setLocalStream(null); setCallError(errorMessage(cause))
    }
  }

  const acceptCall = async (incomingCall: Call) => {
    setCallError('')
    try {
      const stream = await getMedia(incomingCall.kind)
      localStreamRef.current = stream
      setLocalStream(stream)
      callRef.current = incomingCall
      const connection = makePeer(stream)
      await connection.setRemoteDescription(JSON.parse(incomingCall.offer) as RTCSessionDescriptionInit)
      await flushRemoteCandidates()
      const answer = await connection.createAnswer()
      await connection.setLocalDescription(answer)
      const { data } = await api.post<Call>(`/calls/${incomingCall.id}/accept/`, { answer: connection.localDescription?.toJSON() })
      callRef.current = data; setCall(data); setIncoming(null); flushLocalCandidates(data.id)
    } catch (cause) {
      peer.current?.close(); peer.current = null
      localStreamRef.current?.getTracks().forEach(track => track.stop())
      localStreamRef.current = null
      setLocalStream(null); setCallError(errorMessage(cause))
    }
  }
  const rejectCall = async (incomingCall: Call) => {
    try { await api.post(`/calls/${incomingCall.id}/reject/`) } catch (cause) { setCallError(errorMessage(cause)) }
    setIncoming(null)
  }
  const endCall = async () => {
    const active = callRef.current
    if (!active) return disposePeer()
    try { const { data } = await api.post<Call>(`/calls/${active.id}/end/`); setCall(data); callRef.current = data }
    catch (cause) { setCallError(errorMessage(cause)) }
    closeTimer.current = window.setTimeout(disposePeer, 1200)
  }

  useEffect(() => {
    if (!user || call) return
    let alive = true
    const pollIncoming = async () => {
      try {
        const { data } = await api.get<Call[]>('/calls/')
        if (alive && !callRef.current) setIncoming(data[0] || null)
      } catch { /* A transient poll error should not interrupt the app. */ }
    }
    void pollIncoming()
    const timer = window.setInterval(pollIncoming, 2000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [user?.id, call?.id, incoming?.id])

  useEffect(() => {
    if (!call || !user) return
    let alive = true
    let polling = false
    const pollCall = async () => {
      if (polling) return
      polling = true
      try {
        const { data: latest } = await api.get<Call>(`/calls/${call.id}/`)
        if (!alive) return
        callRef.current = latest; setCall(latest)
        if (terminalStatuses.has(latest.status)) {
          if (closeTimer.current === null) closeTimer.current = window.setTimeout(disposePeer, latest.status === 'ended' ? 1500 : 3500)
          return
        }
        const connection = peer.current
        if (connection && latest.answer && !connection.remoteDescription) {
          await connection.setRemoteDescription(JSON.parse(latest.answer) as RTCSessionDescriptionInit)
          await flushRemoteCandidates()
        }
        const { data: signalData } = await api.get<{ results: { id: number; payload: RTCIceCandidateInit }[]; next_after: number }>(`/calls/${call.id}/signals/?after=${signalCursor.current}`)
        signalCursor.current = signalData.next_after
        for (const signal of signalData.results) {
          if (connection?.remoteDescription) await connection.addIceCandidate(signal.payload).catch(() => {})
          else pendingRemote.current.push(signal.payload)
        }
      } catch { /* Calls remain usable during brief signaling network delays. */ }
      finally { polling = false }
    }
    void pollCall()
    const timer = window.setInterval(pollCall, 1100)
    return () => { alive = false; window.clearInterval(timer) }
  }, [call?.id, user?.id])

  const toggleMute = () => { const next = !muted; localStream?.getAudioTracks().forEach(track => { track.enabled = !next }); setMuted(next) }
  const toggleCamera = () => { const next = !cameraOff; localStream?.getVideoTracks().forEach(track => { track.enabled = !next }); setCameraOff(next) }
  const toggleSpeaker = () => setSpeakerOn(value => !value)
  const remotePerson = call ? call.caller.id === user?.id ? call.recipient : call.caller : incoming?.caller
  const incomingType = incoming?.kind === 'video' ? 'video' : 'audio'

  return <CallContext.Provider value={{ startCall }}>
    {children}
    <audio ref={remoteAudio} autoPlay playsInline/>
    {callError && <div className="call-error-toast" role="alert">{callError}<button onClick={() => setCallError('')}>×</button></div>}
    {incoming && <div className="call-overlay-backdrop"><section className="call-overlay incoming-call" role="dialog" aria-modal="true"><div className="call-avatar"><Avatar user={incoming.caller} size="xl"/></div><p className="eyebrow">INCOMING {incomingType.toUpperCase()} CALL</p><h2>{incoming.caller.full_name || incoming.caller.username}</h2><p>is calling you</p><div className="call-controls"><button className="accept-call" aria-label="Accept call" onClick={() => void acceptCall(incoming)}><Phone/></button><button className="reject-call" aria-label="Reject call" onClick={() => void rejectCall(incoming)}><PhoneOff/></button></div></section></div>}
    {call && remotePerson && <div className={`call-overlay-backdrop ${call.kind === 'video' ? 'video-call-backdrop' : ''}`}><section className={`call-overlay ${call.kind === 'video' ? 'video-call' : ''}`} role="dialog" aria-modal="true" aria-label={`${call.kind} call with ${remotePerson.username}`}>
      {call.kind === 'video' && <><video ref={remoteVideo} className="call-remote-video" autoPlay playsInline muted/><video ref={localVideo} className="call-local-video" autoPlay playsInline muted/></>}
      <div className="call-person-info">{call.kind === 'audio' && <Avatar user={remotePerson} size="xl"/>}<h2>{remotePerson.full_name || remotePerson.username}</h2><p>{call.status === 'ringing' ? 'Calling…' : call.status === 'accepted' ? 'Connected' : call.status === 'missed' ? 'Missed call' : call.status === 'rejected' ? 'Call declined' : 'Call ended'}</p></div>
      {call.kind === 'audio' && <video ref={localVideo} className="call-local-audio-preview" autoPlay playsInline muted/>}
      <div className="call-controls"><button className={muted ? 'control-off' : ''} onClick={toggleMute} aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}>{muted ? <MicOff/> : <Mic/>}</button><button className={!speakerOn ? 'control-off' : ''} onClick={toggleSpeaker} aria-label={speakerOn ? 'Turn speaker off' : 'Turn speaker on'}>{speakerOn ? <Volume2/> : <VolumeX/>}</button>{call.kind === 'video' && <button className={cameraOff ? 'control-off' : ''} onClick={toggleCamera} aria-label={cameraOff ? 'Turn camera on' : 'Turn camera off'}>{cameraOff ? <CameraOff/> : <Camera/>}</button>}<button className="reject-call" onClick={() => void endCall()} aria-label="End call"><PhoneOff/></button></div>
    </section></div>}
  </CallContext.Provider>
}

export function useCalls() {
  const value = useContext(CallContext)
  if (!value) throw new Error('useCalls must be used inside CallProvider')
  return value
}
