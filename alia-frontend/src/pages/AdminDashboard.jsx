import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/admin-dashboard.css';

export default function AdminDashboard() {
    const navigate = useNavigate();
    const [delegues, setDelegues] = useState([]);
    const [assignments, setAssignments] = useState([]);
    const [currentView, setCurrentView] = useState('delegues');
    const [loading, setLoading] = useState(false);
    const [stats, setStats] = useState({
        totalDelegues: 0,
        totalAssignments: 0,
        avgScore: 0,
        completionRate: 0
    });
    const [filters, setFilters] = useState({
        delegueSearch: '',
        niveauFilter: '',
        assignmentSearch: '',
        statutFilter: ''
    });
    const [editingAssignment, setEditingAssignment] = useState(null);
    const [editForm, setEditForm] = useState({
        score_module1: 0,
        score_module2: 0,
        score_module3: 0,
        statut: 'non_commence'
    });
    const [showCreateUserModal, setShowCreateUserModal] = useState(false);
    const [createUserForm, setCreateUserForm] = useState({
        first_name: '',
        last_name: '',
        email: '',
        password: ''
    });
    const [createUserError, setCreateUserError] = useState('');
    const [creatingUser, setCreatingUser] = useState(false);
    
    const [showAssignModal, setShowAssignModal] = useState(false);
    const [medicaments, setMedicaments] = useState([]);
    const [assignForm, setAssignForm] = useState({
        delegue_id: '',
        medicament_id: ''
    });
    const [assignError, setAssignError] = useState('');
    const [assigning, setAssigning] = useState(false);

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (!token) navigate('/login');
        loadDelegues();
        loadMedicaments();
    }, []);

    async function loadDelegues() {
        setLoading(true);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/admin/delegues', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            const data = await res.json();
            setDelegues(data.delegues || []);
            
            // Calculate stats
            let totalAssignments = 0;
            let globalScores = [];
            let completed = 0;
            
            (data.delegues || []).forEach(d => {
                const assCount = d.assignments?.length || 0;
                totalAssignments += assCount;
                (d.assignments || []).forEach(a => {
                    if (a.score_global) globalScores.push(a.score_global);
                    if (a.statut === 'termine') completed++;
                });
            });

            const avgScore = globalScores.length ? Math.round(globalScores.reduce((a, b) => a + b) / globalScores.length) : 0;
            const completionRate = totalAssignments ? Math.round((completed / totalAssignments) * 100) : 0;

            setStats({
                totalDelegues: (data.delegues || []).length,
                totalAssignments,
                avgScore,
                completionRate
            });

            // Flatten assignments
            let flatAssignments = [];
            (data.delegues || []).forEach(d => {
                (d.assignments || []).forEach(a => {
                    flatAssignments.push({
                        ...a,
                        delegue_name: `${d.first_name} ${d.last_name}`,
                        delegue_id: d.id,
                        niveau: d.niveau
                    });
                });
            });
            setAssignments(flatAssignments);
        } catch (err) {
            console.error('Error loading delegues:', err);
        }
        setLoading(false);
    }

    async function loadMedicaments() {
        try {
            const res = await fetch('http://127.0.0.1:8000/api/admin/medicaments', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            if (!res.ok) {
                console.error('Error response from /api/admin/medicaments:', res.status);
                return;
            }
            const data = await res.json();
            console.log('Medicaments loaded:', data.medicaments?.length || 0);
            setMedicaments(data.medicaments || []);
        } catch (err) {
            console.error('Error loading medicaments:', err);
        }
    }

    function handleEditAssignment(assignment) {
        setEditingAssignment(assignment);
        setEditForm({
            score_module1: assignment.score_module1 || 0,
            score_module2: assignment.score_module2 || 0,
            score_module3: assignment.score_module3 || 0,
            statut: assignment.statut
        });
    }

    async function handleUpdateAssignment() {
        if (!editingAssignment) return;
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/admin/assignment/${editingAssignment.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify(editForm)
            });
            if (!res.ok) throw new Error('Failed to update');
            setEditingAssignment(null);
            loadDelegues();
        } catch (err) {
            alert('Error: ' + err.message);
        }
    }

    async function handleDeleteAssignment(id) {
        if (!confirm('Êtes-vous sûr?')) return;
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/admin/assignment/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            if (!res.ok) throw new Error('Failed to delete');
            loadDelegues();
        } catch (err) {
            alert('Error: ' + err.message);
        }
    }

    async function handleCreateUser() {
        if (!createUserForm.first_name || !createUserForm.last_name || !createUserForm.email || !createUserForm.password) {
            setCreateUserError('Tous les champs sont obligatoires');
            return;
        }
        
        setCreatingUser(true);
        setCreateUserError('');
        try {
            const res = await fetch('http://127.0.0.1:8000/api/admin/create-user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify(createUserForm)
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to create user');
            }
            setShowCreateUserModal(false);
            setCreateUserForm({first_name: '', last_name: '', email: '', password: ''});
            loadDelegues();
        } catch (err) {
            setCreateUserError(err.message);
        } finally {
            setCreatingUser(false);
        }
    }

    async function handleAssign() {
        if (!assignForm.delegue_id || !assignForm.medicament_id) {
            setAssignError('Veuillez sélectionner un délégué et un médicament');
            return;
        }
        
        setAssigning(true);
        setAssignError('');
        try {
            const res = await fetch('http://127.0.0.1:8000/api/admin/assign', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify(assignForm)
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to assign');
            }
            setShowAssignModal(false);
            setAssignForm({delegue_id: '', medicament_id: ''});
            loadDelegues();
        } catch (err) {
            setAssignError(err.message);
        } finally {
            setAssigning(false);
        }
    }

    const filteredDelegues = delegues.filter(d => {
        const search = filters.delegueSearch.toLowerCase();
        const niveau = filters.niveauFilter;
        return (d.first_name.toLowerCase().includes(search) || d.last_name.toLowerCase().includes(search)) &&
               (!niveau || d.niveau === niveau);
    });

    const filteredAssignments = assignments.filter(a => {
        const search = filters.assignmentSearch.toLowerCase();
        const statut = filters.statutFilter;
        return (a.delegue_name.toLowerCase().includes(search) || a.medicament_nom.toLowerCase().includes(search)) &&
               (!statut || a.statut === statut);
    });

    return (
        <div className="admin-dashboard">
            {/* SIDEBAR */}
            <aside className="sidebar">
                <div className="logo">✨ ALIA Admin</div>
                <nav className="sidebar-nav">
                    <div className={`nav-item ${currentView === 'delegues' ? 'active' : ''}`} onClick={() => setCurrentView('delegues')}>
                        <span>👥 Délégués</span>
                    </div>
                    <div className={`nav-item ${currentView === 'assignments' ? 'active' : ''}`} onClick={() => setCurrentView('assignments')}>
                        <span>📋 Assignations</span>
                    </div>
                </nav>
            </aside>

            {/* MAIN */}
            <main className="main">
                <div className="header">
                    <h1>Dashboard ALIA</h1>
                    <div style={{display: 'flex', gap: '12px'}}>
                        <button onClick={() => setShowCreateUserModal(true)} className="btn btn-primary">
                            + Créer Délégué
                        </button>
                        <button onClick={() => {
                            localStorage.removeItem('token');
                            navigate('/login');
                        }} className="btn btn-secondary">Déconnexion</button>
                    </div>
                </div>

                {/* STATS */}
                <div className="stats-grid">
                    <div className="stat-card">
                        <div className="stat-value">{stats.totalDelegues}</div>
                        <div className="stat-label">Délégués Actifs</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">{stats.totalAssignments}</div>
                        <div className="stat-label">Assignations</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">{stats.avgScore}%</div>
                        <div className="stat-label">Score Moyen</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">{stats.completionRate}%</div>
                        <div className="stat-label">Taux Complétude</div>
                    </div>
                </div>

                {currentView === 'delegues' ? (
                    <div className="content-panel">
                        <h2>👥 Gestion des Délégués</h2>
                        <div className="search-bar">
                            <input
                                type="text"
                                placeholder="Rechercher..."
                                value={filters.delegueSearch}
                                onChange={(e) => setFilters({...filters, delegueSearch: e.target.value})}
                            />
                            <select
                                value={filters.niveauFilter}
                                onChange={(e) => setFilters({...filters, niveauFilter: e.target.value})}
                            >
                                <option value="">Tous les niveaux</option>
                                <option value="débutant">Débutant</option>
                                <option value="intermédiaire">Intermédiaire</option>
                                <option value="confirmé">Confirmé</option>
                            </select>
                            <button onClick={() => setShowAssignModal(true)} className="btn btn-secondary" style={{marginLeft: 'auto'}}>
                                📦 Assigner Méd.
                            </button>
                        </div>

                        <div className="delegues-grid">
                            {filteredDelegues.map(d => (
                                <div key={d.id} className="delegue-card">
                                    <div className="delegue-name">{d.first_name} {d.last_name}</div>
                                    <div className="delegue-email">{d.email}</div>
                                    <div className={`niveau-badge niveau-${d.niveau}`}>{d.niveau}</div>
                                    <div className="delegue-stats">
                                        <div>Produits: {d.nb_produits}</div>
                                        <div>Assignations: {d.assignments?.length || 0}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="content-panel">
                        <h2>📋 Gestion des Assignations</h2>
                        <div className="search-bar">
                            <input
                                type="text"
                                placeholder="Rechercher..."
                                value={filters.assignmentSearch}
                                onChange={(e) => setFilters({...filters, assignmentSearch: e.target.value})}
                            />
                            <select
                                value={filters.statutFilter}
                                onChange={(e) => setFilters({...filters, statutFilter: e.target.value})}
                            >
                                <option value="">Tous les statuts</option>
                                <option value="non_commence">Non commencé</option>
                                <option value="en_cours">En cours</option>
                                <option value="termine">Terminé</option>
                            </select>
                        </div>

                        <table className="assignments-table">
                            <thead>
                                <tr>
                                    <th>Délégué</th>
                                    <th>Médicament</th>
                                    <th>Module 1</th>
                                    <th>Module 2</th>
                                    <th>Module 3</th>
                                    <th>Score Global</th>
                                    <th>Statut</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredAssignments.map(a => (
                                    <tr key={a.id}>
                                        <td>{a.delegue_name}</td>
                                        <td>{a.medicament_nom}</td>
                                        <td>{a.score_module1 || '-'}</td>
                                        <td>{a.score_module2 || '-'}</td>
                                        <td>{a.score_module3 || '-'}</td>
                                        <td><strong>{a.score_global || '-'}</strong></td>
                                        <td><span className={`statut-badge statut-${a.statut}`}>{a.statut}</span></td>
                                        <td>
                                            <button onClick={() => handleEditAssignment(a)} className="btn btn-small">✏️</button>
                                            <button onClick={() => handleDeleteAssignment(a.id)} className="btn btn-danger btn-small">🗑️</button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* EDIT MODAL */}
                {editingAssignment && (
                    <div className="modal">
                        <div className="modal-content">
                            <h3>Modifier Assignation</h3>
                            <input
                                type="number"
                                min="0" max="100"
                                value={editForm.score_module1}
                                onChange={(e) => setEditForm({...editForm, score_module1: parseInt(e.target.value)})}
                                placeholder="Module 1"
                            />
                            <input
                                type="number"
                                min="0" max="100"
                                value={editForm.score_module2}
                                onChange={(e) => setEditForm({...editForm, score_module2: parseInt(e.target.value)})}
                                placeholder="Module 2"
                            />
                            <input
                                type="number"
                                min="0" max="100"
                                value={editForm.score_module3}
                                onChange={(e) => setEditForm({...editForm, score_module3: parseInt(e.target.value)})}
                                placeholder="Module 3"
                            />
                            <select value={editForm.statut} onChange={(e) => setEditForm({...editForm, statut: e.target.value})}>
                                <option value="non_commence">Non commencé</option>
                                <option value="en_cours">En cours</option>
                                <option value="termine">Terminé</option>
                            </select>
                            <div className="modal-actions">
                                <button onClick={handleUpdateAssignment} className="btn btn-primary">Mettre à jour</button>
                                <button onClick={() => setEditingAssignment(null)} className="btn btn-secondary">Annuler</button>
                            </div>
                        </div>
                    </div>
                )}

                {/* CREATE USER MODAL */}
                {showCreateUserModal && (
                    <div className="modal">
                        <div className="modal-content">
                            <h3>Créer un Nouveau Délégué</h3>
                            {createUserError && (
                                <div style={{background: 'rgba(239,68,68,0.1)', color: '#fca5a5', padding: '12px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px'}}>
                                    {createUserError}
                                </div>
                            )}
                            <input
                                type="text"
                                value={createUserForm.first_name}
                                onChange={(e) => setCreateUserForm({...createUserForm, first_name: e.target.value})}
                                placeholder="Prénom"
                            />
                            <input
                                type="text"
                                value={createUserForm.last_name}
                                onChange={(e) => setCreateUserForm({...createUserForm, last_name: e.target.value})}
                                placeholder="Nom"
                            />
                            <input
                                type="email"
                                value={createUserForm.email}
                                onChange={(e) => setCreateUserForm({...createUserForm, email: e.target.value})}
                                placeholder="Email"
                            />
                            <input
                                type="password"
                                value={createUserForm.password}
                                onChange={(e) => setCreateUserForm({...createUserForm, password: e.target.value})}
                                placeholder="Mot de passe"
                            />
                            <div className="modal-actions">
                                <button onClick={handleCreateUser} className="btn btn-primary" disabled={creatingUser}>
                                    {creatingUser ? 'Création...' : 'Créer'}
                                </button>
                                <button onClick={() => {
                                    setShowCreateUserModal(false);
                                    setCreateUserError('');
                                }} className="btn btn-secondary">Annuler</button>
                            </div>
                        </div>
                    </div>
                )}

                {/* ASSIGN MEDICAMENT MODAL */}
                {showAssignModal && (
                    <div className="modal">
                        <div className="modal-content">
                            <h3>Assigner un Médicament</h3>
                            {assignError && (
                                <div style={{background: 'rgba(239,68,68,0.1)', color: '#fca5a5', padding: '12px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px'}}>
                                    {assignError}
                                </div>
                            )}
                            <select
                                value={assignForm.delegue_id}
                                onChange={(e) => setAssignForm({...assignForm, delegue_id: e.target.value})}
                            >
                                <option value="">-- Sélectionner un délégué --</option>
                                {delegues.map(d => (
                                    <option key={d.id} value={d.id}>{d.first_name} {d.last_name}</option>
                                ))}
                            </select>
                            <select
                                value={assignForm.medicament_id}
                                onChange={(e) => setAssignForm({...assignForm, medicament_id: e.target.value})}
                            >
                                <option value="">-- Sélectionner un médicament --</option>
                                {medicaments.map(m => (
                                    <option key={m.id} value={m.id}>{m.nom}</option>
                                ))}
                            </select>
                            <div className="modal-actions">
                                <button onClick={handleAssign} className="btn btn-primary" disabled={assigning}>
                                    {assigning ? 'Assignation...' : 'Assigner'}
                                </button>
                                <button onClick={() => {
                                    setShowAssignModal(false);
                                    setAssignError('');
                                }} className="btn btn-secondary">Annuler</button>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
