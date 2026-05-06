import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminAPI } from '../services/api'

export default function AdminPage() {
  const [delegues, setDelegues] = useState([])
  const [medicaments, setMedicaments] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingAssign, setLoadingAssign] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [form, setForm] = useState({
    delegueId: '',
    medicamentId: '',
  })
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [activeDelegueId, setActiveDelegueId] = useState(null)
  const [creatingDelegue, setCreatingDelegue] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createMessage, setCreateMessage] = useState('')
  const [newDelegue, setNewDelegue] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
  })
  const [editingAssignment, setEditingAssignment] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [updatingAssignment, setUpdatingAssignment] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [deletingAssignment, setDeletingAssignment] = useState(false)
  const navigate = useNavigate()
  const selectedDelegue = delegues.find((d) => String(d.id) === String(form.delegueId))
  const assignedMedicamentIds = new Set((selectedDelegue?.assignments || []).map((a) => a.medicament_id))
  const availableMedicaments = form.delegueId
    ? medicaments.filter((m) => !assignedMedicamentIds.has(m.id))
    : medicaments
  const activeDelegue = delegues.find((d) => d.id === activeDelegueId) || null
  const filteredDelegues = useMemo(() => {
    return delegues.filter((delegue) => {
      const text = `${delegue.first_name || ''} ${delegue.last_name || ''} ${delegue.email || ''}`.toLowerCase()
      const searchOk = text.includes(search.trim().toLowerCase())
      if (!searchOk) return false

      if (statusFilter === 'all') return true
      if (statusFilter === 'none') return (delegue.assignments || []).length === 0
      return (delegue.assignments || []).some((a) => a.statut === statusFilter)
    })
  }, [delegues, search, statusFilter])

  useEffect(() => {
    let isMounted = true

    const loadData = async () => {
      setLoading(true)
      setError('')

      try {
        const [deleguesResponse, medicamentsResponse, assignmentsResponse] = await Promise.all([
          adminAPI.getDelegues(),
          adminAPI.getMedicaments(),
          adminAPI.getAssignments(),
        ])

        if (!isMounted) return

        const deleguesRaw = deleguesResponse.data?.delegues || []
        const assignments = assignmentsResponse.data?.assignments || []
        const assignmentsByDelegue = assignments.reduce((acc, assignment) => {
          if (!acc[assignment.delegue_id]) acc[assignment.delegue_id] = []
          acc[assignment.delegue_id].push(assignment)
          return acc
        }, {})
        const deleguesWithAssignments = deleguesRaw.map((delegue) => ({
          ...delegue,
          assignments: assignmentsByDelegue[delegue.id] || delegue.assignments || [],
        }))

        setDelegues(deleguesWithAssignments)
        setMedicaments(medicamentsResponse.data?.medicaments || [])
      } catch (err) {
        if (!isMounted) return
        setError(err.response?.data?.error || 'Impossible de charger les donnees admin.')
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    loadData()

    return () => {
      isMounted = false
    }
  }, [])

  const refreshDelegues = async () => {
    try {
      const [deleguesResponse, assignmentsResponse] = await Promise.all([
        adminAPI.getDelegues(),
        adminAPI.getAssignments(),
      ])
      const deleguesRaw = deleguesResponse.data?.delegues || []
      const assignments = assignmentsResponse.data?.assignments || []
      const assignmentsByDelegue = assignments.reduce((acc, assignment) => {
        if (!acc[assignment.delegue_id]) acc[assignment.delegue_id] = []
        acc[assignment.delegue_id].push(assignment)
        return acc
      }, {})
      setDelegues(
        deleguesRaw.map((delegue) => ({
          ...delegue,
          assignments: assignmentsByDelegue[delegue.id] || delegue.assignments || [],
        })),
      )
    } catch (err) {
      setError(err.response?.data?.error || 'Impossible de rafraichir la liste.')
    }
  }

  const handleAssign = async (event) => {
    event.preventDefault()
    setMessage('')
    setError('')

    if (!form.delegueId || !form.medicamentId) {
      setError('Selectionnez un delegue et un medicament.')
      return
    }

    setLoadingAssign(true)

    try {
      const response = await adminAPI.assign(Number(form.delegueId), Number(form.medicamentId))
      const backendMessage = response.data?.message || 'Operation terminee.'
      setMessage(backendMessage)
      setForm((prev) => ({ ...prev, medicamentId: '' }))
      await refreshDelegues()
    } catch (err) {
      setError(err.response?.data?.error || "Echec de l'assignation.")
    } finally {
      setLoadingAssign(false)
    }
  }

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login')
  }

  const handleCreateDelegue = async (event) => {
    event.preventDefault()
    setCreateError('')
    setCreateMessage('')

    if (!newDelegue.firstName || !newDelegue.lastName || !newDelegue.email || !newDelegue.password) {
      setCreateError('Tous les champs sont requis pour creer un delegue.')
      return
    }

    setCreatingDelegue(true)
    try {
      const response = await adminAPI.createUser(
        newDelegue.email.trim(),
        newDelegue.password,
        newDelegue.firstName.trim(),
        newDelegue.lastName.trim(),
        'delegue',
      )
      setCreateMessage(response.data?.message || 'Delegue cree avec succes.')
      setNewDelegue({
        firstName: '',
        lastName: '',
        email: '',
        password: '',
      })
      await refreshDelegues()
    } catch (err) {
      setCreateError(err.response?.data?.error || 'Impossible de creer le delegue.')
    } finally {
      setCreatingDelegue(false)
    }
  }

  const handleEditAssignment = (assignment) => {
    setEditingAssignment(assignment)
    setEditForm({
      score_module1: assignment.score_module1 || 0,
      score_module2: assignment.score_module2 || 0,
      score_module3: assignment.score_module3 || 0,
      statut: assignment.statut || 'non_commence',
    })
  }

  const getCalculatedGlobalScore = () => {
    const m1 = editForm.score_module1 || 0
    const m2 = editForm.score_module2 || 0
    const m3 = editForm.score_module3 || 0
    return Math.round((m1 + m2 + m3) / 3)
  }

  const handleUpdateAssignment = async () => {
    if (!editingAssignment) return
    setUpdatingAssignment(true)
    setError('')

    try {
      const globalScore = getCalculatedGlobalScore()
      const response = await adminAPI.updateAssignment(editingAssignment.id, {
        ...editForm,
        score_global: globalScore,
      })
      setMessage(response.data?.message || 'Assignment mise a jour avec succes.')
      setEditingAssignment(null)
      setEditForm({})
      await refreshDelegues()
    } catch (err) {
      setError(err.response?.data?.error || 'Impossible de mettre a jour.')
    } finally {
      setUpdatingAssignment(false)
    }
  }

  const handleDeleteAssignment = async (assignmentId) => {
    setDeletingAssignment(true)
    setError('')

    try {
      const response = await adminAPI.deleteAssignment(assignmentId)
      setMessage(response.data?.message || 'Assignment supprimee.')
      setDeleteConfirm(null)
      await refreshDelegues()
    } catch (err) {
      setError(err.response?.data?.error || 'Impossible de supprimer.')
    } finally {
      setDeletingAssignment(false)
    }
  }

  if (loading) return <div style={styles.loading}>Chargement de la console admin...</div>
  if (error && delegues.length === 0) return <div style={styles.errorPage}>{error}</div>

  const totalAssignments = delegues.reduce((sum, delegue) => sum + (delegue.assignments?.length || 0), 0)
  const completedAssignments = delegues.reduce(
    (sum, delegue) => sum + (delegue.assignments || []).filter((a) => a.statut === 'termine').length,
    0,
  )
  const inProgressAssignments = delegues.reduce(
    (sum, delegue) => sum + (delegue.assignments || []).filter((a) => a.statut === 'en_cours').length,
    0,
  )
  const completionRate = totalAssignments ? Math.round((completedAssignments / totalAssignments) * 100) : 0
  const averageScore = totalAssignments
    ? Math.round(
        delegues.reduce(
          (sum, delegue) =>
            sum + (delegue.assignments || []).reduce((s, assignment) => s + (assignment.score_global || 0), 0),
          0,
        ) / totalAssignments,
      )
    : 0

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.headerContent}>
          <div>
            <h1 style={styles.title}>ALIA Admin</h1>
            <p style={styles.subtitle}>Gestion des delegues et medicaments</p>
          </div>
          <button onClick={handleLogout} style={styles.logoutBtn}>
            Deconnexion
          </button>
        </div>
      </div>

      <div style={styles.content}>
        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Delegues actifs</p>
            <p style={styles.statValue}>{delegues.length}</p>
          </div>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Assignments total</p>
            <p style={styles.statValue}>{totalAssignments}</p>
          </div>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Score moyen global</p>
            <p style={styles.statValue}>{averageScore}/100</p>
          </div>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Progression terminee</p>
            <p style={styles.statValue}>{completionRate}%</p>
          </div>
          <div style={styles.statCard}>
            <p style={styles.statLabel}>Assignments en cours</p>
            <p style={styles.statValue}>{inProgressAssignments}</p>
          </div>
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Assigner un medicament</h2>
          <form onSubmit={handleAssign} style={styles.assignForm}>
            <select
              style={styles.select}
              value={form.delegueId}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  delegueId: e.target.value,
                  medicamentId: '',
                }))
              }
            >
              <option value="">Selectionner un delegue</option>
              {delegues.map((delegue) => (
                <option key={delegue.id} value={delegue.id}>
                  {delegue.first_name} {delegue.last_name} ({delegue.email})
                </option>
              ))}
            </select>

            <select
              style={styles.select}
              value={form.medicamentId}
              onChange={(e) => setForm((prev) => ({ ...prev, medicamentId: e.target.value }))}
            >
              <option value="">Selectionner un medicament</option>
              {availableMedicaments.map((medicament) => (
                <option key={medicament.id} value={medicament.id}>
                  {medicament.nom}
                </option>
              ))}
            </select>

            <button type="submit" style={styles.assignBtn} disabled={loadingAssign}>
              {loadingAssign ? 'Assignation...' : 'Assigner'}
            </button>
          </form>
          {message && <div style={styles.successMessage}>{message}</div>}
          {error && <div style={styles.errorMessage}>{error}</div>}
          {form.delegueId && availableMedicaments.length === 0 && (
            <div style={styles.infoMessage}>Tous les medicaments sont deja assignes a ce delegue.</div>
          )}
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Ajouter un delegue</h2>
          <form onSubmit={handleCreateDelegue} style={styles.createForm}>
            <input
              style={styles.searchInput}
              placeholder="Prenom"
              value={newDelegue.firstName}
              onChange={(e) => setNewDelegue((prev) => ({ ...prev, firstName: e.target.value }))}
            />
            <input
              style={styles.searchInput}
              placeholder="Nom"
              value={newDelegue.lastName}
              onChange={(e) => setNewDelegue((prev) => ({ ...prev, lastName: e.target.value }))}
            />
            <input
              style={styles.searchInput}
              type="email"
              placeholder="Email"
              value={newDelegue.email}
              onChange={(e) => setNewDelegue((prev) => ({ ...prev, email: e.target.value }))}
            />
            <input
              style={styles.searchInput}
              type="password"
              placeholder="Mot de passe initial"
              value={newDelegue.password}
              onChange={(e) => setNewDelegue((prev) => ({ ...prev, password: e.target.value }))}
            />
            <button type="submit" style={styles.assignBtn} disabled={creatingDelegue}>
              {creatingDelegue ? 'Creation...' : 'Creer delegue'}
            </button>
          </form>
          {createMessage && <div style={styles.successMessage}>{createMessage}</div>}
          {createError && <div style={styles.errorMessage}>{createError}</div>}
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Delegues et assignments</h2>
          <div style={styles.filtersRow}>
            <input
              placeholder="Rechercher delegue (nom, email)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={styles.searchInput}
            />
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={styles.select}>
              <option value="all">Tous les statuts</option>
              <option value="non_commence">Non commence</option>
              <option value="en_cours">En cours</option>
              <option value="termine">Termine</option>
              <option value="none">Sans assignment</option>
            </select>
          </div>

          {filteredDelegues.length === 0 ? (
            <div style={styles.emptyState}>Aucun delegue trouve.</div>
          ) : (
            <div style={styles.dashboardGrid}>
              <div style={styles.tableWrapper}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Email</th>
                    <th style={styles.th}>Prenom</th>
                    <th style={styles.th}>Nom</th>
                    <th style={styles.th}>Medications</th>
                    <th style={styles.th}>Scores</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDelegues.map((delegue) => (
                    <tr
                      key={delegue.id}
                      onClick={() => setActiveDelegueId(delegue.id)}
                      style={activeDelegueId === delegue.id ? styles.activeRow : undefined}
                    >
                      <td style={styles.td}>{delegue.email}</td>
                      <td style={styles.td}>{delegue.first_name || '-'}</td>
                      <td style={styles.td}>{delegue.last_name || '-'}</td>
                      <td style={styles.td}>
                        {delegue.assignments?.length ? (
                          <div style={styles.tagList}>
                            {delegue.assignments.map((assignment) => (
                              <span key={assignment.id} style={styles.tag}>
                                {assignment.medicament_nom}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={styles.muted}>Aucun</span>
                        )}
                      </td>
                      <td style={styles.td}>
                        {delegue.assignments?.length ? (
                          <div style={styles.scoreList}>
                            {delegue.assignments.map((assignment) => (
                              <span key={assignment.id} style={{ color: getColor(assignment.score_global ?? 0) }}>
                                {assignment.medicament_nom}: {assignment.score_global ?? 0}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={styles.muted}>-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              <div style={styles.detailPanel}>
                <h3 style={styles.detailTitle}>Detail delegue</h3>
                {!activeDelegue ? (
                  <p style={styles.muted}>Cliquez sur une ligne du tableau.</p>
                ) : (
                  <>
                    <p style={styles.detailIdentity}>
                      {activeDelegue.first_name} {activeDelegue.last_name}
                    </p>
                    <p style={styles.muted}>{activeDelegue.email}</p>
                    
                    {editingAssignment && (
                      <div style={styles.editPanel}>
                        <h4 style={styles.editTitle}>Modifier: {editingAssignment.medicament_nom}</h4>
                        <div style={styles.editField}>
                          <label style={styles.label}>Statut</label>
                          <select
                            style={styles.editSelect}
                            value={editForm.statut || 'non_commence'}
                            onChange={(e) => setEditForm((prev) => ({ ...prev, statut: e.target.value }))}
                          >
                            <option value="non_commence">Non commence</option>
                            <option value="en_cours">En cours</option>
                            <option value="termine">Termine</option>
                          </select>
                        </div>
                        <div style={styles.editField}>
                          <label style={styles.label}>Score Module 1</label>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            style={styles.editInput}
                            value={editForm.score_module1 || 0}
                            onChange={(e) => setEditForm((prev) => ({ ...prev, score_module1: Number(e.target.value) }))}
                          />
                        </div>
                        <div style={styles.editField}>
                          <label style={styles.label}>Score Module 2</label>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            style={styles.editInput}
                            value={editForm.score_module2 || 0}
                            onChange={(e) => setEditForm((prev) => ({ ...prev, score_module2: Number(e.target.value) }))}
                          />
                        </div>
                        <div style={styles.editField}>
                          <label style={styles.label}>Score Module 3</label>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            style={styles.editInput}
                            value={editForm.score_module3 || 0}
                            onChange={(e) => setEditForm((prev) => ({ ...prev, score_module3: Number(e.target.value) }))}
                          />
                        </div>
                        <div style={styles.editField}>
                          <label style={styles.label}>Score Global (moyennes des 3 modules)</label>
                          <div
                            style={{
                              ...styles.editInput,
                              background: 'rgba(180,160,255,0.15)',
                              padding: '6px 8px',
                              borderRadius: '4px',
                              color: '#b4a0ff',
                              fontWeight: 600,
                              display: 'flex',
                              alignItems: 'center',
                            }}
                          >
                            {getCalculatedGlobalScore()}
                          </div>
                        </div>
                        <div style={styles.editButtons}>
                          <button
                            onClick={handleUpdateAssignment}
                            disabled={updatingAssignment}
                            style={styles.saveBtn}
                          >
                            {updatingAssignment ? 'Sauvegarde...' : 'Sauvegarder'}
                          </button>
                          <button
                            onClick={() => {
                              setEditingAssignment(null)
                              setEditForm({})
                            }}
                            style={styles.cancelBtn}
                          >
                            Annuler
                          </button>
                        </div>
                      </div>
                    )}

                    {deleteConfirm && (
                      <div style={styles.confirmPanel}>
                        <p style={styles.confirmText}>
                          Êtes-vous sur de supprimer cette assignation ?
                        </p>
                        <p style={styles.confirmMuted}>{deleteConfirm.medicament_nom}</p>
                        <div style={styles.editButtons}>
                          <button
                            onClick={() => handleDeleteAssignment(deleteConfirm.id)}
                            disabled={deletingAssignment}
                            style={styles.dangerBtn}
                          >
                            {deletingAssignment ? 'Suppression...' : 'Supprimer'}
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(null)}
                            style={styles.cancelBtn}
                          >
                            Annuler
                          </button>
                        </div>
                      </div>
                    )}

                    {!editingAssignment && !deleteConfirm && (
                      <div style={styles.progressWrap}>
                        {(activeDelegue.assignments || []).map((assignment) => (
                          <div key={assignment.id} style={styles.progressItem}>
                            <div style={styles.progressHead}>
                              <span>{assignment.medicament_nom}</span>
                              <span>{assignment.score_global || 0}%</span>
                            </div>
                            <div style={styles.progressBar}>
                              <div
                                style={{
                                  ...styles.progressFill,
                                  width: `${Math.min(Math.max(assignment.score_global || 0, 0), 100)}%`,
                                  background: getColor(assignment.score_global || 0),
                                }}
                              />
                            </div>
                            <span style={styles.progressStatus}>{assignment.statut}</span>
                            <div style={styles.assignmentButtons}>
                              <button
                                onClick={() => handleEditAssignment(assignment)}
                                style={styles.editBtn}
                              >
                                ✏️ Modifier
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(assignment)}
                                style={styles.deleteBtn}
                              >
                                🗑️ Supprimer
                              </button>
                            </div>
                          </div>
                        ))}
                        {(activeDelegue.assignments || []).length === 0 && (
                          <p style={styles.muted}>Aucun medicament assigne.</p>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function getColor(score) {
  if (score >= 80) return '#00d2aa'
  if (score >= 60) return '#b4a0ff'
  if (score >= 40) return '#ffa500'
  return '#ff6b6b'
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
    maxWidth: '1400px',
    margin: '0 auto',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
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
    maxWidth: '1400px',
    margin: '0 auto 18px auto',
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
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
    maxWidth: '1400px',
    margin: '0 auto',
    width: '100%',
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: 600,
    marginBottom: '24px',
    color: '#e8e4f8',
  },
  assignForm: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr auto',
    gap: '12px',
    alignItems: 'center',
    marginBottom: '12px',
  },
  select: {
    padding: '8px 12px',
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(180,160,255,0.2)',
    color: '#e8e4f8',
    borderRadius: '6px',
    fontSize: '13px',
  },
  assignBtn: {
    padding: '9px 16px',
    background: 'linear-gradient(135deg, #b4a0ff, #00d2aa)',
    color: '#0c0b14',
    fontWeight: 700,
    border: 'none',
    borderRadius: '6px',
  },
  successMessage: {
    padding: '10px 12px',
    borderRadius: '6px',
    background: 'rgba(0, 210, 170, 0.15)',
    border: '1px solid rgba(0, 210, 170, 0.4)',
    color: '#71f2d3',
    marginBottom: '10px',
  },
  errorMessage: {
    padding: '10px 12px',
    borderRadius: '6px',
    background: 'rgba(255, 59, 59, 0.12)',
    border: '1px solid rgba(255, 59, 59, 0.4)',
    color: '#ff9b9b',
    marginBottom: '10px',
  },
  infoMessage: {
    padding: '10px 12px',
    borderRadius: '6px',
    background: 'rgba(255,255,255,0.08)',
    border: '1px solid rgba(180,160,255,0.25)',
    color: 'rgba(255,255,255,0.85)',
    marginBottom: '10px',
  },
  tableWrapper: {
    overflowX: 'auto',
    border: '1px solid rgba(180,160,255,0.1)',
    borderRadius: '10px',
    background: 'rgba(20, 18, 35, 0.6)',
  },
  dashboardGrid: {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr',
    gap: '12px',
    alignItems: 'start',
  },
  activeRow: {
    background: 'rgba(180,160,255,0.08)',
  },
  detailPanel: {
    border: '1px solid rgba(180,160,255,0.12)',
    borderRadius: '10px',
    background: 'rgba(20, 18, 35, 0.6)',
    padding: '12px',
    position: 'sticky',
    top: '12px',
  },
  detailTitle: {
    margin: '0 0 8px 0',
    color: '#b4a0ff',
    fontSize: '14px',
  },
  detailIdentity: {
    margin: '0 0 3px 0',
    fontSize: '16px',
    fontWeight: 600,
    color: '#e8e4f8',
  },
  progressWrap: {
    display: 'grid',
    gap: '10px',
    marginTop: '12px',
  },
  progressItem: {
    border: '1px solid rgba(180,160,255,0.12)',
    borderRadius: '8px',
    padding: '8px',
    background: 'rgba(255,255,255,0.03)',
  },
  progressHead: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
    marginBottom: '6px',
  },
  progressBar: {
    height: '8px',
    borderRadius: '999px',
    background: 'rgba(255,255,255,0.12)',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: '999px',
  },
  progressStatus: {
    marginTop: '5px',
    display: 'inline-block',
    fontSize: '11px',
    color: 'rgba(255,255,255,0.7)',
  },
  filtersRow: {
    display: 'flex',
    gap: '10px',
    marginBottom: '12px',
  },
  createForm: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1.2fr 1fr auto',
    gap: '10px',
    marginBottom: '10px',
  },
  searchInput: {
    flex: 1,
    padding: '8px 12px',
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(180,160,255,0.2)',
    color: '#e8e4f8',
    borderRadius: '6px',
    fontSize: '13px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    minWidth: '820px',
  },
  th: {
    textAlign: 'left',
    padding: '12px',
    borderBottom: '1px solid rgba(180,160,255,0.15)',
    color: '#b4a0ff',
    fontSize: '13px',
    background: 'rgba(255,255,255,0.03)',
  },
  td: {
    verticalAlign: 'top',
    padding: '12px',
    borderBottom: '1px solid rgba(180,160,255,0.08)',
    fontSize: '13px',
    color: '#e8e4f8',
  },
  tagList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
  },
  tag: {
    fontSize: '12px',
    borderRadius: '999px',
    padding: '3px 10px',
    background: 'rgba(255,255,255,0.08)',
    border: '1px solid rgba(180,160,255,0.15)',
  },
  scoreList: {
    display: 'grid',
    gap: '6px',
  },
  muted: {
    color: 'rgba(255,255,255,0.5)',
  },
  emptyState: {
    padding: '16px',
    borderRadius: '8px',
    background: 'rgba(255,255,255,0.05)',
    color: 'rgba(255,255,255,0.7)',
    border: '1px solid rgba(180,160,255,0.1)',
  },
  assignmentButtons: {
    display: 'flex',
    gap: '6px',
    marginTop: '8px',
  },
  editBtn: {
    flex: 1,
    padding: '6px 10px',
    fontSize: '11px',
    background: 'rgba(180,160,255,0.25)',
    color: '#b4a0ff',
    border: '1px solid rgba(180,160,255,0.3)',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  deleteBtn: {
    flex: 1,
    padding: '6px 10px',
    fontSize: '11px',
    background: 'rgba(255,107,107,0.25)',
    color: '#ff9b9b',
    border: '1px solid rgba(255,107,107,0.3)',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  editPanel: {
    background: 'rgba(180,160,255,0.1)',
    border: '1px solid rgba(180,160,255,0.25)',
    borderRadius: '8px',
    padding: '12px',
    marginBottom: '12px',
  },
  editTitle: {
    margin: '0 0 10px 0',
    fontSize: '13px',
    color: '#b4a0ff',
  },
  editField: {
    marginBottom: '8px',
  },
  label: {
    display: 'block',
    fontSize: '11px',
    color: 'rgba(255,255,255,0.7)',
    marginBottom: '3px',
  },
  editSelect: {
    width: '100%',
    padding: '6px 8px',
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(180,160,255,0.2)',
    color: '#e8e4f8',
    borderRadius: '4px',
    fontSize: '12px',
  },
  editInput: {
    width: '100%',
    padding: '6px 8px',
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(180,160,255,0.2)',
    color: '#e8e4f8',
    borderRadius: '4px',
    fontSize: '12px',
    boxSizing: 'border-box',
  },
  editButtons: {
    display: 'flex',
    gap: '8px',
    marginTop: '10px',
  },
  saveBtn: {
    flex: 1,
    padding: '7px 12px',
    fontSize: '12px',
    background: 'linear-gradient(135deg, #b4a0ff, #00d2aa)',
    color: '#0c0b14',
    fontWeight: 600,
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  cancelBtn: {
    flex: 1,
    padding: '7px 12px',
    fontSize: '12px',
    background: 'rgba(255,255,255,0.1)',
    color: '#e8e4f8',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  dangerBtn: {
    flex: 1,
    padding: '7px 12px',
    fontSize: '12px',
    background: 'rgba(255,107,107,0.3)',
    color: '#ff6b6b',
    fontWeight: 600,
    border: '1px solid rgba(255,107,107,0.4)',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  confirmPanel: {
    background: 'rgba(255,107,107,0.12)',
    border: '1px solid rgba(255,107,107,0.3)',
    borderRadius: '8px',
    padding: '12px',
    marginBottom: '12px',
  },
  confirmText: {
    margin: '0 0 4px 0',
    fontSize: '12px',
    color: '#ff9b9b',
  },
  confirmMuted: {
    margin: '0 0 10px 0',
    fontSize: '11px',
    color: 'rgba(255,255,255,0.5)',
  },
}
