"""Experiment arms."""
ARM_IDS = ("c0-deepseek", "c0-glm", "c1-10", "c2-5", "c2-3", "c3-supervisor", "a1-same-family")


async def run_arm(arm, cfg, models, brief, data_dir, db_path, variant, seed, meter):
    """Dispatch one arm with the shared per-arm budget."""
    from agora.eval.arms.single import run_single_arm
    from agora.eval.arms.supervisor import run_supervisor_arm
    from agora.eval.arms.swarm import run_swarm_arm
    from agora.eval.config import ArmBudget

    if arm not in ARM_IDS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {list(ARM_IDS)}")
    budget = ArmBudget(cfg.budget_usd, float(cfg.wall_clock_s), cfg.episode_recursion_limit)
    if arm in ("c0-deepseek", "c0-glm"):
        spec, model = models[arm.split("-", 1)[1]]
        return await run_single_arm(arm, spec, model, brief, data_dir, budget, meter, variant, seed)
    if arm == "c3-supervisor":
        spec, model = models["deepseek"]
        return await run_supervisor_arm(arm, spec, model, models, brief, data_dir, budget, meter,
                                        variant, seed)
    n_peers, same = {"c1-10": (10, False), "c2-5": (5, False), "c2-3": (3, False),
                     "a1-same-family": (10, True)}[arm]
    return await run_swarm_arm(arm, n_peers, same, models, brief, cfg.template_path, data_dir,
                               budget, db_path, variant, seed)
