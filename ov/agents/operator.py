"""The Operator agent — the model-bound perceive→decide→act→record loop.

In Phases 1–3 the *host* plays the operator, following the ``ov-operate`` skill: it
reads affordances, decides the next action, and records intent. Phase 4 packages that
loop as a runnable agent. The deterministic "hands" (``observe`` / ``act`` /
``make_step`` / ``journal`` / ``progress``) are reused unchanged; the only thing the
agent adds is the **decide** step — and that is *injected* (``decider``), so:

* the package never hard-depends on an LLM (the host, a script, or a model can all
  supply ``decide``); and
* the loop is unit-testable with a trivial decider and fake ``observe``/``act``
  callables — no browser, no API call.

The agent satisfies the ``aw.AgenticStep`` protocol structurally
(``execute(input_data, context) -> (artifact, info)``), so it drops into an ``aw``
workflow (see :mod:`ov.agents.orchestrator`). Its artifact is the populated
:class:`~ov.base.CaptureRun`; the model-free :func:`~ov.operate.progress` facts are
the deterministic stop signal a budget-bound manager interprets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, MutableMapping, Optional

from ..base import Action, CaptureRun, JourneyStep, Observation
from ..operate import act as _act
from ..operate import journal, make_step, observe as _observe, progress

#: A decider maps the current observation (+ goal + history) to the next action,
#: or ``None`` to stop. The model's only job in the loop.
Decider = Callable[..., Optional[Action]]


@dataclass
class OperatorAgent:
    """Drive a target toward a goal, recording every step (an ``aw.AgenticStep``).

    Args:
        decider: ``(observation, *, goal, history) -> Action | None``. Returns the
            next action, or ``None`` to stop. Use :func:`make_llm_decider` for a
            model-backed one, or any callable (host / script / test stub).
        session: a :class:`~ov.capture.session.CaptureSession` (supplies ``.page`` +
            ``.run``). Optional — ``page`` and ``run`` may instead arrive via the
            ``context`` passed to :meth:`execute` (keys ``"page"`` / ``"run"``).
        max_steps: hard cap on actions (a budget; the deterministic loop signal is
            advisory, the cap is the backstop).
        strategy: perception strategy for the default ``observe`` (``"ax_snapshot"``
            | ``"screenshot"`` | ``"hybrid"``).
        observe_fn / act_fn: injection seams for the hands (default to the real
            :func:`~ov.operate.observe` / :func:`~ov.operate.act`); tests pass fakes.
    """

    decider: Decider
    session: Any = None
    max_steps: int = 12
    strategy: str = "ax_snapshot"
    polite_rate_s: float = 0.0
    no_progress_steps: int = 3
    observe_fn: Optional[Callable[[Any], Observation]] = None
    act_fn: Optional[Callable[[Any, Action], Any]] = None
    model: Optional[str] = "haiku"
    name: str = "operator"

    def _observe(self, page: Any) -> Observation:
        if self.observe_fn is not None:
            return self.observe_fn(page)
        return _observe(page, self.strategy)

    def _act(self, page: Any, action: Action):
        if self.act_fn is not None:
            return self.act_fn(page, action)
        return _act(
            page, action, perception=self.strategy, polite_rate_s=self.polite_rate_s
        )

    def _page_and_run(
        self, context: Optional[MutableMapping]
    ) -> tuple[Any, CaptureRun]:
        """Resolve the live page + the run to journal into (session first, then context)."""
        if self.session is not None:
            return self.session.page, self.session.run
        ctx = context or {}
        page = ctx.get("page")
        run = ctx.get("run") or CaptureRun(target_url=str(ctx.get("url", "")))
        return page, run

    def execute(
        self, input_data: Any, context: Optional[MutableMapping[str, Any]] = None
    ) -> tuple[CaptureRun, dict[str, Any]]:
        """Pursue ``input_data`` (the goal) and return ``(CaptureRun, info)`` (aw protocol)."""
        goal = input_data if isinstance(input_data, str) else str(input_data or "")
        page, run = self._page_and_run(context)

        obs = self._observe(page)
        stopped_reason = "max-steps"
        loop_suspected = False
        steps_taken = 0
        for _ in range(self.max_steps):
            action = self.decider(obs, goal=goal, history=run.steps)
            if action is None:
                stopped_reason = "decider-stop"
                break
            result = self._act(page, action)
            step = make_step(
                intent="advance",
                action=getattr(result, "action", action),
                pre_observation=obs,
                result=result,
            )
            journal(run, step)
            steps_taken += 1

            signal = progress(run.steps, no_progress_steps=self.no_progress_steps)
            if signal.loop_suspected:
                stopped_reason = "loop-suspected"
                loop_suspected = True
                break
            obs = getattr(result, "observation", None) or self._observe(page)

        info = {
            "success": True,
            "agent": self.name,
            "model": self.model,
            "backend": "in-package",
            "goal": goal,
            "steps_taken": steps_taken,
            "stopped_reason": stopped_reason,
            "loop_suspected": loop_suspected,
            "run_id": run.run_id,
        }
        if context is not None:
            context["operator"] = {
                k: info[k] for k in ("run_id", "steps_taken", "stopped_reason")
            }
        return run, info


def _affordance_lines(obs: Observation, *, limit: int = 30) -> str:
    """Render an observation's affordances as a compact, ref-bearing list for the model."""
    rows = []
    for aff in obs.affordances[:limit]:
        name = f" '{aff.name}'" if aff.name else ""
        state = "" if aff.enabled else " (disabled)"
        rows.append(f"  {aff.ref}: {aff.role}{name}{state}")
    extra = len(obs.affordances) - limit
    if extra > 0:
        rows.append(f"  … and {extra} more")
    return "\n".join(rows) or "  (no actionable affordances perceived)"


def _operator_prompt(
    obs: Observation,
    *,
    goal: str,
    history: list[JourneyStep],
    instruction: Optional[str],
) -> str:
    """Build the decide-step prompt: goal + current affordances + recent steps."""
    recent = "; ".join(
        f"{s.intent}:{(s.action.type if s.action else '?')}->{s.outcome}"
        for s in history[-5:]
    )
    return (
        (
            instruction
            or "You are driving a web app toward a goal. Choose the SINGLE "
            "next action, or stop when the goal is met or no action helps."
        )
        + f"\n\nGoal: {goal or '(explore/crawl)'}"
        + f"\nCurrent URL: {obs.url or '(unknown)'}"
        + f"\nAffordances (use the ref):\n{_affordance_lines(obs)}"
        + (f"\nRecent steps: {recent}" if recent else "")
        + "\n\nReply with an Action object (type + ref/description, and text/url/value as "
        "needed). To stop, set type to 'wait' with args.stop=true or return no action."
    )


def make_llm_decider(llm: Any = None, *, instruction: Optional[str] = None) -> Decider:
    """A model-backed :data:`Decider` that picks the next :class:`~ov.base.Action`.

    Uses the injected ``llm`` through :func:`ov.agents.llm.structured` to choose an
    action conforming to ``Action``'s schema. Returns ``None`` (stop) when no LLM is
    resolvable, on a parse miss, or when the model signals a stop — so an operator
    built with this decider degrades safely to a no-op rather than crashing.
    """
    from .llm import structured
    from ..base import Action as _Action

    schema = _Action.model_json_schema()
    fields = set(_Action.model_fields)

    def decide(
        obs: Observation, *, goal: str, history: list[JourneyStep]
    ) -> Optional[Action]:
        prompt = _operator_prompt(
            obs, goal=goal, history=history, instruction=instruction
        )
        data = structured(prompt, schema, llm=llm)
        if not isinstance(data, dict) or not data.get("type"):
            return None
        if data.get("args", {}).get("stop") or data["type"] == "stop":
            return None
        try:
            return _Action(**{k: v for k, v in data.items() if k in fields})
        except Exception:
            return None

    return decide
