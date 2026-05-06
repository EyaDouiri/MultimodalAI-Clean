import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { delegueAPI, simulationAPI } from '../services/api'
import AvatarCanvas from '../components/AvatarCanvas'

function apiErrorMessage(err, fallback) {
  const payload = err?.response?.data
  if (payload?.error) return payload.error
  if (typeof payload === 'string' && payload.trim()) {
    return `${fallback} (backend ${err?.response?.status || 'error'})`
  }
  return err?.message || fallback
}

export default function SimulationPage() {
  const navigate = useNavigate()
  const { medicamentId } = useParams()
  const videoRef = useRef(null)
  const messagesEndRef = useRef(null)

  const [mode, setMode] = useState('text')
  const [interlocuteur, setInterlocuteur] = useState('medecin')
  const [sessionActive, setSessionActive] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [bilan, setBilan] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historySessions, setHistorySessions] = useState([])
  const [loadingStart, setLoadingStart] = useState(false)
  const [loadingSend, setLoadingSend] = useState(false)
  const [loadingStop, setLoadingStop] = useState(false)
  const [cameraEnabled, setCameraEnabled] = useState(false)
  const [cameraError, setCameraError] = useState('')

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    let mounted = true
    const loadHistory = async () => {
      try {
        const res = await delegueAPI.getHistorique()
        if (!mounted) return
        setHistorySessions(res.data?.sessions || [])
      } catch (e) {
        // non-blocking
      }
    }
    loadHistory()
    return () => {
      mounted = false
    }
  }, [])

  const historyPreview = useMemo(() => historySessions.slice(0, 12), [historySessions])

  const toggleCamera = async (turnOn) => {
    try {
      if (turnOn) {
        setCameraError('')
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
        setCameraEnabled(true)
        return
      }

      if (videoRef.current?.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks()
        tracks.forEach((track) => track.stop())
        videoRef.current.srcObject = null
      }
      setCameraEnabled(false)
    } catch (e) {
      setCameraError('Camera indisponible sur ce navigateur ou sans permission.')
    }
  }

  useEffect(() => {
    const shouldEnable = mode === 'voice' || sessionActive
    toggleCamera(shouldEnable)
    return () => {
      if (videoRef.current?.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks()
        tracks.forEach((track) => track.stop())
      }
    }
  }, [mode, sessionActive])

  const handleModeChange = (nextMode) => {
    setMode(nextMode)
  }

  const loadHistory = async () => {
    const res = await delegueAPI.getHistorique()
    setHistorySessions(res.data?.sessions || [])
  }

  const handleStart = async () => {
    setError('')
    setBilan('')
    setLoadingStart(true)
    try {
      await simulationAPI.start(Number(medicamentId || 1), 'training', interlocuteur)
      setSessionActive(true)
      setMessages([
        {
          role: 'assistant',
          text: `Simulation demarree (${interlocuteur}). Presentez votre medicament.`,
          ts: Date.now(),
        },
      ])
    } catch (err) {
      console.error('[SimulationPage] start failed', err)
      setError(apiErrorMessage(err, 'Impossible de demarrer la simulation.'))
    } finally {
      setLoadingStart(false)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || !sessionActive) return
    const userMsg = input.trim()
    setInput('')
    setError('')
    setMessages((prev) => [...prev, { role: 'user', text: userMsg, ts: Date.now() }])
    setLoadingSend(true)
    try {
      const res = await simulationAPI.message(userMsg)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: res.data?.response || 'Pas de reponse.', ts: Date.now() },
      ])
    } catch (err) {
      console.error('[SimulationPage] message failed', err)
      setError(apiErrorMessage(err, "Erreur lors de l'envoi."))
    } finally {
      setLoadingSend(false)
    }
  }

  const handleStop = async () => {
    setError('')
    setLoadingStop(true)
    try {
      const res = await simulationAPI.stop()
      setBilan(res.data?.bilan || 'Simulation terminee.')
      setSessionActive(false)
      await loadHistory()
    } catch (err) {
      console.error('[SimulationPage] stop failed', err)
      setError(apiErrorMessage(err, "Erreur lors de l'arret."))
    } finally {
      setLoadingStop(false)
    }
  }

  const handleCommand = async (command) => {
    if (!sessionActive) return
    try {
      const res = await simulationAPI.command(command)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: res.data?.result || `Commande ${command} executee.`, ts: Date.now() },
      ])
      if (command === 'save') {
        setSessionActive(false)
        await loadHistory()
      }
    } catch (err) {
      console.error('[SimulationPage] command failed', command, err)
      setError(apiErrorMessage(err, `Erreur commande ${command}.`))
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.leftPanel}>
        <div style={styles.leftTop}>
          <span style={styles.persona}>ALIA</span>
          <span style={styles.pill}>{sessionActive ? 'Session active' : 'Session inactive'}</span>
        </div>
        <div style={styles.avatarStage}>
          <AvatarCanvas active={sessionActive || loadingSend} />
          {cameraEnabled ? (
            <div style={styles.cameraCard}>
              <video ref={videoRef} autoPlay muted playsInline style={styles.video} />
              <span style={styles.cameraLabel}>Camera delegue</span>
            </div>
          ) : (
            <div style={styles.cameraHint}>Mode voix pour activer la camera</div>
          )}
          {cameraError && <div style={styles.cameraError}>{cameraError}</div>}
        </div>
        <div style={styles.leftBottom}>Simulation medicament #{medicamentId || '-'}</div>
      </div>

      <div style={styles.rightPanel}>
        <div style={styles.topbar}>
          <div>
            <h2 style={styles.title}>Session de formation</h2>
            <p style={styles.subtitle}>Training delegue pharmaco</p>
          </div>
          <div style={styles.topbarActions}>
            <button style={{ ...styles.modeBtn, ...(mode === 'text' ? styles.modeBtnActive : {}) }} onClick={() => handleModeChange('text')}>
              Texte
            </button>
            <button style={{ ...styles.modeBtn, ...(mode === 'voice' ? styles.modeBtnActive : {}) }} onClick={() => handleModeChange('voice')}>
              Voix
            </button>
            <button style={styles.ghostBtn} onClick={() => setHistoryOpen((v) => !v)}>
              Historique
            </button>
            <button style={styles.ghostBtn} onClick={() => toggleCamera(!cameraEnabled)}>
              {cameraEnabled ? 'Couper camera' : 'Activer camera'}
            </button>
          </div>
        </div>

        <div style={styles.quickRow}>
          <select value={interlocuteur} onChange={(e) => setInterlocuteur(e.target.value)} style={styles.select}>
            <option value="medecin">Interlocuteur: medecin</option>
            <option value="pharmacien">Interlocuteur: pharmacien</option>
          </select>
          <button style={styles.quickBtn} onClick={() => handleCommand('eval')} disabled={!sessionActive}>eval</button>
          <button style={styles.quickBtn} onClick={() => handleCommand('next')} disabled={!sessionActive}>next</button>
          <button style={styles.quickBtn} onClick={() => handleCommand('save')} disabled={!sessionActive}>save</button>
        </div>

        {error && <div style={styles.errorBox}>{error}</div>}
        {bilan && !sessionActive && <div style={styles.successBox}>{bilan}</div>}

        <div style={styles.chatWrap}>
          <div style={styles.messages}>
            {messages.length === 0 ? (
              <div style={styles.empty}>Demarrez une simulation pour discuter avec Alia.</div>
            ) : (
              messages.map((m, i) => (
                <div key={`${m.ts || i}-${i}`} style={{ ...styles.msg, ...(m.role === 'user' ? styles.msgUser : styles.msgAssistant) }}>
                  {m.text}
                </div>
              ))
            )}
            {loadingSend && <div style={styles.typing}>ALIA est en train de repondre...</div>}
            <div ref={messagesEndRef} />
          </div>

          {historyOpen && (
            <div style={styles.history}>
              <h4 style={styles.historyTitle}>Historique recent</h4>
              {historyPreview.length === 0 ? (
                <p style={styles.historyEmpty}>Aucune session disponible.</p>
              ) : (
                historyPreview.map((s) => (
                  <div key={s.id} style={styles.historyItem}>
                    <span>{s.medicament || '-'}</span>
                    <span>{s.score_final ?? '-'} / 100</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div style={styles.inputRow}>
          {!sessionActive ? (
            <>
              <button style={styles.primaryBtn} onClick={handleStart} disabled={loadingStart}>
                {loadingStart ? 'Demarrage...' : 'Demarrer simulation'}
              </button>
              <button style={styles.ghostBtn} onClick={() => navigate('/delegue')}>Retour</button>
            </>
          ) : (
            <>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Entrez votre message..."
                style={styles.input}
                disabled={loadingSend || loadingStop}
              />
              <button style={styles.primaryBtn} onClick={handleSend} disabled={loadingSend || loadingStop}>Envoyer</button>
              <button style={styles.stopBtn} onClick={handleStop} disabled={loadingStop}>
                {loadingStop ? 'Arret...' : 'Terminer'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

const styles = {
  page: {
    height: '100vh',
    display: 'grid',
    gridTemplateColumns: '340px 1fr',
    background: 'radial-gradient(circle at 20% 10%, #121827 0%, #070a10 55%)',
    color: '#e2e8f0',
  },
  leftPanel: {
    position: 'relative',
    borderRight: '1px solid rgba(255,255,255,.08)',
    background: 'linear-gradient(180deg, #0d1320 0%, #090d15 100%)',
    display: 'flex',
    flexDirection: 'column',
  },
  leftTop: {
    position: 'absolute',
    top: '14px',
    left: '14px',
    right: '14px',
    zIndex: 1,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  persona: {
    fontWeight: 700,
    letterSpacing: '.08em',
  },
  pill: {
    fontSize: '11px',
    background: 'rgba(0,0,0,.4)',
    border: '1px solid rgba(255,255,255,.1)',
    borderRadius: '10px',
    padding: '4px 8px',
  },
  avatarStage: {
    flex: 1,
    display: 'grid',
    placeItems: 'center',
    position: 'relative',
    overflow: 'hidden',
  },
  cameraCard: {
    position: 'absolute',
    right: '12px',
    bottom: '12px',
    width: '140px',
    borderRadius: '10px',
    overflow: 'hidden',
    border: '1px solid rgba(255,255,255,.18)',
    background: 'rgba(0,0,0,.35)',
    backdropFilter: 'blur(6px)',
  },
  video: {
    width: '100%',
    height: '100px',
    objectFit: 'cover',
    display: 'block',
    transform: 'scaleX(-1)',
  },
  cameraLabel: {
    display: 'block',
    fontSize: '10px',
    padding: '6px 8px',
    color: 'rgba(255,255,255,.75)',
  },
  cameraHint: {
    position: 'absolute',
    bottom: '18px',
    left: '18px',
    right: '18px',
    fontSize: '11px',
    color: 'rgba(255,255,255,.6)',
    textAlign: 'center',
    border: '1px solid rgba(255,255,255,.12)',
    borderRadius: '8px',
    padding: '8px',
    background: 'rgba(255,255,255,.03)',
  },
  cameraError: {
    position: 'absolute',
    top: '56px',
    left: '18px',
    right: '18px',
    fontSize: '11px',
    color: '#fecaca',
    border: '1px solid rgba(248,113,113,.35)',
    borderRadius: '8px',
    padding: '8px',
    background: 'rgba(248,113,113,.12)',
  },
  leftBottom: {
    padding: '10px 14px',
    borderTop: '1px solid rgba(255,255,255,.08)',
    fontSize: '12px',
    background: '#0e1218',
  },
  rightPanel: {
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  },
  topbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 20px',
    borderBottom: '1px solid rgba(255,255,255,.08)',
    background: 'rgba(10,14,22,.9)',
  },
  title: {
    margin: 0,
    fontSize: '22px',
  },
  subtitle: {
    margin: 0,
    fontSize: '12px',
    color: 'rgba(255,255,255,.55)',
  },
  topbarActions: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  modeBtn: {
    border: '1px solid rgba(255,255,255,.2)',
    background: 'transparent',
    color: '#e2e8f0',
    borderRadius: '8px',
    padding: '6px 12px',
    fontSize: '12px',
  },
  modeBtnActive: {
    background: '#7c6af5',
    borderColor: '#7c6af5',
  },
  ghostBtn: {
    border: '1px solid rgba(255,255,255,.2)',
    background: 'rgba(255,255,255,.06)',
    color: '#e2e8f0',
    borderRadius: '8px',
    padding: '8px 12px',
  },
  quickRow: {
    display: 'flex',
    gap: '8px',
    padding: '10px 20px',
    borderBottom: '1px solid rgba(255,255,255,.08)',
  },
  select: {
    background: '#141a24',
    color: '#e2e8f0',
    border: '1px solid rgba(255,255,255,.14)',
    borderRadius: '8px',
    padding: '6px 8px',
    minWidth: '210px',
  },
  quickBtn: {
    background: 'rgba(255,255,255,.06)',
    color: '#a78bfa',
    border: '1px solid rgba(255,255,255,.12)',
    borderRadius: '8px',
    padding: '6px 10px',
    fontSize: '12px',
  },
  errorBox: {
    margin: '8px 20px 0 20px',
    padding: '10px 12px',
    borderRadius: '8px',
    background: 'rgba(248,113,113,.12)',
    color: '#fca5a5',
    border: '1px solid rgba(248,113,113,.4)',
    fontSize: '13px',
  },
  successBox: {
    margin: '8px 20px 0 20px',
    padding: '10px 12px',
    borderRadius: '8px',
    background: 'rgba(52,211,153,.12)',
    color: '#86efac',
    border: '1px solid rgba(52,211,153,.4)',
    fontSize: '13px',
  },
  chatWrap: {
    flex: 1,
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    minHeight: 0,
  },
  messages: {
    padding: '14px 20px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  empty: {
    margin: 'auto',
    color: 'rgba(255,255,255,.5)',
    textAlign: 'center',
  },
  msg: {
    maxWidth: '78%',
    padding: '11px 13px',
    borderRadius: '12px',
    lineHeight: 1.5,
    fontSize: '14px',
  },
  msgAssistant: {
    background: 'linear-gradient(180deg, #141a24, #111827)',
    border: '1px solid rgba(255,255,255,.1)',
    alignSelf: 'flex-start',
  },
  msgUser: {
    background: 'linear-gradient(135deg, #7c6af5, #6d5ce6)',
    color: '#fff',
    alignSelf: 'flex-end',
  },
  typing: {
    fontSize: '12px',
    color: 'rgba(255,255,255,.65)',
  },
  history: {
    width: '280px',
    borderLeft: '1px solid rgba(255,255,255,.08)',
    padding: '12px',
    overflowY: 'auto',
    background: '#0e1218',
  },
  historyTitle: {
    margin: '0 0 8px 0',
    color: '#a78bfa',
    fontSize: '13px',
  },
  historyEmpty: {
    color: 'rgba(255,255,255,.6)',
    fontSize: '12px',
  },
  historyItem: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid rgba(255,255,255,.08)',
    fontSize: '12px',
  },
  inputRow: {
    borderTop: '1px solid rgba(255,255,255,.08)',
    padding: '12px 20px',
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  input: {
    flex: 1,
    minWidth: 0,
    background: '#141a24',
    color: '#e2e8f0',
    border: '1px solid rgba(255,255,255,.14)',
    borderRadius: '10px',
    padding: '10px 12px',
  },
  primaryBtn: {
    background: '#7c6af5',
    color: '#fff',
    border: '1px solid #7c6af5',
    borderRadius: '10px',
    padding: '9px 14px',
    fontWeight: 600,
  },
  stopBtn: {
    background: 'rgba(248,113,113,.15)',
    color: '#fca5a5',
    border: '1px solid rgba(248,113,113,.35)',
    borderRadius: '10px',
    padding: '9px 12px',
    fontWeight: 600,
  },
}
