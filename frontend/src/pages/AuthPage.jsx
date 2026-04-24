import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, requestOtp, verifyOtp } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function AuthPage() {
  const navigate = useNavigate()
  const { saveTokens } = useAuth()
  const devLoginEnabled = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEV_LOGIN === 'true'
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [otpRequested, setOtpRequested] = useState(false)
  const [isRequestingOtp, setIsRequestingOtp] = useState(false)
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false)
  const [isDevLogin, setIsDevLogin] = useState(false)

  async function onRequestOtp(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setIsRequestingOtp(true)
    try {
      await requestOtp(phone)
      setOtpRequested(true)
      setMessage('Code OTP envoye par SMS.')
    } catch (err) {
      setError(err.message)
    } finally {
      setIsRequestingOtp(false)
    }
  }

  async function onVerifyOtp(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setIsVerifyingOtp(true)
    try {
      const res = await verifyOtp(phone, code)
      saveTokens(res.access_token, res.refresh_token || '')
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setIsVerifyingOtp(false)
    }
  }

  async function onDevLogin(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setIsDevLogin(true)
    try {
      const res = await login(phone)
      saveTokens(res.access_token, res.refresh_token || '')
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setIsDevLogin(false)
    }
  }

  return (
    <section className="auth-wrap">
      <article className="auth-panel">
        <p className="eyebrow">Secure Access</p>
        <h2>Connexion OTP</h2>
        <form className="form" onSubmit={onRequestOtp}>
          <input
            placeholder="+257..."
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            pattern="^\+[1-9]\d{7,19}$"
            required
          />
          <button type="submit" disabled={isRequestingOtp}>
            {isRequestingOtp ? 'Envoi en cours...' : 'Recevoir OTP'}
          </button>
        </form>

        {otpRequested ? (
          <form className="form" onSubmit={onVerifyOtp}>
            <input
              placeholder="code OTP"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              minLength={4}
              maxLength={8}
              pattern="^\d{4,8}$"
              required
            />
            <button type="submit" disabled={isVerifyingOtp}>
              {isVerifyingOtp ? 'Verification...' : 'Verifier OTP'}
            </button>
          </form>
        ) : null}

        {devLoginEnabled ? (
          <form className="form" onSubmit={onDevLogin}>
            <button type="submit" className="button-secondary" disabled={isDevLogin}>
              {isDevLogin ? 'Connexion...' : 'Connexion rapide (dev)'}
            </button>
          </form>
        ) : null}

        {message ? <p className="status-line">{message}</p> : null}
      </article>
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
