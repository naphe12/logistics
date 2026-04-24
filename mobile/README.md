# Logix Mobile (Flutter)

App mobile offline-first pour clients, agents et admin.

## Lancer l'app

```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Pour emulateur Android, utiliser typiquement:

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

## Ce qui est inclus (MVP mobile)

- Auth OTP + fallback dev login
- UI mobile professionnelle (design system centralise dans `lib/ui/app_theme.dart`)
- Base locale SQLite (`shipments`, `offline_actions`)
- Queue offline d'actions metier
- Sync push/pull manuel + auto-sync (timer + retour reseau)
- Ecrans essentiels:
  - Client: creer colis + liste locale
  - Agent: validation/confirmation code retrait
  - Admin: vue KPI backoffice compacte

## Strategie offline

- Si pas de reseau: les actions sont stockees dans `offline_actions`
- Au retour reseau (ou sync manuel): push queue vers API backend
- Auto-sync toutes les ~45s quand online
- Puis pull des colis (`/shipments/my`) vers la base locale
- Les drafts `create_shipment` sont reconcilies avec la reponse serveur pour eviter les doublons locaux
