import json
import re

import pytest

from psyteardown.experience.models import DomainStateError
from psyteardown.product import InMemoryProductGenerationJobRepository, ProductGenerationJobService
from psyteardown.product.execution import validate_generated_workspace
from psyteardown.product.source_model import (
    DeepSeekProductSourceModel,
    SourceModelError,
    build_source_prompt,
    check_model_source,
    contract_browser_test,
    parse_source_reply,
)
import psyteardown.product.source_model as source_model_module
from .source_model_fixtures import REFERENCE_CSS, ScriptedSourceModel, reference_app, reply_for
from .test_generation import NOW, SequenceIds, confirmed_generation
from .test_jobs import build_services


def _services(tmp_path, model):
    application, _, proposal_jobs = build_services()
    project, contract = confirmed_generation(application, proposal_jobs)
    generation = ProductGenerationJobService(
        application,
        InMemoryProductGenerationJobRepository(),
        workspace_root=tmp_path / "workspaces",
        clock=lambda: NOW,
        id_factory=SequenceIds(),
        source_model=model,
    )
    return application, generation, project, contract


def test_model_job_writes_only_gated_source_and_a_contract_derived_test(tmp_path):
    model = ScriptedSourceModel()
    application, generation, project, contract = _services(tmp_path, model)
    model.replies.append(reply_for(reference_app(contract)))

    job = generation.create_job(project_id=project.project_id, actor="user-li", reason="model draft", source="model")
    assert job.provider == "model_source" and job.materialization_kind == "model"
    assert job.budget.max_cost_units == 2
    done = generation.run_job(project.project_id, job.job_id, actor="worker")

    assert done.status == "succeeded", done.error_summary
    [call] = done.model_calls
    assert call.outcome == "accepted" and call.sent_object_types == ("web_generation_contract",)
    workspace = generation._workspace_path(done)
    validate_generated_workspace(workspace, done)
    assert (workspace / "src" / "App.tsx").read_text(encoding="utf-8") == reference_app(contract)
    assert (workspace / "src" / "styles.css").read_text(encoding="utf-8") == REFERENCE_CSS
    spec = (workspace / "tests" / "generated-contract.spec.ts").read_text(encoding="utf-8")
    assert spec == contract_browser_test(contract)
    # Fixed template files are untouched by the model.
    assert json.loads((workspace / "package.json").read_text(encoding="utf-8"))["dependencies"] == {"react": "19.1.1", "react-dom": "19.1.1"}

    # Only the confirmed contract is sent: nothing from intent/problem/outcome upstream.
    view = application.get_project_view(project.project_id)
    prompt = model.calls[0]["prompt"]
    assert view.problem_model.facts[0].statement not in prompt
    assert view.outcome_contract.revision_id not in prompt and view.product_intent.revision_id not in prompt
    assert view.product_intent.desired_change not in prompt
    for screen in contract.screens:
        assert screen.screen_id in prompt

    transcript = generation.transcript_path(done, 1)
    assert workspace not in transcript.parents
    saved = json.loads(transcript.read_text(encoding="utf-8"))
    assert saved["prompt"] == prompt and saved["gate"] == {"accepted": True, "reasons": []}

    # Each explicit model request is a new spend, so a finished job is not reused.
    again = generation.create_job(project_id=project.project_id, actor="user-li", reason="another draft", source="model")
    assert again.job_id != job.job_id


def test_rejected_draft_is_not_materialized_and_retry_carries_only_gate_reasons(tmp_path):
    model = ScriptedSourceModel()
    _, generation, project, contract = _services(tmp_path, model)
    bad = reference_app(contract).replace(
        'import "./styles.css";', 'import "./styles.css";\nimport axios from "axios";\nfetch("https://example.com");'
    )
    model.replies += [reply_for(bad), reply_for(reference_app(contract))]

    job = generation.create_job(project_id=project.project_id, actor="user-li", reason="model draft", source="model")
    failed = generation.run_job(project.project_id, job.job_id, actor="worker")
    assert failed.status == "failed" and failed.error_code == "model_output_rejected"
    assert failed.manifest is None and not generation._workspace_path(failed).exists()
    reasons = failed.model_calls[0].rejection_reasons
    assert "import of 'axios' is not allowed" in reasons
    assert "network call fetch() is not allowed" in reasons
    assert json.loads(generation.transcript_path(failed, 1).read_text(encoding="utf-8"))["gate"]["accepted"] is False

    retried = generation.retry_job(project.project_id, job.job_id, actor="user-li")
    done = generation.run_job(project.project_id, retried.job_id, actor="worker")
    assert done.status == "succeeded"
    assert [call.outcome for call in done.model_calls] == ["rejected", "accepted"]
    assert done.consumed_cost_units == 2
    assert "import of 'axios' is not allowed" in model.calls[1]["prompt"]


def test_model_budget_allows_two_calls_and_provider_errors_are_recorded(tmp_path):
    model = ScriptedSourceModel(SourceModelError("model provider returned HTTP 503"), "no code here")
    _, generation, project, _ = _services(tmp_path, model)
    job = generation.create_job(project_id=project.project_id, actor="user-li", reason="model draft", source="model")

    first = generation.run_job(project.project_id, job.job_id, actor="worker")
    assert first.error_code == "model_call_failed" and first.model_calls[0].outcome == "failed"
    generation.retry_job(project.project_id, job.job_id, actor="user-li")
    second = generation.run_job(project.project_id, job.job_id, actor="worker")
    assert second.error_code == "model_output_rejected"
    exhausted = generation.retry_job(project.project_id, job.job_id, actor="user-li")
    assert exhausted.status == "budget_exhausted"
    assert len(model.calls) == 2


def test_model_source_requires_a_configured_provider(tmp_path):
    _, generation, project, _ = _services(tmp_path, None)
    with pytest.raises(DomainStateError, match="requires a configured source model"):
        generation.create_job(project_id=project.project_id, actor="user-li", reason="model draft", source="model")


def test_retry_prompt_lists_previous_reasons(tmp_path):
    _, _, _, contract = _services(tmp_path, None)
    assert "fix all of them" not in build_source_prompt(contract)
    assert "- bad import" in build_source_prompt(contract, ("bad import",))


@pytest.mark.parametrize(
    ("snippet", "reason"),
    [
        ("localStorage.setItem('a', 'b');", "persistent browser storage is not allowed"),
        ("window.parent.location;", "cross-window access is not allowed"),
        ("const x = eval('1');", "dynamic code evaluation is not allowed"),
        ("const m = import('./x');", "dynamic imports are not allowed"),
        ("const h = {dangerouslySetInnerHTML: {__html: ''}};", "raw HTML injection is not allowed"),
        ("const s = new WebSocket('ws://x');", "network channels are not allowed"),
    ],
)
def test_static_gate_rejects_capabilities_outside_the_sandbox(tmp_path, snippet, reason):
    _, _, _, contract = _services(tmp_path, None)
    files = {"src/App.tsx": reference_app(contract) + snippet + "\n", "src/styles.css": REFERENCE_CSS}
    assert reason in check_model_source(files, contract)
    assert check_model_source({"src/App.tsx": reference_app(contract), "src/styles.css": REFERENCE_CSS}, contract) == []


def test_static_gate_checks_css_contract_ids_and_reply_shape(tmp_path):
    _, _, _, contract = _services(tmp_path, None)
    files = {"src/App.tsx": "export default function App() { return null; }\n", "src/styles.css": "@import 'x.css';\nb { background: url(x.png); }\n"}
    reasons = check_model_source(files, contract)
    assert "CSS @import is not allowed" in reasons and "CSS url() is not allowed" in reasons
    for identifier in [
        *(item.screen_id for item in contract.screens),
        *(item.task_id for item in contract.tasks),
        *(item.slot_id for item in contract.content_slots if item.required),
    ]:
        assert any(identifier in reason for reason in reasons)
    assert parse_source_reply("```tsx\nA\n```")[1] == ["reply must contain exactly one css code block for src/styles.css"]


def test_static_gate_resolves_prefixed_template_literal_contract_ids(tmp_path):
    _, _, _, contract = _services(tmp_path, None)
    prefix = contract.screens[0].screen_id.removesuffix("-setup-screen")
    identifiers = [
        *(item.screen_id for item in contract.screens),
        *(item.task_id for item in contract.tasks),
        *(item.slot_id for item in contract.content_slots if item.required),
    ]
    names = {identifier: f"ID_{index}" for index, identifier in enumerate(identifiers)}
    declarations = [f'const P = "{prefix}";']
    content_slot_ids = {item.slot_id for item in contract.content_slots if item.required}
    for identifier, name in names.items():
        assert identifier.startswith(prefix)
        if identifier not in content_slot_ids:
            declarations.append(f"const {name} = `${{P}}{identifier[len(prefix):]}`;")

    screen_sections = []
    nav_buttons = []
    for screen in contract.screens:
        screen_name = names[screen.screen_id]
        nav_buttons.append(f'<button data-screen-link={{{screen_name}}}>Open</button>')
        task_buttons = "".join(
            f'<button data-task-id={{{names[task_id]}}}>Task</button>'
            for task_id in screen.task_ids
        )
        screen_sections.append(
            f'<section data-screen-id={{{screen_name}}}>{task_buttons}</section>'
        )
    slot_nodes = "".join(
        f'<p data-slot-id={{`${{P}}{slot.slot_id[len(prefix):]}`}}>Fallback content</p>'
        for slot in contract.content_slots
        if slot.required
    )
    app = "\n".join([
        *declarations,
        "export default function App() {",
        "  return <main>",
        f"    <nav>{''.join(nav_buttons)}</nav>",
        *[
            f"    {section[:-10]}{slot_nodes}</section>" if index == 0 else f"    {section}"
            for index, section in enumerate(screen_sections)
        ],
        '    <p role="status" aria-live="polite" data-state-kind="ready">Ready</p>',
        '    <button data-recovery="true">Recover</button>',
        '    <div data-primary-flow-step="0" />',
        "  </main>;",
        "}",
    ])
    reasons = check_model_source({"src/App.tsx": app, "src/styles.css": ""}, contract)
    assert not [reason for reason in reasons if "id " in reason and "from the contract is missing" in reason]


def test_source_reply_requires_only_ordered_code_blocks():
    accepted = parse_source_reply("\n```tsx\napp\n```\n\n```css\ncss\n```\n")
    assert accepted == ({"src/App.tsx": "app\n", "src/styles.css": "css\n"}, [])
    extra = parse_source_reply("Here is the app:\n```tsx\napp\n```\n```css\ncss\n```")
    assert extra[1] == ["reply must contain only the two required code blocks"]
    reversed_blocks = parse_source_reply("```css\ncss\n```\n```tsx\napp\n```")
    assert reversed_blocks[1] == ["the tsx code block for src/App.tsx must come before the css code block"]
    extra_block = parse_source_reply("```tsx\napp\n```\n```css\ncss\n```\n```txt\nnotes\n```")
    assert extra_block[1] == ["reply must contain exactly two code blocks"]


def test_contract_browser_test_covers_every_screen_task_and_required_slot(tmp_path):
    _, _, _, contract = _services(tmp_path, None)
    spec = contract_browser_test(contract)
    for identifier in [
        *(item.screen_id for item in contract.screens),
        *(item.task_id for item in contract.tasks),
        *(item.slot_id for item in contract.content_slots if item.required),
    ]:
        assert f'"{identifier}"' in spec
    assert "reached.has('success')" in spec and "AxeBuilder" in spec
    # The primary journey must start from the untouched ready/step-0 state;
    # per-screen checks also click tasks and advance the same app state.
    assert spec.index("if (contract.primary_flow_task_ids.length)") < spec.index("for (const screen of contract.screens)")
    payload_match = re.search(r"const contract = (\{[\s\S]*?\}) as const;", spec)
    assert payload_match is not None
    payload = json.loads(payload_match.group(1))
    assert payload["primary_flow_task_ids"] == list(contract.primary_flow_task_ids)
    primary_flow_section = spec.index("const tracker = page.locator('[data-primary-flow-step]')")
    screen_sweep_section = spec.index("for (const screen of contract.screens)")
    assert primary_flow_section < screen_sweep_section
    assert "const tracker = page.locator('[data-primary-flow-step]')" in spec
    assert "await expect(status).toHaveAttribute('data-state-kind', new RegExp(`^(${taskScreen.outcomes.join('|')})$`));" in spec
    assert "await page.locator(`[data-screen-link=\"${firstTask.screen_id}\"]`).click();\n      await expect(tracker)" in spec
    assert payload["tasks"] == [
        {"task_id": item.task_id, "screen_id": item.screen_id}
        for item in contract.tasks
    ]


def test_deepseek_source_model_sends_bounded_chat_request_and_usage(monkeypatch):
    calls = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "deepseek-chat",
                    "choices": [{"message": {"content": "reply"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 34},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr(source_model_module, "urlopen", fake_urlopen)
    model = DeepSeekProductSourceModel(api_key="secret", model="deepseek-chat", base_url="http://provider")
    reply = model.generate(system="system", prompt="prompt")
    payload = json.loads(calls[0][0].data)
    assert calls[0][0].full_url == "http://provider/chat/completions"
    assert calls[0][1] == 240
    assert payload["model"] == "deepseek-chat"
    assert payload["max_tokens"] == 8000
    assert payload["messages"] == [{"role": "system", "content": "system"}, {"role": "user", "content": "prompt"}]
    assert reply.text == "reply" and reply.input_tokens == 12 and reply.output_tokens == 34


@pytest.mark.parametrize(
    ("body", "message"),
    [(b"not-json", "invalid JSON"), (json.dumps({"choices": [{"message": {"content": 1}}]}).encode(), "not text")],
)
def test_deepseek_source_model_rejects_malformed_provider_responses(monkeypatch, body, message):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    monkeypatch.setattr(source_model_module, "urlopen", lambda request, timeout: Response())
    with pytest.raises(SourceModelError, match=message):
        DeepSeekProductSourceModel(api_key="secret").generate(system="system", prompt="prompt")
