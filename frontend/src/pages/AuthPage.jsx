import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { requestOtp, verifyOtp } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function AuthPage() {
  const navigate = useNavigate()
  const { saveTokens } = useAuth()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [otpRequested, setOtpRequested] = useState(false)

  async function onRequestOtp(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      await requestOtp(phone)
      setOtpRequested(true)
      setMessage('Code OTP envoye par SMS.')
    } catch (err) {
      setError(err.message)
    }
  }

  async function onVerifyOtp(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      const res = await verifyOtp(phone, code)
      saveTokens(res.access_token, res.refresh_token || '')
      navigate('/shipments')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section>
      <article className="card">
        <h2>Login OTP</h2>
        <form className="form" onSubmit={onRequestOtp}>
          <input
            placeholder="phone_e164"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
          />
          <button type="submit">Recevoir OTP</button>
        </form>

        {otpRequested ? (
          <form className="form" onSubmit={onVerifyOtp}>
            <input
              placeholder="code OTP"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              minLength={4}
              maxLength={8}
              required
            />
            <button type="submit">Verifier OTP</button>
          </form>
        ) : null}
      </article>

      {message ? <p>{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
