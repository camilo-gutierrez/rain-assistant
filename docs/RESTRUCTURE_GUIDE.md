# Guia de Reestructuracion: Core vs Premium

## Resumen

Esta guia detalla paso a paso como separar el codigo de Rain Assistant
en dos partes: Core (open source) y Premium (propietario).

---

## Paso 1: Crear el sistema de Feature Flags

### 1.1 Crear `feature_flags.py` (nuevo archivo)

```python
"""
Rain Assistant Feature Flags
Controla que features estan habilitadas segun la licencia del usuario.
"""
import os
import json
from pathlib import Path

# Directorio de config
CONFIG_DIR = Path.home() / ".rain-assistant"
LICENSE_FILE = CONFIG_DIR / "license.json"

# Features premium y sus tiers
FEATURE_TIERS = {
    # Tier Pro ($15/mes)
    "plugins":       "pro",
    "marketplace":   "pro",
    "documents":     "pro",
    "memories":      "pro",
    "alter_egos":    "pro",
    "telegram":      "pro",
    "mobile_app":    "pro",
    # Tier Enterprise ($39/mes)
    "computer_use":  "enterprise",
    "directors":     "enterprise",
    "subagents":     "enterprise",
    "scheduled":     "enterprise",
    "multi_user":    "enterprise",
}

TIER_HIERARCHY = {"community": 0, "pro": 1, "enterprise": 2}


def get_user_tier() -> str:
    """Lee la licencia del usuario y retorna su tier."""
    if not LICENSE_FILE.exists():
        return "community"
    try:
        data = json.loads(LICENSE_FILE.read_text())
        key = data.get("license_key", "")
        if not key:
            return "community"
        # TODO: Verificar firma de la license key
        return data.get("tier", "community")
    except Exception:
        return "community"


def is_feature_enabled(feature: str) -> bool:
    """Verifica si una feature esta habilitada para el usuario actual."""
    # Override por variable de entorno (para desarrollo)
    env_key = f"RAIN_FEATURE_{feature.upper()}"
    env_val = os.getenv(env_key)
    if env_val is not None:
        return env_val.lower() in ("true", "1", "yes")

    # Verificar tier del usuario
    if feature not in FEATURE_TIERS:
        return True  # Features no listadas son core (siempre habilitadas)

    required_tier = FEATURE_TIERS[feature]
    user_tier = get_user_tier()

    return TIER_HIERARCHY.get(user_tier, 0) >= TIER_HIERARCHY.get(required_tier, 99)


def get_all_features() -> dict:
    """Retorna el estado de todas las features."""
    return {
        feature: is_feature_enabled(feature)
        for feature in FEATURE_TIERS
    }


def get_user_info() -> dict:
    """Info completa del usuario para el frontend."""
    tier = get_user_tier()
    return {
        "tier": tier,
        "features": get_all_features(),
        "tier_display": {
            "community": "Community (Free)",
            "pro": "Pro",
            "enterprise": "Enterprise",
        }.get(tier, "Community (Free)"),
    }
```

### 1.2 Agregar endpoint de features en `routes/settings.py`

```python
from feature_flags import get_user_info, is_feature_enabled

@router.get("/api/license")
async def get_license_info():
    """Retorna info de licencia y features habilitadas."""
    return get_user_info()

@router.post("/api/license/activate")
async def activate_license(body: dict):
    """Activa una license key."""
    key = body.get("license_key", "")
    # TODO: Verificar key contra servidor de licencias
    # Por ahora, guardar localmente
    config_dir = Path.home() / ".rain-assistant"
    license_file = config_dir / "license.json"
    license_file.write_text(json.dumps({"license_key": key, "tier": "pro"}))
    return {"status": "activated", **get_user_info()}
```

---

## Paso 2: Hacer imports condicionales en server.py

### 2.1 Modificar la seccion de imports

Buscar todos los imports de modulos premium en `server.py` y hacerlos condicionales:

```python
# --- Core imports (siempre disponibles) ---
from providers import get_provider
from tools.definitions import get_core_tool_definitions
from tools.executor import execute_tool
from permission_classifier import classify, PermissionLevel
from rate_limiter import RateLimiter
from database import Database
# ... etc

# --- Premium imports (condicionales) ---
from feature_flags import is_feature_enabled

if is_feature_enabled("plugins"):
    from plugins.loader import load_plugins
    from plugins.executor import execute_plugin
    from plugins.meta_tool import PLUGIN_TOOL_DEFINITION, handle_manage_plugins
else:
    load_plugins = lambda: []

if is_feature_enabled("documents"):
    from documents.meta_tool import DOCUMENT_TOOL_DEFINITION, handle_manage_documents
    from documents.storage import DocumentStorage

if is_feature_enabled("memories"):
    from memories.meta_tool import MEMORY_TOOL_DEFINITION, handle_manage_memories
    from memories.storage import MemoryStorage

if is_feature_enabled("alter_egos"):
    from alter_egos.meta_tool import EGO_TOOL_DEFINITION, handle_manage_alter_egos
    from alter_egos.storage import AlterEgoStorage

if is_feature_enabled("directors"):
    from directors.meta_tool import DIRECTOR_TOOL_DEFINITION, handle_manage_directors
    from directors.executor import DirectorExecutor
    from routes.directors import router as directors_router

if is_feature_enabled("computer_use"):
    from computer_use import ComputerUseExecutor

if is_feature_enabled("telegram"):
    from telegram_bot import TelegramBot

if is_feature_enabled("subagents"):
    from subagents.manager import SubAgentManager
    from subagents.meta_tool import SUBAGENT_TOOL_DEFINITION

if is_feature_enabled("marketplace"):
    from marketplace.meta_tool import MARKETPLACE_TOOL_DEFINITION

if is_feature_enabled("scheduled"):
    from scheduled_tasks.meta_tool import SCHEDULE_TOOL_DEFINITION
```

### 2.2 Modificar `get_all_tool_definitions()`

```python
def get_all_tool_definitions():
    """Retorna tools basado en features habilitadas."""
    tools = get_core_tool_definitions()  # siempre disponibles

    if is_feature_enabled("plugins"):
        tools.append(PLUGIN_TOOL_DEFINITION)
        tools.extend(get_plugin_tools())

    if is_feature_enabled("documents"):
        tools.append(DOCUMENT_TOOL_DEFINITION)

    if is_feature_enabled("memories"):
        tools.append(MEMORY_TOOL_DEFINITION)

    if is_feature_enabled("alter_egos"):
        tools.append(EGO_TOOL_DEFINITION)

    if is_feature_enabled("directors"):
        tools.append(DIRECTOR_TOOL_DEFINITION)

    if is_feature_enabled("subagents"):
        tools.append(SUBAGENT_TOOL_DEFINITION)

    if is_feature_enabled("marketplace"):
        tools.append(MARKETPLACE_TOOL_DEFINITION)

    if is_feature_enabled("scheduled"):
        tools.append(SCHEDULE_TOOL_DEFINITION)

    return tools
```

### 2.3 Modificar el router de FastAPI

```python
# En la funcion create_app() o donde se registran los routers:
app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(files_router)
app.include_router(images_router)
app.include_router(settings_router)

if is_feature_enabled("directors"):
    app.include_router(directors_router)
```

---

## Paso 3: Modificar el Frontend

### 3.1 Crear store de licencia: `useSubscriptionStore.ts`

```typescript
import { create } from 'zustand';
import { api } from '@/lib/api';

interface SubscriptionState {
  tier: 'community' | 'pro' | 'enterprise';
  features: Record<string, boolean>;
  loading: boolean;
  fetchLicense: () => Promise<void>;
  isFeatureEnabled: (feature: string) => boolean;
}

export const useSubscriptionStore = create<SubscriptionState>((set, get) => ({
  tier: 'community',
  features: {},
  loading: true,

  fetchLicense: async () => {
    try {
      const data = await api.get('/api/license');
      set({ tier: data.tier, features: data.features, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  isFeatureEnabled: (feature: string) => {
    return get().features[feature] ?? false;
  },
}));
```

### 3.2 Crear componente `PremiumGate.tsx`

```tsx
import { useSubscriptionStore } from '@/stores/useSubscriptionStore';
import { useTranslation } from '@/hooks/useTranslation';

interface Props {
  feature: string;
  requiredTier: 'pro' | 'enterprise';
  children: React.ReactNode;
}

export function PremiumGate({ feature, requiredTier, children }: Props) {
  const { isFeatureEnabled } = useSubscriptionStore();
  const { t } = useTranslation();

  if (isFeatureEnabled(feature)) {
    return <>{children}</>;
  }

  return (
    <div className="relative">
      <div className="opacity-30 pointer-events-none blur-sm">
        {children}
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="bg-surface border border-surface2 rounded-2xl p-8 text-center max-w-sm">
          <div className="text-4xl mb-4">
            {requiredTier === 'enterprise' ? '🏢' : '⭐'}
          </div>
          <h3 className="text-lg font-semibold mb-2">
            Rain {requiredTier === 'enterprise' ? 'Enterprise' : 'Pro'}
          </h3>
          <p className="text-text2 text-sm mb-4">
            {t('upgrade_description')}
          </p>
          <a
            href="https://rain-assistant.com/#pricing"
            target="_blank"
            className="btn-primary text-sm"
          >
            {t('view_plans')}
          </a>
        </div>
      </div>
    </div>
  );
}
```

### 3.3 Usar PremiumGate en los panels

```tsx
// En page.tsx o donde se renderizan los panels:

// Panel de Memories (Pro)
<PremiumGate feature="memories" requiredTier="pro">
  <MemoriesPanel />
</PremiumGate>

// Panel de Directors (Enterprise)
<PremiumGate feature="directors" requiredTier="enterprise">
  <DirectorsPanel />
</PremiumGate>
```

### 3.4 Agregar badge PRO/ENTERPRISE en TabBar

```tsx
// En TabBar.tsx, junto al nombre de cada tab:
{tab.premium && (
  <span className="ml-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full
    bg-gradient-to-r from-cyan to-mauve text-bg-deep">
    {tab.requiredTier === 'enterprise' ? 'ENT' : 'PRO'}
  </span>
)}
```

---

## Paso 4: Modificar pyproject.toml

```toml
[project]
name = "rain-assistant"
license = "AGPL-3.0-only"   # <-- Cambiar de Apache-2.0

# Agregar feature_flags.py a la lista de modulos
[tool.setuptools]
py-modules = [
    "server",
    "feature_flags",      # <-- NUEVO
    "shared_state",
    "database",
    # ... resto igual
]
```

---

## Paso 5: Crear script de separacion

### `scripts/prepare_public_repo.sh`

```bash
#!/bin/bash
# Script para preparar el repo publico (solo core)
# USO: bash scripts/prepare_public_repo.sh /ruta/destino

set -e
DEST=${1:-"../rain-assistant-public"}

echo "=== Preparando repo publico en: $DEST ==="

mkdir -p "$DEST"

# --- Copiar archivos CORE ---
echo "[1/6] Copiando archivos core..."

# Root files
cp server.py main.py database.py key_manager.py "$DEST/"
cp transcriber.py synthesizer.py recorder.py "$DEST/"
cp permission_classifier.py rate_limiter.py "$DEST/"
cp shared_state.py prompt_composer.py "$DEST/"
cp logging_config.py metrics.py claude_client.py "$DEST/"
cp tunnel.py telegram_config.py "$DEST/"
cp feature_flags.py "$DEST/"

# Config files
cp pyproject.toml Dockerfile docker-compose.yml "$DEST/"
cp .env.example .gitignore .dockerignore "$DEST/"
cp CONTRIBUTING.md CHANGELOG.md "$DEST/"
cp MANIFEST.in "$DEST/" 2>/dev/null || true

# Scripts de instalacion
cp install.sh install.ps1 "$DEST/"
cp build.sh build.bat setup.sh setup.bat "$DEST/"

# Landing page
cp landing.html "$DEST/"

echo "[2/6] Copiando directorios core..."

# Directorios CORE completos
cp -r providers/ "$DEST/providers/"
cp -r tools/ "$DEST/tools/"
cp -r voice/ "$DEST/voice/"
cp -r utils/ "$DEST/utils/"
cp -r routes/ "$DEST/routes/"

# Remover rutas premium de routes/
rm -f "$DEST/routes/directors.py"

echo "[3/6] Copiando frontend..."
cp -r frontend/ "$DEST/frontend/"
cp -r static/ "$DEST/static/"

echo "[4/6] Copiando tests core..."
mkdir -p "$DEST/tests"
cp tests/conftest.py "$DEST/tests/"
cp tests/test_websocket.py "$DEST/tests/"
cp tests/test_server_api.py "$DEST/tests/"
cp tests/test_server_auth.py "$DEST/tests/"
cp tests/test_permission_classifier.py "$DEST/tests/"
cp tests/test_database.py "$DEST/tests/"

echo "[5/6] Copiando docs..."
mkdir -p "$DEST/docs"
cp docs/PROJECT_STATUS.md "$DEST/docs/" 2>/dev/null || true
cp docs/RELEASE_GUIDE.md "$DEST/docs/" 2>/dev/null || true

echo "[6/6] Copiando CI/CD..."
cp -r .github/ "$DEST/.github/"

# --- Copiar README y LICENSE del Open Core ---
cp docs/README_PUBLIC.md "$DEST/README.md"

# --- Crear LICENSE AGPL-3.0 ---
# (Descargar texto completo de AGPL-3.0)
echo "TODO: Descargar AGPL-3.0 license text a $DEST/LICENSE"

# --- Crear stubs para modulos premium ---
echo "[BONUS] Creando stubs para imports premium..."
mkdir -p "$DEST/plugins" "$DEST/documents" "$DEST/memories"
mkdir -p "$DEST/alter_egos" "$DEST/directors" "$DEST/marketplace"
mkdir -p "$DEST/subagents" "$DEST/scheduled_tasks"

# Crear __init__.py vacios para que los imports no fallen
for dir in plugins documents memories alter_egos directors marketplace subagents scheduled_tasks; do
    echo "# Rain Pro feature - https://rain-assistant.com/#pricing" > "$DEST/$dir/__init__.py"
done

echo ""
echo "=== Repo publico listo en: $DEST ==="
echo ""
echo "Archivos NO incluidos (PREMIUM):"
echo "  - documents/*.py (RAG system)"
echo "  - memories/*.py (semantic memories)"
echo "  - alter_egos/*.py (personalities)"
echo "  - directors/*.py (autonomous agents)"
echo "  - plugins/*.py (plugin engine)"
echo "  - marketplace/*.py (plugin store)"
echo "  - subagents/*.py (multi-agent)"
echo "  - scheduled_tasks/*.py (cron)"
echo "  - computer_use*.py (desktop automation)"
echo "  - telegram_bot.py (telegram interface)"
echo "  - rain_flutter/ (mobile app)"
echo "  - routes/directors.py"
echo ""
echo "Siguiente paso: cd $DEST && git init && git add . && git commit -m 'Initial public release'"
```

---

## Paso 6: Verificar que el Core funciona solo

### Tests a ejecutar despues de la separacion:

```bash
# Desde el repo publico
cd rain-assistant-public

# 1. Instalar solo core deps
pip install -e .

# 2. Verificar que el server arranca
python -c "from server import create_app; print('Server OK')"

# 3. Verificar providers
python -c "from providers import get_provider; print('Providers OK')"

# 4. Verificar tools
python -c "from tools.definitions import get_all_tool_definitions; print(f'{len(get_all_tool_definitions())} tools')"

# 5. Ejecutar tests del core
pytest tests/ -v

# 6. Verificar que features premium estan deshabilitadas
python -c "from feature_flags import get_all_features; print(get_all_features())"
# Debe mostrar todo en False
```

---

## Checklist de Lanzamiento

### Pre-lanzamiento
- [ ] Implementar `feature_flags.py`
- [ ] Hacer imports condicionales en `server.py`
- [ ] Verificar que server arranca sin modulos premium
- [ ] Actualizar `tools/definitions.py` para filtrar tools premium
- [ ] Agregar `PremiumGate` al frontend
- [ ] Agregar `useSubscriptionStore`
- [ ] Agregar endpoint `/api/license`
- [ ] Escribir tests para feature flags
- [ ] Cambiar licencia a AGPL-3.0
- [ ] Preparar README del repo publico
- [ ] Ejecutar script de separacion
- [ ] Verificar que tests del core pasan en repo separado

### Lanzamiento
- [ ] Crear repo publico en GitHub
- [ ] Push del core
- [ ] Publicar en PyPI (version core)
- [ ] Crear GitHub Release con changelog
- [ ] Actualizar landing page con links reales
- [ ] Publicar en Product Hunt
- [ ] Publicar en Reddit (r/programming, r/artificial, r/selfhosted)
- [ ] Publicar en Hacker News
- [ ] Crear video demo para YouTube

### Post-lanzamiento
- [ ] Configurar Stripe/Lemon Squeezy para pagos
- [ ] Implementar sistema de license keys
- [ ] Dashboard de usuario para gestionar licencia
- [ ] Crear Discord server para comunidad
- [ ] Documentar como contribuir al core

---

## Notas Importantes

1. **No apresurarse**: Mejor lanzar un core solido que un producto a medias
2. **Feature flags primero**: Implementar feature_flags.py ANTES de separar repos
3. **Tests son clave**: Si el core no pasa tests, no publicar
4. **La landing vende**: Invertir tiempo en screenshots bonitos y un video demo
5. **Comunidad primero**: Los primeros 100 usuarios son los mas importantes
