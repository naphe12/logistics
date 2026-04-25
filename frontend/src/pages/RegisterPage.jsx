import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { requestOtp, verifyOtp } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { saveTokens } = useAuth()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [otpRequested, setOtpRequested] = useState(false)
  const [isRequestingOtp, setIsRequestingOtp] = useState(false)
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false)

  async function onRequestOtp(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setIsRequestingOtp(true)
    try {
      await requestOtp(phone)
      setOtpRequested(true)
      setMessage('Code OTP envoye pour creation du compte.')
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

  return (
    <section className="auth-wrap auth-modern">
      <article className="auth-panel auth-modern-panel">
        <div className="auth-modern-brand">
          <img src="/favicon.svg" alt="Logix" className="auth-modern-logo spin-slow" />
          <h2>LOGIX</h2>
        </div>
        <p className="eyebrow">Inscription</p>
        <p className="auth-modern-subtitle">
          Creez votre compte avec votre numero de telephone et accedez immediatement a votre espace.
        </p>

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
            {isRequestingOtp ? 'Envoi en cours...' : 'Recevoir OTP de creation'}
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
              {isVerifyingOtp ? 'Verification...' : 'Valider et acceder'}
            </button>
          </form>
        ) : null}

        {message ? <p className="status-line">{message}</p> : null}
        {error ? <p className="error">{error}</p> : null}

        <p className="auth-modern-footnote">
          Deja un compte ? <Link to="/auth">Se connecter</Link>
        </p>
      </article>
    </section>
  )
}
