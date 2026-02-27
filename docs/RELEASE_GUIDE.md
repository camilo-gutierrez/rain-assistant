# Release Guide — Rain Assistant

Guía paso a paso para publicar una nueva versión completa.
Cubre: bump de versión, frontend, git, PyPI, instaladores, APK de Flutter, y limpieza.

---

## Resumen rápido (TL;DR)

```
1. Bump versión en pyproject.toml + pubspec.yaml
2. npm run deploy  (frontend → static/)
3. git add + commit + push
4. git tag v1.X.X + push tag  (dispara GitHub Actions → PyPI)
5. flutter build apk --release  (APK)
6. Limpiar build artifacts de Flutter
7. Subir APK al GitHub Release (opcional)
```

---

## Paso 0 — Decidir la versión

Elegir la nueva versión siguiendo semver: `MAJOR.MINOR.PATCH`

- **PATCH** (1.0.12 → 1.0.13): bug fixes, mejoras menores
- **MINOR** (1.0.12 → 1.1.0): nueva funcionalidad, sin romper nada
- **MAJOR** (1.0.12 → 2.0.0): cambios que rompen compatibilidad

> En los ejemplos usamos `1.0.13`. Reemplazar con la versión real.

---

## Paso 1 — Bump de versión

Actualizar en **dos** archivos:

### pyproject.toml (línea 7)
```toml
version = "1.0.13"
```

### rain_flutter/pubspec.yaml (línea 4)
```yaml
version: 1.0.13+13
```

> El `+13` es el `versionCode` de Android. Incrementar siempre en 1.
> Si la versión anterior era `1.0.12+12`, la nueva es `1.0.13+13`.

---

## Paso 2 — Rebuild del frontend

Esto compila Next.js y copia el output a `static/` para que FastAPI lo sirva.

```bash
cd frontend
npm run deploy
cd ..
```

Esto internamente hace:
1. `next build` → genera `out/` (static export)
2. `deploy.mjs` → copia `out/` → `static/`, crea `__init__.py`, copia `sw.js`

**Verificar:** debe aparecer `"Deploy complete!"` al final.

---

## Paso 3 — Commit y push a main

```bash
git add -A
git commit -m "chore: bump to 1.0.13 — descripción breve de los cambios"
git push origin main
```

> Esto dispara el CI (lint, tests, security scan). Esperar a que pase antes del tag.

---

## Paso 4 — Tag y push del tag (dispara release a PyPI)

```bash
git tag v1.0.13
git push origin v1.0.13
```

Esto dispara `.github/workflows/release.yml` que automáticamente:
1. Builds frontend (`npm run deploy`)
2. Builds el paquete Python (`python -m build`)
3. Crea un **GitHub Release** con los artifacts
4. Publica en **PyPI** via Trusted Publishing (OIDC)

**Verificar en:** `https://github.com/camilo-gutierrez/rain-assistant/actions`

Una vez publicado, los usuarios actualizan con:
```bash
pip install --upgrade rain-assistant
```

---

## Paso 5 — Build del APK de Flutter

```bash
cd rain_flutter
flutter build apk --release
```

El APK queda en:
```
rain_flutter/build/app/outputs/flutter-apk/app-release.apk
```

> **Requisito:** tener `key.properties` en `rain_flutter/android/` con la signing key.
> Si no existe, usa debug signing (no apto para distribución en Play Store).

---

## Paso 6 — Limpiar artifacts de Flutter

Después de copiar/subir el APK, limpiar para no inflar el repo:

```bash
cd rain_flutter
flutter clean
```

Esto elimina:
- `build/` (~500MB+ de artifacts)
- `.dart_tool/` cache
- Archivos temporales de compilación

> **Importante:** no commitear la carpeta `build/`. Debería estar en `.gitignore`.

---

## Paso 7 — (Opcional) Subir APK al GitHub Release

Si quieres adjuntar el APK al release de GitHub:

```bash
gh release upload v1.0.13 rain_flutter/build/app/outputs/flutter-apk/app-release.apk --clobber
```

> Hacer esto **antes** de `flutter clean`, o guardar el APK en otra ubicación primero.

---

## Paso 8 — Actualizar instaladores (si cambiaron)

Los scripts `install.sh` e `install.ps1` se sincronizan automáticamente al repo público
`rain-assistant-installer` cuando se pushean cambios a `main` (via `.github/workflows/sync-installers.yml`).

Los usuarios instalan con:
```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant/main/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant/main/install.ps1 | iex
```

> Si no tocaste los instaladores, no hay que hacer nada. Se sincronizan solos.

---

## Checklist completo

```
[ ] Versión bumpeada en pyproject.toml
[ ] Versión bumpeada en pubspec.yaml (version + versionCode)
[ ] Frontend rebuilt (npm run deploy)
[ ] Commit + push a main
[ ] CI verde (tests, lint, security)
[ ] Tag creado y pusheado (v1.X.X)
[ ] GitHub Actions: release workflow completado
[ ] PyPI: versión nueva visible en pypi.org/project/rain-assistant
[ ] APK generado (flutter build apk --release)
[ ] APK subido al GitHub Release (opcional)
[ ] Flutter limpio (flutter clean)
[ ] Instaladores sincronizados (automático si cambiaron)
```

---

## Archivos clave

| Archivo | Qué hace |
|---|---|
| `pyproject.toml:7` | Versión del paquete Python |
| `rain_flutter/pubspec.yaml:4` | Versión de la app Flutter |
| `frontend/scripts/deploy.mjs` | Script que copia build → static/ |
| `.github/workflows/release.yml` | CI: build + PyPI + GitHub Release |
| `.github/workflows/ci.yml` | CI: tests, lint, security |
| `.github/workflows/sync-installers.yml` | Sincroniza instaladores al repo público |
| `install.sh` / `install.ps1` | Instaladores zero-dependency |
| `rain_flutter/android/key.properties` | Signing key del APK (no en git) |

---

## Troubleshooting

### El release workflow falla en PyPI
- Verificar que el tag matchea el formato `v*`
- Verificar que el environment `pypi` está configurado en GitHub Settings → Environments
- Verificar Trusted Publishing en pypi.org

### El APK no se firma correctamente
- Verificar que `rain_flutter/android/key.properties` existe con:
  ```
  storePassword=...
  keyPassword=...
  keyAlias=...
  storeFile=ruta/al/keystore.jks
  ```

### `npm run deploy` falla
- Verificar que estás en `frontend/`
- Ejecutar `npm ci` primero si faltan dependencias
- Verificar que `out/` se genera correctamente con `npm run build`

### Los instaladores no se sincronizan
- Verificar que el secret `INSTALLER_REPO_TOKEN` existe en GitHub Settings → Secrets
- El token debe ser un Fine-Grained PAT con acceso al repo `rain-assistant-installer`
