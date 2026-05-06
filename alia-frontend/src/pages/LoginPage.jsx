import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '../services/api'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await authAPI.login(email, password)
      const { token, role, user } = res.data

      localStorage.setItem('token', token)
      localStorage.setItem('role', role)
      localStorage.setItem('user', JSON.stringify(user))

      navigate(role === 'admin' ? '/admin' : '/delegue')
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur de connexion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>ALIA</h1>
        <p style={styles.subtitle}>Assistant Pharmaceutique Intelligent</p>

        <form onSubmit={handleLogin} style={styles.form}>
          {error && <div style={styles.error}>{error}</div>}

          <div style={styles.group}>
            <label style={styles.label}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="vous@example.com"
              style={styles.input}
              required
            />
          </div>

          <div style={styles.group}>
            <label style={styles.label}>Mot de passe</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={styles.input}
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{...styles.button, opacity: loading ? 0.6 : 1}}
          >
            {loading ? 'Connexion...' : 'Se connecter'}
          </button>
        </form>

        <p style={styles.hint}>
          Utilisateur de test: <code>admin@test.com</code> / <code>pass123</code>
        </p>
      </div>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    background: 'linear-gradient(135deg, #0c0b14 0%, #1a1825 100%)',
  },
  card: {
    background: 'rgba(20, 18, 35, 0.8)',
    border: '1px solid rgba(180,160,255,0.2)',
    borderRadius: '12px',
    padding: '48px 40px',
    width: '100%',
    maxWidth: '400px',
    backdropFilter: 'blur(10px)',
  },
  title: {
    fontSize: '36px',
    fontWeight: 700,
    marginBottom: '8px',
    background: 'linear-gradient(135deg, #b4a0ff, #00d2aa)',
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  subtitle: {
    fontSize: '13px',
    color: 'rgba(255,255,255,0.5)',
    marginBottom: '32px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  group: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  label: {
    fontSize: '13px',
    color: 'rgba(255,255,255,0.7)',
    fontWeight: 500,
  },
  input: {
    padding: '10px 12px',
    borderRadius: '6px',
    border: '1px solid rgba(180,160,255,0.2)',
    background: 'rgba(255,255,255,0.05)',
    color: '#e8e4f8',
    fontSize: '14px',
    transition: 'all 0.2s',
  },
  button: {
    marginTop: '12px',
    padding: '12px 16px',
    background: 'linear-gradient(135deg, #b4a0ff, #00d2aa)',
    color: '#0c0b14',
    fontWeight: 600,
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  error: {
    padding: '12px',
    background: 'rgba(255, 59, 59, 0.1)',
    border: '1px solid rgba(255, 59, 59, 0.3)',
    color: '#ff3b3b',
    borderRadius: '6px',
    fontSize: '13px',
  },
  hint: {
    marginTop: '24px',
    fontSize: '12px',
    color: 'rgba(255,255,255,0.4)',
    textAlign: 'center',
  },
}
