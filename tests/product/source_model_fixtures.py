"""A hand-written, protocol-conforming App used as a fake model reply."""

import json

from psyteardown.product.source_model import SourceModelReply


def reference_app(contract) -> str:
    kinds = {item.state_id: item.kind for item in contract.states}
    behaviour = {item.kind: item.user_visible_behavior for item in contract.states}
    screens = []
    for screen in contract.screens:
        outcomes = [kinds[state] for state in screen.state_ids if kinds.get(state) not in {None, "ready", "loading"}]
        outcomes = outcomes or ["success"]
        tasks = [
            {"id": task.task_id, "label": task.goal, "outcome": "success" if index == 0 and "success" in outcomes else outcomes[index % len(outcomes)]}
            for index, task in enumerate(item for item in contract.tasks if item.task_id in screen.task_ids)
        ]
        screens.append({"id": screen.screen_id, "title": screen.title, "tasks": tasks})
    slots = [{"id": slot.slot_id, "text": slot.fallback_text} for slot in contract.content_slots if slot.required]
    data = {
        "title": contract.app_title,
        "screens": screens,
        "slots": slots,
        "behaviour": behaviour,
        "primaryFlow": list(getattr(contract, "primary_flow_task_ids", ())),
    }
    return (
        'import {useState} from "react";\n'
        'import "./styles.css";\n\n'
        f"const data = {json.dumps(data, ensure_ascii=False, indent=2)};\n\n"
        "export default function App() {\n"
        "  const [screenId, setScreenId] = useState(data.screens[0].id);\n"
        "  const [kind, setKind] = useState('ready');\n"
        "  const [flowStep, setFlowStep] = useState(0);\n"
        "  const screen = data.screens.find((item) => item.id === screenId) ?? data.screens[0];\n"
        "  const text = (data.behaviour as Record<string, string>)[kind] ?? kind;\n"
        "  function runTask(task: {id: string; outcome: string}) {\n"
        "    setKind(task.outcome);\n"
        "    if (data.primaryFlow[flowStep] === task.id) setFlowStep(flowStep + 1);\n"
        "  }\n"
        "  return (\n"
        "    <div data-primary-flow-step={flowStep}>\n"
        "      <h1>{data.title}</h1>\n"
        "      <nav aria-label=\"Screens\">{data.screens.map((item) => (\n"
        "        <button key={item.id} type=\"button\" data-screen-link={item.id} onClick={() => setScreenId(item.id)}>{item.title}</button>\n"
        "      ))}</nav>\n"
        "      <section data-screen-id={screen.id} aria-labelledby=\"screen-title\">\n"
        "        <h2 id=\"screen-title\">{screen.title}</h2>\n"
        "        {data.slots.map((slot) => <p key={slot.id} data-slot-id={slot.id}>{slot.text}</p>)}\n"
        "        {screen.tasks.map((task) => (\n"
        "          <button key={task.id} type=\"button\" data-task-id={task.id} onClick={() => runTask(task)}>{task.label}</button>\n"
        "        ))}\n"
        "      </section>\n"
        "      <p role=\"status\" aria-live=\"polite\" data-state-kind={kind}>{text}</p>\n"
        "      {kind !== 'ready' ? <button type=\"button\" data-recovery=\"true\" onClick={() => setKind('ready')}>Back to ready</button> : null}\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    )


# The reference app renders ids from a JSON literal; the static gate looks for
# each id as text, which the literal satisfies.
REFERENCE_CSS = "body { font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }\nbutton { margin: 0 .5rem .5rem 0; }\n"


def reply_for(app: str, css: str = REFERENCE_CSS) -> str:
    return f"```tsx\n{app}```\n\n```css\n{css}```\n"


class ScriptedSourceModel:
    name = "scripted"
    model = "scripted-v1"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def generate(self, *, system: str, prompt: str) -> SourceModelReply:
        self.calls.append({"system": system, "prompt": prompt})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SourceModelReply(text=reply, model=self.model, input_tokens=100, output_tokens=200)
