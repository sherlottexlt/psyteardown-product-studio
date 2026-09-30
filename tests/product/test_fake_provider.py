from psyteardown.product.providers import DeterministicFakeProductContractProvider


def test_fake_provider_follows_chinese_input_language(proposed_intent, proposed_problem):
    provider = DeterministicFakeProductContractProvider()
    intent = provider.propose_intent("我希望比较两个选择时更快看出差异", job_id="intent-job")
    assert "原始描述" in intent.affected_people[0]

    chinese_intent = proposed_intent.model_copy(
        update={
            "desired_change": "我希望比较两个选择时更快看出差异",
            "current_situation": "面对多个方案时，我经常无法快速判断",
            "affected_people": ("需要做选择的人",),
        }
    )
    problem = provider.propose_problem(chinese_intent, job_id="problem-job")
    assert problem.facts[0].statement.startswith("用户报告：")
    assert all("The " not in item.statement for item in problem.competing_explanations)

    outcome = provider.propose_outcome_contract(chinese_intent, proposed_problem, job_id="outcome-job")
    assert outcome.success_indicators[0].observation_method.startswith("经同意")


def test_fake_provider_keeps_theses_and_web_contract_tied_to_actual_outcome(proposed_problem, proposed_contract, proposed_thesis):
    provider = DeterministicFakeProductContractProvider()
    outcome = proposed_contract.target_outcomes[0].model_copy(update={"description": "比较两个选择时更快看出差异"})
    contract = proposed_contract.model_copy(update={"target_outcomes": (outcome,)})
    theses = provider.propose_theses(proposed_problem, contract, job_id="theses-job")
    assert len(theses) == 3
    assert theses[0].name == "最小对比板"
    assert all("专注" not in thesis.product_promise for thesis in theses)

    thesis = proposed_thesis.model_copy(update={"name": "最小对比板", "product_promise": "比较两个选择时更快看出差异"})
    web = provider.propose_web_generation_contract(thesis, contract, suggestion_id="web-job")
    assert [screen.title for screen in web.screens] == ["设定这次决定", "选项对比", "决策简报"]
    assert web.tasks[0].goal.startswith("写下这次要做的决定")
    assert len(web.primary_flow_task_ids) == 4
    assert any(task.task_id.endswith("-save-brief") for task in web.tasks)
    assert any(slot.slot_id.endswith("-next-question") for slot in web.content_slots)
