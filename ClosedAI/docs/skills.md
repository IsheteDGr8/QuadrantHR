**A substantial part of the skills system is already there.**

From what we've established:

* The **skills framework/plumbing already exists through OpenHands**.
* The main missing piece is the **skills library/content**, not inventing a new skills architecture.
* The existing system is expected to discover/load skills from the existing skills path.
* We were planning to populate that with **dummy Markdown skills first** to verify the entire pipeline.
* The important thing is to test the existing plumbing end-to-end: **skill file → discovery → loading → runtime/agent → chat**.
* We specifically **do not want to create a new skills framework or replace the existing architecture**.

So when I described "skills" above, I was describing **what we need the existing skills system to provide**, not saying we need to build a skills framework from scratch.

And this actually makes your current situation much clearer: **you already have one of the major pieces.** The next step is getting the existing skills system properly populated and actually used by the agent alongside MCP tools and your data/execution layer.

Populate the **existing skills system** with dummy skills so we can validate the full skills pipeline before building out the real business capabilities.

**Do not create a new skills framework.** Use the skills system that already exists in the codebase and wire the dummy skills into that existing system.

### First skill: Onboarding

Create the first dummy skill as an **Onboarding skill**.

The skill should be represented using the existing skill format/mechanism already supported by the project. It should contain realistic business knowledge about employee onboarding, but it should **not be implemented as a hardcoded executable workflow**.

The onboarding skill should teach the agent things such as:

* What onboarding is trying to accomplish
* What information should be checked about a new employee
* Common onboarding requirements
* What systems may need to be involved
* What kinds of tasks/actions may be required
* What information may be missing
* When approvals may be necessary
* When the agent should verify that an action actually completed
* When the agent should escalate instead of assuming something is complete

The skill should provide **procedural/business knowledge**, while the agent decides at runtime which parts are relevant and which MCP tools to use.

### Add a few additional dummy skills

For now, create only **3 total dummy skills**, with Onboarding being the first one.

Use two additional simple HR skills such as:

1. **Employee Transfer**
2. **PTO / Leave Management**

These can be smaller dummy implementations. The purpose right now is to prove that the skills system can handle multiple skills and that the agent can retrieve/use the relevant skill based on the user's request.

### Critical requirement

Do **not** hardcode:

```text
if onboarding:
    run onboarding workflow
```

Do not create special-case routing for these skills.

The test needs to demonstrate that:

```text
User request
    ↓
Agent identifies relevant business context
    ↓
Relevant skill is loaded/retrieved
    ↓
Skill provides business knowledge
    ↓
Agent reasons about what needs to happen
    ↓
Agent selects available MCP/tools
    ↓
Agent executes
```

The skill should **not dictate the exact execution sequence**.

### Use dummy data where necessary

If the skill references things that do not currently exist in the system — for example IT systems, payroll systems, documents, tickets, employees, or other HR records — **do not stop because those things don't exist yet**.

Create reasonable dummy/mock data or dummy references where necessary so we can test the skills pipeline.

For example, the onboarding skill can reference a fictional employee and fictional onboarding requirements if needed.

The goal right now is **not to make the entire onboarding business process production-ready**. The goal is to prove that the existing skills infrastructure can actually provide business knowledge to the agent at runtime.

### Validation

After creating the 3 skills:

1. Verify they are discovered by the existing skills system.
2. Verify they can be loaded by the agent.
3. Test an onboarding request.
4. Test an employee-transfer request.
5. Test a PTO/leave request.
6. Confirm the agent is actually using the relevant skill rather than a hardcoded workflow.
7. Confirm the existing MCP/tool execution path still works.
8. Run the specialized skills tests and report exactly what passed and what failed.

**Do only these 3 skills right now. Do not expand into a large skills library yet.**

The purpose of this phase is to prove the architecture end-to-end before we add more skills, more tools, or more complex business capabilities.