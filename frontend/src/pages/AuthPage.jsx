import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { login, requestOtp, verifyOtp } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function AuthPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { saveTokens } = useAuth()
  const devLoginEnabled = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEV_LOGIN === 'true'
  const queryMode = searchParams.get('mode') === 'register' ? 'register' : 'login'
  const [mode, setMode] = useState(queryMode)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [otpRequested, setOtpRequested] = useState(false)
  const [isRequestingOtp, setIsRequestingOtp] = useState(false)
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false)
  const [isDevLogin, setIsDevLogin] = useState(false)

  useEffect(() => {
    setMode(queryMode)
  }, [queryMode])

  function switchMode(nextMode) {
    setMode(nextMode)
    setOtpRequested(false)
    setCode('')
    setError('')
    setMessage('')
    setSearchParams({ mode: nextMode }, { replace: true })
  }

  async function onRequestOtp(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setIsRequestingOtp(true)
    try {
      await requestOtp(phone)
      setOtpRequested(true)
      setMessage(mode === 'register' ? 'Code OTP envoye pour creation du compte.' : 'Code OTP envoye par SMS.')
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
    <section className="auth-wrap auth-modern">
      <article className="auth-panel auth-modern-panel">
        <div className="auth-modern-brand">
          <img src="/favicon.svg" alt="Logix" className="auth-modern-logo spin-slow" />
          <h2>LOGIX</h2>
        </div>
        <p className="auth-modern-subtitle">
          {mode === 'register'
            ? 'Creez votre acces et commencez a gerer vos expeditions en quelques secondes.'
            : 'Connectez-vous a votre espace logistique securise.'}
        </p>

        <div className="auth-mode-switch">
          <button
            type="button"
            className={mode === 'login' ? 'auth-mode-btn active' : 'auth-mode-btn'}
            onClick={() => switchMode('login')}
          >
            Connexion
          </button>
          <button
            type="button"
            className={mode === 'register' ? 'auth-mode-btn active' : 'auth-mode-btn'}
            onClick={() => switchMode('register')}
          >
            Creer un compte
          </button>
        </div>

        <form className="form" onSubmit={onRequestOtp}>
          <label>
            Telephone
            <input
              placeholder="+257..."
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              pattern="^\+[1-9]\d{7,19}$"
              required
            />
          </label>
          <button type="submit" disabled={isRequestingOtp}>
            {isRequestingOtp
              ? 'Envoi en cours...'
              : mode === 'register'
                ? 'Recevoir OTP de creation'
                : 'Recevoir OTP de connexion'}
          </button>
        </form>

        {otpRequested ? (
          <form className="form" onSubmit={onVerifyOtp}>
            <label>
              Code OTP
              <input
                placeholder="code OTP"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                minLength={4}
                maxLength={8}
                pattern="^\d{4,8}$"
                required
              />
            </label>
            <button type="submit" disabled={isVerifyingOtp}>
              {isVerifyingOtp
                ? 'Verification...'
                : mode === 'register'
                  ? 'Valider et acceder'
                  : 'Verifier OTP'}
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
        {error ? <p className="error">{error}</p> : null}

        <p className="auth-modern-footnote">
          <Link to="/">Retour a l accueil</Link>
        </p>
      </article>
    </section>
  )
}
