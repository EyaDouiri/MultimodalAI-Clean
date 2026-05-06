import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DeieguePages from './pages/DeieguePages'
import AdminDashboard from './pages/AdminDashboard'
import SimulationPage from './pages/SimulationPage'

function PrivateRoute({ children, requiredRole }) {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')

  if (!token) {
    return <Navigate to="/login" />
  }

  if (requiredRole && role !== requiredRole) {
    return <Navigate to="/" />
  }

  return children
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        
        <Route
          path="/delegue"
          element={
            <PrivateRoute requiredRole="delegue">
              <DeieguePages />
            </PrivateRoute>
          }
        />
        
        <Route
          path="/simulation/:medicamentId"
          element={
            <PrivateRoute requiredRole="delegue">
              <SimulationPage />
            </PrivateRoute>
          }
        />
        
        <Route
          path="/admin"
          element={
            <PrivateRoute requiredRole="admin">
              <AdminDashboard />
            </PrivateRoute>
          }
        />

        <Route path="/" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  )
}
