/**
 * RequireAuth – Protects the entire dashboard.
 * If not authenticated (no token), redirects to /login.
 */
import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import authService from '../services/authService'

export default function RequireAuth({ children }) {
  const location = useLocation()

  if (!authService.isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
