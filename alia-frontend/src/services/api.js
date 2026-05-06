import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Ajouter le token à chaque requête
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const authAPI = {
  login: (email, password) => api.post('/auth/login', { email, password }),
}

export const delegueAPI = {
  getProfil: () => api.get('/delegue/profil'),
  getHistorique: () => api.get('/delegue/historique'),
}

export const medicamentsAPI = {
  getList: () => api.get('/medicaments'),
}

export const simulationAPI = {
  start: (medicament_id, mode = 'training', interlocuteur = 'medecin') =>
    api.post('/sim/start', { medicament_id, mode, interlocuteur }),
  message: (message) =>
    api.post('/sim/message', { message }),
  stop: () =>
    api.post('/sim/stop', {}),
  command: (command) =>
    api.post('/sim/command', { command }),
}

export const avatarAPI = {
  push: (state) => api.post('/avatar/state', state),
  get: () => api.get('/avatar/last'),
}

export const adminAPI = {
  getDelegues: () => api.get('/admin/delegues'),
  getAssignments: () => api.get('/admin/assignments'),
  assign: (delegue_id, medicament_id) =>
    api.post('/admin/assign', { delegue_id, medicament_id }),
  getAssignment: (assignment_id) =>
    api.get(`/admin/assignment/${assignment_id}`),
  updateAssignment: (assignment_id, data) =>
    api.put(`/admin/assignment/${assignment_id}`, data),
  deleteAssignment: (assignment_id) =>
    api.delete(`/admin/assignment/${assignment_id}`),
  getMedicaments: () => api.get('/admin/medicaments'),
  createUser: (email, password, first_name, last_name, role) =>
    api.post('/admin/create-user', { email, password, first_name, last_name, role }),
}

export default api
