"""
Job Analysis Interview App - Anthropic Version
Run: streamlit run app.py
"""

import streamlit as st
import anthropic
import json

MODEL = "claude-sonnet-4-20250514"
TARGET_EXCHANGES = 7
client = anthropic.Anthropic()

INTERVIEWER_SYSTEM_PROMPT = """You are an expert I/O psychologist conducting a job analysis interview for "{job_title}".

{job_context_section}

RULES:
- Ask ONE question at a time
- Keep responses to 2-3 sentences plus your question
- Probe vague answers by asking for specific examples
- Acknowledge good answers briefly, then move on
- NEVER output coverage status, progress tracking, or any meta-information in your response
- NEVER use bullet points or lists in your response
- Just respond conversationally as an interviewer would

INTERNAL TRACKING (do NOT include any of this in your response):
Coverage: {coverage}
Progress: {exchange_count}/{target_exchanges} exchanges

If coverage is good and you've hit the target, suggest wrapping up conversationally."""

SYNTHESIS_PROMPT = """Based on this interview for "{job_title}", create a KSAO analysis.

TRANSCRIPT:
{transcript}

Return ONLY valid JSON with this structure:
{{"job_title": "{job_title}", "role_summary": "2-3 sentences", "knowledge": [{{"item": "...", "importance": "critical|important|helpful", "evidence": "quote from interview"}}], "skills": [{{"item": "...", "importance": "...", "evidence": "..."}}], "abilities": [{{"item": "...", "importance": "...", "evidence": "..."}}], "other_characteristics": [{{"item": "...", "importance": "...", "evidence": "..."}}], "key_tasks": ["..."], "gaps": ["areas needing follow-up"]}}"""

COVERAGE_AREAS = {
    "core_responsibilities": {"name": "Core Responsibilities", "covered": False},
    "technical_skills": {"name": "Technical Skills", "covered": False},
    "soft_skills": {"name": "Interpersonal Skills", "covered": False},
    "knowledge_areas": {"name": "Required Knowledge", "covered": False},
    "success_factors": {"name": "Top Performer Traits", "covered": False},
    "challenges": {"name": "Challenges", "covered": False},
    "critical_incidents": {"name": "Specific Examples", "covered": False}
}

def format_coverage(coverage):
    covered = [a['name'] for a in coverage.values() if a['covered']]
    not_covered = [a['name'] for a in coverage.values() if not a['covered']]
    return f"Explored: {', '.join(covered) if covered else 'None yet'}. Still need: {', '.join(not_covered) if not_covered else 'All covered'}."

def update_coverage(msg, coverage):
    m = msg.lower()
    checks = [
        ("core_responsibilities", ["day-to-day", "typical", "responsibilities", "tasks", "week"]),
        ("technical_skills", ["python", "sql", "tool", "software", "excel", "code"]),
        ("soft_skills", ["stakeholder", "communicate", "team", "collaborate", "meeting"]),
        ("knowledge_areas", ["know", "understand", "learn", "background", "domain"]),
        ("success_factors", ["great", "top performer", "best", "successful", "distinguish"]),
        ("challenges", ["challenge", "difficult", "hard", "frustrat", "problem"]),
        ("critical_incidents", ["example", "recently", "once", "specific", "instance"])
    ]
    for key, words in checks:
        if any(w in m for w in words):
            coverage[key]["covered"] = True
    return coverage

def call_llm(messages, system_prompt):
    try:
        resp = client.messages.create(model=MODEL, max_tokens=500, system=system_prompt, messages=messages)
        text = resp.content[0].text
        
        # Strip any leaked system prompt content
        for marker in ["COVERAGE", "PROGRESS:", "INTERNAL", "exchanges", "◐", "○", "✓"]:
            if marker in text:
                text = text.split(marker)[0].strip()
        
        # Remove any trailing incomplete sentences
        if text and text[-1] not in '.?!':
            last_period = max(text.rfind('.'), text.rfind('?'), text.rfind('!'))
            if last_period > 0:
                text = text[:last_period + 1]
        
        return text if text else "Could you tell me more about that?"
    except Exception as e:
        return f"Technical issue: {str(e)[:50]}"

def generate_synthesis(messages, job_title):
    transcript = "\n".join([f"{'SME' if m['role']=='user' else 'Interviewer'}: {m['content']}" for m in messages])
    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=2000, system="Output valid JSON only, no markdown.",
            messages=[{"role": "user", "content": SYNTHESIS_PROMPT.format(job_title=job_title, transcript=transcript)}]
        )
        text = resp.content[0].text
        start, end = text.find('{'), text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"error": "No JSON found", "raw": text}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"error": str(e)}

def get_intro(job_title, has_context):
    if has_context:
        return f"""Hi! I'm here to learn about the **{job_title}** role.

I've been given a formal description, but I want to understand how YOUR experience compares — where it aligns, differs, and what's missing.

**How would YOU describe the core purpose of a {job_title}?**"""
    return f"""Hi! I'm here to learn about the **{job_title}** role through a brief conversation.

**Can you give me a high-level overview of what a {job_title} actually does?**"""

def main():
    st.set_page_config(page_title="Job Analysis Interview", page_icon="🎯")
    
    defaults = {"messages": [], "coverage": {k: dict(v) for k, v in COVERAGE_AREAS.items()},
                "interview_complete": False, "ksao_result": None, "initialized": False,
                "job_context": "", "job_title": "", "setup_complete": False}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    # Setup screen
    if not st.session_state.setup_complete:
        st.title("🎯 Job Analysis Interview")
        job_title = st.text_input("Job Title *", placeholder="e.g., People Scientist, Software Engineer")
        job_context = st.text_area("Job Description (optional)", height=200)
        if st.button("Start Interview", type="primary"):
            if job_title.strip():
                st.session_state.job_title = job_title.strip()
                st.session_state.job_context = job_context
                st.session_state.setup_complete = True
                st.rerun()
            else:
                st.warning("Please enter a job title.")
        return
    
    st.title("🎯 Job Analysis Interview")
    st.caption(f"Role: **{st.session_state.job_title}** | Target: ~{TARGET_EXCHANGES} exchanges")
    
    if not st.session_state.initialized:
        st.session_state.messages.append({"role": "assistant", "content": get_intro(st.session_state.job_title, bool(st.session_state.job_context))})
        st.session_state.initialized = True
    
    # Sidebar
    with st.sidebar:
        st.markdown("### Controls")
        exchanges = len([m for m in st.session_state.messages if m["role"] == "user"])
        st.markdown(f"**Exchanges:** {exchanges}/{TARGET_EXCHANGES}")
        st.markdown(f"**Context:** {'✅' if st.session_state.job_context else 'None'}")
        st.markdown("**Coverage:**")
        for a in st.session_state.coverage.values():
            st.markdown(f"{'✅' if a['covered'] else '⬜'} {a['name']}")
        st.divider()
        if st.button("🏁 Finish Interview", type="primary"):
            if exchanges < 3:
                st.warning("Complete at least 3 exchanges.")
            else:
                with st.spinner("Generating KSAO..."):
                    st.session_state.ksao_result = generate_synthesis(st.session_state.messages, st.session_state.job_title)
                    st.session_state.interview_complete = True
                st.rerun()
        if st.button("🔄 Reset"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    
    # Messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Results
    if st.session_state.interview_complete and st.session_state.ksao_result:
        st.divider()
        st.subheader("📋 KSAO Analysis")
        r = st.session_state.ksao_result
        if "error" in r:
            st.error(r["error"])
            if "raw" in r:
                st.code(r["raw"])
        else:
            st.markdown(f"**Summary:** {r.get('role_summary', 'N/A')}")
            for sec in ["knowledge", "skills", "abilities", "other_characteristics"]:
                items = r.get(sec, [])
                if items:
                    st.markdown(f"### {sec.replace('_', ' ').title()}")
                    for i in items:
                        em = {"critical": "🔴", "important": "🟡", "helpful": "🟢"}.get(i.get("importance"), "⚪")
                        st.markdown(f"{em} **{i.get('item')}** — _{i.get('evidence')}_")
            if r.get("key_tasks"):
                st.markdown("### Key Tasks")
                for t in r["key_tasks"]:
                    st.markdown(f"- {t}")
            if r.get("gaps"):
                st.markdown("### Gaps")
                for g in r["gaps"]:
                    st.markdown(f"- {g}")
            st.download_button("📥 Download JSON", json.dumps(r, indent=2), "ksao.json")
        return
    
    # Chat input
    if prompt := st.chat_input("Your response..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.coverage = update_coverage(prompt, st.session_state.coverage)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                ctx = f"FORMAL DESCRIPTION:\n{st.session_state.job_context}\n\nCompare against this." if st.session_state.job_context else ""
                system = INTERVIEWER_SYSTEM_PROMPT.format(
                    job_title=st.session_state.job_title, job_context_section=ctx,
                    coverage=format_coverage(st.session_state.coverage),
                    exchange_count=len([m for m in st.session_state.messages if m["role"] == "user"]),
                    target_exchanges=TARGET_EXCHANGES
                )
                response = call_llm(st.session_state.messages, system)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
