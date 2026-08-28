# Agent Workbench Page Rules

This page is a dense analysis workspace, so it overrides the Master landing-page pattern.

- Layout: thread rail + primary task column + evidence rail at >= 1180px; collapse to one document flow below 900px.
- Primary action: one “开始分析” action in the task composer. Approval/rejection appear only during an interrupt.
- Progress: four user-facing stages — 规划任务、检索核验、检查差异、生成报告. Never show chain-of-thought.
- Events: show operational summaries only. Tool names may appear as secondary metadata, not as the main title.
- Evidence: numbered cards with source, summary, optional jurisdiction, and an external-source link.
- Conflict: use an icon plus text and semantic color; never rely on color alone.
- Long report: readable 65–75 character measure; headings and bullets remain semantic.
- Motion: opacity/background transitions only, 160–220ms, disabled under reduced motion.
- Mobile: core report and pending action first; thread history and evidence become ordinary collapsible sections with 44px controls.
