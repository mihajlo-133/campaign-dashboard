# Agent Team Protocol (APPLY ALWAYS)

## The Rule

When the user says "agent team", "spin up a team", "get a team on this", "have them debate", or ANY variation implying multiple agents collaborating — spawn **peer-to-peer agents that SendMessage to each other**. NEVER spawn independent subagents that report back to the parent.

This has been corrected 12+ times. There is no ambiguity.

## Subagents vs Agent Teams

| | Subagents (WRONG for teams) | Agent Teams (CORRECT) |
|---|---|---|
| **Communication** | Report back to parent only | Message EACH OTHER directly |
| **Pattern** | Hub-and-spoke (silos) | Peer-to-peer (debate) |
| **Value** | Parallel execution | Challenge, refine, converge |
| **When to use** | Solo tasks (file search, API call, data fetch) | Decisions, reviews, builds, analysis |

## How to Spawn an Agent Team

Every agent team member MUST:
1. Have a **unique name** (`name: "strategist"`, `name: "critic"`)
2. Know **who their teammates are** by name
3. Have **explicit instructions to SendMessage to teammates**
4. Have **a defined role and deliverable**

### Prompt Template

Each agent's prompt must include this block (adapted to the specific team):

```
## Your Team
You are the [ROLE] on a team with:
- [name]: [role description]
- [name]: [role description]

## How to Collaborate
- Use SendMessage(to: "[teammate_name]") to communicate with teammates
- [ROLE-SPECIFIC COLLABORATION INSTRUCTIONS]
- After receiving input from teammates, refine your position
- When the team converges, send your final recommendation to the user via SendMessage(to: "user")
```

### Example: Strategist + Critic Team

```python
# Agent 1: Strategist
Agent(
    name="strategist",
    prompt="""You are the strategist on a team with:
    - critic: Will stress-test your proposal and find weaknesses

    ## Your Task
    [THE ACTUAL TASK]

    ## How to Collaborate
    1. Develop your recommendation and send it to the critic:
       SendMessage(to: "critic", message: "Here's my analysis: ...")
    2. Wait for the critic's response
    3. Refine based on their challenges
    4. When you've converged, send the final joint recommendation:
       SendMessage(to: "user", message: "## Team Recommendation\n...")
    """
)

# Agent 2: Critic
Agent(
    name="critic",
    prompt="""You are the critic on a team with:
    - strategist: Will propose the initial approach

    ## Your Task
    Wait for the strategist's proposal, then stress-test it.

    ## How to Collaborate
    1. Wait for the strategist to send their proposal
    2. Challenge assumptions, find failure modes, identify hidden risks
    3. Send your critique: SendMessage(to: "strategist", message: "...")
    4. The strategist will refine — review the revision
    5. Continue until you're satisfied or disagree (state the disagreement clearly)
    """
)
```

## Common Team Shapes

| Team | When | Agents |
|------|------|--------|
| **Decision** | Trade-off analysis, architecture choices | strategist + critic |
| **Build** | Frontend, dashboards, tools | architect + builder + qa-tester |
| **Review** | Code review, copy review, security | reviewer-1 + reviewer-2 (compare notes) |
| **Research** | Deep investigation | researcher + fact-checker |
| **Full stack** | Complex builds | architect + backend + frontend + qa |

## What NEVER to Do

- Spawn 2+ agents with `run_in_background: true` that both report back to you independently — that's subagents, not a team
- Spawn agents without names — they can't message each other
- Forget to tell agents who their teammates are
- Summarize agent A's output and paste it into agent B's prompt — let them talk directly
