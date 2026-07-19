"""Prompt builders. Words come from the LLM; every number in a prompt was
computed in SQL first (spec design rule)."""


def risk_narrative_prompt(equipment, factors, recent_complaints, recent_remarks):
    complaint_lines = "\n".join(
        f"- {c.created_at:%Y-%m-%d}: {c.description[:300]}" for c in recent_complaints
    ) or "- none on record in the window"
    remark_lines = "\n".join(
        f"- {r.created_at:%Y-%m-%d} ({r.kind}): {r.text[:300]}" for r in recent_remarks
    ) or "- none on record in the window"
    return [
        {
            "role": "system",
            "content": (
                "You are a biomedical maintenance analyst. Write a short, plain "
                "paragraph (3-5 sentences) explaining why this device is "
                "high-risk, quoting concrete complaint or remark snippets. Do "
                "not invent numbers; use only the facts given."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Device: {equipment}\n"
                f"Completed repairs in the last {factors['window_months']} "
                f"months: {factors['repairs_in_window']}\n"
                f"Risk score: "
                f"{factors['repairs_in_window'] * factors['points_per_repair']} "
                f"(threshold {factors['high_risk_threshold']})\n\n"
                f"Recent complaints:\n{complaint_lines}\n\n"
                f"Recent repair remarks:\n{remark_lines}"
            ),
        },
    ]


def report_narrative_prompt(m):
    return [
        {
            "role": "system",
            "content": (
                "You are writing the executive summary of a hospital biomedical "
                "maintenance monthly report for management. 5-8 sentences, plain "
                "language, no bullet lists. Use only the numbers provided — "
                "never invent or recompute figures."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Month: {m['month']}\n"
                f"Repairs completed: {m['repairs_completed']}\n"
                "Critical-asset downtime hours by department: "
                f"{m['downtime_by_department']}\n"
                f"Complaints per department: {m['complaints_per_department']}\n"
                f"Most complained devices: {m['most_complained_devices']}\n"
                f"Fault categories: {m['fault_category_counts']}\n"
                "Delayed repairs: "
                f"{[d['latest_delay_note'] for d in m['delayed_repairs']]}\n"
            ),
        },
    ]
