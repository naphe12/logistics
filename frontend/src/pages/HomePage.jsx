import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function HomePage() {
  const { dashboardRole, isAuthenticated } = useAuth()
  const location = useLocation()
  const isPublicLanding = location.pathname === '/' && !isAuthenticated

  const homeByRole = {
    client: {
      eyebrow: 'Client Experience',
      title: 'Envoyer et suivre vos colis en confiance',
      description:
        'Creation rapide, assurance optionnelle, suivi temps reel et reclamations pilotees avec SLA.',
      actions: [
        { to: '/shipments', label: 'Creer un envoi' },
        { to: '/tracking', label: 'Suivre un colis' },
      ],
    },
    agent: {
      eyebrow: 'Field Ops',
      title: 'Operations terrain et remise securisee',
      description:
        'Mise a jour statuts, scans de remise, verification codes et coordination transport en temps reel.',
      actions: [
        { to: '/tracking', label: 'Operations live' },
        { to: '/transport', label: 'Gestion transport' },
      ],
    },
    admin: {
      eyebrow: 'Control Tower',
      title: 'Pilotage reseau, SLA et performance',
      description:
        'Vue globale operations, alerting, performance claims, finance assurance et orchestration des equipes.',
      actions: [
        { to: '/backoffice', label: 'Ouvrir backoffice' },
        { to: '/incidents', label: 'SLA incidents/claims' },
      ],
    },
  }
  const roleHome = homeByRole[dashboardRole] || homeByRole.client

  if (isPublicLanding) {
    return (
      <section className="public-home">
        <article className="home-spotlight">
          <div className="home-logo-row">
            <img src="/favicon.svg" alt="Logix" className="home-logo spin-slow" />
            <h1 className="home-title">LOGIX</h1>
          </div>
          <p className="home-subtitle">
            Plateforme de livraison moderne pour les clients, agents et administrateurs.
          </p>
          <div className="home-cta-row">
            <Link to="/auth" className="button-link">
              Connexion
            </Link>
          </div>
        </article>
      </section>
    )
  }

  return (
    <section className="dashboard-home">
      <article className="home-spotlight">
        <div className="home-logo-row">
          <img src="/favicon.svg" alt="Logix" className="home-logo spin-slow" />
          <h1 className="home-title">LOGIX</h1>
        </div>
        <p className="eyebrow hero-eyebrow">{roleHome.eyebrow}</p>
        <h2>{roleHome.title}</h2>
        <p className="home-subtitle">{roleHome.description}</p>
        <div className="home-cta-row">
          <Link to={roleHome.actions[0].to} className="button-link">
            {roleHome.actions[0].label}
          </Link>
          <Link to={roleHome.actions[1].to} className="button-link button-ghost">
            {roleHome.actions[1].label}
          </Link>
        </div>
      </article>

      <article className="panel home-simple-card">
        <p className="eyebrow">Acces Rapide</p>
        <h3>Navigation principale</h3>
        <div className="home-simple-links">
          <Link to={roleHome.actions[0].to} className="button-link">
            {roleHome.actions[0].label}
          </Link>
          <Link to={roleHome.actions[1].to} className="button-link button-ghost">
            {roleHome.actions[1].label}
          </Link>
          {dashboardRole === 'admin' ? (
            <Link to="/backoffice" className="button-link button-ghost">
              Backoffice
            </Link>
          ) : null}
        </div>
      </article>
    </section>
  )
}
