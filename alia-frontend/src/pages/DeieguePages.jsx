import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { delegueAPI } from '../services/api'

export default function DeieguePages() {
  const [user, setUser] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [historique, setHistorique] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    let isMounted = true

    const loadData = async () => {
      setLoading(true)
      setError('')
      try {
        const [profilRes, historiqueRes] = await Promise.all([
          delegueAPI.getProfil(),
          delegueAPI.getHistorique(),
        ])

        if (!isMounted) return

        const profil = profilRes.data || {}
        setUser(profil)
        setAssignments(profil.assignments || [])
        setHistorique(historiqueRes.data?.sessions || [])
      } catch (err) {
        if (!isMounted) return
        console.error('[DeieguePages] loadData failed', {
          message: err?.message,
          status: err?.response?.status,
          data: err?.response?.data,
        })
        setError(err.response?.data?.error || 'Impossible de charger vos donnees.')
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    loadData()

    return () => {
      isMounted = false
    }
  }, [])

  const handleStartSimulation = (medicamentId) => {
    navigate(`/simulation/${medicamentId}`)
  }

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login')
  }

  if (loading) return <div style={styles.loading}>Chargement de votre espace delegue...</div>
  if (error) return <div style={styles.errorPage}>{error}</div>
  if (!user) return <div style={styles.errorPage}>Utilisateur introuvable.</div>

  const totalAssignments = assignments.length
  const finishedAssignments = assignments.filter((a) => a.statut === 'termine').length
  const inProgressAssignments = assignments.filter((a) => a.statut === 'en_cours').length
  const averageScore = totalAssignments
    ? Math.round(assignments.reduce((sum, a) => sum + (a.score_global || 0), 0) / totalAssignments)
    : 0

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.headerContent}>
          <div>
            <h1 style={styles.title}>Mon espace delegue</h1>
            <p style={styles.subtitle}>
              {user.first_name} {user.last_name} - {user.email}
              <span style={getNiveauBadgeStyle(user.niveau)}>
                {user.niveau}
              </span>
            </p>
          </div>
          <button onClick={handleLogout} style={styles.logoutBtn}>
            Déconnexion
          </button>
        </div>
      </div>

      <div style={styles.content}>
        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Medicaments assignes</p>
            <p style={styles.statValue}>{totalAssignments}</p>
          </div>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>En cours</p>
            <p style={styles.statValue}>{inProgressAssignments}</p>
          </div>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Termines</p>
            <p style={styles.statValue}>{finishedAssignments}</p>
          </div>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Score moyen</p>
            <p style={styles.statValue}>{averageScore}/100</p>
          </div>
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Mes medicaments assignes</h2>
          {assignments.length === 0 ? (
            <div style={styles.emptyState}>Aucun medicament assigne pour le moment.</div>
          ) : (
            <div style={styles.grid}>
              {assignments.map((assignment, index) => (
                <div key={assignment.id || `${assignment.medicament_id}-${index}`} style={styles.card}>
                  <h3 style={styles.cardTitle}>{assignment.medicament_nom}</h3>
                  <p style={{ ...styles.statut, color: getStatutColor(assignment.statut) }}>
                    Statut: {assignment.statut}
                  </p>

                  <div style={styles.scores}>
                    <p>Module 1: {assignment.score_module1 ?? 0}</p>
                    <p>Module 2: {assignment.score_module2 ?? 0}</p>
                    <p>Module 3: {assignment.score_module3 ?? 0}</p>
                    <p style={styles.scoreGlobal}>Score global: {assignment.score_global ?? 0}</p>
                  </div>

                  <div style={styles.scoreBar}>
                    <div
                      style={{
                        ...styles.scoreBarFill,
                        width: `${Math.min(Math.max(assignment.score_global ?? 0, 0), 100)}%`,
                      }}
                    />
                  </div>

                  <button onClick={() => handleStartSimulation(assignment.medicament_id)} style={styles.startBtn}>
                    Pratiquer
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Historique des sessions</h2>
          {historique.length === 0 ? (
            <div style={styles.emptyState}>Aucune session enregistree.</div>
          ) : (
            <div style={styles.list}>
              {historique.map((session) => (
                <div key={session.id} style={styles.item}>
                  <div>
                    <h4>{session.medicament || 'Session'}</h4>
                    <p style={styles.itemMeta}>
                      {session.mode || 'training'} • {session.interlocuteur || 'medecin'} • {session.started_at || '-'}
                    </p>
                  </div>
                  <div style={styles.itemScore}>
                    <span>{session.score_final ?? '-'} / 100</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function getStatutColor(statut) {
  switch(statut) {
    case 'termine': return '#00d2aa'
    case 'en_cours': return '#b4a0ff'
    case 'non_commence': return 'rgba(255,255,255,0.4)'
    default: return '#e8e4f8'
  }
}

function getNiveauBadgeStyle(niveau) {
  const baseStyle = {
    marginLeft: '12px',
    padding: '4px 12px',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: '600',
    display: 'inline-block'
  }

  switch(niveau?.toLowerCase()) {
    case 'débutant':
      return { ...baseStyle, background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5' }
    case 'intermédiaire':
      return { ...baseStyle, background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24' }
    case 'confirmé':
      return { ...baseStyle, background: 'rgba(16, 185, 129, 0.2)', color: '#6ee7b7' }
    default:
      return { ...baseStyle, background: 'rgba(124, 58, 237, 0.2)', color: '#a78bfa' }
  }
}

const styles = {
  container: {
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: '#0c0b14',
  },
  header: {
    padding: '24px',
    borderBottom: '1px solid rgba(180,160,255,0.1)',
    background: 'rgba(20, 18, 35, 0.5)',
  },
  headerContent: {
    maxWidth: '1200px',
    margin: '0 auto',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontSize: '28px',
    fontWeight: 700,
    color: '#e8e4f8',
    margin: 0,
  },
  subtitle: {
    fontSize: '13px',
    color: 'rgba(255,255,255,0.5)',
    margin: '4px 0 0 0',
  },
  logoutBtn: {
    padding: '8px 16px',
    background: 'rgba(255,255,255,0.1)',
    color: '#e8e4f8',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '13px',
  },
  loading: {
    height: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#e8e4f8',
  },
  errorPage: {
    height: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#ff6b6b',
  },
  content: {
    flex: 1,
    overflowY: 'auto',
    padding: '32px 24px',
  },
  statsGrid: {
    maxWidth: '1200px',
    margin: '0 auto 18px auto',
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
    gap: '12px',
    width: '100%',
  },
  statCard: {
    background: 'rgba(20, 18, 35, 0.6)',
    border: '1px solid rgba(180,160,255,0.15)',
    borderRadius: '10px',
    padding: '14px',
  },
  statLabel: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: '12px',
  },
  statValue: {
    marginTop: '4px',
    color: '#e8e4f8',
    fontWeight: 700,
    fontSize: '22px',
  },
  section: {
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%',
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: 600,
    marginBottom: '24px',
    color: '#e8e4f8',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '20px',
  },
  card: {
    background: 'rgba(20, 18, 35, 0.6)',
    border: '1px solid rgba(180,160,255,0.1)',
    borderRadius: '10px',
    padding: '20px',
  },
  scores: {
    display: 'grid',
    gap: '4px',
    color: 'rgba(255,255,255,0.8)',
    fontSize: '13px',
    marginBottom: '10px',
  },
  scoreGlobal: {
    color: '#b4a0ff',
    fontWeight: 600,
  },
  cardTitle: {
    fontSize: '16px',
    fontWeight: 600,
    marginBottom: '16px',
    color: '#e8e4f8',
  },
  scoreBar: {
    width: '100%',
    height: '8px',
    background: 'rgba(255,255,255,0.1)',
    borderRadius: '4px',
    overflow: 'hidden',
    marginBottom: '8px',
  },
  scoreBarFill: {
    height: '100%',
    background: 'linear-gradient(90deg, #b4a0ff, #00d2aa)',
    transition: 'width 0.3s',
  },
  score: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#b4a0ff',
    marginBottom: '8px',
  },
  statut: {
    fontSize: '12px',
    marginBottom: '16px',
  },
  startBtn: {
    width: '100%',
    padding: '10px',
    background: 'linear-gradient(135deg, #b4a0ff, #00d2aa)',
    color: '#0c0b14',
    fontWeight: 600,
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    marginBottom: '24px',
  },
  item: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '16px',
    background: 'rgba(20, 18, 35, 0.6)',
    border: '1px solid rgba(180,160,255,0.1)',
    borderRadius: '8px',
  },
  itemMeta: {
    fontSize: '12px',
    color: 'rgba(255,255,255,0.5)',
    marginTop: '4px',
  },
  itemScore: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#b4a0ff',
  },
  emptyState: {
    padding: '16px',
    borderRadius: '8px',
    background: 'rgba(255,255,255,0.05)',
    color: 'rgba(255,255,255,0.7)',
    border: '1px solid rgba(180,160,255,0.1)',
  },
}
