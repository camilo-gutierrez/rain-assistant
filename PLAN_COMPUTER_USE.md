# Plan de Implementación: Computer Use para Rain Assistant

> **Fecha**: 2026-02-16
> **Autor**: Rain (Claude Agent)
> **Estado**: Planificación
> **Riesgo**: Alto — Acceso directo al sistema operativo
> **Estimación**: ~1500-2000 líneas nuevas/modificadas

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Arquitectura Propuesta](#2-arquitectura-propuesta)
3. [Dependencias Nuevas](#3-dependencias-nuevas)
4. [Fase 1: Backend — Módulo computer_use.py](#4-fase-1-backend--módulo-computer_usepy)
5. [Fase 2: Backend — Integración con server.py](#5-fase-2-backend--integración-con-serverpy)
6. [Fase 3: Backend — Sistema de Permisos](#6-fase-3-backend--sistema-de-permisos)
7. [Fase 4: Frontend — Tipos y Store](#7-fase-4-frontend--tipos-y-store)
8. [Fase 5: Frontend — Componentes UI](#8-fase-5-frontend--componentes-ui)
9. [Fase 6: Frontend — WebSocket y Hooks](#9-fase-6-frontend--websocket-y-hooks)
10. [Fase 7: Seguridad y Rate Limiting](#10-fase-7-seguridad-y-rate-limiting)
11. [Fase 8: Testing y QA](#11-fase-8-testing-y-qa)
12. [Guía de Rollback](#12-guía-de-rollback)
13. [Consideraciones de Costo](#13-consideraciones-de-costo)
14. [Archivos Afectados (Resumen)](#14-archivos-afectados-resumen)

---

## 1. Resumen Ejecutivo

### Qué es Computer Use
La API de Computer Use de Anthropic permite que Claude **vea la pantalla** (screenshots), **mueva el ratón**, **escriba con el teclado** y **controle aplicaciones** de forma autónoma. Es una API beta que requiere un header especial y usa un agent loop diferente al actual.

### Cómo Encaja con Rain
Rain actualmente usa el **Claude Agent SDK** (`claude_agent_sdk`) con su propio sistema de herramientas (Read, Write, Bash, etc.). Computer Use usa la **API directa de Anthropic** (`anthropic` SDK) con herramientas especiales (`computer_20250124`). Necesitamos un **segundo modo de operación** que coexista con el modo actual.

### Enfoque: Modo Dual
```
┌─────────────────────────────────────────────────────┐
│  Rain Assistant                                      │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │ Modo Coding      │  │ Modo Computer Use        │ │
│  │ (Actual)         │  │ (Nuevo)                  │ │
│  │                  │  │                          │ │
│  │ claude_agent_sdk │  │ anthropic SDK (beta)     │ │
│  │ Read/Write/Bash  │  │ Screenshot/Click/Type    │ │
│  │ Permission 3-tier│  │ Permission COMPUTER-tier │ │
│  │ Text streaming   │  │ Text + Screenshot stream │ │
│  └──────────────────┘  └──────────────────────────┘ │
│                                                      │
│  Compartido: WebSocket, Auth, Database, Frontend     │
└─────────────────────────────────────────────────────┘
```

---

## 2. Arquitectura Propuesta

### Flujo de Computer Use

```
Usuario (Frontend)                    Backend (server.py)                  PC (Windows)
─────────────────                    ───────────────────                  ────────────

1. "Abre Chrome y
    busca gatitos"   ──WS──►
                              2. Envía a Claude API
                                 con computer_20250124
                              ◄── Claude: screenshot
                              3. Captura pantalla ────────────────────►  📸
                              ◄───────────────────── PNG base64
                              4. Envía screenshot
                                 a Claude API
                              ◄── Claude: left_click [x,y]
                              5. Ejecuta click ───────────────────────►  🖱️
                              ◄───────────────────── OK
                              6. Captura nuevo
                                 screenshot ──────────────────────────►  📸
                              ◄── (repite hasta completar)

                     ◄──WS── 7. Envía screenshots
                                 + acciones al frontend
                                 en tiempo real
```

### Agent Loop de Computer Use (Diferente al actual)

El modo actual usa `claude_agent_sdk` que maneja su propio agent loop internamente.
Computer Use requiere un **agent loop manual** usando la API directa de Anthropic:

```python
# Pseudocódigo del agent loop
while True:
    response = client.beta.messages.create(
        model="claude-sonnet-4-5",
        tools=[computer_tool, bash_tool, text_editor_tool],
        messages=conversation,
        betas=["computer-use-2025-01-24"],
    )

    # Procesar respuesta
    tool_results = []
    for block in response.content:
        if block.type == "text":
            # Enviar texto al frontend via WS
            await send({"type": "assistant_text", ...})

        elif block.type == "tool_use":
            if block.name == "computer":
                # Ejecutar acción de computer use
                result = await execute_computer_action(block.input)
                # Enviar screenshot al frontend
                await send({"type": "computer_screenshot", ...})
            elif block.name == "bash":
                result = await execute_bash(block.input)
            elif block.name == "str_replace_based_edit_tool":
                result = await execute_text_edit(block.input)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

    if not tool_results:
        break  # Claude terminó

    conversation.append({"role": "assistant", "content": response.content})
    conversation.append({"role": "user", "content": tool_results})
```

---

## 3. Dependencias Nuevas

### Python (agregar a `requirements.txt`)
```
anthropic>=0.79.0    # SDK directo de Anthropic (para beta.messages.create)
pyautogui>=0.9.54    # Control de ratón y teclado
mss>=9.0.0           # Screenshots rápidos (más rápido que pyautogui)
Pillow>=10.0.0       # Redimensionar screenshots
```

### Frontend (sin cambios en package.json)
No se necesitan dependencias nuevas. Las imágenes base64 se renderizan nativamente.

### Verificar compatibilidad
```bash
# pyautogui necesita en Windows:
# - No requiere dependencias extra en Windows
# - En Linux necesitaría: python3-tk, scrot

# mss no necesita dependencias extra en ningún OS
```

---

## 4. Fase 1: Backend — Módulo `computer_use.py`

### Nuevo archivo: `computer_use.py` (~250-350 líneas)

Este módulo encapsula TODA la interacción con el PC:

```python
"""
computer_use.py — Rain Assistant Computer Use Module
Ejecuta acciones de computer use en el PC local.
"""
import asyncio
import base64
import io
import math
import logging
import subprocess
from typing import Any

import pyautogui
import mss
from PIL import Image

logger = logging.getLogger("rain.computer_use")

# Configuración de PyAutoGUI
pyautogui.FAILSAFE = True       # Mover ratón a esquina superior-izq = ABORT
pyautogui.PAUSE = 0.1           # Pausa entre acciones (100ms)

# Resolución máxima recomendada por Anthropic
MAX_LONG_EDGE = 1568
MAX_TOTAL_PIXELS = 1_150_000


class ComputerUseExecutor:
    """Ejecuta acciones de computer use en el PC local."""

    def __init__(self, display_width: int = 0, display_height: int = 0):
        """
        Args:
            display_width: Ancho real de la pantalla (0 = autodetectar)
            display_height: Alto real de la pantalla (0 = autodetectar)
        """
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Monitor principal
            self.screen_width = display_width or monitor["width"]
            self.screen_height = display_height or monitor["height"]

        self.scale_factor = self._calculate_scale_factor()
        self.scaled_width = int(self.screen_width * self.scale_factor)
        self.scaled_height = int(self.screen_height * self.scale_factor)

        logger.info(
            f"ComputerUse: {self.screen_width}x{self.screen_height} "
            f"→ scaled {self.scaled_width}x{self.scaled_height} "
            f"(factor: {self.scale_factor:.3f})"
        )

    def _calculate_scale_factor(self) -> float:
        """Calcula factor de escala para cumplir límites de la API."""
        long_edge = max(self.screen_width, self.screen_height)
        total_pixels = self.screen_width * self.screen_height

        long_edge_scale = MAX_LONG_EDGE / long_edge
        total_pixels_scale = math.sqrt(MAX_TOTAL_PIXELS / total_pixels)

        return min(1.0, long_edge_scale, total_pixels_scale)

    def _scale_coordinates_to_screen(self, x: int, y: int) -> tuple[int, int]:
        """Convierte coordenadas de Claude (escaladas) a coordenadas reales de pantalla."""
        screen_x = int(x / self.scale_factor)
        screen_y = int(y / self.scale_factor)
        # Clamp a los límites de pantalla
        screen_x = max(0, min(screen_x, self.screen_width - 1))
        screen_y = max(0, min(screen_y, self.screen_height - 1))
        return screen_x, screen_y

    async def take_screenshot(self) -> str:
        """Captura pantalla y retorna como base64 PNG."""
        def _capture():
            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                # Redimensionar al tamaño escalado
                img = img.resize(
                    (self.scaled_width, self.scaled_height),
                    Image.LANCZOS,
                )
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", optimize=True)
                return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")

        return await asyncio.to_thread(_capture)

    async def execute_action(self, action: str, params: dict[str, Any]) -> list[dict]:
        """
        Ejecuta una acción de computer use.

        Returns:
            Lista de content blocks para enviar como tool_result a la API.
            Generalmente incluye un screenshot después de la acción.
        """
        try:
            await self._do_action(action, params)
        except Exception as e:
            logger.error(f"Computer action failed: {action} - {e}")
            return [{"type": "text", "text": f"Error executing {action}: {str(e)}"}]

        # Después de cada acción, tomar screenshot
        if action != "screenshot":
            await asyncio.sleep(0.3)  # Esperar a que la UI se actualice

        screenshot_b64 = await self.take_screenshot()
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot_b64,
                },
            }
        ]

    async def _do_action(self, action: str, params: dict[str, Any]) -> None:
        """Ejecuta la acción real con PyAutoGUI."""

        def _run():
            if action == "screenshot":
                pass  # Se maneja arriba

            elif action == "left_click":
                x, y = self._scale_coordinates_to_screen(*params["coordinate"])
                modifier = params.get("text")
                if modifier:
                    pyautogui.keyDown(modifier)
                pyautogui.click(x, y)
                if modifier:
                    pyautogui.keyUp(modifier)

            elif action == "right_click":
                x, y = self._scale_coordinates_to_screen(*params["coordinate"])
                pyautogui.rightClick(x, y)

            elif action == "double_click":
                x, y = self._scale_coordinates_to_screen(*params["coordinate"])
                pyautogui.doubleClick(x, y)

            elif action == "triple_click":
                x, y = self._scale_coordinates_to_screen(*params["coordinate"])
                pyautogui.tripleClick(x, y)

            elif action == "middle_click":
                x, y = self._scale_coordinates_to_screen(*params["coordinate"])
                pyautogui.middleClick(x, y)

            elif action == "mouse_move":
                x, y = self._scale_coordinates_to_screen(*params["coordinate"])
                pyautogui.moveTo(x, y)

            elif action == "left_click_drag":
                sx, sy = self._scale_coordinates_to_screen(*params["start_coordinate"])
                ex, ey = self._scale_coordinates_to_screen(*params["coordinate"])
                pyautogui.moveTo(sx, sy)
                pyautogui.mouseDown()
                pyautogui.moveTo(ex, ey, duration=0.5)
                pyautogui.mouseUp()

            elif action == "left_mouse_down":
                pyautogui.mouseDown()

            elif action == "left_mouse_up":
                pyautogui.mouseUp()

            elif action == "type":
                text = params.get("text", "")
                # PyAutoGUI typewrite solo soporta ASCII
                # Para Unicode, usamos pyperclip + paste
                import pyperclip
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")

            elif action == "key":
                keys = params.get("text", "")
                # Formato: "ctrl+s", "alt+tab", "Return", etc.
                if "+" in keys:
                    pyautogui.hotkey(*keys.split("+"))
                else:
                    pyautogui.press(keys)

            elif action == "scroll":
                x, y = self._scale_coordinates_to_screen(*params.get("coordinate", [0, 0]))
                direction = params.get("scroll_direction", "down")
                amount = params.get("scroll_amount", 3)

                pyautogui.moveTo(x, y)
                if direction == "down":
                    pyautogui.scroll(-amount)
                elif direction == "up":
                    pyautogui.scroll(amount)
                elif direction == "left":
                    pyautogui.hscroll(-amount)
                elif direction == "right":
                    pyautogui.hscroll(amount)

            elif action == "hold_key":
                key = params.get("text", "")
                duration = params.get("duration", 1.0)
                pyautogui.keyDown(key)
                import time
                time.sleep(duration)
                pyautogui.keyUp(key)

            elif action == "wait":
                duration = params.get("duration", 1.0)
                import time
                time.sleep(min(duration, 10.0))  # Max 10 segundos

            else:
                raise ValueError(f"Unknown computer action: {action}")

        await asyncio.to_thread(_run)

    def get_tool_definition(self) -> dict:
        """Retorna la definición del tool para la API de Anthropic."""
        return {
            "type": "computer_20250124",
            "name": "computer",
            "display_width_px": self.scaled_width,
            "display_height_px": self.scaled_height,
        }

    def get_display_info(self) -> dict:
        """Info de pantalla para el frontend."""
        return {
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "scaled_width": self.scaled_width,
            "scaled_height": self.scaled_height,
            "scale_factor": self.scale_factor,
        }
```

### Puntos Clave:
- **`mss`** para screenshots (más rápido que pyautogui, ~20ms vs ~300ms)
- **`pyautogui.FAILSAFE = True`** — mover ratón a esquina superior-izquierda aborta todo
- **Escalado de coordenadas** — Claude trabaja con resolución reducida, las coordenadas se escalan de vuelta
- **Thread pool** — todas las operaciones GUI corren en `asyncio.to_thread()` para no bloquear el event loop
- **Unicode support** — `type` usa clipboard para soportar texto en español, emojis, etc.

---

## 5. Fase 2: Backend — Integración con `server.py`

### 5.1 Nuevos imports (agregar al inicio de server.py)

```python
from anthropic import AsyncAnthropic  # SDK directo para Computer Use
from computer_use import ComputerUseExecutor
```

### 5.2 Nuevas constantes

```python
# Computer Use Configuration
COMPUTER_USE_BETA = "computer-use-2025-01-24"
COMPUTER_USE_MODEL = "claude-sonnet-4-5"  # Mejor relación costo/precisión
COMPUTER_USE_MAX_TOKENS = 4096
COMPUTER_USE_MAX_ITERATIONS = 50  # Máximo de acciones por tarea
COMPUTER_USE_TIMEOUT = 600  # 10 minutos máx por tarea
```

### 5.3 Nuevo estado por agente

Modificar la estructura de `agents` dict para soportar ambos modos:

```python
# Antes:
agents[agent_id] = {
    "client": client,           # ClaudeSDKClient
    "cwd": resolved_cwd,
    "streaming_task": None,
}

# Después (agregar campos):
agents[agent_id] = {
    "client": client,           # ClaudeSDKClient (modo coding)
    "cwd": resolved_cwd,
    "streaming_task": None,
    # === NUEVOS CAMPOS ===
    "mode": "coding",           # "coding" | "computer_use"
    "computer_executor": None,  # ComputerUseExecutor instance
    "computer_messages": [],    # Historial de mensajes para la API
    "computer_task": None,      # asyncio.Task del agent loop
    "computer_paused": False,   # Modo supervisado: pausado esperando OK
}
```

### 5.4 Nuevo mensaje WebSocket: `set_mode`

```python
# Frontend → Backend
{"type": "set_mode", "agent_id": "tab1", "mode": "computer_use"}
{"type": "set_mode", "agent_id": "tab1", "mode": "coding"}
```

**Handler:**
```python
elif msg_type == "set_mode":
    agent_id = data.get("agent_id", "")
    mode = data.get("mode", "coding")

    if agent_id not in agents:
        await send({"type": "error", "agent_id": agent_id, "text": "Agent not found"})
        return

    if mode == "computer_use":
        # Inicializar executor de computer use
        executor = ComputerUseExecutor()
        agents[agent_id]["mode"] = "computer_use"
        agents[agent_id]["computer_executor"] = executor
        agents[agent_id]["computer_messages"] = []

        await send({
            "type": "mode_changed",
            "agent_id": agent_id,
            "mode": "computer_use",
            "display_info": executor.get_display_info(),
        })

    elif mode == "coding":
        # Limpiar estado de computer use
        agents[agent_id]["mode"] = "coding"
        agents[agent_id]["computer_executor"] = None
        agents[agent_id]["computer_messages"] = []

        await send({
            "type": "mode_changed",
            "agent_id": agent_id,
            "mode": "coding",
        })
```

### 5.5 Agent Loop de Computer Use

```python
async def computer_use_loop(
    agent_id: str,
    user_text: str,
    api_key: str,
    executor: ComputerUseExecutor,
    send_ws: callable,
    agents_dict: dict,
    supervised: bool = True,
):
    """
    Agent loop para Computer Use.
    Envía mensajes a Claude API y ejecuta acciones en el PC.
    """
    client = AsyncAnthropic(api_key=api_key)
    agent = agents_dict[agent_id]

    # Configurar tools
    tools = [
        executor.get_tool_definition(),
        {"type": "bash_20250124", "name": "bash"},
        {"type": "text_editor_20250124", "name": "str_replace_based_edit_tool"},
    ]

    # System prompt específico para computer use
    system_prompt = (
        "You are Rain, an AI assistant with full computer access. "
        "You can see the screen, control the mouse and keyboard. "
        "After each action, take a screenshot to verify the result. "
        "Be precise with clicks. If an action fails, try an alternative approach. "
        "Use keyboard shortcuts when possible (they're more reliable than mouse clicks). "
        "The user's OS is Windows. Respond in Spanish unless told otherwise."
    )

    # Mensaje inicial con screenshot del estado actual
    initial_screenshot = await executor.take_screenshot()
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": initial_screenshot,
                    },
                },
                {"type": "text", "text": user_text},
            ],
        }
    ]
    agent["computer_messages"] = messages

    # Enviar screenshot inicial al frontend
    await send_ws({
        "type": "computer_screenshot",
        "agent_id": agent_id,
        "image": initial_screenshot,
        "action": "initial",
        "description": "Estado inicial de la pantalla",
    })

    iterations = 0
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        while iterations < COMPUTER_USE_MAX_ITERATIONS:
            iterations += 1

            # Verificar si fue cancelado
            if agents_dict.get(agent_id, {}).get("computer_task_cancelled"):
                await send_ws({
                    "type": "status",
                    "agent_id": agent_id,
                    "text": "Computer use cancelled by user.",
                })
                break

            # Llamar a Claude API
            response = await client.beta.messages.create(
                model=COMPUTER_USE_MODEL,
                max_tokens=COMPUTER_USE_MAX_TOKENS,
                system=system_prompt,
                tools=tools,
                messages=messages,
                betas=[COMPUTER_USE_BETA],
            )

            # Tracking de tokens
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # Procesar respuesta
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []

            for block in assistant_content:
                if hasattr(block, "text"):
                    # Texto del asistente
                    await send_ws({
                        "type": "assistant_text",
                        "agent_id": agent_id,
                        "text": block.text,
                    })

                elif block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input if hasattr(block, "input") else {}

                    # === SISTEMA DE PERMISOS ===
                    if supervised:
                        # Enviar solicitud de permiso al frontend
                        action_desc = _describe_computer_action(tool_name, tool_input)
                        permission_granted = await _request_computer_permission(
                            agent_id, tool_name, tool_input, action_desc, send_ws
                        )
                        if not permission_granted:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "Action denied by user.",
                                "is_error": True,
                            })
                            continue

                    # Enviar acción al frontend (preview)
                    await send_ws({
                        "type": "computer_action",
                        "agent_id": agent_id,
                        "tool": tool_name,
                        "action": tool_input.get("action", "unknown"),
                        "input": tool_input,
                        "iteration": iterations,
                    })

                    # Ejecutar acción
                    if tool_name == "computer":
                        action = tool_input.get("action", "screenshot")
                        result_content = await executor.execute_action(action, tool_input)

                        # Enviar screenshot al frontend
                        for item in result_content:
                            if item.get("type") == "image":
                                await send_ws({
                                    "type": "computer_screenshot",
                                    "agent_id": agent_id,
                                    "image": item["source"]["data"],
                                    "action": action,
                                    "description": _describe_computer_action(tool_name, tool_input),
                                    "iteration": iterations,
                                })

                    elif tool_name == "bash":
                        # Ejecutar comando bash
                        cmd = tool_input.get("command", "")
                        try:
                            proc = await asyncio.create_subprocess_shell(
                                cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            stdout, stderr = await asyncio.wait_for(
                                proc.communicate(), timeout=30
                            )
                            output = stdout.decode() + stderr.decode()
                            result_content = [{"type": "text", "text": output[:10000]}]
                        except Exception as e:
                            result_content = [{"type": "text", "text": f"Error: {e}"}]

                    elif tool_name == "str_replace_based_edit_tool":
                        # Text editor tool
                        # TODO: Implementar si es necesario
                        result_content = [{"type": "text", "text": "Text editor not yet implemented in computer use mode."}]

                    else:
                        result_content = [{"type": "text", "text": f"Unknown tool: {tool_name}"}]

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    })

            # Si no hubo tool_use, Claude terminó
            if not tool_results:
                break

            # Agregar resultados para la siguiente iteración
            messages.append({"role": "user", "content": tool_results})

        # Calcular costo estimado (Sonnet 4.5 pricing)
        input_cost = total_input_tokens * 3.0 / 1_000_000   # $3/M input
        output_cost = total_output_tokens * 15.0 / 1_000_000  # $15/M output
        total_cost = input_cost + output_cost

        # Enviar resultado final
        await send_ws({
            "type": "result",
            "agent_id": agent_id,
            "cost": round(total_cost, 4),
            "usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            },
            "turns": iterations,
            "duration_ms": 0,  # TODO: calcular
            "session_id": None,
            "is_computer_use": True,
        })

    except asyncio.CancelledError:
        await send_ws({
            "type": "status",
            "agent_id": agent_id,
            "text": "Computer use task cancelled.",
        })
    except Exception as e:
        logger.error(f"Computer use loop error: {e}", exc_info=True)
        await send_ws({
            "type": "error",
            "agent_id": agent_id,
            "text": f"Computer use error: {str(e)}",
        })


def _describe_computer_action(tool_name: str, tool_input: dict) -> str:
    """Genera descripción legible de una acción para el UI."""
    if tool_name == "computer":
        action = tool_input.get("action", "unknown")
        if action == "screenshot":
            return "Capturar pantalla"
        elif action in ("left_click", "right_click", "double_click"):
            coord = tool_input.get("coordinate", [0, 0])
            return f"{action.replace('_', ' ').title()} en ({coord[0]}, {coord[1]})"
        elif action == "type":
            text = tool_input.get("text", "")[:50]
            return f'Escribir: "{text}"'
        elif action == "key":
            return f"Tecla: {tool_input.get('text', '')}"
        elif action == "scroll":
            direction = tool_input.get("scroll_direction", "down")
            return f"Scroll {direction}"
        elif action == "mouse_move":
            coord = tool_input.get("coordinate", [0, 0])
            return f"Mover ratón a ({coord[0]}, {coord[1]})"
        else:
            return f"Acción: {action}"
    elif tool_name == "bash":
        cmd = tool_input.get("command", "")[:80]
        return f"Ejecutar: {cmd}"
    return f"Tool: {tool_name}"
```

### 5.6 Modificar handler de `send_message`

```python
elif msg_type == "send_message":
    text = data.get("text", "").strip()
    agent_id = data.get("agent_id", "")

    if not text or not agent_id or agent_id not in agents:
        # ... validación existente ...
        return

    agent = agents[agent_id]

    # === NUEVO: Bifurcación por modo ===
    if agent.get("mode") == "computer_use":
        # Modo Computer Use — agent loop manual
        await cancel_computer_use_task(agent_id)

        supervised = True  # TODO: leer de settings del agente

        task = asyncio.create_task(
            computer_use_loop(
                agent_id=agent_id,
                user_text=text,
                api_key=api_key,
                executor=agent["computer_executor"],
                send_ws=send,
                agents_dict=agents,
                supervised=supervised,
            )
        )
        agent["computer_task"] = task
    else:
        # Modo Coding — flujo existente (sin cambios)
        # ... código actual de query + stream_claude_response ...
```

### 5.7 Nuevos mensajes WebSocket

**Backend → Frontend (nuevos tipos):**

| Tipo | Campos | Descripción |
|------|--------|-------------|
| `mode_changed` | `agent_id, mode, display_info?` | Confirmación de cambio de modo |
| `computer_screenshot` | `agent_id, image (base64), action, description, iteration` | Screenshot en tiempo real |
| `computer_action` | `agent_id, tool, action, input, iteration` | Preview de acción a ejecutar |

**Frontend → Backend (nuevos tipos):**

| Tipo | Campos | Descripción |
|------|--------|-------------|
| `set_mode` | `agent_id, mode` | Cambiar modo del agente |
| `computer_permission_response` | `request_id, approved, agent_id` | Respuesta a permiso de computer use |

---

## 6. Fase 3: Backend — Sistema de Permisos

### 6.1 Nuevo nivel en `permission_classifier.py`

```python
class PermissionLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    COMPUTER = "computer"  # NUEVO


# Nuevas categorías de acciones de computer use
COMPUTER_SAFE_ACTIONS = {"screenshot", "mouse_move", "wait"}
COMPUTER_MODERATE_ACTIONS = {"left_click", "right_click", "double_click",
                             "scroll", "type", "key"}
COMPUTER_DANGEROUS_ACTIONS = {"left_click_drag", "hold_key", "triple_click"}


def classify_computer_action(action: str, params: dict) -> PermissionLevel:
    """Clasifica acciones de computer use."""
    if action in COMPUTER_SAFE_ACTIONS:
        return PermissionLevel.GREEN  # Screenshot y mouse_move auto-aprobados

    # Detectar atajos peligrosos
    if action == "key":
        key_combo = params.get("text", "").lower()
        dangerous_keys = ["alt+f4", "ctrl+alt+delete", "ctrl+shift+delete"]
        if key_combo in dangerous_keys:
            return PermissionLevel.RED

    # Por defecto, todas las acciones de computer use son COMPUTER level
    return PermissionLevel.COMPUTER
```

### 6.2 Modos de Supervisión

```python
class SupervisionMode(str, Enum):
    SUPERVISED = "supervised"      # Cada acción requiere aprobación
    SEMI_AUTO = "semi_auto"        # Solo acciones peligrosas
    AUTONOMOUS = "autonomous"      # Sin confirmación (solo logging)
```

En modo **SUPERVISED** (por defecto):
- Cada acción muestra preview en el frontend
- El usuario ve qué va a hacer Claude y aprueba/deniega
- Más lento pero seguro

En modo **SEMI_AUTO**:
- Screenshots y mouse_move son auto-aprobados
- Clicks, typing y keyboard requieren confirmación
- Buen balance

En modo **AUTONOMOUS**:
- Todo se ejecuta automáticamente
- Solo logging en base de datos
- Para tareas repetitivas y confiables
- **Requiere PIN para activar este modo**

### 6.3 Kill Switch (Emergencia)

```python
# Frontend → Backend
{"type": "emergency_stop", "agent_id": "tab1"}

# Handler:
elif msg_type == "emergency_stop":
    agent_id = data.get("agent_id", "")
    if agent_id in agents:
        # 1. Cancelar el task
        task = agents[agent_id].get("computer_task")
        if task and not task.done():
            task.cancel()

        # 2. Activar failsafe de PyAutoGUI
        pyautogui.FAILSAFE_TRIGGERED = True

        # 3. Liberar todas las teclas/botones
        pyautogui.mouseUp()
        pyautogui.keyUp("shift")
        pyautogui.keyUp("ctrl")
        pyautogui.keyUp("alt")

        # 4. Notificar
        await send({
            "type": "status",
            "agent_id": agent_id,
            "text": "⚠️ EMERGENCY STOP — All computer actions halted.",
        })

        # 5. Log security event
        database.log_security_event(
            "computer_use_emergency_stop",
            "critical",
            client_ip="local",
            token_prefix=token[:8],
            details=f"Emergency stop for agent {agent_id}",
        )
```

---

## 7. Fase 4: Frontend — Tipos y Store

### 7.1 Nuevos tipos en `types.ts`

```typescript
// ========== COMPUTER USE TYPES ==========

/** Modos del agente */
export type AgentMode = "coding" | "computer_use";

/** Modos de supervisión */
export type SupervisionMode = "supervised" | "semi_auto" | "autonomous";

/** Info de pantalla del servidor */
export interface DisplayInfo {
  screen_width: number;
  screen_height: number;
  scaled_width: number;
  scaled_height: number;
  scale_factor: number;
}

/** Mensaje de screenshot de computer use */
export interface ComputerScreenshotMessage extends BaseMessage {
  type: "computer_screenshot";
  image: string;           // base64 PNG
  action: string;          // "left_click", "type", etc.
  description: string;     // "Click en (500, 300)"
  iteration: number;
}

/** Mensaje de acción de computer use (preview) */
export interface ComputerActionMessage extends BaseMessage {
  type: "computer_action";
  tool: string;
  action: string;
  input: Record<string, unknown>;
  iteration: number;
}

// Agregar a AnyMessage union:
export type AnyMessage =
  | UserMessage
  | AssistantMessage
  | SystemMessage
  | ToolUseMessage
  | ToolResultMessage
  | PermissionRequestMessage
  | ComputerScreenshotMessage   // NUEVO
  | ComputerActionMessage;       // NUEVO
```

### 7.2 Modificar `useAgentStore.ts`

```typescript
// Agregar al interface Agent:
interface Agent {
  // ... campos existentes ...

  // === NUEVOS CAMPOS ===
  mode: AgentMode;                  // "coding" | "computer_use"
  supervisionMode: SupervisionMode; // "supervised" | "semi_auto" | "autonomous"
  displayInfo: DisplayInfo | null;  // Info de resolución
  computerIteration: number;        // Iteración actual del agent loop
  lastScreenshot: string | null;    // Último screenshot (base64)
}

// Agregar al createAgent():
createAgent: () => {
  // ...existente...
  return {
    // ...existente...
    mode: "coding",
    supervisionMode: "supervised",
    displayInfo: null,
    computerIteration: 0,
    lastScreenshot: null,
  };
}

// Nuevas acciones:
setAgentMode: (agentId: string, mode: AgentMode) => void;
setSupervisionMode: (agentId: string, mode: SupervisionMode) => void;
setDisplayInfo: (agentId: string, info: DisplayInfo) => void;
updateLastScreenshot: (agentId: string, image: string) => void;
incrementComputerIteration: (agentId: string) => void;
```

### 7.3 Nuevo store: `useComputerUseStore.ts` (Opcional)

Si la lógica crece mucho, considerar un store dedicado. Por ahora, mantener en `useAgentStore` es suficiente.

---

## 8. Fase 5: Frontend — Componentes UI

### 8.1 Nuevo componente: `ComputerUseViewer.tsx`

Panel principal que muestra los screenshots en tiempo real:

```
┌─────────────────────────────────────────────────┐
│  🖥️ Computer Use  │ Iteration: 5/50 │ ⏹ STOP │
├─────────────────────────────────────────────────┤
│                                                  │
│          ┌────────────────────────┐              │
│          │                        │              │
│          │   Screenshot actual    │              │
│          │   (escalado a fit)     │              │
│          │                        │              │
│          │    🔴 cursor marker    │              │
│          │                        │              │
│          └────────────────────────┘              │
│                                                  │
│  Última acción: Click en (500, 300)             │
│  Próxima acción: Escribir "gatitos"  [✓] [✗]   │
│                                                  │
├─────────────────────────────────────────────────┤
│  [📸 Screenshots]  [💬 Chat]  [📊 Actions Log] │
│                                                  │
│  Historial de screenshots con thumbnails         │
│  scrollable horizontalmente                      │
└─────────────────────────────────────────────────┘
```

**Subcomponentes:**
- `ScreenshotViewer.tsx` — Muestra el screenshot actual a escala
- `ActionPreview.tsx` — Preview de la próxima acción con approve/deny
- `ScreenshotTimeline.tsx` — Historial de screenshots como thumbnails
- `ComputerUseToolbar.tsx` — Controles (stop, modo supervisión, iteration counter)
- `EmergencyStopButton.tsx` — Botón grande y rojo de parada de emergencia

### 8.2 Nuevo componente: `ModeToggle.tsx`

Toggle en la TabBar o ChatPanel para cambiar entre modos:

```typescript
// Ubicación: TabBar.tsx o como componente independiente
<ModeToggle
  mode={agent.mode}
  onModeChange={(mode) => {
    send({ type: "set_mode", agent_id: agent.id, mode });
    setAgentMode(agent.id, mode);
  }}
/>
```

Visual: Un toggle/switch con:
- 💻 Coding (icono de terminal)
- 🖥️ Computer Use (icono de monitor)

### 8.3 Modificar `ChatMessages.tsx`

Agregar rendering para los nuevos tipos de mensaje:

```typescript
case "computer_screenshot":
  return <ComputerScreenshotBubble key={msg.id} message={msg} />;

case "computer_action":
  return <ComputerActionBubble key={msg.id} message={msg} />;
```

### 8.4 Nuevo componente: `ComputerScreenshotBubble.tsx`

Muestra un screenshot inline en el chat:

```typescript
const ComputerScreenshotBubble = ({ message }: Props) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex flex-col gap-1 max-w-md">
      <div className="text-xs text-secondary">
        📸 {message.description} (paso {message.iteration})
      </div>
      <img
        src={`data:image/png;base64,${message.image}`}
        alt={message.description}
        className={cn(
          "rounded-lg border cursor-pointer transition-all",
          expanded ? "max-w-full" : "max-w-xs"
        )}
        onClick={() => setExpanded(!expanded)}
      />
    </div>
  );
};
```

### 8.5 Estructura de paneles actualizada

```
page.tsx (orquestador)
├── StatusBar
├── TabBar + ModeToggle (NUEVO)
├── Panels
│   ├── PinPanel
│   ├── ApiKeyPanel
│   ├── FileBrowserPanel
│   ├── ChatPanel (modo coding - sin cambios)
│   ├── ComputerUsePanel (NUEVO - modo computer_use)
│   │   ├── ComputerUseViewer
│   │   │   ├── ScreenshotViewer
│   │   │   ├── ActionPreview
│   │   │   └── ScreenshotTimeline
│   │   ├── ComputerUseToolbar
│   │   ├── EmergencyStopButton
│   │   └── ChatInput (reutilizado)
│   ├── MetricsPanel
│   └── SettingsPanel + SupervisionModeSelector (NUEVO)
└── HistorySidebar
```

---

## 9. Fase 6: Frontend — WebSocket y Hooks

### 9.1 Modificar `useWebSocket.ts`

Agregar handlers para los nuevos mensajes:

```typescript
// Nuevos cases en el switch:

case "mode_changed": {
  const mode = msg.mode as AgentMode;
  agentStore.setAgentMode(agentId, mode);
  if (msg.display_info) {
    agentStore.setDisplayInfo(agentId, msg.display_info);
  }
  break;
}

case "computer_screenshot": {
  if (!agentStore.agents[agentId]) break;

  // Actualizar último screenshot
  agentStore.updateLastScreenshot(agentId, msg.image);

  // Agregar como mensaje al chat
  const screenshotMsg: ComputerScreenshotMessage = {
    id: crypto.randomUUID(),
    type: "computer_screenshot",
    image: msg.image,
    action: msg.action,
    description: msg.description,
    iteration: msg.iteration || 0,
    timestamp: Date.now(),
    animate: true,
  };
  agentStore.appendMessage(agentId, screenshotMsg);
  break;
}

case "computer_action": {
  if (!agentStore.agents[agentId]) break;

  const actionMsg: ComputerActionMessage = {
    id: crypto.randomUUID(),
    type: "computer_action",
    tool: msg.tool,
    action: msg.action,
    input: msg.input,
    iteration: msg.iteration || 0,
    timestamp: Date.now(),
    animate: true,
  };
  agentStore.appendMessage(agentId, actionMsg);
  agentStore.incrementComputerIteration(agentId);
  break;
}
```

### 9.2 Nuevo hook: `useComputerUse.ts` (Opcional)

Si la lógica de computer use crece, extraer a un hook dedicado:

```typescript
export function useComputerUse(agentId: string) {
  const agent = useAgentStore((s) => s.agents[agentId]);
  const send = useConnectionStore((s) => s.send);

  const switchToComputerUse = () => {
    send({ type: "set_mode", agent_id: agentId, mode: "computer_use" });
  };

  const switchToCoding = () => {
    send({ type: "set_mode", agent_id: agentId, mode: "coding" });
  };

  const emergencyStop = () => {
    send({ type: "emergency_stop", agent_id: agentId });
  };

  const setSupervision = (mode: SupervisionMode) => {
    send({ type: "set_supervision", agent_id: agentId, mode });
  };

  return {
    isComputerUse: agent?.mode === "computer_use",
    displayInfo: agent?.displayInfo,
    lastScreenshot: agent?.lastScreenshot,
    iteration: agent?.computerIteration || 0,
    switchToComputerUse,
    switchToCoding,
    emergencyStop,
    setSupervision,
  };
}
```

---

## 10. Fase 7: Seguridad y Rate Limiting

### 10.1 Rate Limiting para Computer Use

```python
# Agregar a rate_limiter.py o constantes de server.py:
RATE_LIMITS["computer_use"] = {
    "max_requests": 10,    # 10 tareas por minuto (no acciones individuales)
    "window_seconds": 60,
}

RATE_LIMITS["computer_screenshot"] = {
    "max_requests": 100,   # 100 screenshots por minuto
    "window_seconds": 60,
}
```

### 10.2 Quotas Diarias

```python
# Agregar a database.py schema:
# Nuevo campo en usage_quotas:
# computer_use_actions INTEGER DEFAULT 0

DAILY_COMPUTER_USE_QUOTA = 500  # Máximo 500 acciones de computer use por día
```

### 10.3 Logging de Acciones

Todas las acciones de computer use deben loguearse en `permission_log`:

```python
database.log_permission_decision(
    agent_id=agent_id,
    tool_name=f"computer:{action}",  # "computer:left_click"
    tool_input=tool_input,
    level="computer",
    decision="approved",
)
```

### 10.4 Blacklist de Aplicaciones (Futuro)

```python
# Opcional: detectar ventana activa antes de ejecutar acción
# Usar pygetwindow para verificar qué app está en foco
BLOCKED_APPS = [
    "1Password", "KeePass", "LastPass",  # Password managers
    "Windows Security",                    # Antivirus
    "Task Manager",                        # Para evitar kill de procesos
]
```

---

## 11. Fase 8: Testing y QA

### 11.1 Tests Unitarios

```python
# test_computer_use.py
class TestComputerUseExecutor:
    def test_scale_factor_calculation(self):
        """Verifica que la resolución se escala correctamente."""
        executor = ComputerUseExecutor(1920, 1080)
        assert executor.scaled_width <= 1568
        assert executor.scaled_height <= 1568
        assert executor.scaled_width * executor.scaled_height <= 1_150_000

    def test_coordinate_scaling(self):
        """Verifica que las coordenadas se escalan de vuelta."""
        executor = ComputerUseExecutor(1920, 1080)
        # Coordenadas en espacio escalado → espacio real
        sx, sy = executor._scale_coordinates_to_screen(500, 300)
        assert 0 <= sx < 1920
        assert 0 <= sy < 1080

    def test_coordinate_clamping(self):
        """Verifica que coordenadas fuera de rango se clampean."""
        executor = ComputerUseExecutor(1920, 1080)
        sx, sy = executor._scale_coordinates_to_screen(99999, 99999)
        assert sx == 1919
        assert sy == 1079
```

### 11.2 Tests de Integración

- [ ] Screenshot se captura correctamente
- [ ] Click en coordenadas exactas funciona
- [ ] Type con Unicode funciona
- [ ] Atajos de teclado funcionan
- [ ] Emergency stop detiene todo
- [ ] Frontend recibe y muestra screenshots
- [ ] Permisos bloquean acciones cuando se deniegan
- [ ] Rate limiting funciona para computer use
- [ ] Agent loop termina correctamente al completar tarea

### 11.3 Tests Manuales Recomendados

1. **"Abre el Notepad y escribe 'Hola Mundo'"** — Test básico
2. **"Abre Chrome y busca el clima"** — Test con navegación web
3. **"Crea una carpeta en el escritorio llamada 'test'"** — Test de filesystem
4. **Emergency stop durante una tarea** — Test de seguridad
5. **Denegar permiso en modo supervisado** — Test de permisos

---

## 12. Guía de Rollback

### ⚠️ IMPORTANTE: Cómo Revertir si Algo Sale Mal

#### Archivos Nuevos (simplemente eliminar):
```
DELETE → computer_use.py
DELETE → frontend/src/components/computer-use/  (directorio completo)
DELETE → frontend/src/hooks/useComputerUse.ts
```

#### Archivos Modificados (revertir cambios):

**1. `server.py`** — Buscar y eliminar:
- Import de `AsyncAnthropic` y `ComputerUseExecutor`
- Constantes `COMPUTER_USE_*`
- Campos nuevos en `agents[agent_id]`: `mode`, `computer_executor`, `computer_messages`, `computer_task`
- Handler de `set_mode`
- Handler de `emergency_stop`
- Handler de `computer_permission_response`
- Bifurcación en `send_message` (eliminar el `if agent.get("mode") == "computer_use"`)
- Función `computer_use_loop()` completa
- Función `_describe_computer_action()` completa
- Función `_request_computer_permission()` completa
- Función `cancel_computer_use_task()` completa

**2. `permission_classifier.py`** — Revertir:
- Eliminar `COMPUTER = "computer"` del enum
- Eliminar `classify_computer_action()` función
- Eliminar `COMPUTER_*_ACTIONS` sets

**3. `frontend/src/lib/types.ts`** — Revertir:
- Eliminar `AgentMode`, `SupervisionMode`, `DisplayInfo`
- Eliminar `ComputerScreenshotMessage`, `ComputerActionMessage`
- Eliminar de `AnyMessage` union

**4. `frontend/src/stores/useAgentStore.ts`** — Revertir:
- Eliminar campos: `mode`, `supervisionMode`, `displayInfo`, `computerIteration`, `lastScreenshot`
- Eliminar acciones: `setAgentMode`, `setSupervisionMode`, `setDisplayInfo`, etc.

**5. `frontend/src/hooks/useWebSocket.ts`** — Revertir:
- Eliminar cases: `mode_changed`, `computer_screenshot`, `computer_action`

**6. `frontend/src/components/chat/ChatMessages.tsx`** — Revertir:
- Eliminar cases: `computer_screenshot`, `computer_action`

**7. `frontend/src/app/page.tsx`** — Revertir:
- Eliminar `ComputerUsePanel` del panel orchestrator

**8. `frontend/src/components/TabBar.tsx`** — Revertir:
- Eliminar `ModeToggle`

**9. `frontend/src/components/panels/SettingsPanel.tsx`** — Revertir:
- Eliminar `SupervisionModeSelector`

**10. `requirements.txt`** — Revertir:
- Eliminar: `anthropic`, `pyautogui`, `mss`, `Pillow`

#### Comando de Git para rollback total:
```bash
# Si hiciste commits incrementales:
git log --oneline  # encontrar el commit antes de computer use
git revert <commit-hash>..HEAD

# O si prefieres reset duro:
git reset --hard <commit-hash-antes-de-computer-use>
```

#### Rollback de dependencias:
```bash
pip install -r requirements.txt  # restaura el requirements.txt original
cd frontend && npm install        # no debería necesitar cambios
```

---

## 13. Consideraciones de Costo

### Costo por Acción (estimado con Sonnet 4.5)
| Concepto | Tokens | Costo |
|----------|--------|-------|
| System prompt overhead | ~500 input | ~$0.0015 |
| Computer tool definition | ~735 input | ~$0.0022 |
| Screenshot (PNG ~1MP) | ~1,600 input | ~$0.0048 |
| Respuesta de Claude | ~200 output | ~$0.003 |
| **Total por iteración** | **~3,035** | **~$0.01** |

### Costo por Tarea Típica
| Tarea | Iteraciones | Costo Estimado |
|-------|-------------|----------------|
| Abrir app y escribir texto | 5-8 | $0.05-$0.08 |
| Buscar algo en Chrome | 10-15 | $0.10-$0.15 |
| Tarea compleja multi-app | 20-40 | $0.20-$0.40 |
| Tarea máxima (50 iter) | 50 | ~$0.50 |

### Límite de Gasto Recomendado
- **Diario**: ~$5 (500 iteraciones)
- **Por tarea**: ~$1 (configurable con `COMPUTER_USE_MAX_ITERATIONS`)

---

## 14. Archivos Afectados (Resumen)

### Archivos Nuevos
| Archivo | Líneas Est. | Descripción |
|---------|-------------|-------------|
| `computer_use.py` | ~300 | Módulo de control del PC |
| `frontend/src/components/computer-use/ComputerUseViewer.tsx` | ~150 | Panel principal |
| `frontend/src/components/computer-use/ScreenshotViewer.tsx` | ~80 | Visor de screenshots |
| `frontend/src/components/computer-use/ActionPreview.tsx` | ~100 | Preview de acciones |
| `frontend/src/components/computer-use/ScreenshotTimeline.tsx` | ~80 | Timeline de screenshots |
| `frontend/src/components/computer-use/ComputerUseToolbar.tsx` | ~60 | Barra de controles |
| `frontend/src/components/computer-use/EmergencyStopButton.tsx` | ~40 | Botón de emergencia |
| `frontend/src/components/computer-use/ModeToggle.tsx` | ~50 | Toggle coding/computer |
| `frontend/src/components/computer-use/ComputerScreenshotBubble.tsx` | ~40 | Screenshot en chat |
| `frontend/src/components/computer-use/ComputerActionBubble.tsx` | ~40 | Acción en chat |
| `frontend/src/components/panels/ComputerUsePanel.tsx` | ~80 | Panel orquestador |
| `frontend/src/hooks/useComputerUse.ts` | ~60 | Hook de computer use |

### Archivos Modificados
| Archivo | Cambios |
|---------|---------|
| `server.py` | +300 líneas (imports, handlers, agent loop) |
| `permission_classifier.py` | +30 líneas (nuevo nivel, clasificación) |
| `database.py` | +10 líneas (quota field) |
| `rate_limiter.py` | +10 líneas (nuevos límites) |
| `requirements.txt` | +4 líneas |
| `frontend/src/lib/types.ts` | +40 líneas |
| `frontend/src/stores/useAgentStore.ts` | +50 líneas |
| `frontend/src/hooks/useWebSocket.ts` | +40 líneas |
| `frontend/src/components/chat/ChatMessages.tsx` | +10 líneas |
| `frontend/src/app/page.tsx` | +15 líneas |
| `frontend/src/components/TabBar.tsx` | +10 líneas |
| `frontend/src/components/panels/SettingsPanel.tsx` | +30 líneas |
| `frontend/src/lib/translations.ts` | +30 líneas (nuevas traducciones) |

### Estimación Total
- **Archivos nuevos**: ~12 archivos, ~1,130 líneas
- **Archivos modificados**: ~13 archivos, ~575 líneas
- **Total**: ~1,700 líneas nuevas/modificadas

---

## Orden de Implementación Recomendado

```
Fase 1: computer_use.py (backend, independiente)
   ↓
Fase 2: Integración server.py (backend, depende de Fase 1)
   ↓
Fase 3: Permisos (backend, depende de Fase 2)
   ↓
Fase 4: Tipos y Store (frontend, independiente de backend)
   ↓
Fase 5: Componentes UI (frontend, depende de Fase 4)
   ↓
Fase 6: WebSocket hooks (frontend, depende de Fase 4+5)
   ↓
Fase 7: Seguridad (backend+frontend, depende de todo)
   ↓
Fase 8: Testing (depende de todo)
```

**Se pueden paralelizar**: Fases 1-3 (backend) con Fases 4-5 (frontend)

---

## Notas Finales

1. **La API de Computer Use es BETA** — puede cambiar en cualquier momento
2. **No uses Docker** — este proyecto corre en Windows directo, más poder pero más riesgo
3. **PyAutoGUI FAILSAFE** — siempre mantener activado (mover ratón a esquina = abort)
4. **Empezar con modo SUPERVISED** — no activar autónomo hasta estar seguro
5. **Hacer commits incrementales** — un commit por fase para facilitar rollback
6. **El backend actual NO se modifica en su flujo existente** — computer use es un modo paralelo

---

*Documento generado por Rain Assistant — 2026-02-16*
*Para dudas sobre este plan, compartir con cualquier chat de Claude y seguir las instrucciones.*
