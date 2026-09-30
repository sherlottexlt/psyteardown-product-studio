"""B7m model-written source for the fixed React template.

A model may only author ``src/App.tsx`` and ``src/styles.css``.  It receives the
human-confirmed Web generation contract and nothing upstream of it (PS-O011),
its reply passes a static gate before anything reaches a workspace, and the
browser test that B4 runs is derived from the contract here rather than
written by the model.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from psyteardown.product.models import WebProductGenerationContract
from psyteardown.product.env import get_project_env

SOURCE_MODEL_MAX_APP_BYTES = 64 * 1024
SOURCE_MODEL_MAX_CSS_BYTES = 32 * 1024
SOURCE_MODEL_MAX_OUTPUT_TOKENS = 8000
SOURCE_MODEL_GATE_VERSION = "b7m-static-gate-v3"
SOURCE_MODEL_WORKSPACE_VERSION = "b7m-workspace-v5"
SOURCE_MODEL_SENT = (
    "confirmed Web generation contract: app title, screens, tasks, states, content slots, acceptance checks",
    "the previous attempt's static-gate rejection reasons (retry only)",
)
SOURCE_MODEL_NOT_SENT = (
    "original user input",
    "product intent, problem model, outcome contract and product theses",
    "build, browser or repair logs",
    "preview feedback",
)
SOURCE_MODEL_RETENTION = (
    "Full request and response text of every model call is kept locally outside the workspace for review; "
    "it is never packaged into a delivery bundle."
)

_ALLOWED_IMPORTS = frozenset({"react", "./styles.css"})
_IMPORT = re.compile(r"""^\s*import\s+(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]""", re.MULTILINE)
_FORBIDDEN_SOURCE = (
    (re.compile(r"\bfetch\s*\("), "network call fetch() is not allowed"),
    (re.compile(r"\bXMLHttpRequest\b"), "XMLHttpRequest is not allowed"),
    (re.compile(r"\bWebSocket\b|\bEventSource\b|\bsendBeacon\b"), "network channels are not allowed"),
    (re.compile(r"\beval\s*\(|\bnew\s+Function\b"), "dynamic code evaluation is not allowed"),
    (re.compile(r"\bimport\s*\(|\brequire\s*\("), "dynamic imports are not allowed"),
    (re.compile(r"dangerouslySetInnerHTML|\binnerHTML\b|\bouterHTML\b"), "raw HTML injection is not allowed"),
    (re.compile(r"\bwindow\.(?:parent|top|opener|open)\b|\bpostMessage\b"), "cross-window access is not allowed"),
    (re.compile(r"\blocalStorage\b|\bsessionStorage\b|\bindexedDB\b|\bdocument\.cookie\b"), "persistent browser storage is not allowed"),
    (re.compile(r"https?://"), "external URLs are not allowed"),
    (re.compile(r"<\s*(?:script|iframe|object|embed)\b", re.IGNORECASE), "embedded script or frame elements are not allowed"),
)
_FORBIDDEN_CSS = (
    (re.compile(r"@import", re.IGNORECASE), "CSS @import is not allowed"),
    (re.compile(r"\burl\s*\(", re.IGNORECASE), "CSS url() is not allowed"),
    (re.compile(r"expression\s*\(", re.IGNORECASE), "CSS expression() is not allowed"),
)
_FENCE = re.compile(r"```([A-Za-z]*)[^\n]*\n(.*?)```", re.DOTALL)
_JS_STRING_CONSTANT = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:"
    r'"((?:\\.|[^"\\])*)"|'
    r"'((?:\\.|[^'\\])*)'|"
    r"`((?:\\.|[^`\\])*)`)"
)
_JS_TEMPLATE_REFERENCE = re.compile(r"\$\{([A-Za-z_$][A-Za-z0-9_$]*)\}")
_JS_TEMPLATE_LITERAL = re.compile(r"`((?:\\.|[^`\\])*)`")


@dataclass(frozen=True)
class SourceModelReply:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    truncated: bool = False


class SourceModelError(RuntimeError):
    """The provider call failed; the message is safe to show."""


class ProductSourceModel(Protocol):
    name: str
    model: str

    def generate(self, *, system: str, prompt: str) -> SourceModelReply: ...


class DeepSeekProductSourceModel:
    """OpenAI-compatible DeepSeek chat call that also reports token usage."""

    name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 240,
    ) -> None:
        key = api_key or get_project_env("DEEPSEEK_API_KEY")
        if not key:
            raise SourceModelError("DEEPSEEK_API_KEY is not configured")
        self._key = key
        self.model = model or get_project_env("DEEPSEEK_MODEL") or "deepseek-chat"
        self._base_url = (base_url or get_project_env("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        self._timeout = timeout_seconds
        # Reasoning models can spend the whole output budget thinking and
        # return no code, so thinking is off unless explicitly enabled.
        self._thinking = get_project_env("DEEPSEEK_THINKING", "disabled").strip().lower() == "enabled"

    def generate(self, *, system: str, prompt: str) -> SourceModelReply:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": SOURCE_MODEL_MAX_OUTPUT_TOKENS,
            "temperature": 0.2,
            "thinking": {"type": "enabled" if self._thinking else "disabled"},
        }
        request = Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._key}"},
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise SourceModelError(f"model provider returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SourceModelError("model provider could not be reached") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceModelError("model provider returned invalid JSON") from exc
        try:
            choice = payload["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SourceModelError("model provider response had no message content") from exc
        if not isinstance(text, str):
            raise SourceModelError("model provider message content was not text")
        usage = payload.get("usage") or {}
        return SourceModelReply(
            text=text or "",
            model=str(payload.get("model") or self.model),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            truncated=choice.get("finish_reason") == "length",
        )


def build_source_model_from_env() -> ProductSourceModel | None:
    """Opt-in: only ``PSYTEARDOWN_PRODUCT_SOURCE_MODEL=deepseek`` enables a real model."""
    provider = get_project_env("PSYTEARDOWN_PRODUCT_SOURCE_MODEL") or get_project_env("PSYTEARDOWN_LLM", "")
    if provider.strip().lower() != "deepseek":
        return None
    try:
        return DeepSeekProductSourceModel()
    except SourceModelError:
        return None


def contract_payload(contract: WebProductGenerationContract) -> dict:
    """Exactly what leaves the machine: the confirmed contract, nothing upstream."""
    return {
        "app_title": contract.app_title,
        "screens": [item.model_dump(mode="json") for item in contract.screens],
        "tasks": [item.model_dump(mode="json") for item in contract.tasks],
        "primary_flow_task_ids": list(contract.primary_flow_task_ids),
        "states": [item.model_dump(mode="json") for item in contract.states],
        "content_slots": [item.model_dump(mode="json") for item in contract.content_slots],
        "acceptance_checks": [item.model_dump(mode="json") for item in contract.acceptance_checks],
    }


SOURCE_MODEL_SYSTEM = """You write the two source files of a small React 19 + TypeScript (strict) single-page app built with Vite.
Everything else (package.json, index.html, main.tsx, configs, tests) is fixed and must not be mentioned.

Output exactly two fenced code blocks and nothing else:
1. ```tsx  -> src/App.tsx (must `export default function App()`)
2. ```css  -> src/styles.css

Hard rules (a static gate rejects violations):
- Imports: only from "react" and "./styles.css". No other packages or files.
- No network (fetch, XMLHttpRequest, WebSocket, EventSource), no storage (localStorage, sessionStorage, indexedDB, cookies),
  no window.parent/top/opener/open, no postMessage, no eval/new Function/dynamic import, no innerHTML/dangerouslySetInnerHTML,
  no external URLs, no <script>/<iframe>. CSS: no @import and no url().
- All data is local and simulated with React state. Timers, if any, must finish within 800 ms.

DOM protocol (a browser test derived from the contract checks it exactly):
- One <h1> whose text contains the contract app_title.
- An always-visible navigation with one <button type="button" data-screen-link="SCREEN_ID"> per screen, labelled with the screen title.
- Only the active screen is rendered, as <section data-screen-id="SCREEN_ID"> with an <h2>. The first screen is active initially.
- Inside its screen section, one <button type="button" data-task-id="TASK_ID"> per task of that screen, labelled in plain words after the task goal.
  Clicking it must simulate the task locally and set the status to one of that screen's state kinds other than "ready" and "loading"
  (a short "loading" in between is allowed). At least one task must reach "success".
- Implement the contract's core task, not a generic button demo. If required content slots describe options, standards, known facts, concerns, or a user leaning,
  render at least two visible local options and editable controls for those categories; do not leave the user with only fallback paragraphs.
  If the contract includes a decision brief save/export task, render a local JSON export and import control without network calls or browser storage.
  A local fixture must contain useful example content, and the primary-flow tasks must visibly change or record something meaningful.
- If primary_flow_task_ids is non-empty, it is the one end-to-end journey a human should run. Keep it visually obvious, show the current next action, and advance
  data-primary-flow-step from 0 to the completed step count after each matching task is completed. Do not present the journey as unrelated demo buttons.
- Exactly one status element, always rendered outside the sections: <p role="status" aria-live="polite" data-state-kind="KIND">
  whose text is a short message written for the end user that fulfils the current state's user_visible_behavior.
  The contract fields describe behaviour; never paste them verbatim as UI copy. The initial kind is "ready".
- Whenever the status kind is not "ready", a visible <button type="button" data-recovery="true"> exists; clicking it returns the status to "ready".
- For every content slot with required=true, render an element with data-slot-id="SLOT_ID" and non-empty end-user text on at least one screen
  (fallback_text is acceptable; the description explains the slot's purpose and is not UI copy).
- Use the exact ids from the contract. For long IDs, you may declare a literal prefix constant and compose the remaining exact suffix with a simple template literal (for example, `const P = "..."; const SCREEN = `${P}-screen`;`), then bind that constant to the required data attribute. Do not invent or alter IDs.
- The end-to-end primary flow may include tasks on different screens. Its progress tracker must persist in React state and remain available on the primary screen; only advance a step after that matching task actually completes.
- Keep it accessible (WCAG 2 AA contrast, labelled controls, no nested interactive elements).
- Keep copy calm and concrete; do not claim outcomes the app cannot know. The UI language should match the contract text.
"""


def build_source_prompt(contract: WebProductGenerationContract, previous_rejections: tuple[str, ...] = ()) -> str:
    prompt = "Confirmed Web generation contract (JSON):\n" + json.dumps(contract_payload(contract), ensure_ascii=False, indent=2)
    if previous_rejections:
        prompt += "\n\nYour previous draft was rejected by the static gate for these reasons; fix all of them:\n"
        prompt += "\n".join(f"- {reason}" for reason in previous_rejections)
    return prompt


def parse_source_reply(text: str, *, truncated: bool = False) -> tuple[dict[str, str], list[str]]:
    if truncated:
        return {}, ["reply was cut off at the output token limit; write shorter code"]
    if not text.strip():
        return {}, ["reply was empty"]
    matches = list(_FENCE.finditer(text))
    reasons: list[str] = []
    if matches:
        outside = "".join(
            (text[: matches[0].start()],)
            + tuple(text[item.end() : next_item.start()] for item, next_item in zip(matches, matches[1:]))
            + (text[matches[-1].end() :],)
        )
        if outside.strip():
            reasons.append("reply must contain only the two required code blocks")
    blocks = [(match.group(1).lower(), match.group(2)) for match in matches]
    if len(blocks) > 2:
        reasons.append("reply must contain exactly two code blocks")
    tsx = [body for lang, body in blocks if lang in {"tsx", "typescript", "ts", "jsx"}]
    css = [body for lang, body in blocks if lang == "css"]
    if len(tsx) != 1:
        reasons.append("reply must contain exactly one tsx code block for src/App.tsx")
    if len(css) != 1:
        reasons.append("reply must contain exactly one css code block for src/styles.css")
    if len(blocks) == 2 and not reasons and blocks[0][0] not in {"tsx", "typescript", "ts", "jsx"}:
        reasons.append("the tsx code block for src/App.tsx must come before the css code block")
    if reasons:
        return {}, reasons
    return {"src/App.tsx": tsx[0].strip() + "\n", "src/styles.css": css[0].strip() + "\n"}, []


def _declared_string_values(source: str) -> set[str]:
    """Resolve literal and simple template-derived JS constants without evaluation.

    Models commonly factor a long job prefix into one constant and compose
    screen/task/slot IDs with template literals, e.g. ``const ID = `${P}-screen```.
    Those values are statically knowable and must not be rejected just because
    the final ID is not repeated as one source substring. This intentionally
    does not execute JavaScript or resolve arbitrary expressions.
    """
    declarations: dict[str, tuple[str, str]] = {}
    for match in _JS_STRING_CONSTANT.finditer(source):
        name = match.group(1)
        if match.group(2) is not None:
            declarations[name] = ("quoted", match.group(2))
        elif match.group(3) is not None:
            declarations[name] = ("quoted", match.group(3))
        else:
            declarations[name] = ("template", match.group(4) or "")

    values: dict[str, str] = {}
    derived: set[str] = set()
    inline_templates = _JS_TEMPLATE_LITERAL.findall(source)
    for _ in range(len(declarations) + len(inline_templates) + 1):
        changed = False
        for name, (kind, raw) in declarations.items():
            if kind == "quoted":
                candidate = raw
            else:
                refs = _JS_TEMPLATE_REFERENCE.findall(raw)
                if any(ref not in values for ref in refs):
                    continue
                candidate = _JS_TEMPLATE_REFERENCE.sub(
                    lambda item: values[item.group(1)], raw
                )
            if values.get(name) != candidate:
                values[name] = candidate
                derived.add(candidate)
                changed = True
        for raw in inline_templates:
            refs = _JS_TEMPLATE_REFERENCE.findall(raw)
            if any(ref not in values for ref in refs):
                continue
            candidate = _JS_TEMPLATE_REFERENCE.sub(
                lambda item: values[item.group(1)], raw
            )
            if candidate not in derived:
                derived.add(candidate)
                changed = True
        if not changed:
            break
    return derived


def check_model_source(files: dict[str, str], contract: WebProductGenerationContract) -> list[str]:
    """Static gate; returns human-readable reasons, empty when accepted."""
    app = files["src/App.tsx"]
    css = files["src/styles.css"]
    reasons: list[str] = []
    if len(app.encode("utf-8")) > SOURCE_MODEL_MAX_APP_BYTES:
        reasons.append(f"src/App.tsx exceeds {SOURCE_MODEL_MAX_APP_BYTES} bytes")
    if len(css.encode("utf-8")) > SOURCE_MODEL_MAX_CSS_BYTES:
        reasons.append(f"src/styles.css exceeds {SOURCE_MODEL_MAX_CSS_BYTES} bytes")
    for module in sorted(set(_IMPORT.findall(app))):
        if module not in _ALLOWED_IMPORTS:
            reasons.append(f"import of {module!r} is not allowed")
    for pattern, reason in _FORBIDDEN_SOURCE:
        if pattern.search(app):
            reasons.append(reason)
    for pattern, reason in _FORBIDDEN_CSS:
        if pattern.search(css):
            reasons.append(reason)
    if not re.search(r"export\s+default\s+function\s+App\b", app):
        reasons.append("src/App.tsx must `export default function App()`")
    markers = [
        ('role="status"', r"role\s*=\s*['\"]status['\"]"),
        ("data-state-kind", r"data-state-kind\s*="),
        ("data-recovery", r"data-recovery\s*="),
    ]
    if contract.primary_flow_task_ids:
        markers.append(("data-primary-flow-step", r"data-primary-flow-step\s*="))
    for marker, pattern in markers:
        if not re.search(pattern, app):
            reasons.append(f"DOM protocol marker {marker} is missing")
    declared_string_values = _declared_string_values(app)
    required = [
        *(("screen", item.screen_id) for item in contract.screens),
        *(("task", item.task_id) for item in contract.tasks),
        *(("content slot", item.slot_id) for item in contract.content_slots if item.required),
    ]
    for kind, identifier in required:
        if identifier not in app and identifier not in declared_string_values:
            reasons.append(f"{kind} id {identifier} from the contract is missing")
    return reasons[:50]


def contract_browser_test(contract: WebProductGenerationContract) -> str:
    """Playwright/axe test derived from the contract; the model never sees or edits it."""
    kinds = {item.state_id: item.kind for item in contract.states}
    all_final = sorted({kind for kind in kinds.values() if kind not in {"ready", "loading"}})
    screens = []
    for screen in contract.screens:
        final = sorted({kinds[state] for state in screen.state_ids if state in kinds} - {"ready", "loading"})
        screens.append({"id": screen.screen_id, "tasks": list(screen.task_ids), "outcomes": final or all_final})
    data = {
        "appTitle": contract.app_title,
        "screens": screens,
        # The generated browser test below exercises the primary journey too;
        # include the task lookup data it dereferences rather than only screen
        # task IDs. Omitting either field causes the harness itself to throw
        # after the per-screen checks, which B4 correctly reports as failure.
        "tasks": [
            {"task_id": item.task_id, "screen_id": item.screen_id}
            for item in contract.tasks
        ],
        "primary_flow_task_ids": list(contract.primary_flow_task_ids),
        "requiredSlots": [item.slot_id for item in contract.content_slots if item.required],
    }
    primary_flow_test = (
        "  if (contract.primary_flow_task_ids.length) {\n"
        "    const flow = contract.primary_flow_task_ids;\n"
        "    const firstTask = contract.tasks.find((item) => item.task_id === flow[0]);\n"
        "    if (!firstTask) throw new Error('primary flow references an unknown task');\n"
        "    await page.locator(`[data-screen-link=\"${firstTask.screen_id}\"]`).click();\n"
        "    const tracker = page.locator('[data-primary-flow-step]');\n"
        "    await expect(tracker).toHaveAttribute('data-primary-flow-step', '0');\n"
        "    for (let index = 0; index < flow.length; index += 1) {\n"
        "      const task = contract.tasks.find((item) => item.task_id === flow[index]);\n"
        "      if (!task) throw new Error('primary flow task is missing');\n"
        "      const taskScreen = contract.screens.find((item) => item.id === task.screen_id);\n"
        "      if (!taskScreen) throw new Error('primary flow task screen is missing');\n"
        "      await page.locator(`[data-screen-link=\"${task.screen_id}\"]`).click();\n"
        "      const taskButton = page.locator(`[data-screen-id=\"${task.screen_id}\"] [data-task-id=\"${task.task_id}\"]`);\n"
        "      await taskButton.click();\n"
        "      if (task.task_id.endsWith('-save-brief')) await expect(page.locator('[data-export-brief=\"true\"]')).toBeVisible();\n"
        "      // Wait for the task's local transition before navigation can cancel its timer.\n"
        "      await expect(status).toHaveAttribute('data-state-kind', new RegExp(`^(${taskScreen.outcomes.join('|')})$`));\n"
        "      // The progress tracker may live only on the primary screen. Return there before reading it.\n"
        "      await page.locator(`[data-screen-link=\"${firstTask.screen_id}\"]`).click();\n"
        "      await expect(tracker).toHaveAttribute('data-primary-flow-step', String(index + 1));\n"
        "      await expect(status).not.toHaveText(/^\\s*$/);\n"
        "    }\n"
        "  }\n"
    )
    per_screen_test = (
        "  for (const screen of contract.screens) {\n"
        "    for (const task of screen.tasks) {\n"
        "      await page.locator(`[data-screen-link=\"${screen.id}\"]`).click();\n"
        "      const section = page.locator(`[data-screen-id=\"${screen.id}\"]`);\n"
        "      await expect(section).toBeVisible();\n"
        "      for (const slot of await page.locator('[data-slot-id]').all()) {\n"
        "        if ((await slot.innerText()).trim()) seenSlots.add((await slot.getAttribute('data-slot-id')) ?? '');\n"
        "      }\n"
        "      await section.locator(`[data-task-id=\"${task}\"]`).click();\n"
        "      await expect(status).toHaveAttribute('data-state-kind', new RegExp(`^(${screen.outcomes.join('|')})$`));\n"
        "      await expect(status).not.toHaveText(/^\\s*$/);\n"
        "      reached.add((await status.getAttribute('data-state-kind')) ?? '');\n"
        "      await page.locator('[data-recovery=\"true\"]').first().click();\n"
        "      await expect(status).toHaveAttribute('data-state-kind', 'ready');\n"
        "    }\n"
        "    expect(await seriousViolations(page)).toEqual([]);\n"
        "  }\n"
    )
    return (
        "import AxeBuilder from '@axe-core/playwright';\n"
        "import {expect, test, type Page} from '@playwright/test';\n\n"
        "// Derived from the confirmed Web generation contract by Product Studio (B7m).\n"
        f"const contract = {json.dumps(data, ensure_ascii=False, indent=2)} as const;\n\n"
        "async function seriousViolations(page: Page) {\n"
        "  const results = await new AxeBuilder({page}).withTags(['wcag2a', 'wcag2aa']).analyze();\n"
        "  return results.violations.filter((item) => item.impact === 'critical' || item.impact === 'serious').map((item) => item.id);\n"
        "}\n\n"
        "test('model-written app honours the confirmed contract', async ({page}) => {\n"
        "  const errors: string[] = [];\n"
        "  page.on('pageerror', (error) => errors.push(String(error)));\n"
        "  await page.goto('/');\n"
        "  await expect(page.getByRole('heading', {level: 1})).toContainText(contract.appTitle);\n"
        "  const status = page.locator('[role=\"status\"]');\n"
        "  await expect(status).toHaveCount(1);\n"
        "  await expect(status).toHaveAttribute('data-state-kind', 'ready');\n"
        "  expect(await seriousViolations(page)).toEqual([]);\n"
        "  const seenSlots = new Set<string>();\n"
        "  const reached = new Set<string>();\n"
        f"{primary_flow_test}"
        f"{per_screen_test}"
        "  expect([...contract.requiredSlots].filter((slot) => !seenSlots.has(slot))).toEqual([]);\n"
        "  expect(reached.has('success')).toBe(true);\n"
        "  expect(errors).toEqual([]);\n"
        "  await page.screenshot({path: 'test-results/generated-product.png', fullPage: true});\n"
        "});\n"
    )



def timed_generate(model: ProductSourceModel, *, system: str, prompt: str) -> tuple[SourceModelReply, float]:
    started = time.monotonic()
    reply = model.generate(system=system, prompt=prompt)
    return reply, time.monotonic() - started
