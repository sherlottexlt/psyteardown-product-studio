"""Proposal providers for the Product Studio application boundary."""

from __future__ import annotations

import os
import time
from typing import Protocol

from psyteardown.product.commands import (
    OutcomeContractProposal,
    ProblemModelProposal,
    ProductIntentProposal,
    ProductThesisProposal,
    WebProductGenerationContractProposal,
)
from psyteardown.product.models import (
    CompetingExplanation,
    DeliveryEstimate,
    DeliveryMaturity,
    FalsifiablePrediction,
    MechanismHypothesis,
    OutcomeContract,
    PreviewFeedback,
    ProblemFact,
    ProblemModel,
    ProblemUnknown,
    ProhibitedOutcome,
    ResourceBoundary,
    SourceReference,
    StopCondition,
    SuccessIndicator,
    TargetOutcome,
    ProductIntent,
    ProductThesis,
    ValidationStep,
    WebAcceptanceCheck,
    WebContentSlot,
    WebProductGenerationContract,
    WebScreenSpec,
    WebStateSpec,
    WebTaskSpec,
    WEB_TEMPLATE_VERSION,
    MEASUREMENT_THRESHOLD_PLACEHOLDER,
)


class ProductContractProposalProvider(Protocol):
    name: str
    version: str

    def propose_intent(
        self, raw_input: str, *, job_id: str
    ) -> ProductIntentProposal: ...

    def propose_problem(self, intent: ProductIntent, *, job_id: str) -> ProblemModelProposal: ...

    def propose_outcome_contract(
        self,
        intent: ProductIntent,
        problem: ProblemModel,
        *,
        job_id: str,
    ) -> OutcomeContractProposal: ...

    def propose_theses(
        self,
        problem: ProblemModel,
        contract: OutcomeContract,
        *,
        job_id: str,
    ) -> tuple[ProductThesisProposal, ...]: ...

    def propose_web_generation_contract(
        self,
        thesis: ProductThesis,
        contract: OutcomeContract,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Create the V0.2 decision-brief slice, not a generic state demo.

        The first slice now has a product-shaped artifact: a framed decision,
        two independently annotated options, a user-owned leaning, a next
        verification question, and an explicit JSON export/import path. It is
        still local-only and evidence-light; it must not be mistaken for a
        recommendation engine or proof of better decisions.
        """
        chinese = _is_chinese(thesis.name, thesis.product_promise, *(contract.target_segments or ()))
        setup_screen = f"{suggestion_id}-setup-screen"
        compare_screen = f"{suggestion_id}-comparison-screen"
        review_screen = f"{suggestion_id}-review-screen"
        frame_task = f"{suggestion_id}-frame-decision"
        compare_task = f"{suggestion_id}-compare-options"
        record_task = f"{suggestion_id}-record-decision"
        save_task = f"{suggestion_id}-save-brief"
        setup_stop_task = f"{suggestion_id}-setup-stop"
        stop_task = f"{suggestion_id}-stop-recover"
        review_stop_task = f"{suggestion_id}-review-stop"
        state_ids = {
            kind: f"{suggestion_id}-{kind}"
            for kind in ("ready", "loading", "empty", "error", "success", "paused", "stopped")
        }
        copy = {
            "setup_title": _localized(chinese, "设定这次决定", "Frame the decision"),
            "compare_title": _localized(chinese, "选项对比", "Compare options"),
            "review_title": _localized(chinese, "决策简报", "Decision brief"),
            "setup_purpose": _localized(chinese, "先写清楚要决定什么、背景是什么，以及什么时候需要回看。", "State what you need to decide, the context, and when to revisit it."),
            "compare_purpose": _localized(chinese, "把每个选项的标准、已知信息和顾虑分开记录，不自动排序。", "Record standards, known information, and concerns for each option without automatic ranking."),
            "review_purpose": _localized(chinese, "核对这份可带走的简报，记录倾向、未知和下一步，再由你保存。", "Review a take-away brief, record your leaning and next check, then save it yourself."),
            "frame_goal": _localized(chinese, "写下这次要做的决定、背景和需要回看的时间。", "Write the decision, context, and time to revisit it."),
            "frame_success": _localized(chinese, "用户可以说清楚当前决定，而不是直接被推向某个选项。", "The user can state the decision without being pushed toward an option."),
            "compare_goal": _localized(chinese, "分别查看两个选项的决策标准、已知信息和顾虑。", "Review each option's standards, known information, and concerns separately."),
            "compare_success": _localized(chinese, "用户能指出至少一个差异，并知道哪些内容仍待核实。", "The user can name at least one difference and identify what remains to verify."),
            "record_goal": _localized(chinese, "记录自己的当前倾向和下一步要确认的问题。", "Record your current leaning and the next question to check."),
            "record_success": _localized(chinese, "倾向和未知被记录，但工具没有替用户做出决定。", "The leaning and unknown are recorded without the tool deciding for the user."),
            "save_goal": _localized(chinese, "导出一份可重新打开的本地决策简报。", "Export a local decision brief that can be reopened later."),
            "save_success": _localized(chinese, "用户得到一份自己的简报文件，而不是只完成一次演示。", "The user receives their own brief file instead of only completing a demo."),
            "stop_goal": _localized(chinese, "停止流程并恢复到可继续的状态。", "Stop the flow and recover a resumable state."),
            "stop_success": _localized(chinese, "停止和恢复立即可见、可逆。", "Stop and recovery are immediate, visible, and reversible."),
            "goal": _localized(chinese, "把一个近期决定整理成可保存、可重开的简报，但不替你推荐答案。", "Turn one near-term decision into a saveable, reopenable brief without recommending an answer."),
            "decision_question": _localized(chinese, "这次要做什么决定？", "What decision are you making?"),
            "context": _localized(chinese, "背景和约束", "Context and constraints"),
            "deadline": _localized(chinese, "什么时候需要回看？", "When should you revisit it?"),
            "criteria": _localized(chinese, "决策标准", "Decision standards"),
            "facts": _localized(chinese, "已知信息", "Known information"),
            "concerns": _localized(chinese, "顾虑", "Concerns"),
            "option_a": _localized(chinese, "选项 A：本地示例", "Option A: local example"),
            "option_b": _localized(chinese, "选项 B：本地示例", "Option B: local example"),
            "decision": _localized(chinese, "我的当前倾向（不是工具推荐）", "My current leaning (not a tool recommendation)"),
            "next_question": _localized(chinese, "下一步需要核实的问题", "Next question to verify"),
            "save": _localized(chinese, "下载 JSON 保存；刷新页面不会自动保留未导出的内容。", "Download JSON to save; refreshing does not keep unexported content."),
            "unknown": _localized(chinese, "仍待确认：这些记录是否足以支持真实情境中的选择。", "Still unknown: whether these notes are enough for a choice in the real context."),
            "error": _localized(chinese, "本地流程出了问题。请重试或停止。", "The local flow failed. Retry or stop."),
        }
        return WebProductGenerationContractProposal(
            product_thesis_revision_id=thesis.revision_id,
            outcome_contract_revision_id=contract.revision_id,
            app_title=thesis.name,
            screens=[
                WebScreenSpec(
                    screen_id=setup_screen,
                    title=copy["setup_title"],
                    purpose=copy["setup_purpose"],
                    task_ids=(frame_task, setup_stop_task),
                    state_ids=(state_ids["ready"], state_ids["loading"], state_ids["success"], state_ids["stopped"]),
                ),
                WebScreenSpec(
                    screen_id=compare_screen,
                    title=copy["compare_title"],
                    purpose=copy["compare_purpose"],
                    task_ids=(compare_task, stop_task),
                    state_ids=(state_ids["ready"], state_ids["loading"], state_ids["success"], state_ids["stopped"]),
                ),
                WebScreenSpec(
                    screen_id=review_screen,
                    title=copy["review_title"],
                    purpose=copy["review_purpose"],
                    task_ids=(record_task, save_task, review_stop_task),
                    state_ids=(state_ids["empty"], state_ids["error"], state_ids["success"], state_ids["stopped"]),
                ),
            ],
            tasks=[
                WebTaskSpec(task_id=frame_task, screen_id=setup_screen, goal=copy["frame_goal"], success_criteria=copy["frame_success"], user_decision_limit=_localized(chinese, "用户决定这次要解决的决定；不使用隐藏默认值。", "The user frames the decision; no hidden default is used.")),
                WebTaskSpec(task_id=compare_task, screen_id=compare_screen, goal=copy["compare_goal"], success_criteria=copy["compare_success"], user_decision_limit=_localized(chinese, "每个选项只记录用户可见的标准、事实和顾虑。", "Each option exposes only user-visible standards, facts, and concerns.")),
                WebTaskSpec(task_id=record_task, screen_id=review_screen, goal=copy["record_goal"], success_criteria=copy["record_success"], user_decision_limit=_localized(chinese, "工具不排序、不评分、不替用户做决定。", "The tool does not rank, score, or decide for the user.")),
                WebTaskSpec(task_id=save_task, screen_id=review_screen, goal=copy["save_goal"], success_criteria=copy["save_success"], user_decision_limit=_localized(chinese, "用户决定是否下载和保存简报；不自动上传。", "The user decides whether to download the brief; nothing is uploaded.")),
                WebTaskSpec(task_id=setup_stop_task, screen_id=setup_screen, goal=copy["stop_goal"], success_criteria=copy["stop_success"], user_decision_limit=_localized(chinese, "停止或恢复前不设置确认墙。", "No confirmation wall is required before stop or recovery.")),
                WebTaskSpec(task_id=stop_task, screen_id=compare_screen, goal=copy["stop_goal"], success_criteria=copy["stop_success"], user_decision_limit=_localized(chinese, "停止或恢复前不设置确认墙。", "No confirmation wall is required before stop or recovery.")),
                WebTaskSpec(task_id=review_stop_task, screen_id=review_screen, goal=copy["stop_goal"], success_criteria=copy["stop_success"], user_decision_limit=_localized(chinese, "停止或恢复前不设置确认墙。", "No confirmation wall is required before stop or recovery.")),
            ],
            primary_flow_task_ids=[frame_task, compare_task, record_task, save_task],
            states=[
                WebStateSpec(state_id=state_ids["ready"], kind="ready", user_visible_behavior=_localized(chinese, "展示当前决定、选项记录和下一步。", "Show the current decision, option notes, and next action."), recovery_action=_localized(chinese, "继续整理或离开。", "Continue organizing or leave.")),
                WebStateSpec(state_id=state_ids["loading"], kind="loading", user_visible_behavior=_localized(chinese, "展示确定性的本地过渡，不暗示网络活动。", "Show a deterministic local transition without implying network activity."), recovery_action=_localized(chinese, "短暂等待或停止本地过渡。", "Wait briefly or stop the local transition.")),
                WebStateSpec(state_id=state_ids["empty"], kind="empty", user_visible_behavior=_localized(chinese, "说明还没有记录用户自己的判断。", "Explain that the user's own judgment has not been recorded."), recovery_action=_localized(chinese, "返回简报。", "Return to the brief.")),
                WebStateSpec(state_id=state_ids["error"], kind="error", user_visible_behavior=_localized(chinese, "说明本地失败，但不暴露敏感内容。", "Explain the local failure without exposing sensitive content."), recovery_action=_localized(chinese, "在本地重试或停止流程。", "Retry locally or stop the flow.")),
                WebStateSpec(state_id=state_ids["success"], kind="success", user_visible_behavior=_localized(chinese, "确认本地简报已更新，同时保留未知和用户控制。", "Confirm that the local brief was updated while preserving unknowns and user control."), recovery_action=_localized(chinese, "继续编辑、导出或停止。", "Continue editing, export, or stop.")),
                WebStateSpec(state_id=state_ids["paused"], kind="paused", user_visible_behavior=_localized(chinese, "展示流程已暂停且没有主动干预。", "Show that the flow is paused and no intervention is active."), recovery_action=_localized(chinese, "继续或停止。", "Resume or stop.")),
                WebStateSpec(state_id=state_ids["stopped"], kind="stopped", user_visible_behavior=_localized(chinese, "展示流程结束且控制权已恢复。", "Show that the flow ended and controls are restored."), recovery_action=_localized(chinese, "开始新的简报。", "Start a new brief.")),
            ],
            content_slots=[
                WebContentSlot(slot_id=f"{suggestion_id}-title", semantic_role="heading", description=_localized(chinese, "命名这次决定，不声称结果已经验证。", "Name the decision without claiming a measured result."), source_kind="product_thesis", fallback_text=thesis.name),
                WebContentSlot(slot_id=f"{suggestion_id}-goal", semantic_role="instruction", description=_localized(chinese, "说明这次简报的边界。", "Explain the boundary of this brief."), source_kind="outcome_contract", fallback_text=copy["goal"]),
                WebContentSlot(slot_id=f"{suggestion_id}-decision-question", semantic_role="label", description=_localized(chinese, "让用户写清楚当前要做的决定。", "Let the user state the current decision."), source_kind="user_input", fallback_text=copy["decision_question"]),
                WebContentSlot(slot_id=f"{suggestion_id}-context", semantic_role="label", description=_localized(chinese, "记录背景和约束，不把它们伪装成事实。", "Record context and constraints without disguising them as facts."), source_kind="user_input", fallback_text=copy["context"]),
                WebContentSlot(slot_id=f"{suggestion_id}-deadline", semantic_role="label", description=_localized(chinese, "记录需要回看这次决定的时间边界。", "Record when the decision should be revisited."), source_kind="user_input", fallback_text=copy["deadline"]),
                WebContentSlot(slot_id=f"{suggestion_id}-criteria", semantic_role="label", description=_localized(chinese, "明确标准和事实不是同一类内容。", "Keep standards separate from facts."), source_kind="outcome_contract", fallback_text=copy["criteria"]),
                WebContentSlot(slot_id=f"{suggestion_id}-facts", semantic_role="label", description=_localized(chinese, "呈现用户当前知道的信息。", "Present what the user currently knows."), source_kind="outcome_contract", fallback_text=copy["facts"]),
                WebContentSlot(slot_id=f"{suggestion_id}-concerns", semantic_role="label", description=_localized(chinese, "呈现顾虑而不把顾虑伪装成事实。", "Present concerns without treating them as facts."), source_kind="outcome_contract", fallback_text=copy["concerns"]),
                WebContentSlot(slot_id=f"{suggestion_id}-option-a", semantic_role="label", description=_localized(chinese, "提供一个可编辑的本地比较选项。", "Provide one editable local comparison option."), source_kind="local_fixture", fallback_text=copy["option_a"]),
                WebContentSlot(slot_id=f"{suggestion_id}-option-b", semantic_role="label", description=_localized(chinese, "提供第二个可编辑的本地比较选项。", "Provide a second editable local comparison option."), source_kind="local_fixture", fallback_text=copy["option_b"]),
                WebContentSlot(slot_id=f"{suggestion_id}-decision", semantic_role="confirmation", description=_localized(chinese, "记录用户自己的倾向，不输出推荐。", "Record the user's own leaning without outputting a recommendation."), source_kind="user_input", fallback_text=copy["decision"]),
                WebContentSlot(slot_id=f"{suggestion_id}-next-question", semantic_role="confirmation", description=_localized(chinese, "记录下一步需要核实的问题。", "Record the next question to verify."), source_kind="user_input", fallback_text=copy["next_question"]),
                WebContentSlot(slot_id=f"{suggestion_id}-save", semantic_role="status", description=_localized(chinese, "说明本地导出和重新打开的边界。", "Explain the local export and reopen boundary."), source_kind="user_input", fallback_text=copy["save"]),
                WebContentSlot(slot_id=f"{suggestion_id}-unknown", semantic_role="status", description=_localized(chinese, "保留尚未由真实任务验证的问题。", "Keep the question that real task observation has not answered."), source_kind="outcome_contract", fallback_text=copy["unknown"]),
                WebContentSlot(slot_id=f"{suggestion_id}-error", semantic_role="error", description=_localized(chinese, "给出安全的本地恢复指引。", "Give a safe local recovery instruction."), source_kind="local_fixture", fallback_text=copy["error"]),
            ],
            acceptance_checks=[
                WebAcceptanceCheck(check_id=f"{suggestion_id}-frame-check", task_id=frame_task, assertion=_localized(chinese, "用户能写下决定、背景和时间边界，且不被产品预先推荐。", "The user can write the decision, context, and time boundary without a product recommendation.")),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-compare-check", task_id=compare_task, assertion=_localized(chinese, "比较任务让用户能分别查看两个选项的标准、事实、顾虑，并看见仍未知。", "The compare task exposes separate standards, facts, concerns, and remaining unknowns for two options.")),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-record-check", task_id=record_task, assertion=_localized(chinese, "记录任务保存用户自己的倾向和下一步问题，不替用户做决定。", "The record task preserves the user's leaning and next question without deciding for the user.")),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-save-check", task_id=save_task, assertion=_localized(chinese, "保存任务下载一份可重新打开的本地 JSON 简报，不发起网络请求。", "The save task downloads a reopenable local JSON brief without network access.")),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-stop-check", task_id=stop_task, assertion=_localized(chinese, "所有 active 或 paused 状态都可停止和恢复。", "Stop and recovery are available from every active or paused state.")),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-review-stop-check", task_id=review_stop_task, assertion=_localized(chinese, "简报页面也可以停止和恢复。", "The brief page also supports stop and recovery.")),
            ],
            source_refs=[
                SourceReference(source_type="model_proposal", source_id=suggestion_id, revision_id=WEB_TEMPLATE_VERSION),
                SourceReference(source_type="human_decision", source_id=thesis.thesis_id, revision_id=thesis.revision_id),
            ],
        )

    def propose_web_generation_contract_from_feedback(
        self,
        baseline_contract: WebProductGenerationContract,
        feedback: PreviewFeedback,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal: ...


def _is_chinese(*values: object) -> bool:
    """Return whether the user's material is predominantly Chinese text."""
    text = " ".join(str(value or "") for value in values)
    cjk = sum("\u4e00" <= char <= "\u9fff" for char in text)
    # A short Chinese user phrase can be accompanied by long English fixture
    # text in the upstream snapshot. Any meaningful CJK signal should therefore
    # keep the fake proposal in the user's language.
    return cjk >= 2


def _localized(chinese: bool, zh: str, en: str) -> str:
    return zh if chinese else en


class DeterministicFakeProductContractProvider:
    """Network-free A5/B1 provider that makes its synthetic status explicit."""

    name = "deterministic_fake"
    version = "b2-v4"

    def propose_intent(
        self, raw_input: str, *, job_id: str
    ) -> ProductIntentProposal:
        return ProductIntentProposal(
            desired_change=raw_input,
            affected_people=[
                _localized(
                    _is_chinese(raw_input),
                    "原始描述中涉及的人（需要人工校正）",
                    "People implied by the original input — human correction required",
                )
            ],
            current_situation=raw_input,
            explicit_non_goals=[],
            known_constraints=[],
            resource_preferences=[],
            source_refs=[
                SourceReference(
                    source_type="user_input",
                    source_id=f"{job_id}:raw-input",
                    locator="product_proposal_job.raw_input",
                ),
                SourceReference(
                    source_type="model_proposal",
                    source_id=job_id,
                    revision_id=self.version,
                ),
            ],
        )

    def propose_problem(
        self, intent: ProductIntent, *, job_id: str
    ) -> ProblemModelProposal:
        reported = intent.current_situation or intent.desired_change
        chinese = _is_chinese(reported, intent.desired_change)
        fact = ProblemFact(
            fact_id=f"{job_id}-reported-context",
            statement=_localized(chinese, f"用户报告：{reported}", f"The user reports: {reported}"),
            source_refs=intent.source_refs,
        )
        return ProblemModelProposal(
            intent_revision_id=intent.revision_id,
            facts=[fact],
            assumptions=[],
            unknowns=[
                ProblemUnknown(
                    unknown_id=f"{job_id}-observable-failure",
                    question=_localized(
                        chinese,
                        "哪个可观察事件最能说明当前情境正在伤害相关的人？",
                        "Which observable event most clearly shows that the current situation is failing the affected people?",
                    ),
                    decision_impact=_localized(
                        chinese,
                        "它会影响应该选择哪种干预方式以及如何测量成功。",
                        "It changes which intervention and success measure are appropriate.",
                    ),
                    next_step=_localized(
                        chinese,
                        "观察或记录一次具体的近期发生情况。",
                        "Observe or document one concrete recent occurrence.",
                    ),
                ),
                ProblemUnknown(
                    unknown_id=f"{job_id}-existing-alternative",
                    question=_localized(
                        chinese,
                        "已经尝试过哪些现有替代方案，为什么仍然不够？",
                        "Which existing alternative has already been tried, and why was it insufficient?",
                    ),
                    decision_impact=_localized(
                        chinese,
                        "它决定是否真的需要一条新的产品路径。",
                        "It determines whether a new product is needed at all.",
                    ),
                    next_step=_localized(
                        chinese,
                        "先比较当前的变通办法，再选择产品路径。",
                        "Compare the current workaround before selecting a product path.",
                    ),
                ),
            ],
            competing_explanations=[
                CompetingExplanation(
                    explanation_id=f"{job_id}-tool-friction",
                    statement=_localized(
                        chinese,
                        "报告中的困难可能主要来自当前工具或流程中的摩擦。",
                        "The reported difficulty may be driven primarily by friction in the current tools or process.",
                    ),
                    supporting_fact_ids=(fact.fact_id,),
                    cheapest_falsification=_localized(
                        chinese,
                        "进行一次可逆的对比，移除疑似的工具或流程摩擦。",
                        "Try one reversible session with the suspected tool or process friction removed.",
                    ),
                ),
                CompetingExplanation(
                    explanation_id=f"{job_id}-context-clarity",
                    statement=_localized(
                        chinese,
                        "报告中的困难也可能来自目标不清或情境约束，而不是缺少产品。",
                        "The reported difficulty may instead be driven by unclear goals or contextual constraints rather than a missing product.",
                    ),
                    supporting_fact_ids=(fact.fact_id,),
                    cheapest_falsification=_localized(
                        chinese,
                        "在没有新产品的情况下，带着明确目标和约束完成一次可比较的任务。",
                        "Run one comparable session with an explicit goal and constraints but no new product.",
                    ),
                ),
            ],
            stakeholder_tensions=[],
        )

    def propose_outcome_contract(
        self,
        intent: ProductIntent,
        problem: ProblemModel,
        *,
        job_id: str,
    ) -> OutcomeContractProposal:
        chinese = _is_chinese(intent.desired_change, intent.current_situation)
        indicator_id = f"{job_id}-indicator"
        prohibited = [
            ProhibitedOutcome(
                prohibited_outcome_id=f"{job_id}-non-goal-{index}",
                description=value,
                severity="hard",
                detection_method=_localized(
                    chinese,
                    "试用前进行明确人工审查，试用中接受用户报告",
                    "Explicit human review before trial and user report during trial",
                ),
                response=_localized(
                    chinese,
                    "停止试用并重新审视产品路径",
                    "Stop the trial and reframe the product path",
                ),
            )
            for index, value in enumerate(intent.explicit_non_goals, start=1)
        ]
        preferences = tuple(intent.resource_preferences)
        known_constraints = tuple(intent.known_constraints)
        return OutcomeContractProposal(
            intent_revision_id=intent.revision_id,
            problem_model_revision_id=problem.revision_id,
            target_segments=list(intent.affected_people),
            applicable_contexts=[
                intent.current_situation
                or _localized(
                    chinese,
                    "已确认产品意图中描述的情境",
                    "The context described in the confirmed ProductIntent",
                )
            ],
            target_outcomes=[
                TargetOutcome(
                    outcome_id=f"{job_id}-outcome",
                    description=intent.desired_change,
                    indicator_ids=(indicator_id,),
                )
            ],
            success_indicators=[
                SuccessIndicator(
                    indicator_id=indicator_id,
                    operational_definition=_localized(
                        chinese,
                        "在声明情境中，用户能够观察到一次目标变化",
                        "A user-observable instance of the desired change during the declared context",
                    ),
                    observation_method=_localized(
                        chinese,
                        "经同意的真实任务观察与用户报告",
                        "Consented real task observation and user report",
                    ),
                    desired_direction=_localized(
                        chinese,
                        "相较于用户未经辅助的基线有所改善",
                        "improve relative to the user's unaided baseline",
                    ),
                    threshold_or_target=MEASUREMENT_THRESHOLD_PLACEHOLDER,
                    required_evidence="real_user_observation",
                )
            ],
            prohibited_outcomes=prohibited,
            prohibited_outcomes_reviewed=False,
            resource_boundary=ResourceBoundary(
                time_budget=preferences[0] if preferences else None,
                data_boundary=(
                    "; ".join(known_constraints) if known_constraints else None
                ),
                explicit_unknowns=(
                    ()
                    if preferences or known_constraints
                    else (
                        _localized(
                            chinese,
                            "时间、成本、注意力、维护和数据边界仍需人工审查",
                            "Time, cost, attention, maintenance, and data limits need human review",
                        ),
                    )
                ),
            ),
            stop_conditions=[
                StopCondition(
                    condition_id=f"{job_id}-stop",
                    condition=_localized(
                        chinese,
                        "如果出现禁止结果，或无法在约定边界内观察目标指标，就暂停并重新审视路径",
                        "A prohibited outcome occurs, or the target indicator cannot be observed without exceeding the agreed boundary",
                    ),
                    action="reframe",
                )
            ],
            minimum_delivery_maturity=DeliveryMaturity.RUNNABLE_PROTOTYPE,
            required_real_world_evidence=[
                _localized(
                    chinese,
                    "至少一次在适用情境中、经同意的真实任务观察",
                    "At least one consented real task observation in the applicable context",
                )
            ],
        )

    def propose_theses(
        self,
        problem: ProblemModel,
        contract: OutcomeContract,
        *,
        job_id: str,
    ) -> tuple[ProductThesisProposal, ...]:
        """Return three generic, inspectable paths for the user's actual outcome.

        The fake provider must exercise the workflow without silently replacing a
        user's problem with the first focus slice. The three paths differ by
        mechanism, while keeping their copy explicitly synthetic.
        """
        source = SourceReference(
            source_type="model_proposal",
            source_id=job_id,
            revision_id="b1-thesis-set-v2",
        )
        outcome = contract.target_outcomes[0].description if contract.target_outcomes else "the declared outcome"
        chinese = _is_chinese(outcome, *(contract.target_segments or ()), *(item.statement for item in problem.facts))
        subject = f"“{outcome}”"
        if chinese:
            specs = [
                (
                    "最小对比板",
                    f"围绕{subject}把关键选项放在同一屏比较，让用户先看见差异再做选择。",
                    "把信息结构化并排展示，不替用户判断，也不伪装成自动推荐。",
                    "用户能在一次短流程中指出差异并完成一个明确选择。",
                    "如果并排信息增加负担、差异仍不清楚，或用户把排序误解为结论。",
                    "用两到三个本地示例做一次可点击对比任务。",
                ),
                (
                    "分步选择向导",
                    f"把{subject}拆成少量连续问题，帮助用户逐步缩小选择范围。",
                    "通过明确的问题顺序降低一次性比较的认知负担，不收集外部账户数据。",
                    "用户能说明每一步为什么影响下一步选择。",
                    "步骤过多、问题带有暗示，或用户无法回到上一步修正。",
                    "用固定本地选项完成一轮可逆的选择向导。",
                ),
                (
                    "可逆情境试算",
                    f"让用户在{subject}前先用少量假设运行一个可撤销的情境比较。",
                    "先让用户体验差异，再决定是否继续，而不是要求先相信一份推荐。",
                    "用户能看到假设、改变一个变量并理解结果变化。",
                    "试算结果被误认为真实预测，或变量变化没有带来可理解的差异。",
                    "用本地 fixture 做一次单变量情境切换，不接外部数据。",
                ),
            ]
        else:
            specs = [
                (
                    "Minimal comparison board",
                    f"Put the important options for {subject} side by side so the user can see differences before choosing.",
                    "Structures the comparison without choosing for the user or pretending to provide an automatic recommendation.",
                    "The user can identify a difference and make one explicit choice in a short flow.",
                    "The board increases load, differences remain unclear, or ordering is mistaken for a conclusion.",
                    "Run one clickable comparison task with two or three local fixtures.",
                ),
                (
                    "Stepwise choice guide",
                    f"Break {subject} into a small sequence of questions that narrows the choice without hidden defaults.",
                    "Reduces one-time comparison load through explicit questions while keeping the path reversible and local.",
                    "The user can explain why each answer changes the next available choice.",
                    "There are too many steps, questions become leading, or the user cannot revise an answer.",
                    "Run one reversible guide using fixed local options.",
                ),
                (
                    "Reversible scenario trial",
                    f"Let the user test a small, reversible scenario related to {subject} before committing to a path.",
                    "Shows a consequence of one changed assumption instead of asking the user to trust a recommendation.",
                    "The user can see the assumption, change one variable, and understand the resulting difference.",
                    "A fixture result is mistaken for a real prediction or variable changes are not understandable.",
                    "Run a one-variable scenario switch with local fixtures and no external data.",
                ),
            ]
        common = {
            "problem_model_revision_id": problem.revision_id,
            "outcome_contract_revision_id": contract.revision_id,
            "realization_modes": ["software"],
        }
        proposals: list[ProductThesisProposal] = []
        for index, (name, promise, differentiation, prediction, failure, cheapest_test) in enumerate(specs, start=1):
            suffix = ("对比", "向导", "试算")[index - 1] if chinese else ("comparison", "guide", "trial")[index - 1]
            proposals.append(
                ProductThesisProposal(
                    **common,
                    name=name,
                    product_promise=promise,
                    differentiation=differentiation,
                    mechanism_hypotheses=[
                        MechanismHypothesis(
                            mechanism_id=f"{job_id}-{suffix}-mechanism",
                            condition=_localized(chinese, f"用户需要理解{subject}并保留最终决定权。", f"The user needs to understand {subject} while retaining the final decision.") ,
                            proposed_intervention=_localized(chinese, "提供一个只使用本地 fixture 的可逆主流程。", "Provide one reversible primary flow using local fixtures only."),
                            expected_change=prediction,
                            uncertainty=_localized(chinese, "短原型是否足以表达真正的选择困难仍未知。", "It is unknown whether a short prototype captures the real decision difficulty."),
                            evidence_refs=(source,),
                        )
                    ],
                    falsifiable_predictions=[
                        FalsifiablePrediction(
                            prediction_id=f"{job_id}-{suffix}-prediction",
                            prediction=prediction,
                            failure_observation=failure,
                            cheapest_test=cheapest_test,
                        )
                    ],
                    validation_strategy=[
                        ValidationStep(
                            validation_step_id=f"{job_id}-{suffix}-validation",
                            question=_localized(chinese, f"用户能否在不被产品替代判断的情况下理解{subject}？", f"Can the user understand {subject} without the product replacing their judgment?"),
                            method=_localized(chinese, "一次固定 fixture 的浏览器任务，随后进行人工复盘。", "One fixed-fixture browser task followed by human review."),
                            evidence_level="deterministic_check",
                            pass_condition=_localized(chinese, "主流程可完成、可返回，且用户能说出一个仍待验证的未知。", "The primary flow completes, is reversible, and leaves one explicit unknown for review."),
                            estimated_cost=_localized(chinese, "一个本地 Web 原型和一次短任务。", "One local Web prototype and one short task."),
                        )
                    ],
                    key_unknowns=[_localized(chinese, "用户真正卡住的是信息比较、步骤负担还是缺少可逆试错？", "Is the real bottleneck comparison, step burden, or lack of reversible trial?")],
                    key_risks=[_localized(chinese, "合成 fixture 可能让用户误以为已经验证了现实结果。", "Synthetic fixtures may be mistaken for evidence of a real-world result.")],
                    delivery_estimate=DeliveryEstimate(
                        initial_delivery_cost=_localized(chinese, "低：少量本地状态和固定内容。", "Low: a few local states and fixed content."),
                        operating_cost=_localized(chinese, "低：本地运行，无外部服务。", "Low: local runtime with no external service."),
                        maintenance_burden=_localized(chinese, "低到中：取决于是否增加真实数据接入。", "Low to medium, depending on later real-data integrations."),
                    ),
                )
            )
        return tuple(proposals)

    def propose_web_generation_contract(
        self,
        thesis: ProductThesis,
        contract: OutcomeContract,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        # Keep the deterministic implementation aligned with the provider
        # contract's concrete comparison-board first slice.
        return ProductContractProposalProvider.propose_web_generation_contract(
            self, thesis, contract, suggestion_id=suggestion_id
        )

    def propose_web_generation_contract_from_feedback(
        self,
        baseline_contract: WebProductGenerationContract,
        feedback: PreviewFeedback,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Revise a confirmed B2 contract in response to one explicit report (B8).

        Only the anchor, category and feedback ID are used; the report text is
        never copied into the contract, so withdrawing the feedback still
        erases it everywhere.  Every baseline ID is preserved so anchors and
        revision diffs stay comparable; the revision adds one reviewable check.
        """

        screen = next(
            item for item in baseline_contract.screens if item.screen_id == feedback.anchor.screen_id
        )
        task_id = feedback.anchor.task_id or screen.task_ids[0]
        focus = {
            "bug": "no longer reproduces the reported defect",
            "confusing": "makes the next step unambiguous",
            "missing": "exposes the reported missing capability or explains its absence",
            "works": "keeps the confirmed behaviour unchanged",
        }[feedback.category or "works"]
        state_note = f" in state {feedback.anchor.state_id}" if feedback.anchor.state_id else ""
        check = WebAcceptanceCheck(
            check_id=f"{suggestion_id}-feedback-check",
            task_id=task_id,
            assertion=(
                f"Screen {screen.screen_id}{state_note} {focus} "
                f"(preview feedback {feedback.feedback_id}, {feedback.category}); human review required."
            ),
        )
        return WebProductGenerationContractProposal(
            product_thesis_revision_id=baseline_contract.product_thesis_revision_id,
            outcome_contract_revision_id=baseline_contract.outcome_contract_revision_id,
            app_title=baseline_contract.app_title,
            screens=list(baseline_contract.screens),
            tasks=list(baseline_contract.tasks),
            primary_flow_task_ids=list(baseline_contract.primary_flow_task_ids),
            states=list(baseline_contract.states),
            content_slots=list(baseline_contract.content_slots),
            acceptance_checks=[*baseline_contract.acceptance_checks, check],
            source_refs=[
                *baseline_contract.source_refs,
                SourceReference(
                    source_type="preview_feedback",
                    source_id=feedback.feedback_id,
                    revision_id=feedback.revision_id,
                    locator="anchor+category only; text not copied",
                ),
                SourceReference(source_type="model_proposal", source_id=suggestion_id, revision_id="b8-v1"),
            ],
        )


class RealModelProductContractProvider:
    """C0 real model provider for Product Contract proposals (Intent/Problem/Outcome/Thesis).

    Uses DeepSeek via contract_model module. Follows C0 decisions:
    - PS-O017: Full confirmed upstream + user input sent; transcript local only
    - PS-O018: Max 2 calls per object; no monetary budget
    - PS-O019: No automatic retry; user must explicitly retry on failure
    """

    name = "deepseek"
    version = "c0-v1"

    def __init__(self) -> None:
        """Initialize with environment-configured DeepSeek model."""
        from psyteardown.product.contract_model import (
            ContractModelError,
            build_contract_model_from_env,
        )

        model = build_contract_model_from_env()
        if model is None:
            raise ContractModelError(
                "Real model provider requires PSYTEARDOWN_PRODUCT_CONTRACT_MODEL=deepseek and DEEPSEEK_API_KEY"
            )
        self._model = model
        # C0 stage 6 local evidence. This is intentionally an in-memory
        # diagnostic ledger; proposal jobs remain the persisted source of
        # truth and no prompt/response content is retained here.
        self.usage_records: list[dict[str, object]] = []

    def _generate(self, *, kind: str, system: str, prompt: str):
        started = time.monotonic()
        try:
            reply = self._model.generate(system=system, prompt=prompt)
        except Exception as exc:
            self.usage_records.append(
                {
                    "kind": kind,
                    "model": self._model.model,
                    "outcome": "failed",
                    "error_type": type(exc).__name__,
                    "duration_seconds": time.monotonic() - started,
                }
            )
            raise
        self.usage_records.append(
            {
                "kind": kind,
                "model": reply.model,
                "outcome": "accepted",
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
                "truncated": reply.truncated,
                "duration_seconds": time.monotonic() - started,
            }
        )
        return reply

    def propose_intent(
        self, raw_input: str, *, job_id: str
    ) -> ProductIntentProposal:
        """Generate ProductIntent proposal from raw user input."""
        from psyteardown.product.contract_model import (
            INTENT_SYSTEM,
            ContractModelError,
            build_intent_prompt,
            parse_intent_reply,
        )

        prompt = build_intent_prompt(raw_input)
        try:
            reply = self._generate(kind="product_intent", system=INTENT_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_intent_reply(reply.text, job_id=job_id)
        if isinstance(result, list):
            # Static gate rejection
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_problem(
        self, intent: ProductIntent, *, job_id: str
    ) -> ProblemModelProposal:
        """Generate ProblemModel proposal from confirmed ProductIntent."""
        from psyteardown.product.contract_model import (
            PROBLEM_SYSTEM,
            ContractModelError,
            build_problem_prompt,
            parse_problem_reply,
        )

        prompt = build_problem_prompt(intent)
        try:
            reply = self._generate(kind="problem_model", system=PROBLEM_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_problem_reply(reply.text, job_id=job_id, intent=intent)
        if isinstance(result, list):
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_outcome_contract(
        self,
        intent: ProductIntent,
        problem: ProblemModel,
        *,
        job_id: str,
    ) -> OutcomeContractProposal:
        """Generate OutcomeContract proposal from confirmed Intent and ProblemModel."""
        from psyteardown.product.contract_model import (
            OUTCOME_SYSTEM,
            ContractModelError,
            build_outcome_prompt,
            parse_outcome_reply,
        )

        prompt = build_outcome_prompt(intent, problem)
        try:
            reply = self._generate(kind="outcome_contract", system=OUTCOME_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_outcome_reply(reply.text, job_id=job_id, intent=intent, problem=problem)
        if isinstance(result, list):
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_theses(
        self,
        problem: ProblemModel,
        contract: OutcomeContract,
        *,
        job_id: str,
    ) -> tuple[ProductThesisProposal, ...]:
        """Generate 3 ProductThesis proposals from confirmed ProblemModel and OutcomeContract."""
        from psyteardown.product.contract_model import (
            THESIS_SYSTEM,
            ContractModelError,
            build_theses_prompt,
            parse_theses_reply,
        )

        prompt = build_theses_prompt(problem, contract)
        try:
            reply = self._generate(kind="product_theses", system=THESIS_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_theses_reply(reply.text, job_id=job_id, problem=problem, contract=contract)
        if isinstance(result, list):
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_web_generation_contract(
        self,
        thesis: ProductThesis,
        contract: OutcomeContract,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Delegate to fake provider for now; real model Web generation is B7m's domain."""
        fake = DeterministicFakeProductContractProvider()
        return fake.propose_web_generation_contract(thesis, contract, suggestion_id=suggestion_id)

    def propose_web_generation_contract_from_feedback(
        self,
        baseline_contract: WebProductGenerationContract,
        feedback: PreviewFeedback,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Delegate to fake provider for now; feedback iteration uses fake revision."""
        fake = DeterministicFakeProductContractProvider()
        return fake.propose_web_generation_contract_from_feedback(
            baseline_contract, feedback, suggestion_id=suggestion_id
        )


def build_provider_from_env(provider_name: str = "fake") -> ProductContractProposalProvider:
    """Build provider from environment or explicit name.

    Args:
        provider_name: "fake" (default) or "real"

    Returns:
        DeterministicFakeProductContractProvider or RealModelProductContractProvider

    Raises:
        ValueError: if provider_name is invalid or real provider cannot be initialized
    """
    if provider_name == "fake":
        return DeterministicFakeProductContractProvider()
    elif provider_name == "real":
        return RealModelProductContractProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}; expected 'fake' or 'real'")
