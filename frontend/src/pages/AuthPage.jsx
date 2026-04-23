import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, registerUser } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function AuthPage() {
  const navigate = useNavigate()
  const { saveToken } = useAuth()
  const [error, setError] = useState('')
  const [loginForm, setLoginForm] = useState({ phone: '', password: '' })
  const [registerForm, setRegisterForm] = useState({
    phone_e164: '',
    password: '',
    first_name: '',
    last_name: '',
    user_type: 'customer',
  })

  async function onLogin(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await login(loginForm.phone, loginForm.password)
      saveToken(res.access_token)
      navigate('/shipments')
    } catch (err) {
      setError(err.message)
    }
  }

  async function onRegister(e) {
    e.preventDefault()
    setError('')
    try {
      await registerUser(registerForm)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="grid-two">
      <article className="card">
        <h2>Login</h2>
        <form className="form" onSubmit={onLogin}>
          <input
            placeholder="phone_e164"
            value={loginForm.phone}
            onChange={(e) => setLoginForm((s) => ({ ...s, phone: e.target.value }))}
            required
          />
          <input
            type="password"
            placeholder="password"
            value={loginForm.password}
            onChange={(e) => setLoginForm((s) => ({ ...s, password: e.target.value }))}
            required
          />
          <button type="submit">Se connecter</button>
        </form>
      </article>

      <article className="card">
        <h2>Register</h2>
        <form className="form" onSubmit={onRegister}>
          <input
            placeholder="phone_e164"
            value={registerForm.phone_e164}
            onChange={(e) => setRegisterForm((s) => ({ ...s, phone_e164: e.target.value }))}
            required
          />
          <input
            type="password"
            placeholder="password"
            value={registerForm.password}
            onChange={(e) => setRegisterForm((s) => ({ ...s, password: e.target.value }))}
            required
          />
          <input
            placeholder="first_name"
            value={registerForm.first_name}
            onChange={(e) => setRegisterForm((s) => ({ ...s, first_name: e.target.value }))}
          />
          <input
            placeholder="last_name"
            value={registerForm.last_name}
            onChange={(e) => setRegisterForm((s) => ({ ...s, last_name: e.target.value }))}
          />
          <select
            value={registerForm.user_type}
            onChange={(e) => setRegisterForm((s) => ({ ...s, user_type: e.target.value }))}
          >
            <option value="customer">customer</option>
            <option value="business">business</option>
            <option value="agent">agent</option>
            <option value="hub">hub</option>
            <option value="driver">driver</option>
            <option value="admin">admin</option>
          </select>
          <button type="submit">Créer le compte</button>
        </form>
      </article>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
