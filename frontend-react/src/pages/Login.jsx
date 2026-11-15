import React, { useState } from 'react'
import { Form, Input, Button, Typography, Alert } from 'antd'
import { UserOutlined, LockOutlined, ArrowRightOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import authService from '../services/authService'
import { BRAND, NEUTRAL } from '../theme/tokens'

const { Title, Text } = Typography

const ROYAL = BRAND[800]        // #1E40AF-ish — brand body
const ROYAL_DEEP = BRAND[900]   // #1E3A8A — gradient dark corner
const ROYAL_BRIGHT = BRAND[600] // #2563EB — button gradient highlight

function BrandMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#eaf1ff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="M7 15l3.5-4 3 2.5L21 7" />
    </svg>
  )
}

export default function Login() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/a1-data-overview'

  const handleSubmit = async ({ username, password }) => {
    setLoading(true)
    setError(null)
    try {
      await authService.login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err?.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 16px',
        background: `
          radial-gradient(1200px 600px at 15% -10%, ${BRAND[50]} 0%, transparent 60%),
          radial-gradient(1000px 700px at 110% 120%, ${BRAND[100]} 0%, transparent 55%),
          ${NEUTRAL[50]}
        `,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 880,
          background: NEUTRAL.white,
          border: `1px solid ${NEUTRAL[200]}`,
          borderRadius: 14,
          boxShadow: '0 24px 60px -20px rgba(18,41,77,0.35)',
          overflow: 'hidden',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
        }}
        className="login-card"
      >
        {/* Brand panel */}
        <div
          style={{
            position: 'relative',
            padding: '48px 44px',
            color: '#eaf1ff',
            background: `linear-gradient(155deg, ${ROYAL} 0%, ${ROYAL_DEEP} 100%)`,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          <div style={{
            position: 'absolute', inset: 0, pointerEvents: 'none',
            background: `
              radial-gradient(340px 340px at 85% 15%, rgba(255,255,255,0.10), transparent 70%),
              radial-gradient(260px 260px at 10% 100%, ${BRAND[500]}88, transparent 70%)
            `,
          }} />

          <div style={{ position: 'relative', zIndex: 1 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12, marginBottom: 34 }}>
              <div style={{
                width: 42, height: 42, borderRadius: 10,
                background: 'rgba(255,255,255,0.12)',
                border: '1px solid rgba(255,255,255,0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <BrandMark />
              </div>
              <span style={{ fontSize: 15, letterSpacing: '0.12em', fontWeight: 600, textTransform: 'uppercase', opacity: 0.92 }}>
                SMI DSS
              </span>
            </div>

            <Title level={1} style={{ color: '#fff', fontSize: 28, lineHeight: 1.25, margin: '0 0 14px', fontWeight: 600, letterSpacing: '0.01em' }}>
              Decision Support<br />System
            </Title>
            <Text style={{ color: '#c5d4f0', fontSize: 14.5, lineHeight: 1.7, maxWidth: '34ch', display: 'block' }}>
              Supplier-managed inventory — proactive order allocation and lateral transshipment.
            </Text>
          </div>
        </div>

        {/* Login form */}
        <div style={{ padding: '48px 44px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <Title level={2} style={{ margin: '0 0 6px', fontSize: 22, fontWeight: 600, color: NEUTRAL[900] }}>
            Sign in
          </Title>
          <Text style={{ display: 'block', margin: '0 0 28px', fontSize: 14, color: NEUTRAL[500] }}>
            Please enter your credentials to continue.
          </Text>

          {error && (
            <Alert type="error" message={error} showIcon style={{ marginBottom: 18, borderRadius: 10 }} />
          )}

          <Form layout="vertical" onFinish={handleSubmit} requiredMark={false} autoComplete="off">
            <Form.Item
              label={<span style={{ fontSize: 13, fontWeight: 600, color: NEUTRAL[700] }}>Username</span>}
              name="username"
              rules={[{ required: true, message: 'Please enter your username' }]}
            >
              <Input
                prefix={<UserOutlined style={{ color: NEUTRAL[400] }} />}
                placeholder="admin"
                size="large"
                style={{ borderRadius: 10, background: NEUTRAL[50] }}
                autoFocus
              />
            </Form.Item>

            <Form.Item
              label={<span style={{ fontSize: 13, fontWeight: 600, color: NEUTRAL[700] }}>Password</span>}
              name="password"
              rules={[{ required: true, message: 'Please enter your password' }]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: NEUTRAL[400] }} />}
                placeholder="••••••••"
                size="large"
                style={{ borderRadius: 10, background: NEUTRAL[50] }}
              />
            </Form.Item>

            <Form.Item style={{ marginTop: 26, marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                icon={!loading && <ArrowRightOutlined />}
                iconPosition="end"
                style={{
                  height: 48,
                  borderRadius: 10,
                  fontWeight: 600,
                  fontSize: 15.5,
                  letterSpacing: '0.02em',
                  background: `linear-gradient(135deg, ${ROYAL_BRIGHT}, ${ROYAL})`,
                  boxShadow: `0 12px 24px -10px ${ROYAL}b3`,
                  border: 'none',
                }}
              >
                Sign in
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>

      <style>{`
        @media (max-width: 720px) {
          .login-card { grid-template-columns: 1fr !important; max-width: 440px !important; }
        }
      `}</style>
    </div>
  )
}
